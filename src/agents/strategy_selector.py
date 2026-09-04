"""Strategy Selector for TradeAID.

Calculates multi-criteria strategy affinity based on the MARKET STATE VECTOR:
Regime + Predictive Heart + Historical Analogs + Tournament Rankings + Experience Matrix Reliability.
Supports explicit EXIT decisions when market conditions degrade or overextend.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class MarketStateVector(BaseModel):
    asset: str = "POL/USDT"
    regime: str = "TRENDING_BULL"
    predictive_forecast_pct: float = 0.015  # +1.5%
    forecast_confidence: float = 0.75       # 0.0 to 1.0
    historical_analog_score: float = 0.80   # Analog pattern match fidelity
    tournament_rankings: dict[str, float] = Field(default_factory=dict)
    strategy_reliability: dict[str, float] = Field(default_factory=dict)
    adx: float = 28.0                      # Trend strength (>25 trending)
    rsi_14: float = 58.0                   # Momentum indicator
    volatility_ratio: float = 1.1          # Current ATR / Baseline ATR
    is_overextended: bool = False          # Price stretched far from mean
    in_active_position: bool = False       # True if already holding a position


class StrategySelectionResult(BaseModel):
    selected_strategy: str                 # "MOMENTUM", "TREND", "BREAKOUT", "MEAN_REVERSION", "SCALP", "EXIT"
    secondary_strategy: str | None = None
    action: str = "ENTER"                  # "ENTER", "HOLD", "EXIT", "NO_TRADE"
    strategy_scores: dict[str, float]      # 0.0 to 1.0 affinity for each DNA
    explanation: str = ""
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump()


class StrategySelector:
    """Selects the optimal Strategy DNA or triggers an EXIT based on Market State Vector."""

    # Baseline affinity matrix: Strategy affinity per Regime
    REGIME_AFFINITY = {
        "TRENDING_BULL": {
            "MOMENTUM": 0.85,
            "TREND": 0.80,
            "BREAKOUT": 0.75,
            "SCALP": 0.60,
            "MEAN_REVERSION": 0.20,
        },
        "TRENDING_BEAR": {
            "TREND": 0.85,
            "MOMENTUM": 0.75,
            "BREAKOUT": 0.70,
            "SCALP": 0.60,
            "MEAN_REVERSION": 0.25,
        },
        "RANGING_LOW_VOL": {
            "MEAN_REVERSION": 0.85,
            "SCALP": 0.75,
            "MOMENTUM": 0.30,
            "TREND": 0.15,
            "BREAKOUT": 0.25,
        },
        "RANGING_HIGH_VOL": {
            "BREAKOUT": 0.80,
            "MEAN_REVERSION": 0.65,
            "SCALP": 0.70,
            "MOMENTUM": 0.50,
            "TREND": 0.35,
        },
        "HIGH_VOLATILITY_EXPANSION": {
            "SCALP": 0.85,
            "BREAKOUT": 0.75,
            "MOMENTUM": 0.60,
            "MEAN_REVERSION": 0.30,
            "TREND": 0.30,
        },
        "UNKNOWN": {
            "SCALP": 0.60,
            "MEAN_REVERSION": 0.50,
            "MOMENTUM": 0.40,
            "BREAKOUT": 0.40,
            "TREND": 0.30,
        },
    }

    def evaluate(self, state: MarketStateVector) -> StrategySelectionResult:
        regime = state.regime.upper()
        base_affinities = self.REGIME_AFFINITY.get(regime, self.REGIME_AFFINITY["UNKNOWN"])

        scores: dict[str, float] = {}

        # 1. Calculate weighted affinity for each trading DNA
        for strat, base_aff in base_affinities.items():
            # Tournament weight (default 0.70 if not ranked)
            t_rank = state.tournament_rankings.get(strat, 0.70)
            # Experience Matrix reliability (default 0.70 if unobserved)
            rel = state.strategy_reliability.get(strat, 0.70)
            # Historical analog resonance
            analog = state.historical_analog_score

            # Composite Score = 40% Base Regime + 25% Reliability + 20% Tournament + 15% Analog
            raw_score = (base_aff * 0.40) + (rel * 0.25) + (t_rank * 0.20) + (analog * 0.15)

            # Specific DNA adjustments based on micro-state
            if strat == "MOMENTUM":
                if state.adx > 25 and state.rsi_14 > 50 and state.predictive_forecast_pct > 0.01:
                    raw_score += 0.10
                if state.is_overextended:
                    raw_score -= 0.35  # Momentum dies when overextended

            elif strat == "TREND":
                if state.adx > 30 and state.volatility_ratio < 1.4:
                    raw_score += 0.10
                if state.is_overextended:
                    raw_score -= 0.25

            elif strat == "BREAKOUT":
                if state.volatility_ratio > 1.3 and abs(state.predictive_forecast_pct) > 0.015:
                    raw_score += 0.12

            elif strat == "MEAN_REVERSION":
                if state.is_overextended or state.rsi_14 > 75 or state.rsi_14 < 25:
                    raw_score += 0.35
                if state.adx > 35:
                    raw_score -= 0.30  # Don't fade a strong runaway trend

            elif strat == "SCALP":
                if state.volatility_ratio > 1.2:
                    raw_score += 0.08

            scores[strat] = round(max(0.05, min(0.99, raw_score)), 2)

        # 2. Evaluate EXIT Score
        # Exit score spikes if position is active and:
        # - Market is overextended and predictive forecast turns negative
        # - Confidence collapses
        # - Regime shifts violently away from active strategy
        exit_score = 0.05
        if state.in_active_position:
            if state.is_overextended and state.predictive_forecast_pct < 0.0:
                exit_score = 0.82
            elif state.forecast_confidence < 0.50:
                exit_score = 0.75
            elif state.predictive_forecast_pct < -0.005:  # -0.5% predicted against position
                exit_score = 0.79
            elif state.adx < 15 and scores.get("TREND", 0) < 0.40:
                exit_score = 0.68

        scores["EXIT"] = round(exit_score, 2)

        # 3. Decision arbitration
        if state.in_active_position and exit_score >= 0.70:
            return StrategySelectionResult(
                selected_strategy="EXIT",
                secondary_strategy=None,
                action="EXIT",
                strategy_scores=scores,
                explanation=f"EXIT Triggered: Overextended/degrading condition (Exit Score: {exit_score:.2f})",
            )

        # Rank trading strategies (excluding EXIT)
        trading_scores = {k: v for k, v in scores.items() if k != "EXIT"}
        ranked = sorted(trading_scores.items(), key=lambda x: x[1], reverse=True)

        primary = ranked[0][0]
        secondary = ranked[1][0] if len(ranked) > 1 else None
        top_score = ranked[0][1]

        if top_score < 0.45:
            action = "NO_TRADE"
            explanation = f"No Strategy Reached Minimum Conviction (Top: {primary} at {top_score:.2f})"
        elif state.in_active_position:
            action = "HOLD"
            explanation = f"Holding Active Position aligned with {primary} ({top_score:.2f})"
        else:
            action = "ENTER"
            explanation = f"Selected {primary} ({top_score:.2f}) backed by {secondary} ({ranked[1][1]:.2f})"

        return StrategySelectionResult(
            selected_strategy=primary,
            secondary_strategy=secondary,
            action=action,
            strategy_scores=scores,
            explanation=explanation,
        )
