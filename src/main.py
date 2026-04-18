#!/usr/bin/env python3
"""X Media Downloader -- 自动下载 X (Twitter) 已喜欢的所有媒体"""

import sys
import time
import logging
import os

from rich.console import Console
from rich.progress import (
    Progress, BarColumn, TextColumn, TimeRemainingColumn,
    TransferSpeedColumn, DownloadColumn, TaskProgressColumn,
    SpinnerColumn, MofNCompleteColumn,
)
from rich.table import Table
from rich.live import Live
from rich.panel import Panel
from rich import box

from src.config import load_config
from src.db import DownloadDB
from src.twitter import (
    fetch_liked_tweets, parse_liked_tweets, count_media_by_type
)
from src.downloader import download_media
from src.notifier import TelegramNotifier

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

console = Console()


def _is_tty() -> bool:
    """Check if running in a real terminal (not cron/pipe)."""
    return sys.stdout.isatty()


def run(config_path: str = None) -> dict:
    config = load_config(config_path)
    db = DownloadDB(config["db_path"])
    use_tui = _is_tty()

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

    if use_tui:
        console.print()
        console.print(Panel.fit(
            f"[bold]📥 第 {batch_num} 页[/bold] — 抓取第 {offset + 1} ~ {offset + batch_size} 条喜欢",
            border_style="cyan"
        ))

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

    tweet_groups = {}
    for item in media_items:
        tid = item["tweet_id"]
        tweet_groups.setdefault(tid, []).append(item)

    unique_tweets = len(tweet_groups)
    total_media = len(media_items)

    if use_tui:
        type_str = " | ".join(f"{k}: {v}" for k, v in sorted(type_counts.items()))
        console.print(f"⏱  抓取 {elapsed:.1f}s | 📊 {unique_tweets} 条推文, {total_media} 个媒体 | {type_str}")
        console.print()

    if not total_media:
        if use_tui:
            console.print("[yellow]没有找到新媒体，可能已追到最新。[/yellow]")
        db.close()
        return {"new_downloads": 0, "total": 0, "failed": [], "items": []}

    # --- 下载 ---
    new_downloads = []
    skipped = 0
    failed_items = []

    if use_tui:
        _run_tui(tweet_groups, unique_tweets, config, db,
                 new_downloads, failed_items, skipped)
    else:
        _run_simple(tweet_groups, unique_tweets, config, db,
                    new_downloads, failed_items, skipped)

    # --- 更新偏移 ---
    db.set_fetch_offset(offset + batch_size)

    # --- 报告 ---
    stats = db.get_stats()
    _print_summary(len(new_downloads), skipped, len(failed_items), stats, use_tui)

    # --- Telegram ---
    if notifier and (new_downloads or failed_items):
        by_type = count_media_by_type(new_downloads)
        details = [f"{d['tweet_id']}: {d['media_type']}" for d in new_downloads[:10]]
        notifier.send_download_report(
            new_count=len(new_downloads),
            total_count=stats["total"],
            failed_count=len(failed_items),
            details=details if new_downloads else None,
        )

    db.close()
    return {
        "new_downloads": len(new_downloads),
        "total": stats["total"],
        "failed": failed_items,
        "items": new_downloads,
    }


def _run_tui(tweet_groups, unique_tweets, config, db,
             new_downloads, failed_items, skipped):
    """TUI mode with rich progress bars."""

    progress = Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(bar_width=30),
        TaskProgressColumn(),
        MofNCompleteColumn(),
        TimeRemainingColumn(),
        console=console,
        expand=False,
    )

    # Main tweet progress
    tweet_task = progress.add_task(
        "[cyan]推文进度", total=unique_tweets
    )
    # Per-tweet media progress
    media_task = progress.add_task(
        "[yellow]  当前推文媒体", total=1, visible=False
    )
    # Download speed bar
    dl_task = progress.add_task(
        "[green]  下载速度", total=100, visible=False
    )

    with Live(progress, console=console, refresh_per_second=10):
        for tweet_idx, (tweet_id, items) in enumerate(tweet_groups.items(), 1):
            n_media = len(items)
            new_for_tweet = 0

            # Update tweet progress description
            progress.update(tweet_task,
                            description=f"[cyan]推文 [{tweet_idx}/{unique_tweets}] {tweet_id[:10]}...")

            # Show per-tweet media bar
            progress.update(media_task, visible=True, total=n_media, completed=0,
                            description=f"[yellow]  媒体 ({len(items)}个)")

            for media_idx, item in enumerate(items, 1):
                media_url = item["media_url"]

                if db.is_downloaded(tweet_id, media_url):
                    skipped += 1
                    progress.update(media_task, advance=1)
                    continue

                # Show download bar
                progress.update(dl_task, visible=True, completed=0,
                                description=f"[green]  ↓ {item['media_type']}")

                # Simulate download progress (we can't easily get real-time progress from requests)
                # Use a callback that updates the bar
                def dl_callback(bytes_done, total_bytes):
                    if total_bytes > 0:
                        progress.update(dl_task, completed=bytes_done, total=total_bytes)

                filepath = download_media(
                    media_url,
                    config["download_dir"],
                    tweet_id,
                    item["media_type"],
                    retries=2,
                    progress_cb=dl_callback,
                )

                if filepath:
                    db.mark_downloaded(tweet_id, media_url, filepath, item["media_type"])
                    new_downloads.append(item)
                    new_for_tweet += 1
                    progress.update(media_task, advance=1)
                else:
                    failed_items.append(item)
                    progress.update(media_task, advance=1)

                progress.update(dl_task, visible=False)

            progress.update(media_task, visible=False)
            progress.update(tweet_task, advance=1,
                            description=f"[cyan]推文 [{tweet_idx}/{unique_tweets}]")

    # Final summary below the progress bars
    console.print()


def _run_simple(tweet_groups, unique_tweets, config, db,
                new_downloads, failed_items, skipped):
    """Simple log mode (for cron/non-TTY)."""

    for tweet_idx, (tweet_id, items) in enumerate(tweet_groups.items(), 1):
        n_media = len(items)

        for media_idx, item in enumerate(items, 1):
            media_url = item["media_url"]

            if db.is_downloaded(tweet_id, media_url):
                skipped += 1
                continue

            filepath = download_media(
                media_url, config["download_dir"],
                tweet_id, item["media_type"], retries=2,
            )
            if filepath:
                db.mark_downloaded(tweet_id, media_url, filepath, item["media_type"])
                new_downloads.append(item)
            else:
                failed_items.append(item)


def _print_summary(new_count, skipped, failed, stats, use_tui):
    """Print download summary."""
    if use_tui:
        table = Table(box=box.ROUNDED, show_header=False, border_style="green")
        table.add_column(style="bold")
        table.add_column()

        table.add_row("🆕 新增下载", f"[bold green]{new_count}[/bold green] 个文件")
        table.add_row("⏭️  跳过", f"{skipped} 个（已下载过）")
        if failed:
            table.add_row("⚠️  失败", f"[bold red]{failed}[/bold red] 个")
        table.add_row("📊 媒体库总计",
                      f"[bold]{stats['total']}[/bold] 个文件 / {stats['unique_tweets']} 条推文")
        if stats['by_type']:
            ts = " | ".join(f"{k}: {v}" for k, v in sorted(stats['by_type'].items()))
            table.add_row("📁 类型", ts)

        console.print(table)
    else:
        import logging as _log
        _log.basicConfig(level=_log.INFO, format="%(asctime)s  %(message)s", datefmt="%H:%M:%S")
        lg = _log.getLogger("xdownloader")
        lg.info(f"新增: {new_count} | 跳过: {skipped} | 失败: {failed} | 总计: {stats['total']}")


if __name__ == "__main__":
    config_path = sys.argv[1] if len(sys.argv) > 1 else None
    run(config_path)
