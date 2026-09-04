"""Signal deduplication filter for Telegram publishing."""
from __future__ import annotations

import time
from typing import Any


class SignalDeduplicator:
    """Prevents spamming repetitive signals within a cooldown window."""

    def __init__(self, cooldown_seconds: int = 14400, price_delta_threshold_pct: float = 2.0) -> None:
        self.cooldown_seconds = cooldown_seconds
        self.price_delta_threshold_pct = price_delta_threshold_pct
        self._history: dict[str, dict[str, Any]] = {}

    def is_duplicate(self, asset: str, signal: str, price: float) -> bool:
        """Check if signal is a duplicate within cooldown and price band."""
        key = f"{asset}:{signal}"
        now = time.time()

        if key not in self._history:
            self._history[key] = {"timestamp": now, "price": price}
            return False

        last_entry = self._history[key]
        elapsed = now - last_entry["timestamp"]

        if elapsed > self.cooldown_seconds:
            self._history[key] = {"timestamp": now, "price": price}
            return False

        # If significant price change occurred (> 2%), allow new signal
        price_diff_pct = abs((price - last_entry["price"]) / last_entry["price"]) * 100.0
        if price_diff_pct >= self.price_delta_threshold_pct:
            self._history[key] = {"timestamp": now, "price": price}
            return False

        return True

    def clear(self) -> None:
        self._history.clear()
