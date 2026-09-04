"""Risk Strategy Agent for CryptoAID Trade AI."""
from __future__ import annotations

from src.agents.base import AgentSignal, BaseStrategyAgent, SignalType
from src.data.base import MarketSnapshot


class RiskAgent(BaseStrategyAgent):
    """Evaluates market liquidity, bid/ask spread stability, and structural tail risk."""

    def __init__(self, name: str = "RiskAgent", weight: float = 1.5) -> None:
        super().__init__(name=name, weight=weight)

    def evaluate(self, snapshot: MarketSnapshot) -> AgentSignal:
        spread = snapshot.spread or 0.0
        price = snapshot.price
        spread_bps = (spread / price) * 10_000.0 if price > 0 else 0.0
        volatility = snapshot.volatility_24h

        evidence = [
            f"Observed Spread: {spread:.4f} ({spread_bps:.1f} bps)",
            f"24h Volatility: {volatility:.2f}%",
            f"24h Volume: {snapshot.volume_24h:,.0f}",
        ]

        # Liquidity crunch or abnormal spread
        if spread_bps > 25.0:  # > 0.25% spread
            evidence.append(f"Spread blown out ({spread_bps:.1f} bps > 25 bps limit)")
            return AgentSignal(
                agent_name=self.name,
                asset=snapshot.symbol,
                signal=SignalType.EXIT,
                confidence=0.92,
                expected_return=0.0,
                expected_risk=0.05,
                time_horizon="Immediate",
                invalidation="Spread returns below 20 bps",
                evidence=evidence,
            )

        # Volatility spike above safe threshold
        if volatility > 15.0:
            evidence.append(f"Excessive market volatility ({volatility:.2f}% > 15%)")
            return AgentSignal(
                agent_name=self.name,
                asset=snapshot.symbol,
                signal=SignalType.NO_TRADE,
                confidence=0.88,
                expected_return=0.0,
                expected_risk=0.10,
                time_horizon="12H",
                invalidation="Volatility subsides below 10%",
                evidence=evidence,
            )

        evidence.append("Liquidity and spread conditions pass safety checks")
        return AgentSignal(
            agent_name=self.name,
            asset=snapshot.symbol,
            signal=SignalType.HOLD,
            confidence=0.85,
            expected_return=None,
            expected_risk=0.02,
            time_horizon="Session",
            invalidation="Spread or volatility spike occurs",
            evidence=evidence,
        )
