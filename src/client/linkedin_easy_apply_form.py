"""
Fill LinkedIn Easy Apply multi-step modal: questions, Next, Review, Submit.
"""

from __future__ import annotations

import logging
import re
import time
from typing import Any

from selenium.common.exceptions import NoSuchElementException, StaleElementReferenceException
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select, WebDriverWait

from src.utils.openrouter_client import answer_application_question

logger = logging.getLogger(__name__)

MODAL_SELECTORS = (
    "div.jobs-easy-apply-modal",
    "div[data-test-modal-id='easy-apply-modal']",
    "div.artdeco-modal.jobs-easy-apply-modal",
)

FOOTER_SUBMIT = ("submit application", "submit")
FOOTER_REVIEW = ("review your application", "review")
FOOTER_NEXT = ("continue to next step", "next", "continue")


class LinkedInEasyApplyForm:
    def __init__(self, driver, profile: dict[str, Any], max_steps: int = 25):
        self.driver = driver
        self.profile = profile
        self.max_steps = max_steps

    def wait_for_modal(self, timeout: int = 15) -> bool:
        try:
            WebDriverWait(self.driver, timeout).until(
                lambda d: self.get_modal() is not None
            )
            return True
        except Exception:
            return False

    def get_modal(self) -> WebElement | None:
        for sel in MODAL_SELECTORS:
            for el in self.driver.find_elements(By.CSS_SELECTOR, sel):
                try:
                    if el.is_displayed():
                        return el
                except StaleElementReferenceException:
                    continue
        return None

    def complete(self) -> tuple[bool, str]:
        if not self.wait_for_modal():
            return False, "Easy Apply popup did not open"

        for step in range(self.max_steps):
            modal = self.get_modal()
            if not modal:
                if self._submitted_success():
                    return True, ""
                return False, "Easy Apply popup closed before finish"

            self._fill_current_step(modal)
            time.sleep(0.6)

            if self._click_footer(modal, FOOTER_SUBMIT):
                time.sleep(2)
                if self._submitted_success():
                    return True, ""
                continue

            if self._click_footer(modal, FOOTER_REVIEW):
                time.sleep(1.2)
                continue

            if self._click_footer(modal, FOOTER_NEXT):
                time.sleep(1.2)
                continue

            if self._submitted_success():
                return True, ""

            if self._has_validation_errors(modal):
                self._fill_current_step(modal, force=True)
                if self._click_footer(modal, FOOTER_NEXT + FOOTER_SUBMIT + FOOTER_REVIEW):
                    time.sleep(1)
                    continue

        return False, f"Could not finish Easy Apply after {self.max_steps} steps"

    def _submitted_success(self) -> bool:
        src = (self.driver.page_source or "").lower()
        return any(
            x in src
            for x in (
                "application sent",
                "your application was sent",
                "application submitted",
                "you applied",
            )
        )

    def _has_validation_errors(self, modal: WebElement) -> bool:
        try:
            errs = modal.find_elements(By.CSS_SELECTOR, ".artdeco-inline-feedback--error, .fb-dash-form-element__error-text")
            return any(e.is_displayed() for e in errs)
        except Exception:
            return False

    def _fill_current_step(self, modal: WebElement, force: bool = False) -> None:
        self._fill_text_fields(modal, force)
        self._fill_textareas(modal, force)
        self._fill_number_fields(modal, force)
        self._fill_selects(modal, force)
        self._fill_radios_and_checkboxes(modal, force)
        self._fill_linkedin_dropdowns(modal, force)

    def _fill_text_fields(self, modal: WebElement, force: bool) -> None:
        for inp in modal.find_elements(By.CSS_SELECTOR, "input[type='text'], input[type='email'], input[type='tel']"):
            self._fill_text_input(inp, force)

    def _fill_textareas(self, modal: WebElement, force: bool) -> None:
        for inp in modal.find_elements(By.CSS_SELECTOR, "textarea"):
            self._fill_text_input(inp, force)

    def _fill_number_fields(self, modal: WebElement, force: bool) -> None:
        for inp in modal.find_elements(By.CSS_SELECTOR, "input[type='number']"):
            self._fill_text_input(inp, force)

    def _fill_text_input(self, inp: WebElement, force: bool) -> None:
        try:
            if not inp.is_displayed():
                return
            current = (inp.get_attribute("value") or "").strip()
            if current and not force:
                return
            label = self._element_question_text(inp)
            value = self._answer_for_question(label, field_type="text")
            inp.clear()
            inp.send_keys(value)
        except Exception:
            pass

    def _fill_selects(self, modal: WebElement, force: bool) -> None:
        for sel_el in modal.find_elements(By.CSS_SELECTOR, "select"):
            try:
                if not sel_el.is_displayed():
                    continue
                select = Select(sel_el)
                if select.first_selected_option.text.strip() and not force:
                    continue
                label = self._element_question_text(sel_el)
                options = [o.text.strip() for o in select.options if o.text.strip()]
                answer = self._answer_for_question(label, options=options, field_type="select")
                self._select_best_option(select, options, answer)
            except Exception:
                pass

    def _fill_radios_and_checkboxes(self, modal: WebElement, force: bool) -> None:
        for fieldset in modal.find_elements(By.CSS_SELECTOR, "fieldset"):
            try:
                radios = fieldset.find_elements(By.CSS_SELECTOR, "input[type='radio']")
                if radios and any(r.is_displayed() for r in radios):
                    if any(r.is_selected() for r in radios) and not force:
                        continue
                    question = (fieldset.text or "").strip()
                    options = self._radio_labels(fieldset)
                    answer = self._answer_for_question(question, options=options, field_type="radio")
                    self._pick_radio(fieldset, answer, options)
                    continue

                boxes = fieldset.find_elements(By.CSS_SELECTOR, "input[type='checkbox']")
                for box in boxes:
                    if not box.is_displayed() or box.is_selected():
                        continue
                    question = (fieldset.text or "").strip()
                    if self._should_answer_yes(question):
                        self._click_element(box)
            except Exception:
                pass

        for box in modal.find_elements(By.CSS_SELECTOR, "input[type='checkbox']"):
            try:
                if not box.is_displayed() or box.is_selected():
                    continue
                label = self._element_question_text(box)
                if any(x in label.lower() for x in ("agree", "confirm", "understand", "certify")):
                    self._click_element(box)
            except Exception:
                pass

    def _fill_linkedin_dropdowns(self, modal: WebElement, force: bool) -> None:
        """LinkedIn custom dropdowns (not native select)."""
        toggles = modal.find_elements(
            By.CSS_SELECTOR,
            "div[data-test-text-select-toggle], button[aria-haspopup='listbox']",
        )
        for toggle in toggles:
            try:
                if not toggle.is_displayed():
                    continue
                label = self._element_question_text(toggle)
                if toggle.get_attribute("aria-expanded") == "true" and not force:
                    continue
                self._click_element(toggle)
                time.sleep(0.4)
                options_els = self.driver.find_elements(
                    By.CSS_SELECTOR,
                    "div[role='option'], li[role='option']",
                )
                options = [o.text.strip() for o in options_els if o.text.strip() and o.is_displayed()]
                if not options:
                    continue
                answer = self._answer_for_question(label, options=options, field_type="select")
                self._click_option_match(options_els, answer)
            except Exception:
                pass

    def _radio_labels(self, fieldset: WebElement) -> list[str]:
        labels = []
        for radio in fieldset.find_elements(By.CSS_SELECTOR, "input[type='radio']"):
            rid = radio.get_attribute("id")
            if rid:
                try:
                    lab = self.driver.find_element(By.CSS_SELECTOR, f"label[for='{rid}']")
                    if lab.text.strip():
                        labels.append(lab.text.strip())
                        continue
                except NoSuchElementException:
                    pass
            aria = radio.get_attribute("aria-label")
            if aria:
                labels.append(aria.strip())
        return labels

    def _pick_radio(self, fieldset: WebElement, answer: str, options: list[str]) -> None:
        answer_l = answer.lower()
        for radio in fieldset.find_elements(By.CSS_SELECTOR, "input[type='radio']"):
            rid = radio.get_attribute("id")
            label_text = ""
            if rid:
                try:
                    label_text = self.driver.find_element(By.CSS_SELECTOR, f"label[for='{rid}']").text
                except NoSuchElementException:
                    pass
            if not label_text:
                label_text = radio.get_attribute("aria-label") or ""
            if answer_l in label_text.lower() or label_text.lower() in answer_l:
                self._click_element(radio)
                return
        for opt in options:
            if answer_l in opt.lower():
                for radio in fieldset.find_elements(By.CSS_SELECTOR, "input[type='radio']"):
                    rid = radio.get_attribute("id")
                    try:
                        lab = self.driver.find_element(By.CSS_SELECTOR, f"label[for='{rid}']").text
                        if opt.lower() in lab.lower():
                            self._click_element(radio)
                            return
                    except Exception:
                        pass
        if options and self._should_answer_yes(fieldset.text):
            for radio in fieldset.find_elements(By.CSS_SELECTOR, "input[type='radio']"):
                rid = radio.get_attribute("id")
                try:
                    lab = self.driver.find_element(By.CSS_SELECTOR, f"label[for='{rid}']").text.lower()
                    if "yes" in lab:
                        self._click_element(radio)
                        return
                except Exception:
                    pass

    def _click_option_match(self, options_els: list[WebElement], answer: str) -> None:
        answer_l = answer.lower()
        for el in options_els:
            if not el.is_displayed():
                continue
            text = (el.text or "").strip()
            if answer_l in text.lower() or text.lower() in answer_l:
                self._click_element(el)
                return
        for el in options_els:
            if el.is_displayed() and "yes" in (el.text or "").lower():
                self._click_element(el)
                return

    def _select_best_option(self, select: Select, options: list[str], answer: str) -> None:
        answer_l = answer.lower()
        for i, opt in enumerate(options):
            if answer_l in opt.lower() or opt.lower() in answer_l:
                select.select_by_index(i)
                return
        prefs = self._preference_tokens(answer_l)
        for pref in prefs:
            for i, opt in enumerate(options):
                if pref in opt.lower():
                    select.select_by_index(i)
                    return
        if len(options) > 1:
            select.select_by_index(1)

    def _answer_for_question(
        self,
        question: str,
        options: list[str] | None = None,
        field_type: str = "text",
    ) -> str:
        q = (question or "").lower()
        p = self.profile

        if any(x in q for x in ("notice", "serving notice")):
            return str(p.get("notice_days", 30))
        if any(x in q for x in ("experience", "years of experience", "how many years")):
            return str(p.get("exp_total", "2"))
        if any(x in q for x in ("relocate", "relocation", "willing to move")):
            return "Yes" if p.get("willing_to_relocate") else "No"
        if any(x in q for x in ("location", "city", "where do you live", "based")):
            return str(p.get("current_location", "Pune"))
        if any(x in q for x in ("salary", "ctc", "compensation", "pay")):
            return str(round(p.get("expected_ctc_annual", 500000) / 100000, 1))
        if field_type in ("radio", "select") and options:
            if self._should_answer_yes(q):
                for opt in options:
                    if "yes" in opt.lower():
                        return opt
            if "notice" in q:
                for opt in options:
                    if "30" in opt or "1 month" in opt.lower():
                        return opt
            if "experience" in q or "year" in q:
                for opt in options:
                    if p.get("exp_total", "2") in opt:
                        return opt

        ai = answer_application_question(question or "Application question", options, p)
        if ai:
            if options:
                ai_l = ai.lower()
                for opt in options:
                    if ai_l in opt.lower() or opt.lower() in ai_l:
                        return opt
            return ai

        if field_type in ("radio", "select") and options:
            if self._should_answer_yes(q):
                for opt in options:
                    if "yes" in opt.lower():
                        return opt
            return options[0] if options else "Yes"

        return str(p.get("exp_total", "2"))

    def _should_answer_yes(self, text: str) -> bool:
        t = (text or "").lower()
        if any(x in t for x in ("relocate", "relocation")):
            return bool(self.profile.get("willing_to_relocate"))
        if any(x in t for x in ("authorized", "sponsor", "visa", "legally")):
            return True
        if "no" in t and "yes" not in t:
            return False
        return True

    def _preference_tokens(self, answer_l: str) -> tuple[str, ...]:
        p = self.profile
        tokens = [answer_l, str(p.get("exp_total", "2")), "yes", "30", "1 month"]
        if p.get("willing_to_relocate"):
            tokens.append("yes")
        return tuple(tokens)

    def _element_question_text(self, element: WebElement) -> str:
        parts = []
        eid = element.get_attribute("id") or ""
        if eid:
            try:
                lab = self.driver.find_element(By.CSS_SELECTOR, f"label[for='{eid}']")
                parts.append(lab.text)
            except NoSuchElementException:
                pass
        parts.extend(
            [
                element.get_attribute("aria-label") or "",
                element.get_attribute("placeholder") or "",
            ]
        )
        try:
            group = element.find_element(
                By.XPATH,
                "./ancestor::div[contains(@class, 'fb-dash-form-element')][1]",
            )
            parts.append(group.text)
        except NoSuchElementException:
            pass
        text = " ".join(p for p in parts if p).strip()
        return re.sub(r"\s+", " ", text)[:500]

    def _click_footer(self, modal: WebElement, hints: tuple[str, ...]) -> bool:
        scopes = []
        try:
            scopes.append(modal.find_element(By.CSS_SELECTOR, "footer"))
        except NoSuchElementException:
            scopes.append(modal)

        for scope in scopes:
            buttons = scope.find_elements(By.CSS_SELECTOR, "button")
            ranked = []
            for btn in buttons:
                try:
                    if not btn.is_displayed():
                        continue
                    label = self._button_label(btn).lower()
                    if not btn.is_enabled():
                        continue
                    for i, hint in enumerate(hints):
                        if hint in label:
                            ranked.append((i, btn))
                            break
                except StaleElementReferenceException:
                    continue
            if ranked:
                ranked.sort(key=lambda x: x[0])
                self._click_element(ranked[0][1])
                return True
        return False

    def _button_label(self, element: WebElement) -> str:
        parts = [
            element.text,
            element.get_attribute("aria-label"),
            element.get_attribute("innerText"),
        ]
        return " ".join(p for p in parts if p).strip()

    def _click_element(self, element: WebElement) -> None:
        try:
            self.driver.execute_script(
                "arguments[0].scrollIntoView({block: 'center'});", element
            )
            time.sleep(0.2)
            element.click()
        except Exception:
            self.driver.execute_script("arguments[0].click();", element)
