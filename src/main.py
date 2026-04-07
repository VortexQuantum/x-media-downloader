#!/usr/bin/env python3
"""X Media Downloader -- fetch liked media from X and download locally."""

import sys
import logging

from src.config import load_config
from src.db import DownloadDB
from src.twitter import fetch_liked_tweets, parse_liked_tweets
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

    logger.info("Fetching liked tweets from X...")
    raw_json = fetch_liked_tweets(
        cookies_file=config["gallery_dl"]["cookies_file"],
        max_results=config["gallery_dl"]["likes_per_fetch"],
        gallery_dl_bin=config["gallery_dl"]["bin"],
    )
    media_items = parse_liked_tweets(raw_json)
    logger.info(f"Found {len(media_items)} media items in liked tweets")

    new_downloads = []
    for item in media_items:
        tweet_id = item["tweet_id"]
        if db.is_downloaded(tweet_id):
            continue

        try:
            filepath = download_media(
                item["media_url"],
                config["download_dir"],
                tweet_id,
                item["media_type"],
            )
            db.mark_downloaded(tweet_id, item["media_url"],
                               filepath, item["media_type"])
            new_downloads.append(item)
            logger.info(f"OK Downloaded: {tweet_id} ({item['media_type']})")
        except Exception as e:
            logger.error(f"FAILED {tweet_id}: {e}")

    stats = db.get_stats()
    logger.info(f"Done. New: {len(new_downloads)}, Total: {stats['total']}")

    if notifier and new_downloads:
        details = [f"{d['tweet_id']}: {d['media_type']}" for d in new_downloads]
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
