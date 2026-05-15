# 贡献指南

感谢你为 `x-media-downloader` 做贡献。提交前先确认改动直接解决问题本身，避免只做表面补丁。

## 本地开发

项目基于 Python 3，建议先创建虚拟环境后再安装依赖。

```bash
python3 -m venv .venv
source .venv/bin/activate
pip3 install -r requirements.txt
```

如需完整运行流程，可按下面步骤准备本地环境：

```bash
python3 setup-cookie.py
cp config.example.yaml config.yaml
python3 -m src.main
```

全量扫描模式：

```bash
python3 -m src.main --all
```

## 测试

提交前至少运行项目现有测试：

```bash
pytest tests/
```

如果你的改动影响配置解析、下载逻辑、数据库去重、通知发送或 `gallery-dl` 解析，请补充或更新对应测试。

## Issue

提 Issue 时请尽量提供下面信息，方便定位根因：

- 预期行为与实际行为
- 复现步骤
- 运行命令
- 关键日志或报错
- 使用的 Python 版本、操作系统、`gallery-dl` 版本

涉及凭据、cookies、token、数据库内容或其他敏感信息时，不要公开贴出原文。

## Pull Request

提交 PR 时请保持范围收敛，一次只解决一个明确问题。PR 描述建议包含：

- 改动目的
- 根因说明
- 解决方式
- 验证方法
- 可能影响的模块

如果改动涉及行为变化，请同步更新测试和相关文档。

## 不要提交的文件

以下内容属于本地配置、敏感数据或运行产物，不应提交到仓库：

- `config.yaml`
- `.env`
- `twitter-cookies.txt`
- `downloads.db`
- 下载目录中的媒体文件
- 任何包含 Twitter/X cookies、`auth_token`、Telegram bot token、`chat_id` 的文件

如果你不确定某个文件是否适合提交，先默认不要提交，再确认其是否包含本地状态、凭据或用户数据。
