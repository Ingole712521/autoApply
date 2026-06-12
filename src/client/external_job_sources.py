"""
Fetch DevOps-related jobs from boards beyond Naukri/LinkedIn.

These sources are mostly external-apply: we log company, title, and apply URLs
to Excel so you can apply manually or track companies across platforms.
"""

from __future__ import annotations

import json
import logging
import re
import time
import uuid
from datetime import datetime, timezone

import requests

from src.client.session import build_session
from src.models.models import Job

logger = logging.getLogger(__name__)

_HTTP_HEADERS = {
    "User-Agent": "AutoApplyinNaukari/1.0 (+https://github.com/Traverser25/NopeRi)",
    "Accept": "application/json",
}

_SURELY_REMOTE_API = "https://surelyremote.com/api/fetch-jobs/"
_REMOTE_OK_API = "https://remoteok.com/api"
_REMOTIVE_API = "https://remotive.com/api/remote-jobs"
_FOUNDIT_SEARCH_BASE = "https://www.foundit.in/search"


def _slugify(keyword: str) -> str:
    slug = keyword.lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    return slug.strip("-")


def _foundit_search_url(keyword: str, page: int) -> str:
    slug = _slugify(keyword)
    if page <= 1:
        return f"{_FOUNDIT_SEARCH_BASE}/{slug}-jobs"
    return f"{_FOUNDIT_SEARCH_BASE}/{slug}-jobs-{page}"


def _parse_foundit_job_chunk(chunk: str, fallback_title: str, fallback_url: str) -> Job | None:
    job_id_m = re.search(r'jobId\\":(\d+)', chunk)
    if not job_id_m:
        return None

    job_id = job_id_m.group(1)
    title_m = re.search(r'title\\":\\"([^\\"]+)\\"', chunk)
    company_m = re.search(r'company\\":\{\\"companyId\\":\d+,\\"name\\":\\"([^\\"]+)\\"', chunk)
    city_m = re.search(r'locations\\":\[\{\\"city\\":\\"([^\\"]+)\\"', chunk)
    min_exp_m = re.search(r'minimumExperience\\":\{\\"years\\":(\d+)', chunk)
    max_exp_m = re.search(r'maximumExperience\\":\{\\"years\\":(\d+)', chunk)
    posted_m = re.search(r'postedAt\\":(\d+)', chunk)

    title = title_m.group(1) if title_m else fallback_title
    company = company_m.group(1) if company_m else "Unknown"
    location = city_m.group(1) if city_m else "India"

    experience = "N/A"
    if min_exp_m and max_exp_m:
        experience = f"{min_exp_m.group(1)}-{max_exp_m.group(1)} years"
    elif min_exp_m:
        experience = f"{min_exp_m.group(1)}+ years"

    posted_date = "N/A"
    if posted_m:
        try:
            ts = int(posted_m.group(1)) / 1000
            posted_date = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")
        except (ValueError, OSError):
            pass

    apply_url = fallback_url or f"https://www.foundit.in/job/-{job_id}"
    return Job(
        job_id=f"fdit-{job_id}",
        title=title,
        company=company,
        location=location,
        experience=experience,
        salary="N/A",
        posted_date=posted_date,
        apply_link=apply_url,
        tags=[],
    )


def fetch_foundit_jobs(keyword: str, max_pages: int = 5, delay_sec: float = 1.5) -> list[Job]:
    """Scrape Foundit (Monster India) search pages via httpcloak."""
    session = build_session()
    seen: set[str] = set()
    results: list[Job] = []

    for page in range(1, max_pages + 1):
        url = _foundit_search_url(keyword, page)
        try:
            res = session.get(url)
        except Exception as exc:
            logger.warning("Foundit fetch failed %s p%d: %s", keyword, page, exc)
            break

        if res.status_code != 200:
            logger.warning("Foundit HTTP %s for %s", res.status_code, url)
            break

        html = res.text
        blocks = re.findall(
            r'<script type="application/ld\+json">(.*?)</script>',
            html,
            re.S,
        )
        if not blocks:
            break

        try:
            listing = json.loads(blocks[0])
            items = listing.get("itemListElement") or []
        except json.JSONDecodeError:
            break

        if not items:
            break

        for item in items:
            job_url = item.get("url") or ""
            fallback_title = item.get("name") or keyword
            tail = job_url.rsplit("-", 1)[-1] if job_url else ""
            if not tail.isdigit():
                continue

            needle = f'jobId\\":{tail}'
            idx = html.find(needle)
            if idx < 0:
                continue

            job = _parse_foundit_job_chunk(html[idx : idx + 2500], fallback_title, job_url)
            if not job or job.job_id in seen:
                continue
            seen.add(job.job_id)
            results.append(job)

        if len(items) < 20:
            break
        time.sleep(delay_sec)

    return results


def fetch_remote_ok_jobs() -> list[Job]:
    """Remote OK public JSON feed (all listings — filter locally)."""
    try:
        res = requests.get(_REMOTE_OK_API, headers=_HTTP_HEADERS, timeout=60)
        res.raise_for_status()
        payload = res.json()
    except Exception as exc:
        logger.warning("Remote OK API failed: %s", exc)
        return []

    if not isinstance(payload, list) or len(payload) < 2:
        return []

    results: list[Job] = []
    for raw in payload[1:]:
        if not isinstance(raw, dict) or not raw.get("id"):
            continue

        job_id = str(raw["id"])
        title = (raw.get("position") or raw.get("title") or "").strip()
        company = (raw.get("company") or "Unknown").strip()
        if not title:
            continue

        tags = raw.get("tags") or []
        if isinstance(tags, str):
            tags = [tags]

        location = (raw.get("location") or "Remote").strip()
        salary = (raw.get("salary") or "N/A").strip() or "N/A"
        apply_url = (raw.get("apply_url") or raw.get("url") or "").strip()
        epoch = raw.get("epoch")
        posted_date = "N/A"
        if epoch:
            try:
                posted_date = datetime.fromtimestamp(int(epoch), tz=timezone.utc).strftime("%Y-%m-%d")
            except (ValueError, OSError):
                pass

        results.append(
            Job(
                job_id=f"rok-{job_id}",
                title=title,
                company=company,
                location=location or "Remote",
                experience="N/A",
                salary=salary,
                posted_date=posted_date,
                apply_link=apply_url or f"https://remoteok.com/remote-jobs/{job_id}",
                tags=[str(t) for t in tags],
            )
        )
    return results


def fetch_remotive_jobs() -> list[Job]:
    """Remotive public API (limited free feed)."""
    try:
        res = requests.get(_REMOTIVE_API, headers=_HTTP_HEADERS, timeout=60)
        res.raise_for_status()
        payload = res.json()
    except Exception as exc:
        logger.warning("Remotive API failed: %s", exc)
        return []

    results: list[Job] = []
    for raw in payload.get("jobs") or []:
        if not raw.get("id"):
            continue

        job_id = str(raw["id"])
        title = (raw.get("title") or "").strip()
        company = (raw.get("company_name") or "Unknown").strip()
        if not title:
            continue

        tags = raw.get("tags") or []
        location = (raw.get("candidate_required_location") or "Remote").strip()
        salary = (raw.get("salary") or "N/A").strip() or "N/A"
        apply_url = (raw.get("url") or "").strip()
        posted = (raw.get("publication_date") or "N/A")[:10]

        results.append(
            Job(
                job_id=f"rmv-{job_id}",
                title=title,
                company=company,
                location=location or "Remote",
                experience="N/A",
                salary=salary,
                posted_date=posted or "N/A",
                apply_link=apply_url or f"https://remotive.com/remote-jobs/{job_id}",
                tags=[str(t) for t in tags],
            )
        )
    return results


def fetch_surely_remote_jobs(keyword: str) -> list[Job]:
    """Surely Remote wizard API — returns matched remote roles (apply via their portal)."""
    body = {
        "location": None,
        "jobTitle": keyword,
        "experience": None,
        "salary": 1_200_000,
        "categories": [],
        "searchId": f"autoapply-{uuid.uuid4().hex[:12]}",
    }

    try:
        res = requests.post(
            _SURELY_REMOTE_API,
            headers={**_HTTP_HEADERS, "Content-Type": "application/json"},
            json=body,
            timeout=45,
        )
        res.raise_for_status()
        payload = res.json()
    except Exception as exc:
        logger.warning("Surely Remote API failed for %r: %s", keyword, exc)
        return []

    results: list[Job] = []
    for raw in payload.get("jobs") or []:
        req_id = str(raw.get("requisition_id") or "").strip()
        title = (raw.get("title") or keyword).strip()
        company = (raw.get("company") or "Unknown").strip()
        if not req_id:
            continue

        apply_url = "https://jobs.surelyremote.com/account/sign-in"
        results.append(
            Job(
                job_id=f"sr-{req_id}",
                title=title,
                company=company,
                location="Remote",
                experience="N/A",
                salary="N/A",
                posted_date="N/A",
                apply_link=f"https://surelyremote.com/?job={req_id}",
                tags=[],
            )
        )
    return results
