"""Agents Module for CryptoAID Trade AI."""
from src.agents.base import AgentSignal, BaseStrategyAgent, SignalType
from src.agents.breakout import BreakoutAgent
from src.agents.mean_reversion import MeanReversionAgent
from src.agents.meta_agent import MetaAgent, MetaDecision
from src.agents.momentum import MomentumAgent
from src.agents.regime import MarketRegime, MarketRegimeDetector, RegimeAssessment
from src.agents.risk_agent import RiskAgent
from src.agents.scalp import ScalpingAgent
from src.agents.trend import TrendAgent
from src.agents.volatility import VolatilityAgent

__all__ = [
    "AgentSignal",
    "BaseStrategyAgent",
    "SignalType",
    "TrendAgent",
    "MomentumAgent",
    "MeanReversionAgent",
    "BreakoutAgent",
    "VolatilityAgent",
    "RiskAgent",
    "ScalpingAgent",
    "MarketRegime",
    "MarketRegimeDetector",
    "RegimeAssessment",
    "MetaAgent",
    "MetaDecision",
]
