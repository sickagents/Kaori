"""Telegram notifications for Kaori LP agent.

Sends position updates, deploy alerts, and daily summaries.
"""

import os
import json
from pathlib import Path
import requests


class TelegramNotifier:
    """Send notifications via Telegram bot."""

    def __init__(self, config: dict):
        tg = config.get("telegram", {})
        self.enabled = tg.get("enabled", False)
        self.token = tg.get("bot_token", os.environ.get("TELEGRAM_BOT_TOKEN", ""))
        self.chat_id = tg.get("chat_id", os.environ.get("TELEGRAM_CHAT_ID", ""))
        self.base_url = f"https://api.telegram.org/bot{self.token}" if self.token else ""

    def send(self, text: str, parse_mode: str = "HTML") -> bool:
        """Send message to Telegram."""
        if not self.enabled or not self.token or not self.chat_id:
            return False

        try:
            resp = requests.post(
                f"{self.base_url}/sendMessage",
                json={
                    "chat_id": self.chat_id,
                    "text": text,
                    "parse_mode": parse_mode,
                    "disable_web_page_preview": True,
                },
                timeout=10,
            )
            return resp.status_code == 200
        except Exception:
            return False

    def notify_deploy(self, position: dict):
        """Notify about new LP position."""
        t0 = position.get("token0_symbol", "?")
        t1 = position.get("token1_symbol", "?")
        dex = position.get("dex", "?")
        amount = position.get("amount_eth", 0)
        pool = position.get("pool", "?")

        text = (
            f"<b>[+] LP DEPLOYED</b>\n"
            f"Pair: {t0}/{t1}\n"
            f"DEX: {dex}\n"
            f"Amount: {amount:.4f} ETH\n"
            f"Pool: <code>{pool}</code>\n"
            f"TX: https://basescan.org/tx/{position.get('tx_hash', '?')}"
        )
        self.send(text)

    def notify_close(self, position: dict):
        """Notify about closed position."""
        t0 = position.get("token0_symbol", "?")
        t1 = position.get("token1_symbol", "?")
        pnl = position.get("final_pnl_pct", 0)
        reason = position.get("close_reason", "?")
        hold_min = position.get("hold_duration_min", 0)

        emoji = "[+]" if pnl >= 0 else "[-]"
        text = (
            f"<b>{emoji} LP CLOSED</b>\n"
            f"Pair: {t0}/{t1}\n"
            f"PnL: {pnl:+.2f}%\n"
            f"Reason: {reason}\n"
            f"Hold: {hold_min:.0f}min\n"
            f"TX: https://basescan.org/tx/{position.get('close_tx', '?')}"
        )
        self.send(text)

    def notify_error(self, error: str, context: str = ""):
        """Notify about errors."""
        text = f"<b>[!] ERROR</b>\n{context}\n<pre>{error[:500]}</pre>"
        self.send(text)

    def notify_daily_summary(self, summary: str):
        """Send daily summary."""
        text = f"<b>Kaori Daily Summary</b>\n<pre>{summary}</pre>"
        self.send(text)

    def notify_new_pool(self, pool: dict):
        """Notify about newly discovered pool."""
        t0 = pool.get("token0", {}).get("symbol", "?")
        t1 = pool.get("token1", {}).get("symbol", "?")
        dex = pool.get("dex", "?")

        text = (
            f"<b>[NEW] Pool Detected</b>\n"
            f"Pair: {t0}/{t1}\n"
            f"DEX: {dex}\n"
            f"Pool: <code>{pool.get('pool', '?')}</code>"
        )
        self.send(text)
