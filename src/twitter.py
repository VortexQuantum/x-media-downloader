"""Fetch liked tweets with media from X via gallery-dl."""

import json
import subprocess
import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def fetch_liked_tweets(cookies_file: str, max_results: int = 100,
                       gallery_dl_bin: str = "gallery-dl") -> str:
    """Fetch liked tweets as JSON via gallery-dl. Returns raw JSON string."""
    if not os.path.exists(cookies_file):
        raise FileNotFoundError(
            f"Cookies file not found: {cookies_file}\n"
            f"Run: python3 setup-cookie.py"
        )

    # Prefer 'python3 -m gallery_dl' so PATH doesn't matter
    if gallery_dl_bin in ("gallery-dl", ""):
        cmd = [
            "python3", "-m", "gallery_dl",
            "--cookies", cookies_file,
            "-j",
            "--range", f"1-{max_results}",
            "https://x.com/zhengrenzhe/likes",
        ]
    else:
        cmd = [
            gallery_dl_bin,
            "--cookies", cookies_file,
            "-j",
            "--range", f"1-{max_results}",
            "https://x.com/zhengrenzhe/likes",
        ]

    logger.info(f"Running: {' '.join(cmd)}")
    result = subprocess.run(
        cmd,
        capture_output=True, text=True, timeout=120
    )

    if result.returncode != 0:
        stderr = result.stderr.strip()
        if "401" in stderr or "Unauthorized" in stderr:
            raise RuntimeError(
                "Twitter auth failed. Cookies may have expired.\n"
                "Re-export cookies: python3 setup-cookie.py"
            )
        raise RuntimeError(f"gallery-dl failed: {stderr}")

    return result.stdout


def parse_liked_tweets(raw_json: str) -> list:
    """Parse gallery-dl JSON output, extract media entries.

    gallery-dl outputs newline-delimited JSON arrays:
    [["twitter", num, {...tweet_data...}], ...]

    Returns list of dicts: {tweet_id, media_url, media_type, created_at}
    """
    results = []

    for line in raw_json.strip().split("\n"):
        line = line.strip()
        if not line:
            continue

        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue

        # gallery-dl format: ["twitter", num, {tweet_data}]
        if not isinstance(entry, list) or len(entry) < 3:
            continue

        tweet_data = entry[2]
        if not isinstance(tweet_data, dict):
            continue

        tweet_id = str(tweet_data.get("tweet_id", ""))
        created_at = tweet_data.get("date", "")

        entities = tweet_data.get("entities", {})
        media_list = entities.get("media", [])

        if not media_list:
            # Some tweets embed external media (pbs.twimg.com URLs in content)
            # We skip those without media entities for now
            continue

        for media in media_list:
            media_url = _extract_best_url(media)
            if not media_url:
                continue

            results.append({
                "tweet_id": tweet_id,
                "media_url": media_url,
                "media_type": _normalize_type(media.get("type", "photo")),
                "created_at": created_at,
            })

    return results


def _extract_best_url(media: dict) -> Optional[str]:
    """Get best download URL from a media entity."""
    mtype = media.get("type", "photo")

    if mtype in ("photo", "image"):
        # gallery-dl provides 'media_url' or 'url'
        url = media.get("media_url") or media.get("url")
        if url:
            # Use :orig suffix for full resolution
            return url + ":orig"
        return None

    if mtype in ("video", "animated_gif"):
        variants = media.get("video_info", {}).get("variants", [])
        mp4_variants = [
            v for v in variants
            if v.get("content_type") == "video/mp4"
        ]
        if not mp4_variants:
            mp4_variants = [v for v in variants if "bitrate" in v]
        if not mp4_variants:
            return None
        best = max(mp4_variants, key=lambda v: v.get("bitrate", 0))
        return best.get("url")

    return None


def _normalize_type(media_type: str) -> str:
    """Normalize gallery-dl media types to our types."""
    if media_type in ("photo", "image"):
        return "image"
    if media_type in ("video", "animated_gif"):
        return "video"
    return "image"
