"""Telegram notification sender."""

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
