"""Telegram Topic Routing Engine for CryptoAID Trade AI."""
from __future__ import annotations

import logging
from enum import Enum
from typing import Any
import requests

from src.config import settings

logger = logging.getLogger(__name__)


class TopicDestination(str, Enum):
    TRADE_AI = "TRADE_AI"
    AI_SIGNALS = "AI_SIGNALS"
    SECURITY_SCAM = "SECURITY_SCAM"
    CRYPTOAID_LAB = "CRYPTOAID_LAB"
    CRYPTOAID_SUPPORT = "CRYPTOAID_SUPPORT"
    GENERAL = "GENERAL"


class TelegramTopicRouter:
    """Routes messages to specific topics in @cryptoAIDsupporter and channel @cryptoaidsup."""

    def __init__(self, bot_token: str | None = None) -> None:
        self.bot_token = bot_token or settings.telegram_bot_token
        self.group = settings.telegram_group
        self.channel = settings.telegram_channel
        self.topic_map = {
            TopicDestination.TRADE_AI: settings.topic_trade_ai,
            TopicDestination.AI_SIGNALS: settings.topic_ai_signals,
            TopicDestination.SECURITY_SCAM: settings.topic_security_scam,
            TopicDestination.CRYPTOAID_LAB: settings.topic_cryptoaid_lab,
        }

    def resolve_destination(self, event_type: str) -> tuple[str, int | None]:
        """Determine target chat and message_thread_id based on event type."""
        # Official Channel Broadcasts (@cryptoaidsup)
        if event_type.startswith("CHANNEL_"):
            return self.channel, None

        # Clean AI Signals & Predictive Heart route to designated AI SIGNALS topic
        if event_type in ("VERIFIED_AI_SIGNAL", "PREDICTIVE_HEART_FORECAST", "SIGNAL_ALERT"):
            return self.group, self.topic_map.get(TopicDestination.AI_SIGNALS)
        elif event_type in (
            "PAPER_TRADE_OPENED",
            "PAPER_TRADE_CLOSED",
            "TRADE_DISCUSSION",
            "AUTOTRADE_RUN_STARTED",
            "AUTOTRADE_RUN_WON",
            "AUTOTRADE_RUN_LOST",
            "PROP_CHALLENGE_CREATED",
            "PROP_CHALLENGE_PROGRESS",
            "PROP_CHALLENGE_PASSED",
        ):
            return self.group, self.topic_map.get(TopicDestination.TRADE_AI)
        elif event_type in ("SECURITY_REJECTION", "SCAM_ALERT", "HONEYPOT_DETECTED"):
            return self.group, self.topic_map.get(TopicDestination.SECURITY_SCAM)
        elif event_type in ("SYSTEM_TEST", "HEALTHCHECK", "DEV_LOG", "CORTEX_DECISION", "CORTEX_AUDIT"):
            return self.group, self.topic_map.get(TopicDestination.CRYPTOAID_LAB)
        return self.group, None

    def publish(
        self,
        event_type: str,
        text: str,
        reply_markup: dict[str, Any] | None = None,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """Publish a message to the appropriate topic or channel, or simulate in dry-run mode."""
        chat_id, thread_id = self.resolve_destination(event_type)

        if dry_run or not self.bot_token:
            logger.info("[DRY-RUN TELEGRAM] Target: %s (Thread: %s) ->\n%s", chat_id, thread_id, text)
            return {
                "status": "SIMULATED",
                "chat_id": chat_id,
                "message_thread_id": thread_id,
                "text_length": len(text),
                "has_markup": reply_markup is not None,
            }

        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload: dict[str, Any] = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }
        if thread_id is not None:
            payload["message_thread_id"] = thread_id
        if reply_markup is not None:
            payload["reply_markup"] = reply_markup

        try:
            resp = requests.post(url, json=payload, timeout=5.0)
            data = resp.json()
            if data.get("ok"):
                return {"status": "SUCCESS", "message_id": data["result"]["message_id"]}
            logger.warning("Telegram publish failed: %s", data)
            return {"status": "ERROR", "detail": data}
        except Exception as exc:
            logger.error("Telegram publish exception: %s", exc)
            return {"status": "FAILED", "error": str(exc)}

