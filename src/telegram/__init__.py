"""Telegram Module for CryptoAID Trade AI."""
from src.telegram.dedupe import SignalDeduplicator
from src.telegram.formatter import format_ai_signal, format_paper_trade_event, format_security_rejection
from src.telegram.router import TelegramTopicRouter, TopicDestination

__all__ = [
    "TelegramTopicRouter",
    "TopicDestination",
    "SignalDeduplicator",
    "format_ai_signal",
    "format_paper_trade_event",
    "format_security_rejection",
]
