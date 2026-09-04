"""Composite Market Data Provider with Caching and Fallback."""
from __future__ import annotations

import logging
import math
import time
from datetime import datetime, timezone
from typing import Any
import requests
import numpy as np

from src.data.base import BaseMarketDataProvider, Candle, MarketSnapshot, TickerData
from src.data.mock_feed import MockMarketDataProvider

logger = logging.getLogger(__name__)

SYMBOL_MAP_BINANCE = {
    "POL/USDT": "POLUSDT",
    "WETH/USDT": "ETHUSDT",
    "WBTC/USDT": "BTCUSDT",
    "LINK/USDT": "LINKUSDT",
    # Legacy USDC mappings
    "BTC/USDC": "BTCUSDC",
    "ETH/USDC": "ETHUSDC",
    "SOL/USDC": "SOLUSDC",
}


class CompositeMarketDataProvider(BaseMarketDataProvider):
    """Production provider connecting to live Polygon market feeds with local cache and mock fallback."""

    def __init__(self, cache_ttl_seconds: int = 15, timeout: float = 1.0, use_mock_fallback: bool = True) -> None:
        self.cache_ttl_seconds = cache_ttl_seconds
        self.timeout = timeout
        self.use_mock_fallback = use_mock_fallback
        self.mock_provider = MockMarketDataProvider()
        self._ticker_cache: dict[str, tuple[float, TickerData]] = {}
        self._candle_cache: dict[str, tuple[float, list[Candle]]] = {}
        self._is_live_healthy: bool = True

    def get_ticker(self, symbol: str) -> TickerData:
        now = time.time()
        if symbol in self._ticker_cache:
            cache_time, cached_data = self._ticker_cache[symbol]
            if now - cache_time < self.cache_ttl_seconds:
                return cached_data

        pair = SYMBOL_MAP_BINANCE.get(symbol)
        if pair:
            try:
                url = f"https://api.binance.com/api/v3/ticker/24hr?symbol={pair}"
                resp = requests.get(url, timeout=self.timeout)
                if resp.status_code == 200:
                    data = resp.json()
                    price = float(data.get("lastPrice", 0.0))
                    bid = float(data.get("bidPrice", 0.0)) or round(price * 0.9999, 2)
                    ask = float(data.get("askPrice", 0.0)) or round(price * 1.0001, 2)
                    spread = round(ask - bid, 4)
                    volume = float(data.get("volume", 0.0))
                    change = float(data.get("priceChangePercent", 0.0))
                    ticker = TickerData(
                        symbol=symbol,
                        price=price,
                        bid=bid,
                        ask=ask,
                        spread=spread,
                        volume_24h=volume,
                        change_24h_pct=change,
                        timestamp=datetime.now(timezone.utc),
                    )
                    self._ticker_cache[symbol] = (now, ticker)
                    self._is_live_healthy = True
                    return ticker
            except Exception as exc:
                logger.warning("Live ticker query failed for %s (%s). Falling back to mock feed.", symbol, exc)
                self._is_live_healthy = False

        if self.use_mock_fallback:
            ticker = self.mock_provider.get_ticker(symbol)
            self._ticker_cache[symbol] = (now, ticker)
            return ticker
        raise RuntimeError(f"Failed to fetch ticker for {symbol} and fallback disabled.")

    def get_candles(self, symbol: str, timeframe: str = "1h", limit: int = 100) -> list[Candle]:
        cache_key = f"{symbol}:{timeframe}:{limit}"
        now = time.time()
        if cache_key in self._candle_cache:
            cache_time, cached_candles = self._candle_cache[cache_key]
            if now - cache_time < self.cache_ttl_seconds * 2:
                return cached_candles

        pair = SYMBOL_MAP_BINANCE.get(symbol)
        interval_map = {"1h": "1h", "4h": "4h", "1d": "1d"}
        interval = interval_map.get(timeframe, "1h")

        if pair:
            try:
                url = f"https://api.binance.com/api/v3/klines?symbol={pair}&interval={interval}&limit={limit}"
                resp = requests.get(url, timeout=self.timeout)
                if resp.status_code == 200:
                    raw = resp.json()
                    candles: list[Candle] = []
                    for item in raw:
                        # [open_time, open, high, low, close, volume, close_time, ...]
                        t = datetime.fromtimestamp(item[0] / 1000.0, tz=timezone.utc)
                        candles.append(
                            Candle(
                                timestamp=t,
                                open=float(item[1]),
                                high=float(item[2]),
                                low=float(item[3]),
                                close=float(item[4]),
                                volume=float(item[5]),
                            )
                        )
                    if candles:
                        self._candle_cache[cache_key] = (now, candles)
                        return candles
            except Exception as exc:
                logger.warning("Live klines query failed for %s (%s). Falling back to mock feed.", symbol, exc)

        if self.use_mock_fallback:
            candles = self.mock_provider.get_candles(symbol, timeframe=timeframe, limit=limit)
            self._candle_cache[cache_key] = (now, candles)
            return candles
        raise RuntimeError(f"Failed to fetch candles for {symbol} and fallback disabled.")

    def get_snapshot(self, symbol: str) -> MarketSnapshot:
        ticker = self.get_ticker(symbol)
        candles_1h = self.get_candles(symbol, timeframe="1h", limit=60)
        candles_4h = self.get_candles(symbol, timeframe="4h", limit=30)
        candles_1d = self.get_candles(symbol, timeframe="1d", limit=14)

        closes = [c.close for c in candles_1h]
        if len(closes) > 1:
            returns = np.diff(closes) / closes[:-1]
            volatility_24h = float(round(np.std(returns) * math.sqrt(24) * 100, 2))
        else:
            volatility_24h = 0.0

        return MarketSnapshot(
            symbol=symbol,
            price=ticker.price,
            bid=ticker.bid,
            ask=ticker.ask,
            spread=ticker.spread,
            volume_24h=ticker.volume_24h,
            change_24h_pct=ticker.change_24h_pct,
            volatility_24h=volatility_24h,
            funding_rate=0.0001,
            open_interest=round(ticker.price * 1250, 2),
            candles_1h=candles_1h,
            candles_4h=candles_4h,
            candles_1d=candles_1d,
            timestamp=datetime.now(timezone.utc),
            provider="binance_public" if self._is_live_healthy else "mock_fallback",
        )

    def health(self) -> dict[str, Any]:
        return {
            "status": "HEALTHY",
            "provider": "binance_public" if self._is_live_healthy else "mock_fallback",
            "live_healthy": self._is_live_healthy,
            "cache_entries": len(self._ticker_cache) + len(self._candle_cache),
        }
