"""Normalize company names for duplicate detection across runs."""

from __future__ import annotations

import re


def normalize_company(name: str) -> str:
    if not name:
        return ""
    cleaned = re.sub(r"[^\w\s]", "", name.lower())
    return re.sub(r"\s+", "", cleaned).strip()
