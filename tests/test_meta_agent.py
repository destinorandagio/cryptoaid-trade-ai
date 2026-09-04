"""Unit tests for MetaAgent."""
from src.agents.base import AgentSignal, BaseStrategyAgent, SignalType
from src.agents.meta_agent import MetaAgent, MetaDecision
from src.data.mock_feed import MockMarketDataProvider


class DummyAgent(BaseStrategyAgent):
    def __init__(self, name: str, signal: SignalType, confidence: float, weight: float = 1.0):
        super().__init__(name, weight)
        self._signal = signal
        self._confidence = confidence

    def evaluate(self, snapshot):
        return AgentSignal(
            agent_name=self.name,
            asset=snapshot.symbol,
            signal=self._signal,
            confidence=self._confidence,
            evidence=["Dummy test signal"],
        )


def test_meta_agent_consensus_long():
    provider = MockMarketDataProvider(seed=42)
    snapshot = provider.get_snapshot("BTC/USDC")

    agents = [
        DummyAgent("Agent1", SignalType.LONG, 0.90, weight=1.0),
        DummyAgent("Agent2", SignalType.LONG, 0.85, weight=1.0),
        DummyAgent("Agent3", SignalType.LONG, 0.80, weight=1.0),
    ]

    meta = MetaAgent(agents=agents, min_confidence_threshold=0.65)
    decision = meta.evaluate(snapshot)

    assert isinstance(decision, MetaDecision)
    assert decision.decision == SignalType.LONG
    assert decision.confidence >= 0.65
    assert decision.recommended_stop_loss is not None
    assert decision.recommended_take_profit is not None
    assert decision.recommended_stop_loss < decision.entry_price < decision.recommended_take_profit


def test_meta_agent_no_trade_default():
    provider = MockMarketDataProvider(seed=42)
    snapshot = provider.get_snapshot("ETH/USDC")

    # Conflicting / low-confidence agents -> should default to NO_TRADE
    agents = [
        DummyAgent("Agent1", SignalType.LONG, 0.60, weight=1.0),
        DummyAgent("Agent2", SignalType.SHORT, 0.60, weight=1.0),
        DummyAgent("Agent3", SignalType.HOLD, 0.50, weight=1.0),
    ]

    meta = MetaAgent(agents=agents, min_confidence_threshold=0.65)
    decision = meta.evaluate(snapshot)

    assert decision.decision == SignalType.NO_TRADE
    assert decision.recommended_stop_loss is None


def test_meta_agent_emergency_exit():
    provider = MockMarketDataProvider(seed=42)
    snapshot = provider.get_snapshot("SOL/USDC")

    agents = [
        DummyAgent("BullAgent", SignalType.LONG, 0.95, weight=1.0),
        DummyAgent("ScamOrRiskAgent", SignalType.EXIT, 0.92, weight=1.5),
    ]

    meta = MetaAgent(agents=agents, min_confidence_threshold=0.65)
    decision = meta.evaluate(snapshot)

    assert decision.decision == SignalType.EXIT
    assert decision.confidence >= 0.90
