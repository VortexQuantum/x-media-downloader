"""Fetch liked tweets with media from X via xurl CLI."""

import json
import subprocess
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def _get_user_id(xurl_bin: str = "xurl") -> str:
    result = subprocess.run(
        [xurl_bin, "whoami"],
        capture_output=True, text=True, timeout=30
    )
    data = json.loads(result.stdout)
    return data["data"]["id"]


def fetch_liked_tweets(max_results: int = 100,
                       pagination_token: Optional[str] = None,
                       xurl_bin: str = "xurl") -> str:
    user_id = _get_user_id(xurl_bin)

    url = (
        f"/2/users/{user_id}/liked_tweets"
        f"?max_results={max_results}"
        f"&expansions=attachments.media_keys"
        f"&media.fields=media_key,type,url,preview_image_url,variants"
        f"&tweet.fields=attachments,created_at"
    )
    if pagination_token:
        url += f"&pagination_token={pagination_token}"

    result = subprocess.run(
        [xurl_bin, url],
        capture_output=True, text=True, timeout=60
    )
    if result.returncode != 0:
        raise RuntimeError(f"xurl failed: {result.stderr}")

    return result.stdout


def parse_liked_tweets(raw_json: str) -> list:
    data = json.loads(raw_json)
    tweets = data.get("data", [])
    media_map = {}

    for m in data.get("includes", {}).get("media", []):
        media_map[m["media_key"]] = m

    results = []
    for tweet in tweets:
        attachments = tweet.get("attachments", {})
        media_keys = attachments.get("media_keys", [])
        if not media_keys:
            continue

        for mk in media_keys:
            media = media_map.get(mk)
            if not media:
                continue

            media_url = _extract_best_url(media)
            if not media_url:
                continue

            results.append({
                "tweet_id": tweet["id"],
                "media_url": media_url,
                "media_type": media.get("type", "photo"),
                "created_at": tweet.get("created_at", ""),
            })

    return results


def _extract_best_url(media: dict) -> Optional[str]:
    mtype = media.get("type", "photo")

    if mtype == "photo":
        return media.get("url") or media.get("preview_image_url")

    if mtype in ("video", "animated_gif"):
        variants = media.get("variants", [])
        mp4_variants = [
            v for v in variants
            if v.get("content_type") == "video/mp4"
        ]
        if not mp4_variants:
            mp4_variants = [v for v in variants if "bit_rate" in v]
        if not mp4_variants:
            return None
        best = max(mp4_variants, key=lambda v: v.get("bit_rate", 0))
        return best.get("url")

    return None
