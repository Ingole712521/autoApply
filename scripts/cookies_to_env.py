"""
Print NAUKRI_COOKIES_JSON one-liner for Vercel environment variables.

Usage:
    python scripts/cookies_to_env.py
    python scripts/cookies_to_env.py path/to/naukri_cookies.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT = ROOT / "naukri_cookies.json"


def main() -> int:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT
    if not path.exists():
        print(f"File not found: {path}", file=sys.stderr)
        print("Run: python google_login.py", file=sys.stderr)
        return 1

    data = json.loads(path.read_text(encoding="utf-8"))
    one_line = json.dumps(data, separators=(",", ":"))
    print("Paste this as NAUKRI_COOKIES_JSON in Vercel → Settings → Environment Variables:\n")
    print(one_line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
