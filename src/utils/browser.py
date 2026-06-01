"""Launch Selenium with Brave (Chromium) on Windows."""

from __future__ import annotations

import os
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
try:
    from config import BRAVE_BINARY_PATH, USE_BRAVE_BROWSER
except ImportError:
    USE_BRAVE_BROWSER = True
    BRAVE_BINARY_PATH = ""


def find_brave_binary() -> str | None:
    """Return path to brave.exe if installed."""
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


def create_webdriver(*, headless: bool = False) -> webdriver.Chrome:
    """
    Create a WebDriver. Uses Brave when USE_BRAVE_BROWSER is True and brave.exe exists.
    Requires ChromeDriver (compatible with your Brave/Chromium version).
    """
    options = Options()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--start-maximized")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])

    browser_name = "Chrome"
    if USE_BRAVE_BROWSER:
        brave = find_brave_binary()
        if brave:
            options.binary_location = brave
            browser_name = "Brave"
        else:
            print(
                "Warning: Brave not found. Install Brave or set BRAVE_BINARY_PATH in config.py. "
                "Falling back to Chrome."
            )

    driver = webdriver.Chrome(options=options)
    driver._auto_apply_browser = browser_name  # noqa: SLF001 — for logging only
    return driver


def browser_label() -> str:
    if USE_BRAVE_BROWSER and find_brave_binary():
        return "Brave"
    return "Chrome"
