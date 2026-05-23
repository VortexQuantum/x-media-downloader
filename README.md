# X Media Downloader

自动下载 X (Twitter) 账号「已喜欢」(Likes) 帖子中的所有图片和视频，去重后存至本地，完成后发送 Telegram 通知。

> 本项目只面向个人归档和备份场景。使用者需要自行确认下载行为符合 X/Twitter 服务条款、内容版权和所在地法律要求。

## 功能特点

- 🖼️ 自动下载已喜欢推文中的图片和视频
- 🔗 基于 gallery-dl + cookie，无需付费 API
- 📦 SQLite 去重（tweet_id + media_url 复合主键）
- 📊 多图推文自动生成唯一文件名：`{tweet_id}_{url_hash}.ext`
- 🔔 下载完成后 Telegram 通知（含成功/失败统计）
- 🎯 分批抓取，支持增量下载
- 🖥️ TUI 交互模式（Rich 进度条，自动检测 TTY）
- ⏰ 无头模式（cron 友好，自动降级为文本日志）
- 🔄 失败自动重试（2次，3秒间隔）

## 快速开始

```bash
# 1. 安装依赖
pip3 install -r requirements.txt

# 2. 导出 Twitter Cookie
python3 setup-cookie.py

# 3. 配置
cp config.example.yaml config.yaml
# 编辑 config.yaml，填入 X 用户名、Telegram Bot Token 和 Chat ID

# 4. 运行
python3 -m src.main          # 单次运行（只抓第一页）
python3 -m src.main --all    # 全量扫描（直到追完所有历史喜欢）
```

## 配置

编辑 `config.yaml`：

| 配置项 | 说明 |
|--------|------|
| `download_dir` | 媒体文件保存目录 |
| `db_path` | SQLite 数据库路径 |
| `telegram.bot_token` | Telegram Bot Token（从 @BotFather 获取） |
| `telegram.chat_id` | 通知发送目标 Chat ID |
| `gallery_dl.cookies_file` | Twitter Cookie 文件路径 |
| `gallery_dl.username` | 目标 X/Twitter 用户名，不要包含 URL |
| `gallery_dl.likes_per_fetch` | 每批抓取数量（默认 100） |

也支持环境变量覆盖：`XM_DOWNLOAD_DIR`、`XM_TELEGRAM_BOT_TOKEN`、`XM_TELEGRAM_CHAT_ID`、`XM_X_USERNAME`。

## 安全提醒

不要把下面内容提交到仓库、公开 Issue、公开 PR、截图或日志里：

- `config.yaml`
- `.env`
- `twitter-cookies.txt`
- `downloads.db`
- Twitter/X cookies 或 `auth_token`
- Telegram bot token 或 `chat_id`

更多说明见 [SECURITY.md](SECURITY.md)。

## 项目结构

```
x-media-downloader/
├── src/
│   ├── main.py         # 入口：分页循环、下载主流程、TUI/CLI 渲染
│   ├── twitter.py      # gallery-dl 调用 & 推文解析
│   ├── downloader.py   # HTTP 下载 & 重试逻辑
│   ├── db.py           # SQLite 去重追踪
│   ├── config.py       # 配置加载（YAML + 环境变量）
│   ├── notifier.py     # Telegram 下载报告推送
│   └── __init__.py
├── tests/              # 单元测试
├── config.yaml         # 配置文件（gitignore）
├── config.example.yaml # 配置示例
├── downloads.db        # SQLite 去重数据库（gitignore）
├── install.sh          # 安装脚本
├── setup-cookie.py     # Cookie 导出助手
├── requirements.txt    # Python 依赖
└── twitter-cookies.txt # Twitter Cookie（Netscape 格式，gitignore）
```

## 数据流

```
gallery-dl CLI → JSON stdout
    ↓ 解析
twitter.parse_liked_tweets()
    ↓ tweet + media 条目
main.run() 分页循环
    ↓ 逐条检查
db.is_downloaded()  → 已下载则跳过
    ↓ 新条目
downloader.download_media()  → 保存到 download_dir/
    ↓ 成功
db.mark_downloaded()
    ↓ 每页完成后
TelegramNotifier.send_download_report()
```

## 测试

```bash
python3 -m pytest tests/
```

## 参与贡献

贡献前请先阅读 [CONTRIBUTING.md](CONTRIBUTING.md)。项目路线见 [ROADMAP.md](ROADMAP.md)。

## 许可证

[MIT](LICENSE)
