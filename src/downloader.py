"""Download media files from URLs to local storage."""

import os
import re
import hashlib
import time
import requests
import logging
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
    """Generate a unique filename from URL and metadata.

    Uses tweet_id + short hash of URL to ensure uniqueness across
    multiple media in the same tweet.
    """
    # Extract extension: try path first, then query params (Twitter format),
    # then Content-Type heuristic
    parsed = urlparse(url)
    path_part = parsed.path

    # Try path-based extension
    ext = _ext_from_path(path_part)

    # Try query params: ?format=jpg
    if not ext:
        ext = _ext_from_query(parsed.query)

    # Fallback by type
    if not ext:
        ext = ".jpg" if media_type in ("photo", "image") else ".mp4"

    # Short hash of URL for uniqueness
    url_hash = hashlib.md5(url.encode()).hexdigest()[:8]

    return f"{tweet_id}_{url_hash}{ext}"


def _ext_from_path(path: str) -> str:
    """Extract file extension from URL path."""
    m = re.search(r"\.(\w{3,4})(?:\?|$)", path)
    if m and m.group(1).lower() in ("jpg", "jpeg", "png", "gif", "webp", "mp4"):
        ext = m.group(1).lower()
        return ".jpg" if ext == "jpeg" else f".{ext}"
    return ""


def _ext_from_query(query: str) -> str:
    """Extract format from query params (Twitter uses format=jpg)."""
    m = re.search(r"format=(\w+)", query)
    if m and m.group(1).lower() in ("jpg", "jpeg", "png", "gif", "webp"):
        ext = m.group(1).lower()
        return ".jpg" if ext == "jpeg" else f".{ext}"
    return ""


def download_media(url: str, dest_dir: str, tweet_id: str,
                   media_type: str, retries: int = 3) -> str:
    """Download a media file with retries. Returns the local file path.
    Skips if file already exists.
    """
    ensure_dir(dest_dir)
    fname = filename_from_url(url, tweet_id, media_type)
    filepath = os.path.join(dest_dir, fname)

    # File-level dedup
    if os.path.exists(filepath):
        logger.debug(f"File exists, skipping: {filepath}")
        return filepath

    for attempt in range(1, retries + 1):
        try:
            logger.info(f"Downloading [{attempt}/{retries}]: {url[:80]}...")
            resp = requests.get(url, timeout=(15, 120), stream=True)
            resp.raise_for_status()

            # Correct extension from Content-Type if needed
            ct = resp.headers.get("Content-Type", "").split(";")[0].strip()
            if ct in CONTENT_TYPE_MAP and not filepath.endswith(CONTENT_TYPE_MAP[ct]):
                filepath = filepath.rsplit(".", 1)[0] + CONTENT_TYPE_MAP[ct]

            with open(filepath, "wb") as f:
                for chunk in resp.iter_content(chunk_size=65536):
                    f.write(chunk)

            size_mb = os.path.getsize(filepath) / (1024 * 1024)
            logger.info(f"  -> {os.path.basename(filepath)} ({size_mb:.1f} MB)")
            return filepath

        except requests.exceptions.Timeout:
            logger.warning(f"Timeout on attempt {attempt}/{retries}")
            if attempt == retries:
                raise
            time.sleep(2 ** attempt)

        except requests.exceptions.RequestException as e:
            logger.warning(f"Error on attempt {attempt}/{retries}: {e}")
            if attempt == retries:
                raise
            time.sleep(2 ** attempt)

    raise RuntimeError(f"Failed to download after {retries} attempts: {url}")
