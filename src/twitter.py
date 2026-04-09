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

    gallery-dl outputs a JSON array of mixed entries:
      [NUM, {tweet_metadata}]     -- tweet info (has tweet_id, count)
      [NUM, "URL", {media_meta}]  -- media file URL

    Media entries follow their parent tweet.
    The tweet's 'count' field indicates how many media files it has.

    Returns list of dicts: {tweet_id, media_url, media_type, created_at}
    """
    try:
        entries = json.loads(raw_json)
    except json.JSONDecodeError:
        # Try newline-delimited
        results = []
        for line in raw_json.strip().split("\n"):
            try:
                parsed = json.loads(line)
                results.extend(_extract_from_entries(parsed))
            except json.JSONDecodeError:
                continue
        return results

    return _extract_from_entries(entries)


def _extract_from_entries(entries: list) -> list:
    """Extract media from gallery-dl JSON entries array."""
    results = []
    current_tweet_id = None
    current_date = None
    media_count_expected = 0
    media_count_found = 0

    for entry in entries:
        if not isinstance(entry, list) or len(entry) < 2:
            continue

        second = entry[1]

        # Tweet metadata entry: second element is a dict with tweet_id
        if isinstance(second, dict) and "tweet_id" in second:
            current_tweet_id = str(second["tweet_id"])
            current_date = second.get("date", "")
            media_count_expected = second.get("count", 0)
            media_count_found = 0
            continue

        # Media URL entry: second element is a URL string
        if isinstance(second, str) and (
            "pbs.twimg.com" in second or "video.twimg.com" in second
        ):
            if not current_tweet_id:
                continue

            media_count_found += 1
            media_type = _detect_type_from_url(second)
            # If there's metadata in the third element, use it
            if len(entry) >= 3 and isinstance(entry[2], dict):
                media_type = _detect_type_from_meta(entry[2], second)

            results.append({
                "tweet_id": current_tweet_id,
                "media_url": second,
                "media_type": media_type,
                "created_at": current_date,
            })

            # If we've found all expected media for this tweet, reset
            if media_count_expected > 0 and media_count_found >= media_count_expected:
                # Don't reset current_tweet_id yet — next entry might be
                # a new tweet which will overwrite it
                pass

    return results


def _detect_type_from_url(url: str) -> str:
    """Guess media type from URL."""
    if "video.twimg.com" in url or "amplify_video" in url or url.endswith(".mp4"):
        return "video"
    return "image"


def _detect_type_from_meta(meta: dict, url: str) -> str:
    """Detect media type from gallery-dl metadata."""
    ext = meta.get("extension", "")
    if ext in ("mp4",):
        return "video"
    if ext in ("jpg", "jpeg", "png", "gif", "webp"):
        return "image"
    return _detect_type_from_url(url)
