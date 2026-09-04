"""Unit tests for Strategy Agents."""
from src.agents.breakout import BreakoutAgent
from src.agents.mean_reversion import MeanReversionAgent
from src.agents.momentum import MomentumAgent
from src.agents.risk_agent import RiskAgent
from src.agents.trend import TrendAgent
from src.agents.volatility import VolatilityAgent
from src.data.mock_feed import MockMarketDataProvider


def test_strategy_agents_output_schema():
    provider = MockMarketDataProvider(seed=101, regime="trend_bull")
    snapshot = provider.get_snapshot("BTC/USDC")

    agents = [
        TrendAgent(),
        MomentumAgent(),
        MeanReversionAgent(),
        BreakoutAgent(),
        VolatilityAgent(),
        RiskAgent(),
    ]

    for agent in agents:
        sig = agent.evaluate(snapshot)
        assert sig.asset == "BTC/USDC"
        assert sig.agent_name == agent.name
        assert 0.0 <= sig.confidence <= 1.0
        assert sig.signal in ["LONG", "SHORT", "HOLD", "EXIT", "NO_TRADE"]
        assert isinstance(sig.evidence, list)
        assert len(sig.evidence) > 0
        assert sig.timestamp is not None
