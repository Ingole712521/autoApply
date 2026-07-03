from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
from selenium.webdriver.common.by import By

from src.utils.browser import browser_label, create_webdriver

load_dotenv()

LOGIN_URL = "https://www.workatastartup.com/companies"
SUCCESS_HINTS = ("workatastartup.com/companies", "workatastartup.com/dashboard", "workatastartup.com/profile")
OUTPUT_FILE = Path(os.getenv("WORKATASTARTUP_COOKIES_FILE", "workatastartup_cookies.json"))
TIMEOUT_SEC = 300


def _try_autofill(driver, email: str, password: str) -> None:
    """Best-effort fill of the YC account login form. Silent if fields aren't present."""
    if not email:
        return
    try:
        email_el = None
        for sel in ("input[type='email']", "input[name='email']", "input[name='username']", "#ycid-input"):
            els = driver.find_elements(By.CSS_SELECTOR, sel)
            if els and els[0].is_displayed():
                email_el = els[0]
                break
        if email_el and not (email_el.get_attribute("value") or "").strip():
            email_el.clear()
            email_el.send_keys(email)
    except Exception:
        pass
    try:
        pwd_el = None
        for sel in ("input[type='password']", "input[name='password']", "#password-input"):
            els = driver.find_elements(By.CSS_SELECTOR, sel)
            if els and els[0].is_displayed():
                pwd_el = els[0]
                break
        if pwd_el and password and not (pwd_el.get_attribute("value") or "").strip():
            pwd_el.clear()
            pwd_el.send_keys(password)
    except Exception:
        pass


def _logged_in(driver) -> bool:
    url = (driver.current_url or "").lower()
    if "account.ycombinator.com" in url or "/sign_in" in url or "/login" in url:
        return False
    return any(hint in url for hint in SUCCESS_HINTS)


def main() -> int:
    label = browser_label()
    email = os.getenv("WORKATASTARTUP_EMAIL", "").strip()
    password = os.getenv("WORKATASTARTUP_PASSWORD", "").strip()

    print("=" * 60)
    print(" Work at a Startup (Y Combinator) Sign-In")
    print("=" * 60)
    print()
    print(f"1. {label} opens the login page (via account.ycombinator.com)")
    if email:
        print(f"2. Credentials for {email} are auto-filled from .env")
        print("3. Click the sign-in button (finish any captcha / 2FA)")
    else:
        print("2. Complete login manually")
    print("4. Cookies save automatically once you reach the companies page")
    print()
    print(f"Waiting up to {TIMEOUT_SEC // 60} minutes...")
    print()

    driver = create_webdriver()
    try:
        driver.get(LOGIN_URL)
        time.sleep(3)
        _try_autofill(driver, email, password)

        start = time.time()
        autofill_retries = 0
        while time.time() - start < TIMEOUT_SEC:
            if _logged_in(driver):
                cookies = driver.get_cookies()
                OUTPUT_FILE.write_text(json.dumps(cookies, indent=2), encoding="utf-8")
                print(f"Login successful. Saved {len(cookies)} cookies to {OUTPUT_FILE}")
                print()
                print("Next step:")
                print("  python react_devops_auto_apply.py")
                return 0

            # Re-attempt autofill if we land back on the YC account form.
            if autofill_retries < 3 and "account.ycombinator.com" in (driver.current_url or "").lower():
                _try_autofill(driver, email, password)
                autofill_retries += 1

            elapsed = int(time.time() - start)
            if elapsed > 0 and elapsed % 15 == 0:
                print(f"  Still waiting... ({elapsed}s) — finish sign-in in {label}")
            time.sleep(2)

        print("Timed out waiting for login. Try again within 5 minutes.")
        return 1
    finally:
        driver.quit()


if __name__ == "__main__":
    sys.exit(main())
