from __future__ import annotations
import argparse
import os
import sys
import time
from datetime import datetime
from colorama import Fore, Style, init
from dotenv import load_dotenv

from config import (
    APPLY_DELAY_SEC,
    ENABLE_LINKEDIN,
    ENABLE_NAUKRI,
    ENABLE_WORKATASTARTUP,
    EXCEL_FILE,
    EXPERIENCE_YEARS,
    JOB_AGE_DAYS,
    LINKEDIN_COOKIES_FILE,
    LINKEDIN_HEADLESS,
    LINKEDIN_LOCATION,
    LINKEDIN_MAX_JOBS_PER_QUERY,
    LINKEDIN_SEARCH_QUERIES,
    LOOP_INTERVAL_MINUTES,
    PAGES_PER_QUERY,
    SEARCH_DELAY_SEC,
    SEARCH_QUERIES,
    SKIP_IF_COMPANY_ALREADY_APPLIED,
    TITLE_KEYWORDS,
    WORKATASTARTUP_COMPANIES_URL,
    WORKATASTARTUP_COOKIES_FILE,
    WORKATASTARTUP_FILTER_BY_TITLE,
    WORKATASTARTUP_HEADLESS,
    WORKATASTARTUP_MAX_APPLIES,
    WORKATASTARTUP_MAX_COMPANIES,
)
from src.client.job_client import NaukriJobClient
from src.client.naukri_client import NaukriLoginClient
from src.exceptions.exceptions import NaukriAuthError
from src.utils.company_tracker import normalize_company
from src.utils.excel_logger import ExcelJobLogger
load_dotenv()
init(autoreset=True)
LINE = f"{Fore.WHITE}{'-' * 68}{Style.RESET_ALL}"

def print_section(title: str) -> None:
    print(f'\n{LINE}')
    print(f' {Fore.CYAN}{Style.BRIGHT}{title.upper()}{Style.RESET_ALL}')
    print(LINE)


def title_matches_role(title: str) -> bool:
    lower = title.lower()
    return any(kw in lower for kw in TITLE_KEYWORDS)


def should_skip_company(excel: ExcelJobLogger, company: str, applied_companies: set[str]) -> bool:
    if not SKIP_IF_COMPANY_ALREADY_APPLIED:
        return False
    return excel.is_company_applied(company, applied_companies)

def fetch_naukri_jobs(jc: NaukriJobClient) -> list[tuple]:
    seen: set[str] = set()
    results: list[tuple] = []

    print_section(
        f"Naukri search — {len(SEARCH_QUERIES)} queries, "
        f"{PAGES_PER_QUERY} page(s) each, exp={EXPERIENCE_YEARS}yr"
    )

    for query in SEARCH_QUERIES:
        keyword = query["keyword"]
        location = query.get("location", "")

        for page in range(1, PAGES_PER_QUERY + 1):
            try:
                jobs = jc.search_jobs(
                    keyword=keyword,
                    location=location,
                    experience=EXPERIENCE_YEARS,
                    job_age=JOB_AGE_DAYS,
                    page=page,
                )
            except NaukriAuthError as exc:
                print(f' {Fore.RED}[AUTH]{Style.RESET_ALL} {keyword} p{page}: {exc}')
                time.sleep(3)
                continue
            except Exception as exc:
                print(f' {Fore.RED}[FAIL]{Style.RESET_ALL} {keyword} p{page}: {exc}')
                time.sleep(3)
                continue
            new_count = 0
            for job in jobs:
                if job.job_id in seen:
                    continue
                if not title_matches_role(job.title):
                    continue
                seen.add(job.job_id)
                results.append((job, keyword))
                new_count += 1
            loc_label = location or 'All India'
            print(f' {Fore.WHITE}[{keyword[:28]:<28} | {loc_label[:12]:<12} | p{page}]{Style.RESET_ALL} {len(jobs):>3} fetched, {Fore.GREEN}{new_count:>3} new matches{Style.RESET_ALL}')
            if not jobs:
                break
            time.sleep(SEARCH_DELAY_SEC)
    print(f'\n {Fore.CYAN}Naukri matching jobs: {Style.BRIGHT}{len(results)}{Style.RESET_ALL}')
    return results

def apply_naukri_jobs(jc: NaukriJobClient, job_entries: list[tuple], applied_ids: set[str], applied_companies: set[str], excel: ExcelJobLogger) -> dict:
    stats = {'applied': 0, 'skipped_applied': 0, 'skipped_company': 0, 'skipped_external': 0, 'failed': 0}
    print_section(f'Naukri apply — {len(job_entries)} jobs, {len(applied_ids)} job IDs / {len(applied_companies)} companies in Excel')
    for index, (job, keyword) in enumerate(job_entries, start=1):
        print(f'\n{LINE}')
        print(f' {Fore.CYAN}{Style.BRIGHT}[{index}/{len(job_entries)}]{Style.RESET_ALL} {Style.BRIGHT}{job.title}{Style.RESET_ALL}')
        print(f' {Fore.WHITE}Company:{Style.RESET_ALL} {Fore.YELLOW}{job.company}{Style.RESET_ALL}')
        if job.job_id in applied_ids:
            print(f' {Fore.WHITE}Skipped — job ID already applied{Style.RESET_ALL}')
            excel.append_job(job, keyword, status='Skipped - Already Applied', notes='Same job ID on a later run', platform='Naukri')
            stats['skipped_applied'] += 1
            continue
        if should_skip_company(excel, job.company, applied_companies):
            print(f' {Fore.WHITE}Skipped — company already applied{Style.RESET_ALL}')
            excel.append_job(job, keyword, status='Skipped - Company Applied', notes='Applied to this company earlier', platform='Naukri')
            stats['skipped_company'] += 1
            continue
        if jc.is_external_apply(job.job_id):
            external_url = jc.get_external_apply_url(job.job_id)
            print(f' {Fore.YELLOW}External apply — URL saved to Excel{Style.RESET_ALL}')
            print(f' {Fore.BLUE}{external_url}{Style.RESET_ALL}')
            excel.append_job(job, keyword, status='Skipped - External Apply', notes='Apply on company website (URL saved)', platform='Naukri', external_apply_url=external_url)
            stats['skipped_external'] += 1
            continue
        mandatory = job.tags[:2] if job.tags else []
        optional = job.tags[2:] if len(job.tags) > 2 else []
        try:
            result = jc.apply_job(job, mandatory_skills=mandatory, optional_skills=optional, source='search')
            job_result = (result.get('jobs') or [{}])[0]
            if job_result.get('questionnaire'):
                print(f' {Fore.CYAN}Questionnaire — auto-filling (yes / 30 days notice / 2yr){Style.RESET_ALL}')
                sid = datetime.utcnow().strftime('%Y%m%d%H%M%S') + '0000000'
                jc.handle_static_questionnaire_and_apply(job, questionnaire=job_result['questionnaire'], sid=sid, mandatory_skills=mandatory, optional_skills=optional, source='search')
            applied_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            print(f' {Fore.GREEN}Applied successfully{Style.RESET_ALL}')
            excel.append_job(job, keyword, status='Applied', applied_at=applied_at, notes='Easy apply on Naukri', platform='Naukri')
            applied_ids.add(job.job_id)
            norm = normalize_company(job.company)
            if norm:
                applied_companies.add(norm)
            stats['applied'] += 1
        except Exception as exc:
            print(f' {Fore.RED}Failed — {exc}{Style.RESET_ALL}')
            excel.append_job(job, keyword, status='Failed', notes=str(exc), platform='Naukri')
            stats['failed'] += 1
        time.sleep(APPLY_DELAY_SEC)
    return stats

def fetch_linkedin_jobs(li) -> list[tuple]:
    all_jobs: list[tuple] = []
    seen: set[str] = set()
    print_section(f'LinkedIn search — {len(LINKEDIN_SEARCH_QUERIES)} keywords')
    for keyword in LINKEDIN_SEARCH_QUERIES:
        try:
            jobs = li.search_jobs(keyword, LINKEDIN_LOCATION, LINKEDIN_MAX_JOBS_PER_QUERY)
        except Exception as exc:
            print(f' {Fore.RED}[FAIL]{Style.RESET_ALL} {keyword}: {exc}')
            continue
        new = 0
        for job in jobs:
            if not title_matches_role(job.title):
                continue
            if job.job_id in seen:
                continue
            seen.add(job.job_id)
            all_jobs.append((job, keyword))
            new += 1
        print(f' {Fore.WHITE}[{keyword[:40]:<40}]{Style.RESET_ALL} {len(jobs):>3} listed, {Fore.GREEN}{new:>3} new{Style.RESET_ALL}')
        time.sleep(SEARCH_DELAY_SEC)
    print(f'\n {Fore.CYAN}LinkedIn matching jobs: {Style.BRIGHT}{len(all_jobs)}{Style.RESET_ALL}')
    return all_jobs

def apply_linkedin_jobs(li, excel: ExcelJobLogger, applied_ids: set[str], applied_companies: set[str], job_entries: list[tuple] | None=None) -> dict:
    stats = {'applied': 0, 'skipped_applied': 0, 'skipped_company': 0, 'skipped_external': 0, 'failed': 0}
    all_jobs = job_entries if job_entries is not None else fetch_linkedin_jobs(li)
    print_section(f'LinkedIn apply — {len(all_jobs)} jobs')
    for index, (job, keyword) in enumerate(all_jobs, start=1):
        print(f'\n{LINE}')
        print(f' {Fore.CYAN}{Style.BRIGHT}[{index}/{len(all_jobs)}]{Style.RESET_ALL} {Style.BRIGHT}{job.title}{Style.RESET_ALL}')
        print(f' {Fore.WHITE}Company:{Style.RESET_ALL} {Fore.YELLOW}{job.company}{Style.RESET_ALL}')
        if job.job_id in applied_ids:
            print(f' {Fore.WHITE}Skipped — job ID already applied{Style.RESET_ALL}')
            excel.append_job(job, keyword, status='Skipped - Already Applied', notes='Same job ID on a later run', platform='LinkedIn')
            stats['skipped_applied'] += 1
            continue
        if should_skip_company(excel, job.company, applied_companies):
            print(f' {Fore.WHITE}Skipped — company already applied{Style.RESET_ALL}')
            excel.append_job(job, keyword, status='Skipped - Company Applied', notes='Applied to this company earlier', platform='LinkedIn')
            stats['skipped_company'] += 1
            continue
        try:
            result = li.apply_job(job)
            status = result.get('status', 'failed')
            external_url = result.get('external_url', '')
            notes = result.get('notes', '')
            if status == 'applied':
                applied_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                print(f' {Fore.GREEN}Applied successfully{Style.RESET_ALL}')
                excel.append_job(job, keyword, status='Applied', applied_at=applied_at, notes=notes, platform='LinkedIn')
                applied_ids.add(job.job_id)
                norm = normalize_company(job.company)
                if norm:
                    applied_companies.add(norm)
                stats['applied'] += 1
            elif status == 'already_applied':
                print(f' {Fore.WHITE}Skipped — already applied on LinkedIn{Style.RESET_ALL}')
                excel.append_job(job, keyword, status='Skipped - Already Applied', notes=notes, platform='LinkedIn')
                applied_ids.add(job.job_id)
                stats['skipped_applied'] += 1
            elif status == 'external':
                print(f' {Fore.YELLOW}External apply — URL saved to Excel{Style.RESET_ALL}')
                print(f' {Fore.BLUE}{external_url}{Style.RESET_ALL}')
                excel.append_job(job, keyword, status='Skipped - External Apply', notes=notes, platform='LinkedIn', external_apply_url=external_url)
                stats['skipped_external'] += 1
            else:
                print(f' {Fore.RED}Failed — {notes}{Style.RESET_ALL}')
                excel.append_job(job, keyword, status='Failed', notes=notes, platform='LinkedIn')
                stats['failed'] += 1
        except Exception as exc:
            print(f' {Fore.RED}Failed — {exc}{Style.RESET_ALL}')
            excel.append_job(job, keyword, status='Failed', notes=str(exc), platform='LinkedIn')
            stats['failed'] += 1
        time.sleep(APPLY_DELAY_SEC)

    return stats, len(all_jobs)


def fetch_workatastartup_jobs(client) -> list[tuple]:
    print_section("Work at a Startup — scanning newest roles")
    try:
        jobs = client.fetch_jobs(WORKATASTARTUP_COMPANIES_URL, WORKATASTARTUP_MAX_COMPANIES)
    except Exception as exc:
        print(f' {Fore.RED}[FAIL]{Style.RESET_ALL} listing scrape: {exc}')
        return []
    entries: list[tuple] = []
    for job in jobs:
        if WORKATASTARTUP_FILTER_BY_TITLE and not title_matches_role(job.title):
            continue
        try:
            client.hydrate_company(job)
        except Exception:
            pass
        entries.append((job, "workatastartup"))
    print(f' {Fore.WHITE}{len(jobs)} roles listed, {Fore.GREEN}{len(entries)} match filter{Style.RESET_ALL}')
    print(f'\n {Fore.CYAN}Work at a Startup matching jobs: {Style.BRIGHT}{len(entries)}{Style.RESET_ALL}')
    return entries


def apply_workatastartup_jobs(client, excel: ExcelJobLogger, applied_ids: set[str], applied_companies: set[str], job_entries: list[tuple]) -> tuple[dict, int]:
    from src.client.workatastartup_client import WorkAtAStartupLimitReached
    stats = {'applied': 0, 'skipped_applied': 0, 'skipped_company': 0, 'skipped_external': 0, 'failed': 0}
    print_section(f'Work at a Startup apply — {len(job_entries)} roles (cap {WORKATASTARTUP_MAX_APPLIES}/cycle)')
    for index, (job, keyword) in enumerate(job_entries, start=1):
        print(f'\n{LINE}')
        print(f' {Fore.CYAN}{Style.BRIGHT}[{index}/{len(job_entries)}]{Style.RESET_ALL} {Style.BRIGHT}{job.title}{Style.RESET_ALL}')
        print(f' {Fore.WHITE}Company:{Style.RESET_ALL} {Fore.YELLOW}{job.company}{Style.RESET_ALL}')
        if job.job_id in applied_ids:
            print(f' {Fore.WHITE}Skipped — job ID already applied{Style.RESET_ALL}')
            excel.append_job(job, keyword, status='Skipped - Already Applied', notes='Same job ID on a later run', platform='WorkAtAStartup')
            stats['skipped_applied'] += 1
            continue
        if should_skip_company(excel, job.company, applied_companies):
            print(f' {Fore.WHITE}Skipped — company already applied{Style.RESET_ALL}')
            excel.append_job(job, keyword, status='Skipped - Company Applied', notes='Applied to this company earlier', platform='WorkAtAStartup')
            stats['skipped_company'] += 1
            continue
        if stats['applied'] >= WORKATASTARTUP_MAX_APPLIES:
            print(f' {Fore.YELLOW}Skipped — per-cycle apply cap reached{Style.RESET_ALL}')
            excel.append_job(job, keyword, status='Skipped - Apply Cap', notes='Reached WORKATASTARTUP_MAX_APPLIES', platform='WorkAtAStartup')
            continue
        try:
            result = client.apply_job(job)
            status = result.get('status', 'failed')
            notes = result.get('notes', '')
            if status == 'applied':
                applied_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                print(f' {Fore.GREEN}Applied — {notes}{Style.RESET_ALL}')
                excel.append_job(job, keyword, status='Applied', applied_at=applied_at, notes=notes, platform='WorkAtAStartup')
                applied_ids.add(job.job_id)
                norm = normalize_company(job.company)
                if norm:
                    applied_companies.add(norm)
                stats['applied'] += 1
            elif status == 'already_applied':
                print(f' {Fore.WHITE}Skipped — already applied on Work at a Startup{Style.RESET_ALL}')
                excel.append_job(job, keyword, status='Skipped - Already Applied', notes=notes, platform='WorkAtAStartup')
                applied_ids.add(job.job_id)
                stats['skipped_applied'] += 1
            else:
                print(f' {Fore.RED}Failed — {notes}{Style.RESET_ALL}')
                excel.append_job(job, keyword, status='Failed', notes=notes, platform='WorkAtAStartup')
                stats['failed'] += 1
        except WorkAtAStartupLimitReached as exc:
            print(f' {Fore.YELLOW}Stopping — {exc} (Work at a Startup allows 5 applications/week){Style.RESET_ALL}')
            excel.append_job(job, keyword, status='Skipped - Weekly Limit', notes=str(exc), platform='WorkAtAStartup')
            break
        except Exception as exc:
            print(f' {Fore.RED}Failed — {exc}{Style.RESET_ALL}')
            excel.append_job(job, keyword, status='Failed', notes=str(exc), platform='WorkAtAStartup')
            stats['failed'] += 1
        time.sleep(APPLY_DELAY_SEC)
    return stats, len(job_entries)


def print_summary(platform: str, total: int, stats: dict, excel_file: str) -> None:
    print_section(f'{platform} run summary')
    rows = [('Jobs matched', total, Fore.WHITE), ('Already applied (skipped)', stats['skipped_applied'], Fore.WHITE), ('Company already applied', stats.get('skipped_company', 0), Fore.WHITE), ('Applied this run', stats['applied'], Fore.GREEN), ('External (URL in Excel)', stats['skipped_external'], Fore.YELLOW), ('Failed', stats['failed'], Fore.RED), ('Excel file', excel_file, Fore.CYAN)]
    for label, value, color in rows:
        print(f' {Fore.WHITE}{label:<32}{Style.RESET_ALL} {color}{value}{Style.RESET_ALL}')
    print(LINE)

def _print_search_only_jobs(platform: str, entries: list[tuple]) -> None:
    print_section(f'{platform} — jobs found (search only)')
    if not entries:
        print(f' {Fore.YELLOW}No matching jobs.{Style.RESET_ALL}')
        return
    for index, (job, keyword) in enumerate(entries, start=1):
        print(f' {Fore.CYAN}[{index}]{Style.RESET_ALL} {Style.BRIGHT}{job.title}{Style.RESET_ALL} @ {Fore.YELLOW}{job.company}{Style.RESET_ALL}')
        print(f' {Fore.WHITE}Query:{Style.RESET_ALL} {keyword}')
        url = getattr(job, 'apply_link', None) or getattr(job, 'job_url', '')
        if url:
            print(f' {Fore.BLUE}{url}{Style.RESET_ALL}')

def run_cycle(excel_file: str, search_only: bool=False) -> int:
    excel = ExcelJobLogger(excel_file)
    applied_ids = excel.load_applied_job_ids()
    applied_companies = excel.load_applied_companies()
    if excel.filepath.exists():
        print(f' {Fore.CYAN}Excel: {excel_file} — {len(applied_ids)} jobs, {len(applied_companies)} companies applied{Style.RESET_ALL}')
    else:
        print(f' {Fore.CYAN}Excel: {excel_file} (created on first save){Style.RESET_ALL}')
    exit_code = 0
    if ENABLE_NAUKRI:
        cookies_file = os.getenv('COOKIES_FILE', 'naukri_cookies.json')
        username = os.getenv('USERNAME') or os.getenv('NAUKRI_USERNAME')
        password = os.getenv('PASSWORD') or os.getenv('NAUKRI_PASSWORD')
        client = NaukriLoginClient(username, password)
        print_section('Naukri login')
        if os.path.exists(cookies_file):
            try:
                client.login_from_cookies(cookies_file)
                print(f' {Fore.GREEN}Logged in ({cookies_file}){Style.RESET_ALL}')
            except NaukriAuthError as exc:
                print(f' {Fore.RED}Cookie login failed: {exc}{Style.RESET_ALL}')
                print(f' {Fore.YELLOW}Run: python google_login.py{Style.RESET_ALL}')
                exit_code = 1
        elif username and password:
            try:
                client.login()
                print(f' {Fore.GREEN}Logged in as {username}{Style.RESET_ALL}')
            except NaukriAuthError as exc:
                print(f' {Fore.RED}Login failed: {exc}{Style.RESET_ALL}')
                exit_code = 1
        else:
            print(f' {Fore.YELLOW}Naukri: run google_login.py or set .env credentials{Style.RESET_ALL}')
            exit_code = 1
        if exit_code == 0:
            jc = NaukriJobClient(client)
            entries = fetch_naukri_jobs(jc)
            if search_only:
                _print_search_only_jobs('Naukri', entries)
            elif entries:
                stats = apply_naukri_jobs(jc, entries, applied_ids, applied_companies, excel)
                excel.append_run_summary(stats, total_found=len(entries), platform='Naukri')
                print_summary('Naukri', len(entries), stats, excel_file)
            else:
                print(f'\n{Fore.YELLOW}No matching Naukri jobs this cycle.{Style.RESET_ALL}')
    if ENABLE_LINKEDIN:
        from src.client.linkedin_client import LinkedInApplyClient
        li_cookies = os.getenv('LINKEDIN_COOKIES_FILE', LINKEDIN_COOKIES_FILE)
        li = LinkedInApplyClient(li_cookies, headless=LINKEDIN_HEADLESS)
        print_section('LinkedIn (browser)')
        try:
            li.start()
            print(f' {Fore.GREEN}LinkedIn session ready{Style.RESET_ALL}')
            li_entries = fetch_linkedin_jobs(li)
            if search_only:
                _print_search_only_jobs('LinkedIn', li_entries)
            else:
                stats, total = apply_linkedin_jobs(li, excel, applied_ids, applied_companies, job_entries=li_entries)
                excel.append_run_summary(stats, total_found=total, platform='LinkedIn')
                print_summary('LinkedIn', total, stats, excel_file)
        except FileNotFoundError as exc:
            print(f' {Fore.YELLOW}{exc}{Style.RESET_ALL}')
            print(f' {Fore.YELLOW}Run: python linkedin_login.py{Style.RESET_ALL}')
            exit_code = 1
        except Exception as exc:
            print(f' {Fore.RED}LinkedIn error: {exc}{Style.RESET_ALL}')
            exit_code = 1
        finally:
            li.stop()

    if ENABLE_WORKATASTARTUP:
        from src.client.workatastartup_client import WorkAtAStartupClient
        was_cookies = os.getenv('WORKATASTARTUP_COOKIES_FILE', WORKATASTARTUP_COOKIES_FILE)
        was = WorkAtAStartupClient(was_cookies, headless=WORKATASTARTUP_HEADLESS)
        print_section('Work at a Startup (browser)')
        try:
            was.start()
            print(f' {Fore.GREEN}Work at a Startup session ready{Style.RESET_ALL}')
            was_entries = fetch_workatastartup_jobs(was)
            if search_only:
                _print_search_only_jobs('Work at a Startup', was_entries)
            elif was_entries:
                stats, total = apply_workatastartup_jobs(was, excel, applied_ids, applied_companies, was_entries)
                excel.append_run_summary(stats, total_found=total, platform='WorkAtAStartup')
                print_summary('Work at a Startup', total, stats, excel_file)
            else:
                print(f'\n{Fore.YELLOW}No matching Work at a Startup roles this cycle.{Style.RESET_ALL}')
        except FileNotFoundError as exc:
            print(f' {Fore.YELLOW}{exc}{Style.RESET_ALL}')
            print(f' {Fore.YELLOW}Run: python workatastartup_login.py{Style.RESET_ALL}')
            exit_code = 1
        except Exception as exc:
            print(f' {Fore.RED}Work at a Startup error: {exc}{Style.RESET_ALL}')
            exit_code = 1
        finally:
            was.stop()

    return exit_code

def main() -> int:
    parser = argparse.ArgumentParser(description='Naukri + LinkedIn auto-apply')
    parser.add_argument('--once', action='store_true', help='Run one cycle and exit (default: repeat every LOOP_INTERVAL_MINUTES)')
    parser.add_argument('--search-only', action='store_true', help='Search Naukri + LinkedIn only (no apply)')
    args = parser.parse_args()

    excel_file = os.getenv("EXCEL_FILE", EXCEL_FILE)
    interval = int(os.getenv("LOOP_INTERVAL_MINUTES", LOOP_INTERVAL_MINUTES))

    print_section("Auto-apply started")
    print(f" {Fore.WHITE}Platforms:{Style.RESET_ALL} Naukri={ENABLE_NAUKRI}, LinkedIn={ENABLE_LINKEDIN}, WorkAtAStartup={ENABLE_WORKATASTARTUP}")
    print(f" {Fore.WHITE}Loop:{Style.RESET_ALL} {'once' if args.once else f'every {interval} minutes'}")
    print(f" {Fore.WHITE}Profile:{Style.RESET_ALL} 2yr exp, 30 days notice, relocate=yes, questions=yes")

    cycle = 0
    while True:
        cycle += 1
        print(f"\n{Fore.MAGENTA}{Style.BRIGHT}=== Cycle {cycle} @ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ==={Style.RESET_ALL}")
        run_cycle(excel_file, search_only=args.search_only)
        if args.once:
            break
        print(f'\n{Fore.CYAN}Next run in {interval} minutes (Ctrl+C to stop)...{Style.RESET_ALL}')
        try:
            time.sleep(interval * 60)
        except KeyboardInterrupt:
            print(f'\n{Fore.YELLOW}Stopped by user.{Style.RESET_ALL}')
            break
    return 0
if __name__ == '__main__':
    sys.exit(main())
