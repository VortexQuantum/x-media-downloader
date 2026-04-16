"""Telegram 通知发送模块"""

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
                logger.error(f"Telegram API 错误: {data}")
                return False
            return True
        except Exception as e:
            logger.error(f"Telegram 发送失败: {e}")
            return False

    def send_text(self, text: str) -> bool:
        return self._send("sendMessage", {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": "HTML",
        })

    def send_download_report(self, new_count: int, total_count: int,
                             failed_count: int = 0,
                             details: list = None) -> bool:
        """发送格式化的下载报告"""
        lines = [
            "📥 <b>X 媒体下载报告</b>",
            f"🆕 新增下载: <b>{new_count}</b>",
            f"📊 媒体库总计: <b>{total_count}</b>",
        ]
        if failed_count > 0:
            lines.append(f"⚠️ 下载失败: <b>{failed_count}</b>")

        if details:
            lines.append("")
            lines.append("<b>新增文件:</b>")
            for d in details[:10]:
                lines.append(f"  • {d}")
            if len(details) > 10:
                lines.append(f"  ... 还有 {len(details) - 10} 个")

        return self.send_text("\n".join(lines))
