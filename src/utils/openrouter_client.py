"""Optional OpenRouter LLM answers for LinkedIn application questions."""

from __future__ import annotations

import json
import logging
import os
from typing import Any

import requests
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


def get_openrouter_config() -> dict[str, Any]:
    try:
        from config import OPENROUTER_MODEL, USE_OPENROUTER_FOR_LINKEDIN
    except ImportError:
        OPENROUTER_MODEL = "openai/gpt-oss-120b:free"
        USE_OPENROUTER_FOR_LINKEDIN = True

    return {
        "enabled": USE_OPENROUTER_FOR_LINKEDIN,
        "api_key": os.getenv("OPENROUTER_API_KEY", "").strip(),
        "model": os.getenv("OPENROUTER_MODEL", OPENROUTER_MODEL).strip(),
    }


def answer_application_question(
    question: str,
    options: list[str] | None,
    profile: dict[str, Any],
) -> str | None:
    """
    Ask the LLM for a short answer. Returns None if API unavailable or call fails.
  """
    cfg = get_openrouter_config()
    if not cfg["enabled"] or not cfg["api_key"]:
        return None

    options_text = ""
    if options:
        options_text = "Options:\n" + "\n".join(f"- {o}" for o in options)

    profile_text = (
        f"Years of experience: {profile.get('exp_total', '2')}\n"
        f"Notice period (days): {profile.get('notice_days', 30)}\n"
        f"Willing to relocate: {'Yes' if profile.get('willing_to_relocate') else 'No'}\n"
        f"Current location: {profile.get('current_location', 'Pune')}\n"
        f"Default for yes/no screening questions: Yes\n"
    )

    system = (
        "You fill job application forms. Reply with ONLY the exact answer text to enter "
        "or the exact option label to choose. No explanation."
    )
    user = (
        f"Applicant profile:\n{profile_text}\n\n"
        f"Question:\n{question}\n\n"
        f"{options_text}\n\n"
        "Answer:"
    )

    try:
        res = requests.post(
            OPENROUTER_URL,
            headers={
                "Authorization": f"Bearer {cfg['api_key']}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://github.com/local/auto-apply",
            },
            json={
                "model": cfg["model"],
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "max_tokens": 80,
                "temperature": 0.1,
            },
            timeout=30,
        )
        res.raise_for_status()
        content = res.json()["choices"][0]["message"]["content"].strip()
        return content.strip('"').strip("'")
    except Exception as exc:
        logger.debug("OpenRouter call failed: %s", exc)
        return None
