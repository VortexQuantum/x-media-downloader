"""Download media files from URLs to local storage."""

import os
import re
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
    parsed = urlparse(url)
    path_part = parsed.path
    ext_match = re.search(r"\.(\w+)(?:\?|$)", path_part)
    if ext_match and ext_match.group(1) in ("jpg", "jpeg", "png", "gif", "webp", "mp4"):
        ext = f".{ext_match.group(1)}"
    else:
        ext = ".jpg" if media_type == "photo" else ".mp4"
    return f"{tweet_id}{ext}"


def download_media(url: str, dest_dir: str, tweet_id: str,
                   media_type: str) -> str:
    ensure_dir(dest_dir)
    fname = filename_from_url(url, tweet_id, media_type)
    filepath = os.path.join(dest_dir, fname)

    if os.path.exists(filepath):
        logger.info(f"File exists, skipping: {filepath}")
        return filepath

    logger.info(f"Downloading: {url} -> {filepath}")
    resp = requests.get(url, timeout=120, stream=True)
    resp.raise_for_status()

    ct = resp.headers.get("Content-Type", "").split(";")[0].strip()
    if ct in CONTENT_TYPE_MAP and not filepath.endswith(CONTENT_TYPE_MAP[ct]):
        filepath = filepath.rsplit(".", 1)[0] + CONTENT_TYPE_MAP[ct]

    with open(filepath, "wb") as f:
        for chunk in resp.iter_content(chunk_size=8192):
            f.write(chunk)

    logger.info(f"Downloaded: {filepath} ({os.path.getsize(filepath)} bytes)")
    return filepath
