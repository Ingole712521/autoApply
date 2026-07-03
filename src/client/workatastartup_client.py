"""
Work at a Startup (Y Combinator) auto-apply client.

Design (reverse-engineered from the live site):
  * The site is an Inertia/React app. Every page embeds its data as JSON in a
    ``data-page`` attribute in the server-rendered HTML — so job details,
    founders, custom questions and "already applied" state can all be read with
    a plain HTTP GET (no brittle DOM scraping / JS rendering needed).
  * Applying is a single JSON call::

        POST /apply
        {company_id, job_id, message, custom_question_answers, open_to_relocation}

    guarded by a Rails CSRF token (``meta[name=csrf-token]``) and the session
    cookies. The server enforces a hard cap of 5 applications per week and
    returns ``{"success": false, "limit": true, ...}`` once you hit it.

Listing discovery uses Selenium (the compact list is Algolia-powered and only
rendered client-side); everything else is HTTP for reliability.

Login is cookie-based — see ``workatastartup_login.py``.
"""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path

import requests
from selenium import webdriver
from selenium.common.exceptions import StaleElementReferenceException
from selenium.webdriver.common.by import By

from config import APPLICANT_PROFILE
from src.utils.browser import create_webdriver
from src.utils.openrouter_client import answer_application_question, generate_application_message

logger = logging.getLogger(__name__)

BASE_URL = "https://www.workatastartup.com"
APPLY_ENDPOINT = f"{BASE_URL}/apply"

_BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


@dataclass
class WaaSJob:
    job_id: str
    title: str
    company: str
    location: str = "N/A"
    experience: str = "N/A"
    salary: str = "N/A"
    posted_date: str = "N/A"
    apply_link: str = ""
    job_url: str = ""
    tags: list = field(default_factory=list)


class _DataPageParser(HTMLParser):
    """Pull the CSRF token and Inertia ``data-page`` JSON out of page HTML."""

    def __init__(self) -> None:
        super().__init__()
        self.csrf: str | None = None
        self.data_page: str | None = None

    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        if tag == "meta" and d.get("name") == "csrf-token":
            self.csrf = d.get("content")
        if "data-page" in d and self.data_page is None:
            self.data_page = d["data-page"]


class WorkAtAStartupLimitReached(Exception):
    """Raised when the weekly application cap is hit — stop applying this cycle."""


class WorkAtAStartupClient:
    def __init__(self, cookies_file: str, headless: bool = False):
        self.cookies_file = Path(cookies_file)
        self.headless = headless
        self.driver: webdriver.Chrome | None = None
        self.session = requests.Session()
        self.session.headers.update(_BROWSER_HEADERS)
        self.profile = APPLICANT_PROFILE

    # ------------------------------------------------------------------ setup
    def start(self) -> None:
        if not self.cookies_file.exists():
            raise FileNotFoundError(
                f"Missing {self.cookies_file}. Run: python workatastartup_login.py"
            )
        cookies = self._load_cookies()

        # HTTP session (used for job details + applying).
        for c in cookies:
            try:
                self.session.cookies.set(
                    c["name"], c["value"], domain=c.get("domain", ".workatastartup.com").lstrip(".") or "www.workatastartup.com"
                )
            except Exception:
                pass

        # Verify the session is authenticated by reading a page's Inertia props.
        props, _ = self._get_props(f"{BASE_URL}/companies")
        if props is None or not props.get("hnid"):
            raise RuntimeError(
                "Work at a Startup session expired. Run: python workatastartup_login.py"
            )
        self._hnid = props.get("hnid")

        # Selenium is only needed to discover the newest roles (Algolia listing).
        self.driver = create_webdriver(headless=self.headless)
        self.driver.get(BASE_URL)
        time.sleep(2)
        for c in cookies:
            try:
                self.driver.add_cookie(
                    {
                        "name": c["name"],
                        "value": c["value"],
                        "domain": c.get("domain", ".workatastartup.com"),
                        "path": c.get("path", "/"),
                    }
                )
            except Exception:
                pass

    def stop(self) -> None:
        if self.driver:
            self.driver.quit()
            self.driver = None

    def _load_cookies(self) -> list:
        raw = json.loads(self.cookies_file.read_text(encoding="utf-8"))
        if isinstance(raw, dict) and "cookies" in raw:
            return raw["cookies"]
        return raw

    # --------------------------------------------------------------- HTTP data
    def _get_props(self, url: str) -> tuple[dict | None, str | None]:
        try:
            r = self.session.get(url, timeout=30)
        except Exception as exc:
            logger.warning("WaaS GET failed %s: %s", url, exc)
            return None, None
        parser = _DataPageParser()
        try:
            parser.feed(r.text)
        except Exception:
            return None, None
        if not parser.data_page:
            return None, parser.csrf
        try:
            return json.loads(parser.data_page)["props"], parser.csrf
        except Exception:
            return None, parser.csrf

    # --------------------------------------------------------------- discovery
    def fetch_jobs(self, companies_url: str, max_companies: int) -> list[WaaSJob]:
        if not self.driver:
            raise RuntimeError("Browser not started")
        self.driver.get(companies_url)
        self._wait_for_job_anchors(timeout=30)
        self._scroll_until_stable(max_rounds=25)

        anchors = self.driver.find_elements(By.CSS_SELECTOR, "a[href*='/jobs/']")
        jobs: list[WaaSJob] = []
        seen: set[str] = set()
        for a in anchors:
            try:
                href = a.get_attribute("href") or ""
            except StaleElementReferenceException:
                continue
            m = re.search(r"/jobs/(\d+)", href)
            if not m:
                continue
            jid = m.group(1)
            if jid in seen:
                continue
            title = re.sub(r"\s+", " ", (a.text or a.get_attribute("aria-label") or "").strip()) or "Role"
            company = self._company_near_anchor(a)
            seen.add(jid)
            jobs.append(
                WaaSJob(
                    job_id=f"was-{jid}",
                    title=title,
                    company=company or "Unknown",
                    job_url=f"{BASE_URL}/jobs/{jid}",
                    apply_link=f"{BASE_URL}/jobs/{jid}",
                )
            )
            if len(jobs) >= max_companies * 4:
                break
        return jobs

    def _company_near_anchor(self, anchor) -> str:
        for xp in ("./ancestor::div[3]", "./ancestor::div[2]", "./ancestor::li[1]"):
            try:
                container = anchor.find_element(By.XPATH, xp)
            except Exception:
                continue
            for sel in ("a[href*='/companies/']", "[class*='company']", "h3", "h4", "strong"):
                try:
                    el = container.find_element(By.CSS_SELECTOR, sel)
                    text = re.sub(r"\s+", " ", (el.text or "").strip())
                    if text and len(text) < 60:
                        return text
                except Exception:
                    continue
        return ""

    def _job_anchor_count(self) -> int:
        assert self.driver
        try:
            return len(self.driver.find_elements(By.CSS_SELECTOR, "a[href*='/jobs/']"))
        except Exception:
            return 0

    def _wait_for_job_anchors(self, timeout: int = 30) -> None:
        """Wait for the Algolia-rendered list to produce at least one job link."""
        assert self.driver
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self._job_anchor_count() > 0:
                return
            time.sleep(1.0)

    def _scroll_until_stable(self, max_rounds: int = 25) -> None:
        """Infinite-scroll the list until the job-link count stops growing."""
        assert self.driver
        last = -1
        stable = 0
        for _ in range(max_rounds):
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(1.2)
            count = self._job_anchor_count()
            if count <= last:
                stable += 1
                if stable >= 3:
                    break
            else:
                stable = 0
            last = count

    def hydrate_company(self, job: WaaSJob) -> None:
        """Fill in the real company name from the job JSON (listing only gives DOM text)."""
        if job.company and job.company != "Unknown":
            return
        jid = self._numeric_id(job)
        if not jid:
            return
        props, _ = self._get_props(f"{BASE_URL}/jobs/{jid}")
        if not props:
            return
        cf = props.get("companyFull") or {}
        cm = props.get("company") or {}
        name = cf.get("name") or cm.get("name")
        if name:
            job.company = name

    # ---------------------------------------------------------------- applying
    def apply_job(self, job: WaaSJob) -> dict:
        jid = self._numeric_id(job)
        if not jid:
            return {"status": "failed", "notes": "No numeric job id", "external_url": ""}

        props, csrf = self._get_props(f"{BASE_URL}/jobs/{jid}")
        if props is None:
            return {"status": "failed", "notes": "Could not load job page JSON", "external_url": ""}

        # Already applied? (per-company on WaaS)
        applied_job_ids = {int(x) for x in (props.get("appliedJobIds") or []) if str(x).isdigit()}
        if props.get("appliedToCompany") or int(jid) in applied_job_ids:
            return {"status": "already_applied", "notes": "Already applied on Work at a Startup", "external_url": ""}

        company_full = props.get("companyFull") or {}
        company_meta = props.get("company") or {}
        job_meta = props.get("job") or {}
        company_id = company_full.get("id")
        if not company_id:
            return {"status": "failed", "notes": "Could not resolve company_id", "external_url": ""}

        company = company_full.get("name") or company_meta.get("name") or job.company
        role = job_meta.get("title") or job.title
        person = self._first_founder(company_meta.get("founders") or company_full.get("founders"))
        description = self._plain_text(job_meta.get("descriptionHtml") or company_meta.get("description") or "")

        custom_questions = props.get("customQuestions") or []
        custom_answers = self._build_custom_answers(custom_questions)
        if custom_answers is None:
            return {"status": "failed", "notes": "Required custom questions could not be answered", "external_url": ""}

        message = generate_application_message(
            company=company, role=role, person=person, profile=self.profile, job_description=description
        )

        if not csrf:
            _, csrf = self._get_props(f"{BASE_URL}/jobs/{jid}")
        if not csrf:
            return {"status": "failed", "notes": "Could not read CSRF token", "external_url": ""}

        payload = {
            "company_id": company_id,
            "job_id": int(jid),
            "message": message,
            "custom_question_answers": custom_answers or None,
            "open_to_relocation": bool(self.profile.get("willing_to_relocate", True)),
        }
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "X-Requested-With": "XMLHttpRequest",
            "X-CSRF-Token": csrf,
            "Origin": BASE_URL,
            "Referer": f"{BASE_URL}/jobs/{jid}",
        }
        try:
            resp = self.session.post(APPLY_ENDPOINT, headers=headers, data=json.dumps(payload), timeout=45)
        except Exception as exc:
            return {"status": "failed", "notes": f"apply request error: {exc}", "external_url": ""}

        return self._interpret_apply_response(resp, person)

    def _interpret_apply_response(self, resp, person: str) -> dict:
        try:
            data = resp.json()
        except Exception:
            if resp.ok:
                return {"status": "applied", "notes": "Message sent", "external_url": ""}
            return {"status": "failed", "notes": f"HTTP {resp.status_code}: {resp.text[:120]}", "external_url": ""}

        if data.get("success"):
            note = f"Sent tailored message to {person}" if person else "Sent tailored message"
            return {"status": "applied", "notes": note, "external_url": ""}

        reason = (data.get("reason") or "").strip()
        if data.get("limit"):
            raise WorkAtAStartupLimitReached(reason or "Weekly application limit reached")
        low = reason.lower()
        if "already" in low or "applied" in low:
            return {"status": "already_applied", "notes": reason, "external_url": ""}
        return {"status": "failed", "notes": reason or f"apply rejected (HTTP {resp.status_code})", "external_url": ""}

    # ----------------------------------------------------------------- helpers
    def _numeric_id(self, job: WaaSJob) -> str | None:
        m = re.search(r"(\d+)", job.job_id or "")
        if m:
            return m.group(1)
        m = re.search(r"/jobs/(\d+)", job.job_url or "")
        return m.group(1) if m else None

    def _first_founder(self, founders) -> str:
        if not isinstance(founders, list):
            return ""
        for f in founders:
            if isinstance(f, dict):
                name = (f.get("full_name") or f.get("name") or "").strip()
            else:
                name = str(f).strip()
            if name and 1 <= len(name.split()) <= 4 and "@" not in name:
                return name
        return ""

    def _plain_text(self, html_text: str) -> str:
        text = re.sub(r"<[^>]+>", " ", html_text or "")
        text = re.sub(r"&[a-z]+;", " ", text)
        return re.sub(r"\s+", " ", text).strip()[:3000]

    def _build_custom_answers(self, questions: list) -> dict | None:
        """Return {question_id: value} or None if a required question can't be answered."""
        answers: dict = {}
        for q in questions or []:
            if not isinstance(q, dict) or q.get("archived_at"):
                continue
            qid = q.get("id")
            qtype = q.get("question_type")
            label = q.get("label") or "Application question"
            required = bool(q.get("required"))
            if qid is None:
                continue
            if qtype in ("text", "long_text", "url"):
                ans = answer_application_question(label, None, self.profile) or ""
                if not ans and required:
                    return None
                if ans:
                    answers[qid] = ans
            elif qtype in ("single_choice", "multiple_choice"):
                opts = [o for o in (q.get("options") or []) if not o.get("archived")]
                if not opts:
                    if required:
                        return None
                    continue
                labels = [o.get("label", "") for o in opts]
                pick = answer_application_question(label, labels, self.profile) or ""
                chosen = None
                for o in opts:
                    if pick and pick.lower() in (o.get("label", "").lower()):
                        chosen = o
                        break
                if chosen is None:
                    chosen = opts[0]
                answers[qid] = chosen["id"] if qtype == "single_choice" else [chosen["id"]]
            else:
                if required:
                    return None
        return answers
