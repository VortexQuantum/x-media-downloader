# 1Password for Open Source 申请核对

本文档用于准备 1Password for Open Source 申请材料，目标是真实呈现项目状态，不通过改写 git 历史或伪造活跃度绕过审核条件。

## 当前判断

- 项目：`VortexQuantum/x-media-downloader`
- 类型：本地运行的 Python CLI 工具
- 用途：下载已登录 X/Twitter 账号 Likes 中的媒体，并发送 Telegram 通知
- 许可：MIT License，仓库根目录已提供 `LICENSE`
- 敏感信息：`twitter-cookies.txt`、`config.yaml`、`.env`、Telegram `bot_token`、Telegram `chat_id`
- 项目年龄：公开 git 历史首个提交为 2026-04-06；截至 2026-06-01 已超过 30 天

## 申请前必须满足

- 仓库公开可访问。
- 根目录存在可被 GitHub 识别的 permissive license 文件。
- 申请人是项目 owner 或 core contributor。
- 1Password 账号必须是 Teams 账号，并且用途是非商业开源维护。
- 项目真实存在至少 30 天；不要通过重写 commit date 伪造项目年龄。
- 项目仍然活跃：近期有维护提交、issue/PR 模板、路线图、测试说明和 release/tag。

## 建议提交材料

- Account URL：1Password Teams 账号 URL
- Project name：`X Media Downloader`
- Repository URL：`https://github.com/VortexQuantum/x-media-downloader`
- License URL：`https://github.com/VortexQuantum/x-media-downloader/blob/main/LICENSE`
- License type：`MIT`
- Core contributors：按真实维护者数量填写
- 申请理由：维护者需要安全保存和共享项目相关 secret，例如 X/Twitter cookie、Telegram bot token/chat_id、发布凭据和恢复信息。

## 当前仓库证据

- `LICENSE`：MIT permissive license。
- `README.md`：面向其他用户的安装、配置、运行、安全和限制说明。
- `CONTRIBUTING.md` / `SECURITY.md`：贡献和安全处理流程。
- `.github/ISSUE_TEMPLATE` / `.github/pull_request_template.md`：公开协作入口。
- `CHANGELOG.md`：发布说明。
- `tests/`：自动化测试覆盖核心模块。

## 不建议做

- 不要改写历史提交时间来制造更早的项目年龄。
- 不要把个人私用脚本包装成不存在的组织级项目。
- 不要在公开 issue、README、截图或日志中暴露 cookie、token、chat_id、数据库内容或下载文件路径中的隐私信息。
