"""Trend Strategy Agent for CryptoAID Trade AI."""
from __future__ import annotations

import pandas as pd
from src.agents.base import AgentSignal, BaseStrategyAgent, SignalType
from src.data.base import MarketSnapshot


class TrendAgent(BaseStrategyAgent):
    """Detects medium/long term trend using EMA 12/26 and SMA 50."""

    def __init__(self, name: str = "TrendAgent", weight: float = 1.2) -> None:
        super().__init__(name=name, weight=weight)

    def evaluate(self, snapshot: MarketSnapshot) -> AgentSignal:
        candles = snapshot.candles_1h
        if len(candles) < 30:
            return AgentSignal(
                agent_name=self.name,
                asset=snapshot.symbol,
                signal=SignalType.NO_TRADE,
                confidence=0.5,
                invalidation="Insufficient candle history",
                evidence=["Less than 30 candles available"],
            )

        closes = pd.Series([c.close for c in candles])
        ema12 = closes.ewm(span=12, adjust=False).mean()
        ema26 = closes.ewm(span=26, adjust=False).mean()

        current_price = snapshot.price
        last_ema12 = ema12.iloc[-1]
        last_ema26 = ema26.iloc[-1]
        prev_ema12 = ema12.iloc[-2]
        prev_ema26 = ema26.iloc[-2]

        bullish_cross = prev_ema12 <= prev_ema26 and last_ema12 > last_ema26
        bearish_cross = prev_ema12 >= prev_ema26 and last_ema12 < last_ema26
        bullish_alignment = last_ema12 > last_ema26 and current_price > last_ema12
        bearish_alignment = last_ema12 < last_ema26 and current_price < last_ema12

        evidence = [
            f"Current price: {current_price:.2f}",
            f"EMA(12): {last_ema12:.2f}, EMA(26): {last_ema26:.2f}",
        ]

        if bullish_cross or bullish_alignment:
            confidence = 0.82 if bullish_cross else 0.72
            evidence.append("Bullish EMA crossover / alignment active")
            return AgentSignal(
                agent_name=self.name,
                asset=snapshot.symbol,
                signal=SignalType.LONG,
                confidence=confidence,
                expected_return=0.035,
                expected_risk=0.015,
                time_horizon="4H-1D",
                invalidation=f"Price drops below EMA(26) at {last_ema26:.2f}",
                evidence=evidence,
            )
        elif bearish_cross or bearish_alignment:
            confidence = 0.80 if bearish_cross else 0.70
            evidence.append("Bearish EMA crossover / alignment active")
            return AgentSignal(
                agent_name=self.name,
                asset=snapshot.symbol,
                signal=SignalType.SHORT,
                confidence=confidence,
                expected_return=0.035,
                expected_risk=0.015,
                time_horizon="4H-1D",
                invalidation=f"Price breaks above EMA(26) at {last_ema26:.2f}",
                evidence=evidence,
            )

        return AgentSignal(
            agent_name=self.name,
            asset=snapshot.symbol,
            signal=SignalType.HOLD,
            confidence=0.55,
            invalidation="No clean EMA trend separation",
            evidence=evidence + ["EMAs neutral / compressed"],
        )
