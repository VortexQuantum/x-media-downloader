# X Media Downloader — Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** 自动下载 X (Twitter) 已喜欢（点赞）的所有图片和视频，去重，定时检查新喜欢，完成后发 Telegram 通知。

**Architecture:** Python CLI 工具，通过 `xurl` CLI 调用 X API v2 获取 liked tweets，解析媒体 URL 后用 `requests` 下载，SQLite 记录已下载内容去重，`cronjob` 定时调度，Telegram Bot API 发通知。

**Tech Stack:** Python 3.9+, xurl CLI, SQLite3, requests, PyYAML, Telegram Bot API

---

## 前置准备（用户手动完成）

### P0: 配置 xurl 认证

**用户自己执行，不可代劳：**

```bash
# 1. 去 https://developer.x.com/en/portal/dashboard 创建 App
#    设置 redirect URI 为 http://localhost:8080/callback
#    记下 Client ID 和 Client Secret

# 2. 注册 App
xurl auth apps add x-downloader --client-id YOUR_CLIENT_ID --client-secret YOUR_CLIENT_SECRET

# 3. OAuth 认证
xurl auth oauth2 --app x-downloader

# 4. 设为默认
xurl auth default x-downloader

# 5. 验证
xurl auth status
xurl whoami
```

### P1: 创建 Telegram Bot

1. 在 Telegram 找 @BotFather
2. 发送 `/newbot`，起名，拿到 Token
3. 给 bot 发一条消息，然后访问：
   ```
   https://api.telegram.org/bot<TOKEN>/getUpdates
   ```
4. 从返回 JSON 中找到 `chat.id`

---

## Phase 1: 项目骨架与配置

### Task 1: 初始化项目结构

**Objective:** 创建项目目录和基础文件

**Files:**
- Create: `requirements.txt`
- Create: `config.example.yaml`
- Create: `.gitignore`
- Create: `src/__init__.py`

**Step 1: 创建 requirements.txt**
```
requests>=2.28.0
pyyaml>=6.0
```

**Step 2: 创建 config.example.yaml**
```yaml
# X Media Downloader Configuration
download_dir: "~/Downloads/x-media"
db_path: "~/.x-media-downloader/downloads.db"

telegram:
  enabled: true
  bot_token: "YOUR_BOT_TOKEN"
  chat_id: "YOUR_CHAT_ID"

xurl:
  likes_per_fetch: 100
  bin: ""
```

**Step 3: 创建 .gitignore**
```
__pycache__/
*.pyc
config.yaml
*.db
.env
```

**Step 4: 创建 src/__init__.py**
```python
__version__ = "0.1.0"
```

**Step 5: 验证**
```bash
ls -la ~/Projects/x-media-downloader/src/
cat ~/Projects/x-media-downloader/requirements.txt
```

**Step 6: Commit**
```bash
cd ~/Projects/x-media-downloader
git init
git add .
git commit -m "chore: init project structure"
```

---

### Task 2: 创建配置加载模块

**Objective:** 读取 config.yaml，支持环境变量覆盖

**Files:**
- Create: `src/config.py`
- Create: `tests/test_config.py`

**Step 1: 写失败测试 — tests/test_config.py**
```python
import os
import tempfile
import pytest


def test_load_config_defaults():
    """config.yaml 不存在时用默认值"""
    from src.config import load_config
    config = load_config("/nonexistent/config.yaml")
    assert config["download_dir"] == os.path.expanduser("~/Downloads/x-media")
    assert config["telegram"]["enabled"] == False


def test_load_config_from_file():
    """读取有效的 config.yaml"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write("""
download_dir: /tmp/x-media-test
telegram:
  enabled: true
  bot_token: "123:abc"
  chat_id: "456"
""")
        tmp_path = f.name

    from src.config import load_config
    config = load_config(tmp_path)
    assert config["download_dir"] == "/tmp/x-media-test"
    assert config["telegram"]["bot_token"] == "123:abc"
    assert config["telegram"]["chat_id"] == "456"
    os.unlink(tmp_path)


def test_config_env_override():
    """环境变量可覆盖配置值"""
    os.environ["XM_TELEGRAM_BOT_TOKEN"] = "env-token"
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write("telegram:\n  bot_token: file-token\n  chat_id: '1'")
        tmp_path = f.name

    from src.config import load_config
    config = load_config(tmp_path)
    assert config["telegram"]["bot_token"] == "env-token"
    os.environ.pop("XM_TELEGRAM_BOT_TOKEN")
    os.unlink(tmp_path)
```

**Step 2: 验证测试失败**
```bash
cd ~/Projects/x-media-downloader
pip install -r requirements.txt pytest
python -m pytest tests/test_config.py -v
# Expected: ALL FAIL - module not found
```

**Step 3: 实现 src/config.py**
```python
import os
import yaml


DEFAULT_CONFIG = {
    "download_dir": "~/Downloads/x-media",
    "db_path": "~/.x-media-downloader/downloads.db",
    "telegram": {
        "enabled": False,
        "bot_token": "",
        "chat_id": "",
    },
    "xurl": {
        "likes_per_fetch": 100,
        "bin": "",
    },
}

ENV_MAP = {
    "XM_DOWNLOAD_DIR": "download_dir",
    "XM_TELEGRAM_BOT_TOKEN": "telegram.bot_token",
    "XM_TELEGRAM_CHAT_ID": "telegram.chat_id",
}


def _deep_set(d: dict, key_path: str, value):
    keys = key_path.split(".")
    for k in keys[:-1]:
        d = d.setdefault(k, {})
    d[keys[-1]] = value


def load_config(config_path: str = None) -> dict:
    if config_path is None:
        config_path = os.path.expanduser("~/.x-media-downloader/config.yaml")

    config = {
        "download_dir": DEFAULT_CONFIG["download_dir"],
        "db_path": DEFAULT_CONFIG["db_path"],
        "telegram": dict(DEFAULT_CONFIG["telegram"]),
        "xurl": dict(DEFAULT_CONFIG["xurl"]),
    }

    if os.path.exists(config_path):
        with open(config_path) as f:
            file_config = yaml.safe_load(f) or {}
        for key in file_config:
            if isinstance(file_config[key], dict) and isinstance(config.get(key), dict):
                config[key].update(file_config[key])
            else:
                config[key] = file_config[key]

    for env_key, config_key in ENV_MAP.items():
        val = os.environ.get(env_key)
        if val:
            _deep_set(config, config_key, val)

    config["download_dir"] = os.path.expanduser(config["download_dir"])
    config["db_path"] = os.path.expanduser(config["db_path"])

    return config
```

**Step 4: 运行测试确认通过**
```bash
python -m pytest tests/test_config.py -v
# Expected: 3 passed
```

**Step 5: Commit**
```bash
git add src/config.py tests/test_config.py requirements.txt
git commit -m "feat: add config loader with env var overrides"
```

---

## Phase 2: 核心功能

### Task 3: 创建数据库模块（SQLite 去重）

**Objective:** 管理已下载媒体的记录，判断是否已下载

**Files:**
- Create: `src/db.py`
- Create: `tests/test_db.py`

**Step 1: 写失败测试 — tests/test_db.py**
```python
import os
import tempfile
import pytest
from src.db import DownloadDB


@pytest.fixture
def db():
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    db = DownloadDB(tmp.name)
    yield db
    db.close()
    os.unlink(tmp.name)


def test_init_creates_table(db):
    rows = db.conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='downloads'"
    ).fetchall()
    assert len(rows) == 1


def test_is_downloaded_false(db):
    assert db.is_downloaded("tweet_999") is False


def test_mark_and_check_downloaded(db):
    db.mark_downloaded("tweet_123", "https://pbs.twimg.com/media/abc.jpg",
                        "/tmp/abc.jpg", "image")
    assert db.is_downloaded("tweet_123") is True


def test_mark_downloaded_idempotent(db):
    db.mark_downloaded("tweet_456", "url", "/tmp/x.jpg", "image")
    db.mark_downloaded("tweet_456", "url", "/tmp/x.jpg", "image")
    assert db.is_downloaded("tweet_456") is True


def test_get_stats(db):
    db.mark_downloaded("t1", "u1", "/t1.jpg", "image")
    db.mark_downloaded("t2", "u2", "/t2.mp4", "video")
    stats = db.get_stats()
    assert stats["total"] == 2
    assert stats["by_type"]["image"] == 1
    assert stats["by_type"]["video"] == 1
```

**Step 2: 验证失败**
```bash
python -m pytest tests/test_db.py -v
# Expected: ALL FAIL
```

**Step 3: 实现 src/db.py**
```python
import sqlite3
import os


class DownloadDB:
    def __init__(self, db_path: str):
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS downloads (
                tweet_id TEXT PRIMARY KEY,
                media_url TEXT NOT NULL,
                file_path TEXT NOT NULL,
                media_type TEXT NOT NULL,
                downloaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_downloaded_at
            ON downloads(downloaded_at)
        """)
        self.conn.commit()

    def is_downloaded(self, tweet_id: str) -> bool:
        row = self.conn.execute(
            "SELECT 1 FROM downloads WHERE tweet_id = ?", (tweet_id,)
        ).fetchone()
        return row is not None

    def mark_downloaded(self, tweet_id: str, media_url: str,
                        file_path: str, media_type: str):
        self.conn.execute(
            """INSERT OR IGNORE INTO downloads
               (tweet_id, media_url, file_path, media_type)
               VALUES (?, ?, ?, ?)""",
            (tweet_id, media_url, file_path, media_type)
        )
        self.conn.commit()

    def get_stats(self) -> dict:
        total = self.conn.execute(
            "SELECT COUNT(*) FROM downloads"
        ).fetchone()[0]
        by_type = {}
        for row in self.conn.execute(
            "SELECT media_type, COUNT(*) as cnt FROM downloads GROUP BY media_type"
        ):
            by_type[row[0]] = row[1]
        return {"total": total, "by_type": by_type}

    def close(self):
        self.conn.close()
```

**Step 4: 运行测试确认**
```bash
python -m pytest tests/test_db.py -v
# Expected: 5 passed
```

**Step 5: Commit**
```bash
git add src/db.py tests/test_db.py
git commit -m "feat: add SQLite download tracker with dedup"
```

---

### Task 4: 创建 Twitter liked tweets 获取模块

**Objective:** 通过 xurl CLI 调用 X API，获取 liked tweets 中的媒体

**Files:**
- Create: `src/twitter.py`
- Create: `tests/test_twitter.py`

**Step 1: 写失败测试 — tests/test_twitter.py**
```python
import json
import pytest
from src.twitter import parse_liked_tweets


SAMPLE_JSON = json.dumps({
    "data": [
        {
            "id": "1234567890",
            "text": "Check this out!",
            "created_at": "2026-05-01T10:00:00.000Z",
            "attachments": {"media_keys": ["3_111"]}
        },
        {
            "id": "0987654321",
            "text": "Just text, no media",
            "created_at": "2026-05-02T12:00:00.000Z"
        }
    ],
    "includes": {
        "media": [
            {
                "media_key": "3_111",
                "type": "photo",
                "url": "https://pbs.twimg.com/media/abc.jpg"
            }
        ]
    }
})


def test_parse_liked_tweets_extracts_media():
    results = parse_liked_tweets(SAMPLE_JSON)
    assert len(results) == 1
    r = results[0]
    assert r["tweet_id"] == "1234567890"
    assert r["media_type"] == "photo"
    assert r["media_url"] == "https://pbs.twimg.com/media/abc.jpg"


def test_parse_liked_tweets_skips_no_media():
    results = parse_liked_tweets(json.dumps({
        "data": [{"id": "999", "text": "no media"}]
    }))
    assert len(results) == 0


def test_parse_liked_tweets_handles_video():
    video_json = json.dumps({
        "data": [{
            "id": "v123",
            "text": "video tweet",
            "attachments": {"media_keys": ["7_222"]}
        }],
        "includes": {
            "media": [{
                "media_key": "7_222",
                "type": "video",
                "variants": [
                    {"bit_rate": 832000, "url": "https://video.twimg.com/low.mp4"},
                    {"bit_rate": 2176000, "url": "https://video.twimg.com/high.mp4"}
                ]
            }]
        }
    })
    results = parse_liked_tweets(video_json)
    assert results[0]["media_type"] == "video"
    assert "high.mp4" in results[0]["media_url"]
```

**Step 2: 验证失败**
```bash
python -m pytest tests/test_twitter.py -v
# Expected: ALL FAIL
```

**Step 3: 实现 src/twitter.py**
```python
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
```

**Step 4: 运行测试确认**
```bash
python -m pytest tests/test_twitter.py -v
# Expected: 3 passed
```

**Step 5: Commit**
```bash
git add src/twitter.py tests/test_twitter.py
git commit -m "feat: add Twitter liked-tweets fetcher with media parsing"
```

---

### Task 5: 创建媒体下载模块

**Objective:** 下载图片和视频到本地，自动创建子目录，处理文件名

**Files:**
- Create: `src/downloader.py`
- Create: `tests/test_downloader.py`

**Step 1: 写失败测试 — tests/test_downloader.py**
```python
import os
import tempfile
import pytest
from unittest.mock import patch
from src.downloader import download_media, ensure_dir


def test_ensure_dir_creates():
    with tempfile.TemporaryDirectory() as tmp:
        new_dir = os.path.join(tmp, "images")
        ensure_dir(new_dir)
        assert os.path.isdir(new_dir)


def test_filename_from_url():
    from src.downloader import filename_from_url
    name = filename_from_url(
        "https://pbs.twimg.com/media/ABC123.jpg?format=jpg&name=large",
        "tweet_456", "image"
    )
    assert "tweet_456" in name
    assert name.endswith(".jpg")


@patch("src.downloader.requests.get")
def test_download_image(mock_get, tmp_path):
    mock_get.return_value.status_code = 200
    mock_get.return_value.content = b"fake-image-data"
    mock_get.return_value.headers = {"Content-Type": "image/jpeg"}

    path = download_media(
        "https://example.com/photo.jpg",
        str(tmp_path), "tweet_1", "photo"
    )
    assert os.path.exists(path)
    assert path.endswith(".jpg")


@patch("src.downloader.requests.get")
def test_download_skip_existing(mock_get, tmp_path):
    path = download_media(
        "https://example.com/photo.jpg",
        str(tmp_path), "tweet_1", "photo"
    )
    path2 = download_media(
        "https://example.com/photo.jpg",
        str(tmp_path), "tweet_1", "photo"
    )
    assert path == path2
    assert mock_get.call_count == 1
```

**Step 2: 验证失败**
```bash
python -m pytest tests/test_downloader.py -v
# Expected: ALL FAIL
```

**Step 3: 实现 src/downloader.py**
```python
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
```

**Step 4: 运行测试确认**
```bash
python -m pytest tests/test_downloader.py -v
# Expected: 4 passed
```

**Step 5: Commit**
```bash
git add src/downloader.py tests/test_downloader.py
git commit -m "feat: add media downloader with file-level dedup"
```

---

### Task 6: 创建 Telegram 通知模块

**Objective:** 下载完成后向 Telegram 发送通知

**Files:**
- Create: `src/notifier.py`
- Create: `tests/test_notifier.py`

**Step 1: 写失败测试 — tests/test_notifier.py**
```python
import pytest
from unittest.mock import patch
from src.notifier import TelegramNotifier


@pytest.fixture
def notifier():
    return TelegramNotifier(bot_token="test-token", chat_id="123")


@patch("src.notifier.requests.post")
def test_send_text(mock_post, notifier):
    mock_post.return_value.status_code = 200
    mock_post.return_value.json.return_value = {"ok": True}
    assert notifier.send_text("Hello world") is True
    mock_post.assert_called_once()


@patch("src.notifier.requests.post")
def test_send_download_report(mock_post, notifier):
    mock_post.return_value.status_code = 200
    mock_post.return_value.json.return_value = {"ok": True}

    result = notifier.send_download_report(
        new_count=5,
        total_count=120,
        details=["tweet_1: photo", "tweet_2: video"]
    )
    assert result is True
    call_args = mock_post.call_args[1]["json"]
    assert "5" in call_args["text"]
    assert "120" in call_args["text"]


@patch("src.notifier.requests.post")
def test_send_text_failure(mock_post, notifier):
    mock_post.return_value.status_code = 400
    assert notifier.send_text("test") is False
```

**Step 2: 验证失败**
```bash
python -m pytest tests/test_notifier.py -v
# Expected: ALL FAIL
```

**Step 3: 实现 src/notifier.py**
```python
import requests
import logging

logger = logging.getLogger(__name__)


class TelegramNotifier:
    def __init__(self, bot_token: str, chat_id: str):
        self.base_url = f"https://api.telegram.org/bot{bot_token}"
        self.chat_id = chat_id

    def _send(self, method: str, payload: dict) -> bool:
        try:
            resp = requests.post(
                f"{self.base_url}/{method}",
                json=payload,
                timeout=15
            )
            data = resp.json()
            if not data.get("ok"):
                logger.error(f"Telegram API error: {data}")
                return False
            return True
        except Exception as e:
            logger.error(f"Telegram send failed: {e}")
            return False

    def send_text(self, text: str) -> bool:
        return self._send("sendMessage", {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": "HTML",
        })

    def send_download_report(self, new_count: int, total_count: int,
                             details: list = None) -> bool:
        lines = [
            "📥 <b>X Media Download Report</b>",
            f"🆕 New downloads: <b>{new_count}</b>",
            f"📊 Total in library: <b>{total_count}</b>",
        ]
        if details:
            lines.append("")
            lines.append("<b>New files:</b>")
            for d in details[:10]:
                lines.append(f"  • {d}")
            if len(details) > 10:
                lines.append(f"  ... and {len(details) - 10} more")

        return self.send_text("\n".join(lines))
```

**Step 4: 运行测试确认**
```bash
python -m pytest tests/test_notifier.py -v
# Expected: 3 passed
```

**Step 5: Commit**
```bash
git add src/notifier.py tests/test_notifier.py
git commit -m "feat: add Telegram notification module"
```

---

## Phase 3: 主流程串联

### Task 7: 创建主程序入口

**Objective:** 串联所有模块，实现完整的一次下载流程

**Files:**
- Create: `src/main.py`

**Step 1: 实现 src/main.py**
```python
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
    xurl_bin = config["xurl"]["bin"] or "xurl"
    raw_json = fetch_liked_tweets(
        max_results=config["xurl"]["likes_per_fetch"],
        xurl_bin=xurl_bin,
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
```

**Step 2: 手动验证**

```bash
cd ~/Projects/x-media-downloader
python -c "from src.config import load_config; print(load_config('/nonexistent.yaml'))"
```

**Step 3: Commit**

```bash
git add src/main.py
git commit -m "feat: add main pipeline -- fetch, download, notify"
```

---

## Phase 4: 安装与自动化

### Task 8: 创建安装脚本

**Objective:** 一键安装依赖和初始化配置

**Files:**
- Create: `install.sh`

**内容:**
```bash
#!/bin/bash
set -e

echo "=== X Media Downloader Installer ==="

python3 --version || { echo "Python 3 required"; exit 1; }
which xurl || { echo "xurl not found. Run: brew install --cask xdevplatform/tap/xurl"; exit 1; }

pip3 install -r requirements.txt
mkdir -p ~/.x-media-downloader

if [ ! -f ~/.x-media-downloader/config.yaml ]; then
    cp config.example.yaml ~/.x-media-downloader/config.yaml
    echo "Created ~/.x-media-downloader/config.yaml -- please edit it!"
fi

echo "Done! Now edit ~/.x-media-downloader/config.yaml."
echo "Then run: python3 -m src.main"
```

```bash
chmod +x install.sh
git add install.sh
git commit -m "chore: add install script"
```

---

### Task 9: 创建 Hermes cronjob 定时任务

**Objective:** 在 Hermes 中创建定时任务，自动检查新喜欢并下载

使用 `cronjob` 工具创建（用户后续执行）：

```
cronjob(
    action='create',
    name='x-media-downloader',
    prompt='Run the X Media Downloader: cd ~/Projects/x-media-downloader && python3 -m src.main ~/.x-media-downloader/config.yaml',
    schedule='every 2h',
    deliver='telegram',
    skills=['xurl'],
    enabled_toolsets=['terminal', 'file'],
    workdir='/Users/z/Projects/x-media-downloader'
)
```

说明:
- `schedule='every 2h'` -- 每 2 小时检查一次
- `deliver='telegram'` -- 结果通知发送到 Telegram
- 可调整频率: `every 30m`, `every 1h`, `0 */3 * * *` 等

---

## 项目文件总览

```
~/Projects/x-media-downloader/
├── install.sh                   # 安装脚本
├── requirements.txt             # requests, pyyaml
├── config.example.yaml          # 配置模板
├── .gitignore
├── docs/plans/
│   └── 2026-05-04-x-media-downloader.md
├── src/
│   ├── __init__.py              # __version__
│   ├── config.py                # 配置加载(YAML + env vars)
│   ├── db.py                    # SQLite 下载记录(去重)
│   ├── twitter.py               # xurl CLI 封装, liked tweets
│   ├── downloader.py            # 媒体文件下载
│   ├── notifier.py              # Telegram 通知
│   └── main.py                  # 主流程串联
└── tests/
    ├── test_config.py
    ├── test_db.py
    ├── test_twitter.py
    ├── test_downloader.py
    └── test_notifier.py
```

---

## 关键设计决策

| 决策 | 理由 |
|------|------|
| 用 xurl 而非直接调 API | 已处理好 OAuth、token refresh，维护成本低 |
| SQLite 去重而非文件系统判断 | 数据库记录精确匹配 tweet_id，不会漏判 |
| 文件级 + 数据库级双重去重 | 防御性设计: 即使 DB 异常，磁盘也不重复下载 |
| Telegram 通知只在有新下载时发送 | 避免无意义通知打扰 |
| cronjob 调度而非 Python scheduler | Hermes 的 cronjob 自带失败重试、日志、平台分发 |

---

## 用户后续配置清单

1. ⬜ 配置 xurl 认证（见 P0）
2. ⬜ 创建 Telegram Bot 拿到 Token + Chat ID（见 P1）
3. ⬜ `cd ~/Projects/x-media-downloader && bash install.sh`
4. ⬜ 编辑 `~/.x-media-downloader/config.yaml`，填入 bot_token 和 chat_id
5. ⬜ 测试: `cd ~/Projects/x-media-downloader && python3 -m src.main`
6. ⬜ 创建定时任务（见 Task 9）
