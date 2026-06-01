# Changelog

本项目遵循简单的人工维护 changelog。日期使用北京时间。

## v0.1.0 - 2026-06-01

### Added

- 基于 `gallery-dl` 和 Cookie 的 X/Twitter Likes 媒体抓取流程。
- SQLite 去重，主键为 `tweet_id + media_url`。
- 图片、视频下载和失败重试。
- TUI 进度条与非 TTY 文本日志模式。
- Telegram 下载报告通知。
- `--all` 全量扫描模式。
- `gallery_dl.username` 和 `XM_X_USERNAME`，避免硬编码单一账号。
- MIT `LICENSE`、`CONTRIBUTING.md`、`SECURITY.md`、`ROADMAP.md`、GitHub issue/PR 模板。

### Verified

- `python3 -m pytest tests/` 覆盖配置、解析、下载、数据库、通知和主流程。
