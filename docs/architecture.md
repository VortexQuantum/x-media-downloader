# X Media Downloader — 架构文档

---

## 系统概览

X Media Downloader 是一个 **Python CLI 工具**，用于自动化地将 X (Twitter) 上某个账号「已喜欢」的所有帖子中的图片和视频下载到本地。

核心设计原则：
- **无服务端**：纯本地运行，无需自建服务器
- **幂等性**：多次运行结果一致，SQLite 保证去重
- **无侵入认证**：复用浏览器已登录的 Cookie，不依赖官方 API Key

---

## 技术栈

| 层次 | 技术 |
|------|------|
| 语言 | Python 3.9+ |
| X 数据获取 | [gallery-dl](https://github.com/mikf/gallery-dl)（子进程调用）|
| HTTP 下载 | `requests` |
| 持久化 | SQLite3（标准库）|
| 配置 | PyYAML + 环境变量覆盖 |
| 通知 | Telegram Bot API |
| TUI | [Rich](https://github.com/Textualize/rich) |
| 测试 | pytest |

---

## 目录结构

```
x-media-downloader/
├── AGENTS.md                  # AI 助手快速参考
├── docs/
│   └── architecture.md        # 本文档
├── src/
│   ├── __init__.py            # 版本号
│   ├── main.py                # 入口；主循环；TUI
│   ├── config.py              # 配置加载
│   ├── twitter.py             # gallery-dl 封装；JSON 解析
│   ├── downloader.py          # 媒体文件下载
│   ├── db.py                  # SQLite 去重数据库
│   └── notifier.py            # Telegram 通知
├── tests/                     # pytest 单元测试（各模块对应）
├── config.yaml                # 用户配置（gitignore）
├── config.example.yaml        # 配置模板
├── twitter-cookies.txt        # Netscape Cookie（gitignore）
├── setup-cookie.py            # 一次性 Cookie 配置向导
├── install.sh                 # 安装脚本
└── requirements.txt
```

---

## 架构图

```
┌─────────────────────────────────────────────────────┐
│                   python3 -m src.main                │
│                                                     │
│  ┌─────────────┐    ┌──────────────┐               │
│  │  config.py  │    │   db.py      │               │
│  │  load_config│    │  DownloadDB  │               │
│  └──────┬──────┘    └──────┬───────┘               │
│         │                  │                        │
│  ┌──────▼──────────────────▼───────────────────┐   │
│  │                  main.py                     │   │
│  │              run() 主循环                    │   │
│  │  ┌─────────────┐      ┌──────────────────┐  │   │
│  │  │ twitter.py  │      │  downloader.py   │  │   │
│  │  │fetch_liked_ │──────│  download_media()│  │   │
│  │  │tweets()     │      └──────────────────┘  │   │
│  │  │parse_liked_ │                            │   │
│  │  │tweets()     │      ┌──────────────────┐  │   │
│  │  └─────────────┘      │  notifier.py     │  │   │
│  │                       │TelegramNotifier  │  │   │
│  └───────────────────────┴──────────────────┘  │   │
└─────────────────────────────────────────────────────┘
         │                        │
         ▼                        ▼
   gallery-dl CLI           Telegram Bot API
   (subprocess)             (HTTP POST)
         │
         ▼
   X (Twitter) 服务器
```

---

## 核心模块详解

### `main.py` — 主循环

**入口函数：** `run(config_path, all_pages)`

分页循环逻辑：

```
while True:
    1. fetch_liked_tweets(offset)        # 调用 gallery-dl 抓取第 N 页
    2. parse_liked_tweets(raw_json)      # 解析媒体列表
    3. db.are_all_downloaded(tweet_ids)  # 整页已下载 → break
    4. 下载本页所有媒体（TUI 或 simple 模式）
    5. 发 Telegram 通知
    6. offset += batch_size
    7. if not all_pages: break           # 单页模式退出
```

**TUI / 非 TUI 切换：** `_is_tty()` 检测 stdout 是否为终端。非 TTY（如 cron）自动用 `_run_simple()` 输出纯文本，避免 Rich 控制字符污染日志。

---

### `twitter.py` — gallery-dl 封装

**`fetch_liked_tweets()`**  
通过 `subprocess.run()` 调用 `gallery-dl -j --cookies <file> --range <start>-<end> <url>`，捕获 stdout 返回 JSON 字符串。

**`parse_liked_tweets()` / `_extract_from_entries()`**  
gallery-dl `-j` 输出的 JSON 是**混合类型数组**：

```
[序号, {tweet元数据}]          → 推文行，含 tweet_id / date
[序号, "媒体URL", {媒体元数据}] → 媒体行，含图片/视频 URL
```

解析器维护 `current_tweet_id` 状态变量，将媒体行关联到最近一条推文，输出：

```python
[
  {"tweet_id": "...", "media_url": "...", "media_type": "image|video", "created_at": "..."},
  ...
]
```

**媒体类型检测优先级：**  
元数据 extension 字段 → URL 路径中的扩展名 → URL 域名（`video.twimg.com` → video）

---

### `downloader.py` — 文件下载

**`download_media(url, dest_dir, tweet_id, media_type, retries, progress_cb)`**

- 文件名由 `filename_from_url()` 生成：`{tweet_id}_{url_md5[:8]}.{ext}`
- 文件已存在则直接返回路径（本地去重，补充 DB 去重）
- 图片：短超时（30s），非流式读取
- 视频：长超时（10s connect / 60s read），流式分块写入
- 重试 2 次，最终失败返回 `None`
- 每次下载使用独立 `requests.Session`（规避连接复用问题）

---

### `db.py` — 去重数据库

**`DownloadDB`** 封装 SQLite，主要方法：

| 方法 | 说明 |
|------|------|
| `is_downloaded(tweet_id, media_url)` | 单条媒体是否已下载 |
| `are_all_downloaded(tweet_ids)` | 批量检查整页是否已全部下载（用于快速跳页） |
| `mark_downloaded(tweet_id, media_url, file_path, media_type)` | 记录下载成功 |
| `get_stats()` | 返回 `{total, by_type, unique_tweets}` |

主键为 `(tweet_id, media_url)`，`INSERT OR IGNORE` 保证幂等。

---

### `config.py` — 配置加载

优先级（低→高）：

```
DEFAULT_CONFIG（硬编码默认值）
    ↓ 覆盖
config.yaml（项目根目录）
    ↓ 覆盖
环境变量 XM_*
```

路径处理：
- `download_dir`：展开 `~`
- `db_path`：若为相对路径，相对于 config.yaml 所在目录解析
- `gallery_dl.cookies_file`：同上

---

### `notifier.py` — Telegram 通知

`TelegramNotifier.send_download_report()` 向 Telegram 发送 HTML 格式报告，包含新增数量、媒体库总计、失败数和前 10 条新文件详情。仅在 `new_downloads` 或 `failed` 非空时触发。

---

## 认证机制

gallery-dl 使用 **Netscape 格式 Cookie 文件**（`twitter-cookies.txt`）模拟已登录浏览器访问 X，无需 X Developer API Key。

Cookie 文件由 `setup-cookie.py` 引导用户从 Chrome DevTools 中复制 `auth_token` 后生成：

```
# Netscape HTTP Cookie File
.x.com	TRUE	/	TRUE	0	auth_token	<token_value>
```

---

## 运行模式

| 模式 | 命令 | 适用场景 |
|------|------|----------|
| 单页模式（默认）| `python3 -m src.main` | cron 定期增量同步 |
| 全量模式 | `python3 -m src.main --all` | 首次运行，下载全部历史 |

**推荐 cron 配置：**

```cron
0 * * * * cd /path/to/x-media-downloader && python3 -m src.main >> cron.log 2>&1
```

---

## 错误处理策略

| 场景 | 处理方式 |
|------|----------|
| Cookie 过期（401）| 抛出 `RuntimeError`，提示重新运行 `setup-cookie.py` |
| Cookie 文件不存在 | 抛出 `FileNotFoundError` |
| gallery-dl 超时 | `subprocess.run(timeout=300)` 后抛出 `TimeoutExpired` |
| 单个媒体下载失败 | 重试 2 次，仍失败记入 `failed` 列表，跳过继续 |
| Telegram 发送失败 | 记录 `logger.error`，不中断主流程 |

---

## 扩展指引

**支持新的媒体类型**  
→ 在 `downloader.py` 的 `CONTENT_TYPE_MAP` 和 `_ext_from_path()` 中添加扩展名映射。

**参数化目标账号**  
→ 修改 `twitter.py` 中 `fetch_liked_tweets()` 的硬编码 URL `https://x.com/zhengrenzhe/likes`，改为接受 `username` 参数。

**新增配置项**  
→ 同时更新 `config.py` 的 `DEFAULT_CONFIG` 字典和 `config.example.yaml`。

**数据库 Schema 变更**  
→ `DownloadDB._init_schema()` 使用 `CREATE TABLE IF NOT EXISTS`，不会自动迁移；需手动添加 `ALTER TABLE` 语句或版本升级逻辑。
