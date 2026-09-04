"""Base models and abstract interface for Strategy and Meta Agents."""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from pydantic import BaseModel, Field

from src.data.base import MarketSnapshot


class SignalType(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"
    EXIT = "EXIT"
    NO_TRADE = "NO_TRADE"


class AgentSignal(BaseModel):
    """Standardized Signal JSON output format required by CryptoAID Trade AI."""
    agent_name: str
    asset: str
    signal: SignalType
    confidence: float = Field(ge=0.0, le=1.0)
    expected_return: float | None = None
    expected_risk: float | None = None
    time_horizon: str = "4H"
    invalidation: str = ""
    evidence: list[str] = Field(default_factory=list)
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump()


class BaseStrategyAgent(ABC):
    """Abstract Strategy Agent interface."""

    def __init__(self, name: str, weight: float = 1.0) -> None:
        self.name = name
        self.weight = weight

    @abstractmethod
    def evaluate(self, snapshot: MarketSnapshot) -> AgentSignal:
        """Analyze market snapshot and return standardized AgentSignal."""
        pass
