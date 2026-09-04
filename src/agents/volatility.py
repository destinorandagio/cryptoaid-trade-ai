"""Volatility Strategy Agent for CryptoAID Trade AI."""
from __future__ import annotations

import pandas as pd
from src.agents.base import AgentSignal, BaseStrategyAgent, SignalType
from src.data.base import MarketSnapshot


def calculate_atr(candles: list, period: int = 14) -> pd.Series:
    highs = pd.Series([c.high for c in candles])
    lows = pd.Series([c.low for c in candles])
    closes = pd.Series([c.close for c in candles])
    prev_closes = closes.shift(1)

    tr1 = highs - lows
    tr2 = (highs - prev_closes).abs()
    tr3 = (lows - prev_closes).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.rolling(window=period).mean()


class VolatilityAgent(BaseStrategyAgent):
    """Monitors volatility expansion, compression (squeezes) and sets risk limits."""

    def __init__(self, name: str = "VolatilityAgent", weight: float = 1.0) -> None:
        super().__init__(name=name, weight=weight)

    def evaluate(self, snapshot: MarketSnapshot) -> AgentSignal:
        candles = snapshot.candles_1h
        if len(candles) < 25:
            return AgentSignal(
                agent_name=self.name,
                asset=snapshot.symbol,
                signal=SignalType.NO_TRADE,
                confidence=0.5,
                invalidation="Insufficient candles",
                evidence=["Less than 25 candles available"],
            )

        atr_series = calculate_atr(candles, period=14)
        current_atr = float(atr_series.iloc[-1])
        avg_atr = float(atr_series.tail(20).mean())
        atr_ratio = current_atr / avg_atr if avg_atr > 0 else 1.0
        atr_pct = (current_atr / snapshot.price) * 100.0

        evidence = [
            f"Current ATR(14): {current_atr:.2f} ({atr_pct:.2f}% of price)",
            f"ATR Expansion Ratio: {atr_ratio:.2f}x average",
            f"Observed 24h Volatility: {snapshot.volatility_24h:.2f}%",
        ]

        # Extreme volatility: Danger of whipsaws
        if atr_ratio > 2.0 or snapshot.volatility_24h > 12.0:
            evidence.append("Extreme volatility expansion: market turbulence hazard")
            return AgentSignal(
                agent_name=self.name,
                asset=snapshot.symbol,
                signal=SignalType.EXIT,
                confidence=0.88,
                expected_return=0.0,
                expected_risk=0.08,
                time_horizon="Immediate",
                invalidation="Volatility falls below 1.5x average",
                evidence=evidence,
            )
        # Moderate volatility expansion favorable for directional trades
        elif 1.2 <= atr_ratio <= 1.8:
            evidence.append("Healthy volatility expansion: directional impulse viable")
            return AgentSignal(
                agent_name=self.name,
                asset=snapshot.symbol,
                signal=SignalType.HOLD,
                confidence=0.70,
                expected_return=0.03,
                expected_risk=atr_pct / 100.0,
                time_horizon="4H",
                invalidation="Volatility contracts below baseline",
                evidence=evidence,
            )

        return AgentSignal(
            agent_name=self.name,
            asset=snapshot.symbol,
            signal=SignalType.NO_TRADE,
            confidence=0.60,
            invalidation="Volatility within normal compression band",
            evidence=evidence + ["Normal volatility regime"],
        )
