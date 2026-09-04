"""Mean Reversion Strategy Agent for CryptoAID Trade AI."""
from __future__ import annotations

import pandas as pd
from src.agents.base import AgentSignal, BaseStrategyAgent, SignalType
from src.data.base import MarketSnapshot


class MeanReversionAgent(BaseStrategyAgent):
    """Detects statistical overextension and reverts to the mean using Bollinger Bands and Z-score."""

    def __init__(self, name: str = "MeanReversionAgent", weight: float = 1.0) -> None:
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

        closes = pd.Series([c.close for c in candles])
        sma20 = closes.rolling(window=20).mean()
        std20 = closes.rolling(window=20).std()
        upper_bb = sma20 + (2.0 * std20)
        lower_bb = sma20 - (2.0 * std20)

        current_price = snapshot.price
        mean_price = float(sma20.iloc[-1])
        std = float(std20.iloc[-1]) if float(std20.iloc[-1]) > 0 else 1.0
        z_score = (current_price - mean_price) / std

        lower = float(lower_bb.iloc[-1])
        upper = float(upper_bb.iloc[-1])
        pct_b = (current_price - lower) / (upper - lower) if upper != lower else 0.5

        evidence = [
            f"Price: {current_price:.2f}",
            f"SMA(20): {mean_price:.2f}, Lower BB: {lower:.2f}, Upper BB: {upper:.2f}",
            f"Z-Score: {z_score:.2f}, %B: {pct_b:.2f}",
        ]

        if z_score <= -2.1 or pct_b < 0.05:
            evidence.append("Severe negative statistical extension (Lower Bollinger Band breached)")
            return AgentSignal(
                agent_name=self.name,
                asset=snapshot.symbol,
                signal=SignalType.LONG,
                confidence=0.77,
                expected_return=abs((mean_price - current_price) / current_price),
                expected_risk=0.015,
                time_horizon="1H-4H",
                invalidation=f"Price continues falling below {lower * 0.98:.2f}",
                evidence=evidence,
            )
        elif z_score >= 2.1 or pct_b > 0.95:
            evidence.append("Severe positive statistical extension (Upper Bollinger Band breached)")
            return AgentSignal(
                agent_name=self.name,
                asset=snapshot.symbol,
                signal=SignalType.SHORT,
                confidence=0.75,
                expected_return=abs((current_price - mean_price) / current_price),
                expected_risk=0.015,
                time_horizon="1H-4H",
                invalidation=f"Price continues rising above {upper * 1.02:.2f}",
                evidence=evidence,
            )

        return AgentSignal(
            agent_name=self.name,
            asset=snapshot.symbol,
            signal=SignalType.NO_TRADE,
            confidence=0.60,
            invalidation=f"Price within normal distribution band (|Z| < 2.0)",
            evidence=evidence + ["Price within normal range of 20 SMA"],
        )
