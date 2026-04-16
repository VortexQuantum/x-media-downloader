"""Download media files from URLs to local storage."""

import os
import re
import hashlib
import time
import requests
import logging
from typing import Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

CONTENT_TYPE_MAP = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
    "image/webp": ".webp",
    "video/mp4": ".mp4",
}


def ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)


def filename_from_url(url: str, tweet_id: str, media_type: str) -> str:
    """Generate a unique filename from URL and metadata."""
    parsed = urlparse(url)
    path_part = parsed.path

    ext = _ext_from_path(path_part)
    if not ext:
        ext = _ext_from_query(parsed.query)
    if not ext:
        ext = ".jpg" if media_type in ("photo", "image") else ".mp4"

    url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
    return f"{tweet_id}_{url_hash}{ext}"


def _ext_from_path(path: str) -> str:
    m = re.search(r"\.(\w{3,4})(?:\?|$)", path)
    if m and m.group(1).lower() in ("jpg", "jpeg", "png", "gif", "webp", "mp4"):
        ext = m.group(1).lower()
        return ".jpg" if ext == "jpeg" else f".{ext}"
    return ""


def _ext_from_query(query: str) -> str:
    m = re.search(r"format=(\w+)", query)
    if m and m.group(1).lower() in ("jpg", "jpeg", "png", "gif", "webp"):
        ext = m.group(1).lower()
        return ".jpg" if ext == "jpeg" else f".{ext}"
    return ""


def download_media(url: str, dest_dir: str, tweet_id: str,
                   media_type: str, retries: int = 2) -> Optional[str]:
    """Download a media file. Retries 2 times, skips on failure.
    Returns file path on success, None on failure.
    """
    ensure_dir(dest_dir)
    fname = filename_from_url(url, tweet_id, media_type)
    filepath = os.path.join(dest_dir, fname)

    if os.path.exists(filepath):
        logger.debug(f"  已存在，跳过: {os.path.basename(filepath)}")
        return filepath

    for attempt in range(1, retries + 2):  # 1 initial + 2 retries = 3 total
        try:
            if attempt > 1:
                logger.info(f"  重试 {attempt - 1}/{retries}...")

            resp = requests.get(url, timeout=(15, 120), stream=True)
            resp.raise_for_status()

            ct = resp.headers.get("Content-Type", "").split(";")[0].strip()
            if ct in CONTENT_TYPE_MAP and not filepath.endswith(CONTENT_TYPE_MAP[ct]):
                filepath = filepath.rsplit(".", 1)[0] + CONTENT_TYPE_MAP[ct]

            with open(filepath, "wb") as f:
                for chunk in resp.iter_content(chunk_size=65536):
                    f.write(chunk)

            size_mb = os.path.getsize(filepath) / (1024 * 1024)
            logger.info(f"  ✓ {os.path.basename(filepath)} ({size_mb:.1f} MB)")
            return filepath

        except Exception as e:
            if attempt <= retries:
                logger.warning(f"  失败，{3}s 后重试: {e}")
                time.sleep(3)
            else:
                logger.error(f"  ✗ 重试 {retries} 次后放弃: {e}")
                return None

    return None
