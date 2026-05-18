#!/usr/bin/env python3
"""X Media Downloader -- 自动下载 X (Twitter) 已喜欢的所有媒体"""

import sys
import time
import logging
import os
import warnings

# Suppress urllib3 OpenSSL warning on macOS
warnings.filterwarnings("ignore", module="urllib3")

from rich.console import Console
from rich.progress import (
    Progress, BarColumn, TextColumn, TimeRemainingColumn,
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
    return sys.stdout.isatty()


def run(config_path: str = None, all_pages: bool = False) -> dict:
    config = load_config(config_path)
    db = DownloadDB(config["db_path"])
    use_tui = _is_tty()
    batch_size = config["gallery_dl"]["likes_per_fetch"]

    notifier = None
    if config["telegram"]["enabled"]:
        notifier = TelegramNotifier(
            bot_token=config["telegram"]["bot_token"],
            chat_id=config["telegram"]["chat_id"],
        )

    total_new, total_skipped, total_failed = 0, 0, []
    page = 0
    offset = 0  # Always start from position 1 (newest first)

    while True:
        page += 1

        if use_tui:
            console.print()
            console.print(Panel.fit(
                f"[bold]📥 第 {page} 页[/bold]  抓取第 {offset+1} ~ {offset+batch_size} 条喜欢",
                border_style="cyan"
            ))

        t0 = time.time()
        raw_json = fetch_liked_tweets(
            cookies_file=config["gallery_dl"]["cookies_file"],
            username=config["gallery_dl"]["username"],
            max_results=batch_size, offset=offset,
            gallery_dl_bin=config["gallery_dl"]["bin"],
        )
        elapsed = time.time() - t0

        media_items = parse_liked_tweets(raw_json)
        type_counts = count_media_by_type(media_items)

        tweet_groups = {}
        for item in media_items:
            tweet_groups.setdefault(item["tweet_id"], []).append(item)

        unique_tweets = len(tweet_groups)
        total_media = len(media_items)

        if use_tui:
            type_str = " | ".join(f"{k}: {v}" for k, v in sorted(type_counts.items()))
            console.print(f"⏱  抓取 {elapsed:.1f}s | 📊 {unique_tweets} 条推文, {total_media} 个媒体 | {type_str}")
            console.print()

        # Stop: no media at all (past end of likes)
        if not total_media:
            if use_tui:
                console.print("[yellow]已追到最新，没有更多喜欢了。[/yellow]")
            break

        # Check if entire page is already downloaded
        tweet_ids = list(tweet_groups.keys())
        if db.are_all_downloaded(tweet_ids):
            if use_tui:
                if page == 1:
                    console.print("[green]没有新喜欢，已是最新。[/green]")
                else:
                    console.print(f"[green]第 {page} 页全部已下载，停止扫描。[/green]")
            break

        new_downloads, skipped, failed = [], 0, []

        if use_tui:
            _run_tui(tweet_groups, unique_tweets, config, db,
                     new_downloads, failed, skipped)
        else:
            _run_simple(tweet_groups, config, db,
                        new_downloads, failed, skipped)

        offset += batch_size
        total_new += len(new_downloads)
        total_skipped += skipped
        total_failed.extend(failed)

        stats = db.get_stats()
        _print_summary(len(new_downloads), skipped, len(failed), stats, use_tui)

        if notifier and (new_downloads or failed):
            by_type = count_media_by_type(new_downloads)
            details = [f"{d['tweet_id']}: {d['media_type']}" for d in new_downloads[:10]]
            notifier.send_download_report(
                new_count=len(new_downloads),
                total_count=stats["total"],
                failed_count=len(failed),
                details=details if new_downloads else None,
            )

        # Stop conditions
        if not all_pages:
            # Single-page mode (cron): stop after one page
            break

    # End of loop — exhausted all pages or stopped

    stats = db.get_stats()
    db.close()

    if all_pages and use_tui and page > 1:
        console.print()
        console.print(Panel.fit(
            f"[bold green]🎉 全部完成！[/bold green]\n"
            f"共 {page} 页 | 新增 {total_new} 个 | 跳过 {total_skipped} 个 | 失败 {len(total_failed)} 个\n"
            f"媒体库总计: {stats['total']} 个文件 / {stats['unique_tweets']} 条推文",
            border_style="green"
        ))

    return {
        "new_downloads": total_new,
        "total": stats["total"],
        "failed": total_failed,
        "pages": page,
    }


def _run_tui(tweet_groups, unique_tweets, config, db,
             new_downloads, failed_items, skipped):
    progress = Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(bar_width=30),
        MofNCompleteColumn(),
        TimeRemainingColumn(),
        console=console,
        expand=False,
    )

    tweet_task = progress.add_task("[cyan]推文进度", total=unique_tweets)
    media_task = progress.add_task("[yellow]  当前媒体", total=1, visible=False)
    dl_task = progress.add_task("[green]  下载", total=100, visible=False)

    with Live(progress, console=console, refresh_per_second=10):
        for tweet_idx, (tweet_id, items) in enumerate(tweet_groups.items(), 1):
            n_media = len(items)

            progress.update(tweet_task,
                            description=f"[cyan]推文 [{tweet_idx}/{unique_tweets}] {tweet_id[:10]}...")
            progress.update(media_task, visible=True, total=n_media, completed=0,
                            description=f"[yellow]  媒体 ({n_media}个)")

            for media_idx, item in enumerate(items, 1):
                media_url = item["media_url"]

                if db.is_downloaded(tweet_id, media_url):
                    skipped += 1
                    progress.update(media_task, advance=1)
                    continue

                progress.update(dl_task, visible=True, completed=0,
                                description=f"[green]  ↓ {item['media_type']} {media_idx}/{n_media}")

                def make_cb(task):
                    def cb(bytes_done, total_bytes):
                        if total_bytes > 0:
                            progress.update(task, completed=bytes_done, total=total_bytes)
                    return cb

                filepath = download_media(
                    media_url, config["download_dir"],
                    tweet_id, item["media_type"],
                    retries=2, progress_cb=make_cb(dl_task),
                )

                if filepath:
                    db.mark_downloaded(tweet_id, media_url, filepath, item["media_type"])
                    new_downloads.append(item)
                else:
                    failed_items.append(item)

                progress.update(media_task, advance=1)
                progress.update(dl_task, visible=False)

            progress.update(media_task, visible=False)
            progress.update(tweet_task, advance=1,
                            description=f"[cyan]推文 [{tweet_idx}/{unique_tweets}]")

    console.print()


def _run_simple(tweet_groups, config, db, new_downloads, failed_items, skipped):
    for tweet_id, items in tweet_groups.items():
        for item in items:
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
    if use_tui:
        table = Table(box=box.ROUNDED, show_header=False, border_style="green")
        table.add_column(style="bold"); table.add_column()
        table.add_row("🆕 新增下载", f"[bold green]{new_count}[/bold green] 个")
        table.add_row("⏭️  跳过", f"{skipped} 个（已下载过）")
        if failed:
            table.add_row("⚠️  失败", f"[bold red]{failed}[/bold red] 个")
        table.add_row("📊 媒体库", f"[bold]{stats['total']}[/bold] 个 / {stats['unique_tweets']} 条推文")
        if stats['by_type']:
            ts = " | ".join(f"{k}: {v}" for k, v in sorted(stats['by_type'].items()))
            table.add_row("📁 类型", ts)
        console.print(table)
    else:
        lg = logging.getLogger("xdownloader")
        logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(message)s", datefmt="%H:%M:%S")
        lg.info(f"新增: {new_count} | 跳过: {skipped} | 失败: {failed} | 总计: {stats['total']}")


if __name__ == "__main__":
    all_pages = "--all" in sys.argv
    config_path = next((a for a in sys.argv[1:] if not a.startswith("--")), None)
    run(config_path, all_pages=all_pages)
