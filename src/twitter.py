"""Fetch liked tweets with media from X via gallery-dl."""

import json
import subprocess
import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def fetch_liked_tweets(cookies_file: str, username: str, max_results: int = 100,
                       offset: int = 0,
                       gallery_dl_bin: str = "gallery-dl") -> str:
    """Fetch liked tweets as JSON via gallery-dl. Returns raw JSON string.

    If offset=0 (default), fetches all liked tweets (no range limit).
    If offset>0, fetches range offset+1 to offset+max_results for pagination.
    """
    username = username.strip().lstrip("@") if username else ""
    if not username or username == "YOUR_X_USERNAME":
        raise ValueError(
            "X username is required. Set gallery_dl.username in config.yaml "
            "or XM_X_USERNAME in the environment."
        )
    if any(ch.isspace() for ch in username) or "/" in username:
        raise ValueError("X username must be a handle, not a URL or display name.")

    if not os.path.exists(cookies_file):
        raise FileNotFoundError(
            f"Cookies file not found: {cookies_file}\n"
            f"Run: python3 setup-cookie.py"
        )

    base_cmd = [
        "python3", "-m", "gallery_dl",
        "--cookies", cookies_file,
        "-j",
    ]

    if offset >= 0:
        # Always use range for batch fetching
        start = offset + 1
        end = offset + max_results
        base_cmd.extend(["--range", f"{start}-{end}"])
    # else: no --range = fetch all likes

    base_cmd.append(f"https://x.com/{username}/likes")

    logger.info(f"Running: {' '.join(base_cmd)}")
    result = subprocess.run(
        base_cmd,
        capture_output=True, text=True, timeout=300
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
    """Parse gallery-dl JSON output, extract ALL media entries per tweet.

    gallery-dl outputs a JSON array of mixed entries:
      [NUM, {tweet_metadata}]     -- tweet info (has tweet_id, count)
      [NUM, "URL", {media_meta}]  -- media file URL

    Media entries follow their parent tweet. count=N means N media files.
    ALL media files for a tweet are returned (not just the first one).

    Returns list of dicts: {tweet_id, media_url, media_type, created_at}
    """
    try:
        entries = json.loads(raw_json)
    except json.JSONDecodeError:
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
    """Extract ALL media from gallery-dl JSON entries array."""
    results = []
    current_tweet_id = None
    current_date = None

    for entry in entries:
        if not isinstance(entry, list) or len(entry) < 2:
            continue

        second = entry[1]

        # Tweet metadata entry
        if isinstance(second, dict) and "tweet_id" in second:
            current_tweet_id = str(second["tweet_id"])
            current_date = second.get("date", "")
            continue

        # Media URL entry
        if isinstance(second, str) and (
            "pbs.twimg.com" in second or "video.twimg.com" in second
        ):
            if not current_tweet_id:
                continue

            media_type = _detect_type_from_url(second)
            if len(entry) >= 3 and isinstance(entry[2], dict):
                media_type = _detect_type_from_meta(entry[2], second)

            results.append({
                "tweet_id": current_tweet_id,
                "media_url": second,
                "media_type": media_type,
                "created_at": current_date,
            })

    return results


def _detect_type_from_url(url: str) -> str:
    if "video.twimg.com" in url or "amplify_video" in url or url.endswith(".mp4"):
        return "video"
    return "image"


def _detect_type_from_meta(meta: dict, url: str) -> str:
    ext = meta.get("extension", "")
    if ext in ("mp4",):
        return "video"
    if ext in ("jpg", "jpeg", "png", "gif", "webp"):
        return "image"
    return _detect_type_from_url(url)


def count_media_by_type(items: list) -> dict:
    """Count media items by type for logging."""
    counts = {}
    for item in items:
        t = item.get("media_type", "unknown")
        counts[t] = counts.get(t, 0) + 1
    return counts
