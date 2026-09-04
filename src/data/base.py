"""Base models and abstract interface for Market Data Providers."""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any
from pydantic import BaseModel, Field


class Candle(BaseModel):
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float

    @property
    def hl2(self) -> float:
        return (self.high + self.low) / 2.0

    @property
    def hlc3(self) -> float:
        return (self.high + self.low + self.close) / 3.0


class TickerData(BaseModel):
    symbol: str
    price: float
    bid: float | None = None
    ask: float | None = None
    spread: float | None = None
    volume_24h: float = 0.0
    change_24h_pct: float = 0.0
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def last(self) -> float:
        return self.price


class MarketSnapshot(BaseModel):
    symbol: str
    price: float
    bid: float | None = None
    ask: float | None = None
    spread: float | None = None
    volume_24h: float = 0.0
    change_24h_pct: float = 0.0

    @property
    def last(self) -> float:
        return self.price
    volatility_24h: float = 0.0
    funding_rate: float | None = None
    open_interest: float | None = None
    candles_1h: list[Candle] = Field(default_factory=list)
    candles_4h: list[Candle] = Field(default_factory=list)
    candles_1d: list[Candle] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    provider: str = "unknown"


class BaseMarketDataProvider(ABC):
    """Abstract interface for all market data providers."""

    @abstractmethod
    def get_ticker(self, symbol: str) -> TickerData:
        """Fetch current ticker price, spread and 24h stats."""
        pass

    @abstractmethod
    def get_candles(self, symbol: str, timeframe: str = "1h", limit: int = 100) -> list[Candle]:
        """Fetch historical OHLCV candles."""
        pass

    @abstractmethod
    def get_snapshot(self, symbol: str) -> MarketSnapshot:
        """Fetch comprehensive market snapshot including volatility and multi-timeframe candles."""
        pass

    @abstractmethod
    def health(self) -> dict[str, Any]:
        """Return provider health status."""
        pass
