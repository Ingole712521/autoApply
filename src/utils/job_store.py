"""Persist Excel job log on Vercel via Vercel Blob."""

from __future__ import annotations

import logging
import os
from pathlib import Path

import requests

logger = logging.getLogger(__name__)

BLOB_EXCEL_PATH = os.getenv("BLOB_EXCEL_PATH", "auto-apply/job_applications.xlsx")


def sync_excel_download(local_path: Path) -> bool:
    """Download Excel from blob URL or pathname before a cron run."""
    token = os.getenv("BLOB_READ_WRITE_TOKEN", "").strip()
    blob_url = os.getenv("EXCEL_BLOB_URL", "").strip()

    if blob_url:
        try:
            res = requests.get(blob_url, timeout=60)
            if res.ok:
                local_path.parent.mkdir(parents=True, exist_ok=True)
                local_path.write_bytes(res.content)
                logger.info("Downloaded Excel from EXCEL_BLOB_URL")
                return True
        except Exception as exc:
            logger.warning("Excel download failed: %s", exc)

    if not token:
        return False

    try:
        res = requests.get(
            f"https://blob.vercel-storage.com/{BLOB_EXCEL_PATH}",
            headers={
                "Authorization": f"Bearer {token}",
                "x-api-version": "7",
            },
            timeout=60,
        )
        if res.status_code == 404:
            return False
        res.raise_for_status()
        local_path.parent.mkdir(parents=True, exist_ok=True)
        local_path.write_bytes(res.content)
        logger.info("Downloaded Excel from Vercel Blob")
        return True
    except Exception as exc:
        logger.warning("Blob download failed: %s", exc)
        return False


def sync_excel_upload(local_path: Path) -> str | None:
    """Upload Excel after cron run. Returns public/served URL if available."""
    token = os.getenv("BLOB_READ_WRITE_TOKEN", "").strip()
    if not token or not local_path.exists():
        return None

    try:
        body = local_path.read_bytes()
        res = requests.put(
            f"https://blob.vercel-storage.com/{BLOB_EXCEL_PATH}",
            headers={
                "Authorization": f"Bearer {token}",
                "x-api-version": "7",
                "Content-Type": (
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                ),
            },
            data=body,
            timeout=120,
        )
        res.raise_for_status()
        data = res.json()
        url = data.get("url")
        logger.info("Uploaded Excel to Vercel Blob: %s", url)
        return url
    except Exception as exc:
        logger.warning("Blob upload failed: %s", exc)
        return None
