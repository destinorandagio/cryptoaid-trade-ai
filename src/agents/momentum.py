"""Momentum Strategy Agent for CryptoAID Trade AI."""
from __future__ import annotations

import pandas as pd
from src.agents.base import AgentSignal, BaseStrategyAgent, SignalType
from src.data.base import MarketSnapshot


def calculate_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / (loss.replace(0, 1e-9))
    return 100 - (100 / (1 + rs))


class MomentumAgent(BaseStrategyAgent):
    """Detects velocity and momentum shifts using RSI and MACD."""

    def __init__(self, name: str = "MomentumAgent", weight: float = 1.1) -> None:
        super().__init__(name=name, weight=weight)

    def evaluate(self, snapshot: MarketSnapshot) -> AgentSignal:
        candles = snapshot.candles_1h
        if len(candles) < 30:
            return AgentSignal(
                agent_name=self.name,
                asset=snapshot.symbol,
                signal=SignalType.NO_TRADE,
                confidence=0.5,
                invalidation="Insufficient candles",
                evidence=["Less than 30 candles available"],
            )

        closes = pd.Series([c.close for c in candles])
        rsi_series = calculate_rsi(closes, period=14)
        rsi = float(rsi_series.iloc[-1])

        # MACD
        ema12 = closes.ewm(span=12, adjust=False).mean()
        ema26 = closes.ewm(span=26, adjust=False).mean()
        macd_line = ema12 - ema26
        signal_line = macd_line.ewm(span=9, adjust=False).mean()
        last_macd = float(macd_line.iloc[-1])
        last_signal = float(signal_line.iloc[-1])
        prev_macd = float(macd_line.iloc[-2])
        prev_signal = float(signal_line.iloc[-2])

        evidence = [
            f"RSI(14): {rsi:.1f}",
            f"MACD: {last_macd:.2f}, Signal: {last_signal:.2f}",
        ]

        # Conditions
        if rsi < 32 and (last_macd > prev_macd):
            evidence.append("Oversold RSI with rising MACD momentum (Bullish Rebound)")
            return AgentSignal(
                agent_name=self.name,
                asset=snapshot.symbol,
                signal=SignalType.LONG,
                confidence=0.78,
                expected_return=0.030,
                expected_risk=0.015,
                time_horizon="2H-8H",
                invalidation=f"RSI falls deeper below 25 or price makes lower low",
                evidence=evidence,
            )
        elif rsi > 70 and (last_macd < prev_macd):
            evidence.append("Overbought RSI with turning MACD (Bearish Exhaustion)")
            return AgentSignal(
                agent_name=self.name,
                asset=snapshot.symbol,
                signal=SignalType.SHORT,
                confidence=0.76,
                expected_return=0.030,
                expected_risk=0.015,
                time_horizon="2H-8H",
                invalidation="RSI pushes above 78 continuing parabolic move",
                evidence=evidence,
            )
        elif last_macd > last_signal and prev_macd <= prev_signal:
            evidence.append("MACD Bullish Crossover")
            return AgentSignal(
                agent_name=self.name,
                asset=snapshot.symbol,
                signal=SignalType.LONG,
                confidence=0.70,
                expected_return=0.025,
                expected_risk=0.012,
                time_horizon="4H",
                invalidation="MACD recrosses below signal line",
                evidence=evidence,
            )
        elif last_macd < last_signal and prev_macd >= prev_signal:
            evidence.append("MACD Bearish Crossover")
            return AgentSignal(
                agent_name=self.name,
                asset=snapshot.symbol,
                signal=SignalType.SHORT,
                confidence=0.70,
                expected_return=0.025,
                expected_risk=0.012,
                time_horizon="4H",
                invalidation="MACD recrosses above signal line",
                evidence=evidence,
            )

        return AgentSignal(
            agent_name=self.name,
            asset=snapshot.symbol,
            signal=SignalType.NO_TRADE,
            confidence=0.55,
            invalidation="Momentum in mid-range (35 < RSI < 65)",
            evidence=evidence + ["No momentum extreme or trigger"],
        )
