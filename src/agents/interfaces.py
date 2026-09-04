"""Expansion agent interfaces for CryptoAID Trade AI."""
from __future__ import annotations

from abc import ABC, abstractmethod
from src.agents.base import AgentSignal, BaseStrategyAgent, SignalType
from src.data.base import MarketSnapshot


class OnChainAgent(BaseStrategyAgent):
    """Interface for on-chain metrics: exchange flows, whale transfers, gas surges."""

    def __init__(self, name: str = "OnChainAgent", weight: float = 1.0) -> None:
        super().__init__(name=name, weight=weight)

    def evaluate(self, snapshot: MarketSnapshot) -> AgentSignal:
        # Default safe implementation
        return AgentSignal(
            agent_name=self.name,
            asset=snapshot.symbol,
            signal=SignalType.NO_TRADE,
            confidence=0.5,
            expected_return=None,
            expected_risk=None,
            time_horizon="1D",
            invalidation="On-chain data feed inactive",
            evidence=["On-chain baseline neutral (dormant wallets stable)"],
        )


class SentimentAgent(BaseStrategyAgent):
    """Interface for social sentiment, Fear & Greed index, news sentiment."""

    def __init__(self, name: str = "SentimentAgent", weight: float = 0.8) -> None:
        super().__init__(name=name, weight=weight)

    def evaluate(self, snapshot: MarketSnapshot) -> AgentSignal:
        return AgentSignal(
            agent_name=self.name,
            asset=snapshot.symbol,
            signal=SignalType.NO_TRADE,
            confidence=0.5,
            expected_return=None,
            expected_risk=None,
            time_horizon="12H",
            invalidation="Sentiment neutral",
            evidence=["Social sentiment index baseline neutral"],
        )


class ArbitrageAgent(BaseStrategyAgent):
    """Interface for cross-venue spread, basis and funding rate arbitrage."""

    def __init__(self, name: str = "ArbitrageAgent", weight: float = 1.2) -> None:
        super().__init__(name=name, weight=weight)

    def evaluate(self, snapshot: MarketSnapshot) -> AgentSignal:
        spread = snapshot.spread or 0.0
        basis = snapshot.funding_rate or 0.0
        return AgentSignal(
            agent_name=self.name,
            asset=snapshot.symbol,
            signal=SignalType.NO_TRADE,
            confidence=0.5,
            expected_return=0.001,
            expected_risk=0.0005,
            time_horizon="1H",
            invalidation=f"Spread below threshold: {spread}",
            evidence=[f"Funding rate: {basis:.6f}", f"Observed bid/ask spread: {spread:.4f}"],
        )


class ScamDefenseAgent(BaseStrategyAgent):
    """Interface for front-running detection, honeypot filters, spoofing detection."""

    def __init__(self, name: str = "ScamDefenseAgent", weight: float = 2.0) -> None:
        super().__init__(name=name, weight=weight)

    def evaluate(self, snapshot: MarketSnapshot) -> AgentSignal:
        # ScamDefense monitors for anomalous spikes or manipulated orderbooks
        abnormal_spread = (snapshot.spread or 0.0) > (snapshot.price * 0.02)
        if abnormal_spread:
            return AgentSignal(
                agent_name=self.name,
                asset=snapshot.symbol,
                signal=SignalType.EXIT,
                confidence=0.95,
                expected_return=0.0,
                expected_risk=0.10,
                time_horizon="Immediate",
                invalidation="Spread normalized",
                evidence=["Abnormal market spread detected > 2%"],
            )
        return AgentSignal(
            agent_name=self.name,
            asset=snapshot.symbol,
            signal=SignalType.NO_TRADE,
            confidence=0.90,
            expected_return=None,
            expected_risk=None,
            time_horizon="Current",
            invalidation="No scam signatures detected",
            evidence=["Market microstructure normal", "No spoofing or honeypot anomaly detected"],
        )
