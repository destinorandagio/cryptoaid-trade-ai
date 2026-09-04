"""Polygon DEX Scanner and Liquidity Depth Analyzer for CryptoAID Trade AI."""
from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any
from pydantic import BaseModel, Field

from src.config import settings
from src.data.base import MarketSnapshot, TickerData
from src.data.provider import CompositeMarketDataProvider
from src.risk.cryptoaid_gate import CryptoAidRiskGate

logger = logging.getLogger(__name__)


class PolygonAssetMetrics(BaseModel):
    symbol: str
    token_address: str
    decimals: int
    price_usdt: float
    volume_24h: float
    liquidity_depth_usd: float
    spread_pct: float
    estimated_price_impact_100usd: float
    cryptoaid_risk_passed: bool
    risk_score: float
    is_tradable: bool
    rejection_reasons: list[str] = Field(default_factory=list)
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class PolygonDEXScanner:
    """Scans and scores Polygon DEX assets against liquidity, spread, price impact and risk gates."""

    def __init__(
        self,
        market_provider: CompositeMarketDataProvider | None = None,
        risk_gate: CryptoAidRiskGate | None = None,
    ) -> None:
        self.market_provider = market_provider or CompositeMarketDataProvider()
        self.risk_gate = risk_gate or CryptoAidRiskGate()
        self._scan_cache: dict[str, tuple[float, PolygonAssetMetrics]] = {}

    def scan_asset(self, symbol: str) -> PolygonAssetMetrics:
        """Scan a single Polygon asset through liquidity depth and CryptoAID risk gate."""
        now = time.time()
        if symbol in self._scan_cache:
            ts, cached = self._scan_cache[symbol]
            if now - ts < 15:  # 15s cache
                return cached

        token_base = symbol.split("/")[0]
        token_addr = settings.token_addresses.get(token_base, "0x0000000000000000000000000000000000000000")
        decimals = settings.token_decimals.get(token_base, 18)

        # Get market data snapshot
        try:
            ticker = self.market_provider.get_ticker(symbol)
            price = ticker.price
            spread = ticker.spread or (price * 0.0005)
            spread_pct = (spread / price) if price > 0 else 0.001
            volume_24h = ticker.volume_24h
        except Exception as exc:
            logger.warning("Error getting ticker for %s: %s", symbol, exc)
            price = 1.0
            spread_pct = 0.002
            volume_24h = 100_000.0

        # Estimate on-chain liquidity depth on Polygon
        # POL, WETH, WBTC on Polygon have deep pools ($5M - $50M+)
        liquidity_map = {
            "POL": 35_000_000.0,
            "WPOL": 35_000_000.0,
            "WETH": 85_000_000.0,
            "WBTC": 45_000_000.0,
            "LINK": 12_000_000.0,
        }
        liquidity_depth = liquidity_map.get(token_base, 1_000_000.0)

        # Price impact estimation for $100 trade size: trade_size / (2 * pool_depth)
        trade_size_usd = 100.0
        price_impact = min(trade_size_usd / (liquidity_depth * 0.1), 0.01)

        # Evaluate token security via CryptoAID Gate
        gate_res = self.risk_gate.contract_verifier.verify(token_addr, symbol)
        rejection_reasons: list[str] = []

        if not gate_res.is_verified:
            rejection_reasons.extend(gate_res.warnings)
        if spread_pct > 0.004:
            rejection_reasons.append(f"Spread {spread_pct*100:.2f}% exceeds max threshold 0.40%")
        if price_impact > settings.max_price_impact_pct:
            rejection_reasons.append(f"Price impact {price_impact*100:.3f}% exceeds max {settings.max_price_impact_pct*100:.2f}%")
        if volume_24h < 50_000:
            rejection_reasons.append(f"24h volume ${volume_24h:,.0f} below 50,000 threshold")

        is_tradable = (len(rejection_reasons) == 0) and gate_res.is_verified

        metrics = PolygonAssetMetrics(
            symbol=symbol,
            token_address=token_addr,
            decimals=decimals,
            price_usdt=round(price, 4 if price < 10 else 2),
            volume_24h=round(volume_24h, 2),
            liquidity_depth_usd=round(liquidity_depth, 2),
            spread_pct=round(spread_pct, 5),
            estimated_price_impact_100usd=round(price_impact, 5),
            cryptoaid_risk_passed=gate_res.is_verified,
            risk_score=gate_res.risk_score,
            is_tradable=is_tradable,
            rejection_reasons=rejection_reasons,
        )

        self._scan_cache[symbol] = (now, metrics)
        return metrics

    def scan_universe(self) -> list[PolygonAssetMetrics]:
        """Scan all universe assets and return rankings."""
        results: list[PolygonAssetMetrics] = []
        for symbol in settings.universe:
            metrics = self.scan_asset(symbol)
            results.append(metrics)
        # Sort tradable first, then by liquidity depth
        results.sort(key=lambda m: (m.is_tradable, m.liquidity_depth_usd), reverse=True)
        return results
