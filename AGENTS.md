# AGENTS.md — X Media Downloader

> 本文件为 AI 编程助手提供项目上下文，便于快速理解代码库后进行精准修改。

---

## 项目一句话描述

自动下载 X (Twitter) 账号「已喜欢」帖子中的所有图片和视频，去重后存至本地，完成后发 Telegram 通知。

---

## 快速运行

```bash
# 安装依赖
pip3 install -r requirements.txt

# 首次：导出 Twitter Cookie
python3 setup-cookie.py

# 配置（复制后填入 Telegram Token / chat_id）
cp config.example.yaml config.yaml

# 单次运行（只抓第一页，适合 cron）
python3 -m src.main

# 全量扫描（直到追上所有历史喜欢）
python3 -m src.main --all
```

**测试：**

```bash
pytest tests/
```

---

## 模块职责（src/）

| 文件 | 职责 | 关键符号 |
|------|------|----------|
| `main.py` | 程序入口；分页抓取→下载→通知的主循环；TUI 渲染 | `run()`, `_run_tui()`, `_run_simple()` |
| `twitter.py` | 调用 `gallery-dl` 获取喜欢列表的 JSON；解析媒体条目 | `fetch_liked_tweets()`, `parse_liked_tweets()`, `_extract_from_entries()` |
| `downloader.py` | HTTP 下载单个媒体文件；文件名生成；重试逻辑 | `download_media()`, `filename_from_url()` |
| `db.py` | SQLite 去重追踪；记录已下载记录；统计 | `DownloadDB`, `is_downloaded()`, `are_all_downloaded()`, `mark_downloaded()` |
| `config.py` | 加载 `config.yaml`；环境变量覆盖；路径展开 | `load_config()`, `DEFAULT_CONFIG`, `ENV_MAP` |
| `notifier.py` | Telegram Bot API 发送下载报告 | `TelegramNotifier`, `send_download_report()` |

---

## 数据流

```
gallery-dl CLI (subprocess)
    ↓ JSON (stdout)
twitter.parse_liked_tweets()
    ↓ list[{tweet_id, media_url, media_type, created_at}]
main.run() 分页循环
    ↓ 每条媒体
db.is_downloaded()  → 已下载则跳过
    ↓ 新条目
downloader.download_media()  → 保存到 download_dir/
    ↓ 成功
db.mark_downloaded()
    ↓ 一页完成
TelegramNotifier.send_download_report()
```

---

## 配置键速查

`config.yaml` / `config.example.yaml` 中的顶层键：

| 键 | 类型 | 说明 |
|----|------|------|
| `download_dir` | string | 媒体保存目录，支持 `~` |
| `db_path` | string | SQLite 文件路径（相对项目根） |
| `telegram.enabled` | bool | 是否开启通知 |
| `telegram.bot_token` | string | Telegram Bot Token |
| `telegram.chat_id` | string | Telegram Chat ID |
| `gallery_dl.cookies_file` | string | Netscape 格式 cookie 文件路径 |
| `gallery_dl.bin` | string | gallery-dl 可执行路径（默认 `gallery-dl`） |
| `gallery_dl.likes_per_fetch` | int | 每页抓取数量（默认 100） |

**环境变量覆盖（优先级最高）：**
- `XM_DOWNLOAD_DIR` → `download_dir`
- `XM_TELEGRAM_BOT_TOKEN` → `telegram.bot_token`
- `XM_TELEGRAM_CHAT_ID` → `telegram.chat_id`

---

## SQLite Schema

```sql
CREATE TABLE downloads (
    tweet_id      TEXT NOT NULL,
    media_url     TEXT NOT NULL,
    file_path     TEXT NOT NULL,
    media_type    TEXT NOT NULL,          -- "image" | "video"
    downloaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (tweet_id, media_url)
);
```

---

## gallery-dl JSON 格式（关键知识）

`fetch_liked_tweets()` 通过 `gallery-dl -j` 获得的 JSON 是一个混合数组：

```json
[
  [NUM, {"tweet_id": 123, "date": "...", ...}],   // 推文元数据行
  [NUM, "https://pbs.twimg.com/.../photo.jpg", {...}],  // 媒体 URL 行
  [NUM, "https://video.twimg.com/...mp4", {...}],       // 视频 URL 行
  ...
]
```

`_extract_from_entries()` 在解析时维护 `current_tweet_id` 状态机，将媒体行归属到前一条推文。

---

## 分页逻辑

- `offset=0` → gallery-dl `--range 1-{batch_size}`
- `offset=N` → gallery-dl `--range {N+1}-{N+batch_size}`
- 终止条件：① 本页无媒体（到达列表末尾）② 本页 tweet 全部已下载（缓存命中）③ 单页模式（默认 cron）

---

## 命令行参数

`python3 -m src.main` 接受：

| 参数 | 说明 |
|------|------|
| `--all` | 全量模式，翻页直到追上历史（否则只抓一页后退出） |
| `--config PATH` | 指定配置文件路径 |

---

## 测试文件对应关系

| 测试文件 | 被测模块 |
|----------|----------|
| `tests/test_config.py` | `src/config.py` |
| `tests/test_db.py` | `src/db.py` |
| `tests/test_downloader.py` | `src/downloader.py` |
| `tests/test_notifier.py` | `src/notifier.py` |
| `tests/test_twitter.py` | `src/twitter.py` |

---

## 修改时的注意事项

- **新增配置项**：同时更新 `config.py` 的 `DEFAULT_CONFIG` 和 `config.example.yaml`。
- **修改 DB Schema**：`DownloadDB._init_schema()` 使用 `CREATE TABLE IF NOT EXISTS`，需自行处理迁移。
- **gallery-dl 调用**：`fetch_liked_tweets()` 中 URL 硬编码为 `https://x.com/zhengrenzhe/likes`，如需参数化请修改此处及调用方。
- **TUI / 非 TUI**：`main.py` 通过 `_is_tty()` 判断，非 TTY 环境（如 cron）自动切换为简单文本输出，避免 Rich 控制字符污染日志。
- **不要在 `download_media()` 中引入会话复用**：注释已说明每次下载使用独立 Session 是为了规避连接复用问题。
