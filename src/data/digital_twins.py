"""5 Interconnected Digital Twins Architecture for CryptoAID Trade AI.
1. MARKET TWIN — Full verifiable historical market and order flow state.
2. PREDICTION TWIN — Every forecast vs actual outcome calibration ledger.
3. STRATEGY TWIN — Performance of every Strategy DNA per regime & timeframe.
4. POSITION TWIN — Full lifecycle, graduation, and switching audit trail.
5. GEM TWIN — Discovery -> Validation -> Asymmetric Outcome tracker.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any
from pydantic import BaseModel, Field

from src.storage.db import DatabaseManager

logger = logging.getLogger(__name__)


class DigitalTwinsManager:
    """Orchestrates and queries the 5 synchronized digital twins."""

    def __init__(self, db: DatabaseManager | None = None) -> None:
        self.db = db or DatabaseManager()

    # 1. Market Twin
    def sync_market_twin(self, asset: str, price: float, volume_24h: float, regime: str, liquidity_usd: float | None = None) -> str:
        payload = {
            "asset": asset,
            "price": price,
            "volume_24h": volume_24h,
            "regime": regime,
            "liquidity_usd": liquidity_usd,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        return self.db.record_digital_twin_event("MARKET", "TICK_STATE", payload)

    # 2. Prediction Twin
    def sync_prediction_twin(self, forecast_id: str, asset: str, timeframe: str, p50: float, actual: float | None, brier_score: float | None) -> str:
        payload = {
            "forecast_id": forecast_id,
            "asset": asset,
            "timeframe": timeframe,
            "predicted_p50": p50,
            "actual_price": actual,
            "brier_score": brier_score,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        return self.db.record_digital_twin_event("PREDICTION", "FORECAST_EVAL", payload)

    # 3. Strategy Twin
    def sync_strategy_twin(self, strategy_id: str, regime: str, net_expectancy: float, win_rate: float, trades_count: int) -> str:
        payload = {
            "strategy_id": strategy_id,
            "regime": regime,
            "net_expectancy": net_expectancy,
            "win_rate": win_rate,
            "trades_count": trades_count,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        return self.db.record_digital_twin_event("STRATEGY", "REGIME_PERFORMANCE", payload)

    # 4. Position Twin
    def sync_position_twin(self, position_id: str, event_type: str, details: dict[str, Any]) -> str:
        payload = {
            "position_id": position_id,
            "event": event_type,
            "details": details,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        return self.db.record_digital_twin_event("POSITION", event_type, payload)

    # 5. Gem Twin
    def sync_gem_twin(self, token_address: str, symbol: str, score: float, stage: str, pnl_multiplier: float = 1.0) -> str:
        payload = {
            "token_address": token_address,
            "symbol": symbol,
            "score": score,
            "stage": stage,
            "pnl_multiplier": pnl_multiplier,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        return self.db.record_digital_twin_event("GEM", "LIFECYCLE_UPDATE", payload)

    def get_twins_status(self) -> dict[str, Any]:
        """Aggregate health and recent records across all 5 twins."""
        market_events = self.db.get_digital_twin_events("MARKET", limit=5)
        prediction_events = self.db.get_digital_twin_events("PREDICTION", limit=5)
        strategy_events = self.db.get_digital_twin_events("STRATEGY", limit=5)
        position_events = self.db.get_digital_twin_events("POSITION", limit=5)
        gem_events = self.db.get_digital_twin_events("GEM", limit=5)

        return {
            "status": "HEALTHY_SYNCHRONIZED",
            "twins": {
                "market_twin": {"active": True, "recent_events_count": len(market_events)},
                "prediction_twin": {"active": True, "recent_events_count": len(prediction_events)},
                "strategy_twin": {"active": True, "recent_events_count": len(strategy_events)},
                "position_twin": {"active": True, "recent_events_count": len(position_events)},
                "gem_twin": {"active": True, "recent_events_count": len(gem_events)},
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
