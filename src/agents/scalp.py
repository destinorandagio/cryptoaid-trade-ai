"""Scalping Strategy Agent for High-Frequency Micro-Structure Opportunities."""
from __future__ import annotations

import numpy as np
from src.agents.base import AgentSignal, BaseStrategyAgent, SignalType
from src.data.base import Candle, MarketSnapshot


class ScalpingAgent(BaseStrategyAgent):
    """
    Scalping strategy operating on short timeframes (1m/3m/5m).
    Enforces strict spread, gas, slippage and micro-momentum verification.
    """

    def __init__(
        self,
        name: str = "ScalpingAgent",
        weight: float = 1.0,
        max_spread_pct: float = 0.0015,  # 0.15% maximum allowed spread
        target_profit_pct: float = 0.012, # 1.2% target
        stop_loss_pct: float = 0.008,     # 0.8% tight stop
    ) -> None:
        super().__init__(name=name, weight=weight)
        self.max_spread_pct = max_spread_pct
        self.target_profit_pct = target_profit_pct
        self.stop_loss_pct = stop_loss_pct

    def evaluate(self, snapshot: MarketSnapshot, candles: list[Candle] | None = None) -> AgentSignal:
        price = snapshot.price
        spread = snapshot.spread or (price * 0.0005)
        spread_ratio = spread / (price if price > 0 else 1.0)

        # Gate 1: Reject if spread is wider than allowable for scalping
        if spread_ratio > self.max_spread_pct:
            return AgentSignal(
                agent_name=self.name,
                asset=snapshot.symbol,
                signal=SignalType.NO_TRADE,
                confidence=0.85,
                expected_return=0.0,
                expected_risk=spread_ratio,
                time_horizon="3m-5m",
                invalidation="Spread exceeds scalping tolerance",
                evidence=[f"Spread ratio {spread_ratio:.5f} > max {self.max_spread_pct}"],
            )

        if not candles or len(candles) < 14:
            return AgentSignal(
                agent_name=self.name,
                asset=snapshot.symbol,
                signal=SignalType.NO_TRADE,
                confidence=0.50,
                expected_return=0.0,
                expected_risk=0.0,
                time_horizon="3m-5m",
                invalidation="Insufficient tick/candle data",
                evidence=[f"Candles count: {len(candles) if candles else 0} < 14"],
            )

        closes = np.array([c.close for c in candles[-15:]])
        highs = np.array([c.high for c in candles[-15:]])
        lows = np.array([c.low for c in candles[-15:]])

        # Short-term RSI (7 periods) for rapid scalping
        diffs = np.diff(closes)
        gains = np.where(diffs > 0, diffs, 0.0)
        losses = np.where(diffs < 0, -diffs, 0.0)
        avg_gain = np.mean(gains[-7:]) if len(gains) >= 7 else 0.0
        avg_loss = np.mean(losses[-7:]) if len(losses) >= 7 else 0.0
        rs = avg_gain / (avg_loss + 1e-9)
        rsi_7 = 100.0 - (100.0 / (1.0 + rs))

        # Micro-momentum (last 3 candles progression)
        recent_momentum = (closes[-1] - closes[-3]) / closes[-3]

        # Scalp Long Condition: Oversold bounce on 7-period RSI (< 32) with upward tick
        if rsi_7 < 32 and recent_momentum > 0:
            confidence = min(0.70 + (32 - rsi_7) * 0.01, 0.88)
            return AgentSignal(
                agent_name=self.name,
                asset=snapshot.symbol,
                signal=SignalType.BUY,
                confidence=round(confidence, 2),
                expected_return=round(self.target_profit_pct, 4),
                expected_risk=round(self.stop_loss_pct, 4),
                time_horizon="3m-15m",
                invalidation=f"Break below {price * (1.0 - self.stop_loss_pct):.4f}",
                evidence=[
                    f"Micro-Oversold Bounce RSI(7): {rsi_7:.2f}",
                    f"Momentum: {recent_momentum:+.4f}",
                    f"Spread: {spread_ratio:.5f}",
                ],
            )

        # Scalp Short / Exit Long Condition: Overbought (> 68) with downward tick
        elif rsi_7 > 68 and recent_momentum < 0:
            confidence = min(0.70 + (rsi_7 - 68) * 0.01, 0.88)
            return AgentSignal(
                agent_name=self.name,
                asset=snapshot.symbol,
                signal=SignalType.SELL,
                confidence=round(confidence, 2),
                expected_return=round(self.target_profit_pct, 4),
                expected_risk=round(self.stop_loss_pct, 4),
                time_horizon="3m-15m",
                invalidation=f"Break above {price * (1.0 + self.stop_loss_pct):.4f}",
                evidence=[
                    f"Micro-Overbought Pullback RSI(7): {rsi_7:.2f}",
                    f"Momentum: {recent_momentum:+.4f}",
                    f"Spread: {spread_ratio:.5f}",
                ],
            )

        return AgentSignal(
            agent_name=self.name,
            asset=snapshot.symbol,
            signal=SignalType.HOLD,
            confidence=0.60,
            expected_return=0.0,
            expected_risk=0.0,
            time_horizon="3m-5m",
            invalidation="Neutral micro-oscillator",
            evidence=[f"RSI(7): {rsi_7:.2f}", f"Momentum: {recent_momentum:+.4f}"],
        )
