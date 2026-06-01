"""
LinkedIn Easy Apply automation via Selenium.

Requires linkedin_cookies.json from linkedin_login.py.
"""

from __future__ import annotations

import json
import logging
import re
import time
import urllib.parse
from dataclasses import dataclass, field
from pathlib import Path

from selenium import webdriver
from selenium.common.exceptions import (
    ElementClickInterceptedException,
    NoSuchElementException,
    StaleElementReferenceException,
    TimeoutException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from config import APPLICANT_PROFILE, LINKEDIN_EASY_APPLY_MAX_STEPS
from src.client.linkedin_easy_apply_form import LinkedInEasyApplyForm
from src.utils.browser import create_webdriver

logger = logging.getLogger(__name__)

EASY_APPLY_LABELS = ("easy apply", "in easy apply")
EXTERNAL_APPLY_LABELS = ("apply on company", "apply on the company", "apply on website")
APPLY_BUTTON_WAIT_SEC = 15


@dataclass
class LinkedInJob:
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


class LinkedInApplyClient:
    def __init__(self, cookies_file: str, headless: bool = False):
        self.cookies_file = Path(cookies_file)
        self.headless = headless
        self.driver: webdriver.Chrome | None = None
        self.profile = APPLICANT_PROFILE

    def start(self) -> None:
        self.driver = create_webdriver(headless=self.headless)
        self.driver.get("https://www.linkedin.com")
        time.sleep(2)

        if not self.cookies_file.exists():
            raise FileNotFoundError(
                f"Missing {self.cookies_file}. Run: python linkedin_login.py"
            )

        cookies = json.loads(self.cookies_file.read_text(encoding="utf-8"))
        for cookie in cookies:
            try:
                self.driver.add_cookie(
                    {
                        "name": cookie["name"],
                        "value": cookie["value"],
                        "domain": cookie.get("domain", ".linkedin.com"),
                    }
                )
            except Exception:
                pass

        self.driver.refresh()
        time.sleep(3)

        if "login" in (self.driver.current_url or "").lower():
            raise RuntimeError("LinkedIn session expired. Run: python linkedin_login.py")

    def stop(self) -> None:
        if self.driver:
            self.driver.quit()
            self.driver = None

    def search_jobs(self, keyword: str, location: str, max_jobs: int) -> list[LinkedInJob]:
        if not self.driver:
            raise RuntimeError("Browser not started")

        params = {
            "keywords": keyword,
            "location": location,
            "f_AL": "true",
        }
        url = "https://www.linkedin.com/jobs/search/?" + urllib.parse.urlencode(params)
        self.driver.get(url)
        time.sleep(4)

        self._scroll_results()
        cards = self.driver.find_elements(
            By.CSS_SELECTOR,
            "div.job-card-container, li.jobs-search-results__list-item, div.base-card",
        )

        jobs: list[LinkedInJob] = []
        seen_urls: set[str] = set()

        for card in cards:
            if len(jobs) >= max_jobs:
                break
            try:
                link_el = card.find_element(
                    By.CSS_SELECTOR,
                    "a[href*='/jobs/view/'], a.job-card-container__link, a.base-card__full-link",
                )
                href = link_el.get_attribute("href") or ""
                if not href or href in seen_urls:
                    continue
                seen_urls.add(href)

                job_id_match = re.search(r"/jobs/view/(\d+)", href)
                job_id = f"li-{job_id_match.group(1)}" if job_id_match else f"li-{len(jobs)}"

                title = (link_el.text or link_el.get_attribute("aria-label") or "N/A").strip()
                company = "N/A"
                try:
                    company_el = card.find_element(
                        By.CSS_SELECTOR,
                        ".job-card-container__company-name, "
                        ".base-search-card__subtitle, "
                        "h4.base-search-card__subtitle",
                    )
                    company = (company_el.text or "N/A").strip()
                except NoSuchElementException:
                    pass

                location_text = "N/A"
                try:
                    loc_el = card.find_element(
                        By.CSS_SELECTOR,
                        ".job-card-container__metadata-item, "
                        ".job-search-card__location",
                    )
                    location_text = (loc_el.text or "N/A").strip()
                except NoSuchElementException:
                    pass

                jobs.append(
                    LinkedInJob(
                        job_id=job_id,
                        title=title or "N/A",
                        company=company,
                        location=location_text,
                        job_url=href.split("?")[0],
                        apply_link=href.split("?")[0],
                    )
                )
            except NoSuchElementException:
                continue

        return jobs

    def apply_job(self, job: LinkedInJob) -> dict:
        """
        Returns dict with keys: status, notes, external_url.
        status: applied | external | failed | already_applied
        """
        if not self.driver:
            raise RuntimeError("Browser not started")

        apply_btn = None
        for url in self._job_page_urls(job):
            self.driver.get(url)
            self._prepare_job_page()

            if self._page_shows_applied():
                return {"status": "already_applied", "notes": "Already applied on LinkedIn", "external_url": ""}

            apply_btn = self._find_apply_button()
            if apply_btn:
                break

        if not apply_btn:
            snippet = self._apply_area_debug_hint()
            return {
                "status": "failed",
                "notes": f"No apply button found ({snippet})",
                "external_url": "",
            }

        label = self._button_label(apply_btn)

        if any(x in label for x in EXTERNAL_APPLY_LABELS):
            external_url = self._capture_external_apply_url(apply_btn)
            return {
                "status": "external",
                "notes": "Redirects to company website",
                "external_url": external_url or job.job_url,
            }

        handles_before = set(self.driver.window_handles)
        try:
            self._click_element(apply_btn)
            time.sleep(1)
        except Exception as exc:
            return {"status": "failed", "notes": str(exc), "external_url": ""}

        new_handles = set(self.driver.window_handles) - handles_before
        if new_handles:
            self.driver.switch_to.window(new_handles.pop())
            external_url = self.driver.current_url
            self._close_extra_tabs(keep_main=job.job_url)
            return {
                "status": "external",
                "notes": "Opened company apply page",
                "external_url": external_url,
            }

        form = LinkedInEasyApplyForm(
            self.driver, self.profile, max_steps=LINKEDIN_EASY_APPLY_MAX_STEPS
        )
        ok, err = form.complete()
        if ok:
            return {"status": "applied", "notes": "Easy Apply submitted on LinkedIn", "external_url": ""}
        return {"status": "failed", "notes": err or "Easy Apply form incomplete", "external_url": ""}

    def _job_page_urls(self, job: LinkedInJob) -> list[str]:
        """Prefer jobs search split view — Easy Apply is usually visible there."""
        urls: list[str] = []
        match = re.search(r"(\d+)", job.job_id or "")
        if match:
            jid = match.group(1)
            urls.append(
                "https://www.linkedin.com/jobs/search/?currentJobId="
                f"{jid}&f_AL=true"
            )
            urls.append(f"https://www.linkedin.com/jobs/view/{jid}/")
        if job.job_url and job.job_url not in urls:
            urls.append(job.job_url.split("?")[0])
        return urls or [job.job_url]

    def _scroll_results(self) -> None:
        assert self.driver
        for _ in range(4):
            self.driver.execute_script("window.scrollBy(0, 800);")
            time.sleep(1.2)

    def _page_shows_applied(self) -> bool:
        assert self.driver
        page = (self.driver.page_source or "").lower()
        return "you applied" in page or "application submitted" in page

    def _prepare_job_page(self) -> None:
        """Wait for job details and scroll so the apply button can load."""
        assert self.driver
        wait = WebDriverWait(self.driver, APPLY_BUTTON_WAIT_SEC)
        try:
            wait.until(
                EC.presence_of_element_located(
                    (
                        By.CSS_SELECTOR,
                        ".jobs-unified-top-card, .job-view-layout, "
                        "h1.t-24, h2.job-details-jobs-unified-top-card__job-title",
                    )
                )
            )
        except TimeoutException:
            pass

        for _ in range(3):
            self.driver.execute_script("window.scrollTo(0, 0);")
            time.sleep(0.4)

        for selector in (
            ".jobs-unified-top-card",
            ".jobs-apply-button--top-card",
            ".jobs-s-apply",
            ".jobs-details__main-content",
        ):
            try:
                el = self.driver.find_element(By.CSS_SELECTOR, selector)
                self.driver.execute_script(
                    "arguments[0].scrollIntoView({block: 'center', inline: 'nearest'});",
                    el,
                )
                time.sleep(0.6)
            except NoSuchElementException:
                continue

        time.sleep(1.5)

    def _button_label(self, element) -> str:
        parts = [
            element.text,
            element.get_attribute("aria-label"),
            element.get_attribute("innerText"),
            element.get_attribute("title"),
        ]
        try:
            parts.append(
                self.driver.execute_script(
                    "return (arguments[0].innerText || arguments[0].textContent || '');",
                    element,
                )
            )
        except Exception:
            pass
        return " ".join(p for p in parts if p).strip().lower()

    def _collect_apply_button_candidates(self) -> list:
        assert self.driver
        seen: set[str] = set()
        candidates: list = []

        def add(el) -> None:
            try:
                key = el.id or el.get_attribute("outerHTML")[:120]
                if key in seen:
                    return
                seen.add(key)
                candidates.append(el)
            except StaleElementReferenceException:
                pass

        css_selectors = [
            "button.jobs-apply-button",
            "button.jobs-apply-button--top-card",
            "button.jobs-s-apply__application-button",
            "div.jobs-apply-button--top-card button",
            "div.jobs-s-apply button",
            "button[aria-label*='Easy Apply']",
            "button[aria-label*='easy apply']",
            "button[aria-label*='Apply']",
            "a.jobs-apply-button",
        ]
        xpath_selectors = [
            "//button[contains(@class, 'jobs-apply-button')]",
            "//button[contains(., 'Easy Apply')]",
            "//button[.//span[contains(normalize-space(), 'Easy Apply')]]",
            "//span[contains(normalize-space(), 'Easy Apply')]/ancestor::button[1]",
            "//div[contains(@class, 'jobs-apply-button')]//button",
            "//div[@role='button' and contains(., 'Easy Apply')]",
        ]

        for sel in css_selectors:
            try:
                for el in self.driver.find_elements(By.CSS_SELECTOR, sel):
                    add(el)
            except Exception:
                continue

        for xp in xpath_selectors:
            try:
                for el in self.driver.find_elements(By.XPATH, xp):
                    add(el)
            except Exception:
                continue

        for el in self.driver.find_elements(By.TAG_NAME, "button"):
            try:
                if "apply" in self._button_label(el):
                    add(el)
            except StaleElementReferenceException:
                continue

        return candidates

    def _score_apply_button(self, element) -> int:
        label = self._button_label(element)
        if not label or "applied" in label or "save" in label:
            return -1
        if "easy apply" in label:
            return 100
        if "in easy apply" in label:
            return 90
        if "apply on company" in label or "apply on the company" in label:
            return 50
        if label.strip() == "apply":
            return 40
        if "apply" in label:
            return 30
        return -1

    def _ensure_clickable(self, element):
        assert self.driver
        wait = WebDriverWait(self.driver, APPLY_BUTTON_WAIT_SEC)
        self.driver.execute_script(
            "arguments[0].scrollIntoView({block: 'center', inline: 'nearest'});",
            element,
        )
        time.sleep(0.5)
        return wait.until(EC.element_to_be_clickable(element))

    def _click_element(self, element) -> None:
        assert self.driver
        try:
            element.click()
        except (ElementClickInterceptedException, StaleElementReferenceException):
            self.driver.execute_script("arguments[0].click();", element)

    def _find_apply_button(self):
        assert self.driver
        wait = WebDriverWait(self.driver, APPLY_BUTTON_WAIT_SEC)

        def _best_button(driver):
            ranked = []
            for btn in self._collect_apply_button_candidates():
                score = self._score_apply_button(btn)
                if score > 0:
                    ranked.append((score, btn))
            if not ranked:
                return False
            ranked.sort(key=lambda x: x[0], reverse=True)
            self._last_apply_button = ranked[0][1]
            return True

        self._last_apply_button = None
        try:
            wait.until(_best_button)
            if self._last_apply_button:
                try:
                    return self._ensure_clickable(self._last_apply_button)
                except Exception:
                    return self._last_apply_button
        except TimeoutException:
            pass

        ranked = []
        for btn in self._collect_apply_button_candidates():
            score = self._score_apply_button(btn)
            if score > 0:
                ranked.append((score, btn))
        if not ranked:
            return None
        ranked.sort(key=lambda x: x[0], reverse=True)
        try:
            return self._ensure_clickable(ranked[0][1])
        except Exception:
            return ranked[0][1]

    def _apply_area_debug_hint(self) -> str:
        assert self.driver
        labels = []
        for btn in self._collect_apply_button_candidates()[:8]:
            label = self._button_label(btn)
            if label:
                labels.append(label[:40])
        if labels:
            return "seen: " + "; ".join(labels)
        return f"url={self.driver.current_url[:80]}"

    def _capture_external_apply_url(self, apply_btn) -> str:
        assert self.driver
        main = self.driver.current_window_handle
        handles_before = set(self.driver.window_handles)
        try:
            apply_btn.click()
            time.sleep(3)
        except Exception:
            href = apply_btn.get_attribute("href")
            return href or self.driver.current_url

        new_handles = set(self.driver.window_handles) - handles_before
        if new_handles:
            self.driver.switch_to.window(new_handles.pop())
            url = self.driver.current_url
            self._close_extra_tabs(keep_main=main)
            return url

        url = self.driver.current_url
        if "linkedin.com/jobs" not in url:
            self.driver.get(main)
            return url
        return url

    def _close_extra_tabs(self, keep_main: str | None = None) -> None:
        assert self.driver
        main_handle = self.driver.current_window_handle
        for handle in list(self.driver.window_handles):
            if handle == main_handle:
                continue
            self.driver.switch_to.window(handle)
            self.driver.close()
        self.driver.switch_to.window(main_handle)
        if keep_main and isinstance(keep_main, str) and keep_main.startswith("http"):
            self.driver.get(keep_main)

