#!/usr/bin/env python3
"""X Media Downloader -- fetch liked media from X and download locally."""

import sys
import logging
import time

from src.config import load_config
from src.db import DownloadDB
from src.twitter import (
    fetch_liked_tweets, parse_liked_tweets, count_media_by_type
)
from src.downloader import download_media
from src.notifier import TelegramNotifier

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)


def run(config_path: str = None) -> dict:
    config = load_config(config_path)
    db = DownloadDB(config["db_path"])

    notifier = None
    if config["telegram"]["enabled"]:
        notifier = TelegramNotifier(
            bot_token=config["telegram"]["bot_token"],
            chat_id=config["telegram"]["chat_id"],
        )

    # --- Fetch ---
    offset = db.get_fetch_offset()
    batch_size = config["gallery_dl"]["likes_per_fetch"]

    logger.info(f"Fetching liked tweets {offset+1} to {offset+batch_size}...")
    t0 = time.time()
    raw_json = fetch_liked_tweets(
        cookies_file=config["gallery_dl"]["cookies_file"],
        max_results=batch_size,
        offset=offset,
        gallery_dl_bin=config["gallery_dl"]["bin"],
    )
    elapsed = time.time() - t0

    # --- Parse ---
    media_items = parse_liked_tweets(raw_json)

    # Detailed log
    type_counts = count_media_by_type(media_items)
    unique_tweets = len(set(item["tweet_id"] for item in media_items))

    logger.info(f"Fetched in {elapsed:.1f}s")
    logger.info(f"  Media files found: {len(media_items)}")
    logger.info(f"  From unique tweets: {unique_tweets}")
    logger.info(f"  By type: {type_counts}")

    if not media_items:
        logger.info("No media found in this batch. May be caught up.")
        db.close()
        return {"new_downloads": 0, "total_downloads": db.get_stats()["total"], "items": []}

    # --- Download ---
    new_downloads = []
    skipped = 0
    errors = 0

    for item in media_items:
        tweet_id = item["tweet_id"]
        media_url = item["media_url"]

        if db.is_downloaded(tweet_id, media_url):
            skipped += 1
            continue

        try:
            filepath = download_media(
                media_url,
                config["download_dir"],
                tweet_id,
                item["media_type"],
            )
            db.mark_downloaded(tweet_id, media_url,
                               filepath, item["media_type"])
            new_downloads.append(item)
        except Exception as e:
            errors += 1
            logger.error(f"FAILED {tweet_id}: {e}")

    # --- Update offset ---
    db.set_fetch_offset(offset + batch_size)

    # --- Report ---
    stats = db.get_stats()
    logger.info("-" * 40)
    logger.info(f"Download summary:")
    logger.info(f"  New downloads:  {len(new_downloads)}")
    logger.info(f"  Skipped (dup):  {skipped}")
    logger.info(f"  Errors:         {errors}")
    logger.info(f"  Total in DB:    {stats['total']} files from {stats['unique_tweets']} tweets")
    logger.info(f"  By type:        {stats['by_type']}")

    if notifier and new_downloads:
        by_type = count_media_by_type(new_downloads)
        details = [
            f"{d['tweet_id']}: {d['media_type']}" for d in new_downloads[:10]
        ]
        type_summary = ", ".join(f"{k}: {v}" for k, v in by_type.items())
        notifier.send_download_report(
            new_count=len(new_downloads),
            total_count=stats["total"],
            details=details,
        )

    db.close()
    return {
        "new_downloads": len(new_downloads),
        "total_downloads": stats["total"],
        "items": new_downloads,
    }


if __name__ == "__main__":
    config_path = sys.argv[1] if len(sys.argv) > 1 else None
    run(config_path)
