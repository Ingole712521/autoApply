"""
One-time LinkedIn sign-in for job auto-apply.

Opens Brave so you can log in. After login, saves session cookies to
linkedin_cookies.json for use by react_devops_auto_apply.py.

Usage:
    python linkedin_login.py
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from src.utils.browser import browser_label, create_webdriver

LOGIN_URL = "https://www.linkedin.com/login"
OUTPUT_FILE = Path("linkedin_cookies.json")
TIMEOUT_SEC = 300


def main() -> int:
    label = browser_label()
    print("=" * 60)
    print(" LinkedIn Sign-In")
    print("=" * 60)
    print()
    print(f"1. {label} will open the LinkedIn login page")
    print("2. Complete login (email/password or Google)")
    print("3. Cookies save automatically when login succeeds")
    print()
    print(f"Waiting up to {TIMEOUT_SEC // 60} minutes...")
    print()

    driver = create_webdriver()

    try:
        driver.get(LOGIN_URL)
        start = time.time()

        while time.time() - start < TIMEOUT_SEC:
            cookies = driver.get_cookies()
            li_at = next((c for c in cookies if c.get("name") == "li_at"), None)

            if li_at:
                OUTPUT_FILE.write_text(json.dumps(cookies, indent=2), encoding="utf-8")
                print(f"Login successful. Saved {len(cookies)} cookies to {OUTPUT_FILE}")
                print()
                print("Next step:")
                print("  python react_devops_auto_apply.py")
                return 0

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
