"""Launch Selenium with Brave (preferred) or Chrome on Windows."""

from __future__ import annotations

import os
import tempfile
import uuid
from pathlib import Path

from selenium import webdriver
from selenium.common.exceptions import SessionNotCreatedException, WebDriverException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service

try:
    from config import BRAVE_BINARY_PATH, USE_BRAVE_BROWSER
except ImportError:
    USE_BRAVE_BROWSER = True
    BRAVE_BINARY_PATH = ""


def find_brave_binary() -> str | None:
    if BRAVE_BINARY_PATH:
        path = Path(BRAVE_BINARY_PATH)
        if path.is_file():
            return str(path)

    env_path = os.getenv("BRAVE_BINARY_PATH", "").strip()
    if env_path and Path(env_path).is_file():
        return env_path

    candidates = [
        Path(r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe"),
        Path(r"C:\Program Files (x86)\BraveSoftware\Brave-Browser\Application\brave.exe"),
        Path.home() / "AppData/Local/BraveSoftware/Brave-Browser/Application/brave.exe",
    ]
    for path in candidates:
        if path.is_file():
            return str(path)
    return None


def find_chrome_binary() -> str | None:
    env_path = os.getenv("CHROME_BINARY_PATH", "").strip()
    if env_path and Path(env_path).is_file():
        return env_path

    candidates = [
        Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
        Path(r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
        Path.home() / "AppData/Local/Google/Chrome/Application/chrome.exe",
    ]
    for path in candidates:
        if path.is_file():
            return str(path)
    return None


def _make_profile_dir() -> Path:
    """Separate profile so Selenium works while Brave/Chrome is already open."""
    profile_dir = Path(tempfile.gettempdir()) / f"autoapply-browser-{uuid.uuid4().hex[:8]}"
    profile_dir.mkdir(parents=True, exist_ok=True)
    return profile_dir


def _build_options(*, headless: bool, binary: str | None, profile_dir: Path) -> Options:
    options = Options()
    if binary:
        options.binary_location = binary

    if headless:
        options.add_argument("--headless=new")

    options.add_argument("--start-maximized")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])

    # Windows stability — avoids "DevToolsActivePort file doesn't exist" crashes.
    options.add_argument(f"--user-data-dir={profile_dir}")
    options.add_argument("--no-first-run")
    options.add_argument("--no-default-browser-check")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--remote-debugging-port=0")

    return options


def _start_driver(options: Options, label: str) -> webdriver.Chrome:
    driver = webdriver.Chrome(service=Service(), options=options)
    driver._auto_apply_browser = label  # noqa: SLF001 — logging only
    return driver


def create_webdriver(*, headless: bool = False) -> webdriver.Chrome:
    """
    Create a WebDriver. Tries Brave when enabled, then falls back to Chrome.

    Uses an isolated temp profile so login still works if Brave/Chrome is
  already running in another window.
    """
    profile_dir = _make_profile_dir()
    errors: list[str] = []
    last_exc: Exception | None = None

    if USE_BRAVE_BROWSER:
        brave = find_brave_binary()
        if brave:
            try:
                options = _build_options(headless=headless, binary=brave, profile_dir=profile_dir)
                return _start_driver(options, "Brave")
            except (SessionNotCreatedException, WebDriverException) as exc:
                last_exc = exc
                errors.append(f"Brave: {exc.msg if hasattr(exc, 'msg') else exc}")
                print(
                    "Warning: Brave failed to start for automation. "
                    "Falling back to Chrome. (Close Brave and retry if you prefer Brave.)"
                )
        else:
            print(
                "Warning: Brave not found. Install Brave or set BRAVE_BINARY_PATH. "
                "Falling back to Chrome."
            )

    chrome = find_chrome_binary()
    if chrome:
        try:
            options = _build_options(headless=headless, binary=chrome, profile_dir=profile_dir)
            return _start_driver(options, "Chrome")
        except (SessionNotCreatedException, WebDriverException) as exc:
            last_exc = exc
            errors.append(f"Chrome: {exc.msg if hasattr(exc, 'msg') else exc}")

    # Last resort: let Selenium Manager pick the default Chrome install.
    try:
        options = _build_options(headless=headless, binary=None, profile_dir=profile_dir)
        return _start_driver(options, "Chrome")
    except (SessionNotCreatedException, WebDriverException) as exc:
        errors.append(f"default Chrome: {exc.msg if hasattr(exc, 'msg') else exc}")
        last_exc = exc

    detail = "\n".join(errors) if errors else "No Chromium browser could be started."
    raise RuntimeError(
        "Could not start a browser for automation.\n"
        f"{detail}\n\n"
        "Try:\n"
        "  1. Close all Brave/Chrome windows and run again\n"
        "  2. Install Google Chrome if missing\n"
        "  3. Set USE_BRAVE_BROWSER = False in config.py to force Chrome"
    ) from last_exc


def browser_label() -> str:
    if USE_BRAVE_BROWSER and find_brave_binary():
        return "Brave (falls back to Chrome if Brave fails)"
    if find_chrome_binary():
        return "Chrome"
    return "Chrome"
