#!/usr/bin/env python3
"""X Media Downloader -- 自动下载 X (Twitter) 已喜欢的所有媒体"""

import sys
import time
import logging

from src.config import load_config
from src.db import DownloadDB
from src.twitter import (
    fetch_liked_tweets, parse_liked_tweets, count_media_by_type
)
from src.downloader import download_media
from src.notifier import TelegramNotifier

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(message)s",
    datefmt="%H:%M:%S"
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

    # --- 抓取 ---
    offset = db.get_fetch_offset()
    batch_size = config["gallery_dl"]["likes_per_fetch"]
    batch_num = (offset // batch_size) + 1

    logger.info("=" * 50)
    logger.info(f"📥 第 {batch_num} 页: 抓取第 {offset + 1} ~ {offset + batch_size} 条喜欢")
    t0 = time.time()

    raw_json = fetch_liked_tweets(
        cookies_file=config["gallery_dl"]["cookies_file"],
        max_results=batch_size,
        offset=offset,
        gallery_dl_bin=config["gallery_dl"]["bin"],
    )

    elapsed = time.time() - t0

    # --- 解析 ---
    media_items = parse_liked_tweets(raw_json)
    type_counts = count_media_by_type(media_items)
    unique_tweets = len(set(item["tweet_id"] for item in media_items))

    logger.info(f"⏱  抓取耗时 {elapsed:.1f}s")
    logger.info(f"📊 共 {unique_tweets} 条推文, {len(media_items)} 个媒体文件")
    type_str = " | ".join(f"{k}: {v}" for k, v in sorted(type_counts.items()))
    logger.info(f"   └─ {type_str}")

    if not media_items:
        logger.info("没有找到新媒体，可能已追到最新。")
        db.close()
        return {"new_downloads": 0, "total": 0, "failed": [], "items": []}

    # --- 按推文分组显示进度 ---
    tweet_groups = {}
    for item in media_items:
        tid = item["tweet_id"]
        tweet_groups.setdefault(tid, []).append(item)

    # --- 下载 ---
    new_downloads = []
    skipped = 0
    failed_items = []

    for tweet_idx, (tweet_id, items) in enumerate(tweet_groups.items(), 1):
        n_media = len(items)
        new_for_tweet = 0

        logger.info(f"")
        logger.info(f"  [{tweet_idx}/{unique_tweets}] 推文 {tweet_id} — {n_media} 个媒体")

        for media_idx, item in enumerate(items, 1):
            media_url = item["media_url"]

            if db.is_downloaded(tweet_id, media_url):
                skipped += 1
                continue

            logger.info(f"    下载 {media_idx}/{n_media}: {item['media_type']}")

            filepath = download_media(
                media_url,
                config["download_dir"],
                tweet_id,
                item["media_type"],
                retries=2,
            )

            if filepath:
                db.mark_downloaded(tweet_id, media_url,
                                   filepath, item["media_type"])
                new_downloads.append(item)
                new_for_tweet += 1
            else:
                failed_items.append(item)

        if new_for_tweet > 0:
            logger.info(f"    ✓ 本条新增 {new_for_tweet} 个文件")

    # --- 更新偏移 ---
    db.set_fetch_offset(offset + batch_size)

    # --- 汇总报告 ---
    stats = db.get_stats()

    logger.info("")
    logger.info("=" * 40)
    logger.info(f"📊 本次下载汇总:")
    logger.info(f"   新增:   {len(new_downloads)} 个文件")
    logger.info(f"   跳过:   {skipped} 个（已下载过）")
    logger.info(f"   失败:   {len(failed_items)} 个")
    logger.info(f"   总计库: {stats['total']} 个文件 / {stats['unique_tweets']} 条推文")
    if stats['by_type']:
        ts = " | ".join(f"{k}: {v}" for k, v in sorted(stats['by_type'].items()))
        logger.info(f"   类型:   {ts}")

    # --- Telegram 通知 ---
    if notifier:
        if new_downloads or failed_items:
            by_type = count_media_by_type(new_downloads)
            details = [
                f"{d['tweet_id']}: {d['media_type']}"
                for d in new_downloads[:10]
            ]
            notifier.send_download_report(
                new_count=len(new_downloads),
                total_count=stats["total"],
                failed_count=len(failed_items),
                details=details if new_downloads else None,
            )
        elif skipped > 0 and len(media_items) > 0:
            # 全部跳过，不发通知（避免骚扰）
            logger.info("全部已下载，不发送通知。")

    db.close()
    return {
        "new_downloads": len(new_downloads),
        "total": stats["total"],
        "failed": failed_items,
        "items": new_downloads,
    }


if __name__ == "__main__":
    config_path = sys.argv[1] if len(sys.argv) > 1 else None
    run(config_path)
