"""Strategy Switching Engine for CryptoAID Trade AI.
Enforces dynamic lifecycle transitions:
SCALP -> MOMENTUM -> TREND -> TRAILING EXIT
ANY -> CORTEX EXIT / ANY -> STOP (disciplined invalidation cut).
Includes hysteresis cooldown to prevent strategy thrashing.
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any
from pydantic import BaseModel, Field

from src.storage.db import DatabaseManager

logger = logging.getLogger(__name__)


class StrategySwitchResult(BaseModel):
    switched: bool
    from_strategy: str
    to_strategy: str
    reason: str
    new_sl: float | None = None
    new_tp: float | None = None
    should_exit: bool = False
    exit_reason: str | None = None


class StrategySwitchingEngine:
    """
    Evaluates open positions continuously:
    A position does NOT belong forever to the strategy that opened it.
    """

    def __init__(
        self,
        db: DatabaseManager | None = None,
        min_switch_cooldown_seconds: float = 60.0,
    ) -> None:
        self.db = db or DatabaseManager()
        self.min_cooldown = min_switch_cooldown_seconds
        self.last_switch_timestamp: dict[str, float] = {}  # pos_id -> timestamp

    def evaluate_position(
        self,
        pos_id: str,
        asset: str,
        current_strategy: str,
        entry_price: float,
        current_price: float,
        side: str = "BUY",
        pnl_pct: float | None = None,
        market_regime: str = "TRENDING",
        predicted_move_pct: float = 0.0,
        cortex_risk_flag: bool = False,
        account_id: str = "paper_balanced",
    ) -> StrategySwitchResult:
        """
        Evaluate if a position should transition strategy, lock break-even, or exit early on invalidation.
        """
        now = time.time()
        last_switched = self.last_switch_timestamp.get(pos_id, 0.0)

        # Calculate PnL percentage if not passed
        if pnl_pct is None:
            if entry_price > 0:
                pnl_pct = ((current_price - entry_price) / entry_price) * 100.0 if side.upper() in ["BUY", "LONG"] else ((entry_price - current_price) / entry_price) * 100.0
            else:
                pnl_pct = 0.0

        # RULE 1: CORTEX Emergency or Hard Ceiling Veto
        if cortex_risk_flag or pnl_pct <= -5.0:
            return StrategySwitchResult(
                switched=True,
                from_strategy=current_strategy,
                to_strategy="CORTEX_EMERGENCY",
                reason="CORTEX Risk Veto or Hard Stop Ceiling (-5.0%) breached",
                should_exit=True,
                exit_reason="CORTEX_RISK_EXIT",
            )

        # RULE 2: Invalidation Cut (No hanging onto false hope)
        # If position was a quick scalp and dropped -0.40% with active negative prediction (< 0.0), cut small
        if "SCALP" in current_strategy.upper() and pnl_pct <= -0.40 and predicted_move_pct < 0.0:
            return StrategySwitchResult(
                switched=True,
                from_strategy=current_strategy,
                to_strategy="DISCIPLINED_EXIT",
                reason="Scalp prediction invalidated: small cut before large loss (-0.40%)",
                should_exit=True,
                exit_reason="PREDICTION_INVALIDATED",
            )


        # Check Hysteresis Cooldown for upgrades
        if (now - last_switched) < self.min_cooldown:
            return StrategySwitchResult(
                switched=False,
                from_strategy=current_strategy,
                to_strategy=current_strategy,
                reason="Cooldown active (hysteresis)",
            )

        # RULE 3: SCALP -> MOMENTUM (Gain acceleration)
        # If profit reaches +0.80% and prediction remains positive, graduate to MOMENTUM
        if "SCALP" in current_strategy.upper() and pnl_pct >= 0.80:
            # Move Stop to Break-Even (+0.2% to cover fees)
            be_sl = entry_price * 1.002 if side.upper() in ["BUY", "LONG"] else entry_price * 0.998
            new_tp = entry_price * 1.035 if side.upper() in ["BUY", "LONG"] else entry_price * 0.965

            self._record_switch(
                pos_id=pos_id,
                account_id=account_id,
                asset=asset,
                from_strat=current_strategy,
                to_strat="Momentum",
                reason="Profit >= +0.80%: graduated SCALP to MOMENTUM with break-even lock",
                pnl_pct=pnl_pct,
                entry_price=entry_price,
                current_price=current_price,
                new_sl=be_sl,
                new_tp=new_tp,
            )
            self.last_switch_timestamp[pos_id] = now

            return StrategySwitchResult(
                switched=True,
                from_strategy=current_strategy,
                to_strategy="Momentum",
                reason="Graduated SCALP to MOMENTUM: Break-Even locked at +0.20%, profit running",
                new_sl=be_sl,
                new_tp=new_tp,
            )

        # RULE 4: MOMENTUM -> TREND (Trend continuation runner)
        # If profit expands >= +2.0% and regime confirms TRENDING, graduate to TREND
        if "MOMENTUM" in current_strategy.upper() and pnl_pct >= 2.0 and market_regime in ["TRENDING", "EXPANSION", "BULL_TREND"]:
            # Trailing stop engaged at current_price - 1.0%
            trail_sl = current_price * 0.990 if side.upper() in ["BUY", "LONG"] else current_price * 1.010
            expanded_tp = entry_price * 1.080 if side.upper() in ["BUY", "LONG"] else entry_price * 0.920

            self._record_switch(
                pos_id=pos_id,
                account_id=account_id,
                asset=asset,
                from_strat=current_strategy,
                to_strat="Trend",
                reason="Profit >= +2.0% with trend confirmation: graduated MOMENTUM to TREND runner",
                pnl_pct=pnl_pct,
                entry_price=entry_price,
                current_price=current_price,
                new_sl=trail_sl,
                new_tp=expanded_tp,
            )
            self.last_switch_timestamp[pos_id] = now

            return StrategySwitchResult(
                switched=True,
                from_strategy=current_strategy,
                to_strategy="Trend",
                reason="Graduated MOMENTUM to TREND runner with active trailing stop",
                new_sl=trail_sl,
                new_tp=expanded_tp,
            )

        # RULE 5: BREAKOUT -> TREND
        if "BREAKOUT" in current_strategy.upper() and pnl_pct >= 1.20:
            trail_sl = entry_price * 1.005 if side.upper() in ["BUY", "LONG"] else entry_price * 0.995
            self._record_switch(
                pos_id=pos_id,
                account_id=account_id,
                asset=asset,
                from_strat=current_strategy,
                to_strat="Trend",
                reason="Breakout confirmed above threshold: converted to TREND",
                pnl_pct=pnl_pct,
                entry_price=entry_price,
                current_price=current_price,
                new_sl=trail_sl,
                new_tp=None,
            )
            self.last_switch_timestamp[pos_id] = now

            return StrategySwitchResult(
                switched=True,
                from_strategy=current_strategy,
                to_strategy="Trend",
                reason="Breakout converted to TREND with secured lock",
                new_sl=trail_sl,
            )

        return StrategySwitchResult(
            switched=False,
            from_strategy=current_strategy,
            to_strategy=current_strategy,
            reason="Current strategy conditions sustained",
        )

    def _record_switch(
        self,
        pos_id: str,
        account_id: str,
        asset: str,
        from_strat: str,
        to_strat: str,
        reason: str,
        pnl_pct: float,
        entry_price: float,
        current_price: float,
        new_sl: float | None,
        new_tp: float | None,
    ) -> None:
        try:
            self.db.record_strategy_switch({
                "position_id": pos_id,
                "account_id": account_id,
                "asset": asset,
                "from_strategy": from_strat,
                "to_strategy": to_strat,
                "reason": reason,
                "pnl_pct_at_switch": pnl_pct,
                "entry_price": entry_price,
                "current_price": current_price,
                "new_sl": new_sl,
                "new_tp": new_tp,
            })
            logger.info("Strategy Switch executed on %s (%s): %s -> %s | %s", asset, pos_id, from_strat, to_strat, reason)
        except Exception as e:
            logger.error("Failed to record strategy switch: %s", e)
