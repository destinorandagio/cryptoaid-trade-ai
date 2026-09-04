"""Breakout Strategy Agent for CryptoAID Trade AI."""
from __future__ import annotations

import pandas as pd
from src.agents.base import AgentSignal, BaseStrategyAgent, SignalType
from src.data.base import MarketSnapshot


class BreakoutAgent(BaseStrategyAgent):
    """Detects volatility and range breakout using Donchian 20 channels and volume surge."""

    def __init__(self, name: str = "BreakoutAgent", weight: float = 1.1) -> None:
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

        highs = pd.Series([c.high for c in candles[:-1]])
        lows = pd.Series([c.low for c in candles[:-1]])
        volumes = pd.Series([c.volume for c in candles[:-1]])

        donchian_high = highs.tail(20).max()
        donchian_low = lows.tail(20).min()
        avg_volume = volumes.tail(20).mean()
        last_volume = candles[-1].volume

        current_price = snapshot.price
        volume_ratio = last_volume / avg_volume if avg_volume > 0 else 1.0

        evidence = [
            f"Price: {current_price:.2f}",
            f"20-period High: {donchian_high:.2f}, 20-period Low: {donchian_low:.2f}",
            f"Volume Ratio: {volume_ratio:.2f}x average",
        ]

        if current_price > donchian_high and volume_ratio >= 1.25:
            evidence.append("Bullish Donchian breakout confirmed by volume expansion")
            return AgentSignal(
                agent_name=self.name,
                asset=snapshot.symbol,
                signal=SignalType.LONG,
                confidence=0.81,
                expected_return=0.045,
                expected_risk=0.018,
                time_horizon="4H-12H",
                invalidation=f"Price falls back inside range below {donchian_high:.2f}",
                evidence=evidence,
            )
        elif current_price < donchian_low and volume_ratio >= 1.25:
            evidence.append("Bearish Donchian breakdown confirmed by volume expansion")
            return AgentSignal(
                agent_name=self.name,
                asset=snapshot.symbol,
                signal=SignalType.SHORT,
                confidence=0.79,
                expected_return=0.045,
                expected_risk=0.018,
                time_horizon="4H-12H",
                invalidation=f"Price rises back inside range above {donchian_low:.2f}",
                evidence=evidence,
            )

        return AgentSignal(
            agent_name=self.name,
            asset=snapshot.symbol,
            signal=SignalType.NO_TRADE,
            confidence=0.55,
            invalidation="Price oscillating within Donchian channel",
            evidence=evidence + ["No breakout trigger active"],
        )
