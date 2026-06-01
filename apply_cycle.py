"""
Shared apply cycle for local runs and Vercel Cron.

Returns a JSON-serializable summary dict.
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

load_dotenv()

# Vercel sets VERCEL=1
IS_VERCEL = bool(os.getenv("VERCEL") or os.getenv("VERCEL_ENV"))


def _is_vercel() -> bool:
    return IS_VERCEL


def get_excel_path() -> str:
    if _is_vercel():
        return str(Path(tempfile.gettempdir()) / "job_applications.xlsx")
    return os.getenv("EXCEL_FILE", "job_applications.xlsx")


def _prepare_naukri_cookies_file() -> str | None:
    """Return path to cookies file, creating from env on Vercel if needed."""
    cookies_json = os.getenv("NAUKRI_COOKIES_JSON", "").strip()
    cookies_file = os.getenv("COOKIES_FILE", "naukri_cookies.json")

    if cookies_json:
        path = Path(tempfile.gettempdir()) / "naukri_cookies.json"
        data = json.loads(cookies_json)
        path.write_text(json.dumps(data), encoding="utf-8")
        return str(path)

    if Path(cookies_file).exists():
        return cookies_file
    return None


def run_apply_cycle() -> dict[str, Any]:
    from config import ENABLE_LINKEDIN, ENABLE_NAUKRI, EXCEL_FILE

    from src.utils.job_store import sync_excel_download, sync_excel_upload

    started = datetime.utcnow().isoformat() + "Z"
    excel_file = get_excel_path()

    if _is_vercel():
        sync_excel_download(Path(excel_file))

    enable_naukri = ENABLE_NAUKRI
    enable_linkedin = ENABLE_LINKEDIN and not _is_vercel()

    if _is_vercel() and ENABLE_LINKEDIN:
        # LinkedIn needs Selenium/Brave — not available on Vercel serverless
        enable_linkedin = False

    summary: dict[str, Any] = {
        "started_at": started,
        "vercel": _is_vercel(),
        "platforms": {"naukri": enable_naukri, "linkedin": enable_linkedin},
        "excel_file": excel_file,
        "naukri": None,
        "linkedin": None,
        "errors": [],
        "finished_at": None,
        "excel_blob_url": None,
    }

    # Import after env is loaded
    import react_devops_auto_apply as runner

    os.environ["EXCEL_FILE"] = excel_file

    if not enable_naukri and not enable_linkedin:
        summary["errors"].append("No platforms enabled")
        summary["finished_at"] = datetime.utcnow().isoformat() + "Z"
        return summary

    applied_ids: set[str] = set()
    applied_companies: set[str] = set()
    exit_code = 0

    from src.utils.excel_logger import ExcelJobLogger

    excel = ExcelJobLogger(excel_file)
    applied_ids = excel.load_applied_job_ids()
    applied_companies = excel.load_applied_companies()

    if enable_naukri:
        naukri_result = _run_naukri(runner, excel, excel_file, applied_ids, applied_companies)
        summary["naukri"] = naukri_result
        if naukri_result.get("exit_code", 0) != 0:
            exit_code = 1

    if enable_linkedin:
        linkedin_result = _run_linkedin(runner, excel, excel_file, applied_ids, applied_companies)
        summary["linkedin"] = linkedin_result
        if linkedin_result.get("exit_code", 0) != 0:
            exit_code = 1

    if _is_vercel():
        blob_url = sync_excel_upload(Path(excel_file))
        summary["excel_blob_url"] = blob_url

    summary["exit_code"] = exit_code
    summary["finished_at"] = datetime.utcnow().isoformat() + "Z"
    return summary


def _run_naukri(runner, excel, excel_file, applied_ids, applied_companies) -> dict[str, Any]:
    from src.client.job_client import NaukriJobClient
    from src.client.naukri_client import NaukriLoginClient
    from src.exceptions.exceptions import NaukriAuthError

    result: dict[str, Any] = {"exit_code": 0, "jobs_found": 0, "stats": None, "error": None}

    username = os.getenv("USERNAME") or os.getenv("NAUKRI_USERNAME")
    password = os.getenv("PASSWORD") or os.getenv("NAUKRI_PASSWORD")
    client = NaukriLoginClient(username, password)

    cookies_path = _prepare_naukri_cookies_file()
    cookies_json = os.getenv("NAUKRI_COOKIES_JSON", "").strip()

    try:
        if cookies_json:
            client.login_from_cookies_data(json.loads(cookies_json))
        elif cookies_path:
            client.login_from_cookies(cookies_path)
        elif username and password:
            client.login()
        else:
            result["exit_code"] = 1
            result["error"] = "Set NAUKRI_COOKIES_JSON or USERNAME/PASSWORD in Vercel env"
            return result
    except NaukriAuthError as exc:
        result["exit_code"] = 1
        result["error"] = str(exc)
        return result

    jc = NaukriJobClient(client)
    entries = runner.fetch_naukri_jobs(jc)
    result["jobs_found"] = len(entries)

    if entries:
        stats = runner.apply_naukri_jobs(jc, entries, applied_ids, applied_companies, excel)
        excel.append_run_summary(stats, total_found=len(entries), platform="Naukri")
        result["stats"] = stats
    return result


def _run_linkedin(runner, excel, excel_file, applied_ids, applied_companies) -> dict[str, Any]:
    from config import LINKEDIN_COOKIES_FILE, LINKEDIN_HEADLESS
    from src.client.linkedin_client import LinkedInApplyClient

    result: dict[str, Any] = {"exit_code": 0, "jobs_found": 0, "stats": None, "error": None}
    li_cookies = os.getenv("LINKEDIN_COOKIES_FILE", LINKEDIN_COOKIES_FILE)
    li = LinkedInApplyClient(li_cookies, headless=LINKEDIN_HEADLESS)

    try:
        li.start()
        stats, total = runner.apply_linkedin_jobs(li, excel, applied_ids, applied_companies)
        excel.append_run_summary(stats, total_found=total, platform="LinkedIn")
        result["jobs_found"] = total
        result["stats"] = stats
    except Exception as exc:
        result["exit_code"] = 1
        result["error"] = str(exc)
    finally:
        li.stop()
    return result
