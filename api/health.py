"""Health check and deployment info."""

from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        payload = {
            "ok": True,
            "service": "auto-apply-naukri",
            "vercel": bool(os.getenv("VERCEL")),
            "cron_schedule": "every 30 minutes",
            "cron_path": "/api/cron/apply",
            "naukri_cookies_set": bool(os.getenv("NAUKRI_COOKIES_JSON")),
            "blob_storage": bool(os.getenv("BLOB_READ_WRITE_TOKEN")),
            "linkedin_on_vercel": False,
            "note": "LinkedIn runs locally with Brave; Naukri runs on Vercel Cron.",
        }
        body = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        return
