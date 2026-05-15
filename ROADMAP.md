# Roadmap

本项目的目标是把个人可运行脚本整理成可维护、可复用的本地归档工具。路线图只记录已经明确的方向，不承诺具体交付日期。

## 近期

- 参数化 X/Twitter 用户名，避免代码绑定单个账号。
- 完善敏感信息保护说明，降低误提交 `auth_token`、Telegram token、`config.yaml` 的风险。
- 补齐开源治理文件：`LICENSE`、`CONTRIBUTING.md`、`SECURITY.md`、issue/PR 模板。

## 中期

- 增加 dry-run 模式，只统计将要下载的媒体，不写文件。
- 增加更清晰的错误分类：Cookie 过期、gallery-dl 失败、网络超时、Telegram 通知失败。
- 将常见运行方式整理为示例配置，覆盖 cron、手动全量同步、仅图片/视频过滤等场景。

## 长期

- 评估是否支持更多公开媒体来源。
- 提供更稳定的发布流程，包括 tag、changelog 和可重复安装说明。

