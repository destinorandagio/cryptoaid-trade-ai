"""Tests for Market Data Providers."""
import pytest
from src.data.base import Candle, MarketSnapshot, TickerData
from src.data.mock_feed import MockMarketDataProvider
from src.data.provider import CompositeMarketDataProvider


def test_mock_market_data_provider():
    provider = MockMarketDataProvider(seed=42)
    ticker = provider.get_ticker("BTC/USDC")
    assert isinstance(ticker, TickerData)
    assert ticker.symbol == "BTC/USDC"
    assert ticker.price > 0
    assert ticker.bid is not None and ticker.ask is not None
    assert ticker.bid <= ticker.ask

    candles = provider.get_candles("BTC/USDC", timeframe="1h", limit=50)
    assert len(candles) == 50
    assert isinstance(candles[0], Candle)
    assert candles[0].high >= candles[0].low

    snapshot = provider.get_snapshot("BTC/USDC")
    assert isinstance(snapshot, MarketSnapshot)
    assert snapshot.volatility_24h >= 0
    assert len(snapshot.candles_1h) == 60


def test_composite_provider_with_cache():
    provider = CompositeMarketDataProvider(cache_ttl_seconds=10, use_mock_fallback=True)
    t1 = provider.get_ticker("ETH/USDC")
    assert t1.symbol == "ETH/USDC"
    assert t1.price > 0

    # Ensure cached read works
    t2 = provider.get_ticker("ETH/USDC")
    assert t1.price == t2.price

    snapshot = provider.get_snapshot("SOL/USDC")
    assert snapshot.symbol == "SOL/USDC"
    assert len(snapshot.candles_1h) > 0
    assert provider.health()["status"] == "HEALTHY"
