"""
Vercel Cron — runs Naukri auto-apply once per day.

Secured with CRON_SECRET (Vercel sends Authorization: Bearer <CRON_SECRET>).
"""

from __future__ import annotations

import json
import os
import sys
import traceback
from http.server import BaseHTTPRequestHandler

# Project root on Vercel Python runtime
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def _authorized(handler: BaseHTTPRequestHandler) -> bool:
    secret = os.environ.get("CRON_SECRET", "").strip()
    if not secret:
        return True
    auth = handler.headers.get("Authorization", "")
    return auth == f"Bearer {secret}"


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self._run()

    def do_POST(self):
        self._run()

    def _run(self):
        if not _authorized(self):
            self._json(401, {"ok": False, "error": "Unauthorized"})
            return

        try:
            from apply_cycle import run_apply_cycle

            summary = run_apply_cycle()
            code = 200 if summary.get("exit_code", 0) == 0 else 500
            self._json(code, {"ok": code == 200, "summary": summary})
        except Exception as exc:
            self._json(
                500,
                {
                    "ok": False,
                    "error": str(exc),
                    "trace": traceback.format_exc(),
                },
            )

    def _json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        return
