"""Deterministic Mock & Replay Market Data Feed for offline testing and backtesting."""
from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from typing import Any
import numpy as np

from src.data.base import BaseMarketDataProvider, Candle, MarketSnapshot, TickerData

BASE_PRICES = {
    "POL/USDT": 0.3250,
    "WETH/USDT": 2450.0,
    "WBTC/USDT": 63200.0,
    "LINK/USDT": 11.80,
    # Backward compatibility
    "BTC/USDC": 63200.0,
    "ETH/USDC": 2450.0,
    "SOL/USDC": 135.0,
}


class MockMarketDataProvider(BaseMarketDataProvider):
    """Generates realistic synthetic OHLCV candles, ticker and market snapshot."""

    def __init__(self, seed: int = 42, regime: str = "trend_bull") -> None:
        self.seed = seed
        self.regime = regime
        self.rng = np.random.default_rng(seed)

    def get_ticker(self, symbol: str) -> TickerData:
        base = BASE_PRICES.get(symbol, 100.0)
        noise = self.rng.normal(0, base * 0.002)
        price = round(base + noise, 2)
        half_spread = round(price * 0.0002, 2)
        bid = price - half_spread
        ask = price + half_spread
        spread = round(ask - bid, 2)
        volume = round(base * self.rng.uniform(500, 2000), 2)
        change = round(float(self.rng.normal(1.5 if "bull" in self.regime else -1.5, 2.0)), 2)

        return TickerData(
            symbol=symbol,
            price=price,
            bid=bid,
            ask=ask,
            spread=spread,
            volume_24h=volume,
            change_24h_pct=change,
            timestamp=datetime.now(timezone.utc),
        )

    def get_candles(self, symbol: str, timeframe: str = "1h", limit: int = 100) -> list[Candle]:
        base_price = BASE_PRICES.get(symbol, 100.0)
        minutes = 60 if timeframe == "1h" else (240 if timeframe == "4h" else 1440)
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(minutes=minutes * limit)

        # Drift based on regime
        drift = 0.0005 if "bull" in self.regime else (-0.0005 if "bear" in self.regime else 0.0)
        vol = 0.008

        prices = [base_price]
        for _ in range(limit):
            shock = self.rng.normal(drift, vol)
            p = max(1.0, prices[-1] * (1.0 + shock))
            prices.append(p)

        candles: list[Candle] = []
        for i in range(limit):
            t = start_time + timedelta(minutes=minutes * i)
            o = prices[i]
            c = prices[i + 1]
            wiggle_high = abs(self.rng.normal(0, vol * o))
            wiggle_low = abs(self.rng.normal(0, vol * o))
            h = max(o, c) + wiggle_high
            l = min(o, c) - wiggle_low
            v = float(round(base_price * self.rng.uniform(10, 50), 2))
            candles.append(
                Candle(
                    timestamp=t,
                    open=round(o, 2),
                    high=round(h, 2),
                    low=round(l, 2),
                    close=round(c, 2),
                    volume=v,
                )
            )
        return candles

    def get_snapshot(self, symbol: str) -> MarketSnapshot:
        ticker = self.get_ticker(symbol)
        candles_1h = self.get_candles(symbol, timeframe="1h", limit=60)
        candles_4h = self.get_candles(symbol, timeframe="4h", limit=30)
        candles_1d = self.get_candles(symbol, timeframe="1d", limit=14)

        closes = [c.close for c in candles_1h]
        returns = np.diff(closes) / closes[:-1] if len(closes) > 1 else [0.0]
        volatility_24h = float(round(np.std(returns) * math.sqrt(24) * 100, 2))

        return MarketSnapshot(
            symbol=symbol,
            price=ticker.price,
            bid=ticker.bid,
            ask=ticker.ask,
            spread=ticker.spread,
            volume_24h=ticker.volume_24h,
            change_24h_pct=ticker.change_24h_pct,
            volatility_24h=volatility_24h,
            funding_rate=0.0001,  # 0.01%
            open_interest=round(ticker.price * 1500, 2),
            candles_1h=candles_1h,
            candles_4h=candles_4h,
            candles_1d=candles_1d,
            timestamp=datetime.now(timezone.utc),
            provider="mock_replay",
        )

    def health(self) -> dict[str, Any]:
        return {
            "status": "HEALTHY",
            "provider": "mock_replay",
            "symbols_supported": list(BASE_PRICES.keys()),
            "regime": self.regime,
        }
