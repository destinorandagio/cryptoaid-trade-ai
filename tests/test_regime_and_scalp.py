"""Tests for Market Regime Detector, Scalping Strategy, and MetaStrategy Net Edge."""
from datetime import datetime, timezone
import pytest
from src.agents.regime import MarketRegime, MarketRegimeDetector
from src.agents.scalp import ScalpingAgent
from src.agents.meta_agent import MetaAgent
from src.data.base import Candle, MarketSnapshot


def test_regime_detector_classifications():
    detector = MarketRegimeDetector()

    # 1. Wide spread should detect LOW_LIQUIDITY
    snap_low_liq = MarketSnapshot(
        symbol="POL/USDT",
        price=0.32,
        spread=0.005,  # > 1.5% spread
        volume_24h=20_000.0,
        volatility_24h=0.01,
        timestamp=datetime.now(timezone.utc),
    )
    res_liq = detector.detect(snap_low_liq)
    assert res_liq.regime == MarketRegime.LOW_LIQUIDITY

    # 2. Huge daily move should detect HIGH_VOLATILITY
    snap_high_vol = MarketSnapshot(
        symbol="WETH/USDT",
        price=2500.0,
        spread=0.5,
        volume_24h=50_000_000.0,
        change_24h_pct=12.5,
        volatility_24h=150.0,
        timestamp=datetime.now(timezone.utc),
    )
    res_vol = detector.detect(snap_high_vol)
    assert res_vol.regime == MarketRegime.HIGH_VOLATILITY

    # 3. Solid directional move should detect TRENDING
    snap_trend = MarketSnapshot(
        symbol="WBTC/USDT",
        price=64000.0,
        spread=1.0,
        volume_24h=100_000_000.0,
        change_24h_pct=4.2,
        volatility_24h=500.0,
        timestamp=datetime.now(timezone.utc),
    )
    res_trend = detector.detect(snap_trend)
    assert res_trend.regime == MarketRegime.TRENDING


def test_scalping_agent_spread_gate():
    scalper = ScalpingAgent(max_spread_pct=0.0015)

    # Wide spread snapshot should immediately return NO_TRADE
    wide_snap = MarketSnapshot(
        symbol="POL/USDT",
        price=0.32,
        spread=0.002,  # > 0.15% max allowed
        timestamp=datetime.now(timezone.utc),
    )
    sig = scalper.evaluate(wide_snap)
    assert sig.signal.value == "NO_TRADE"
    assert "Spread exceeds" in sig.invalidation


def test_meta_agent_net_edge_calculation():
    meta = MetaAgent()

    snap = MarketSnapshot(
        symbol="POL/USDT",
        price=0.3250,
        spread=0.0001,
        volume_24h=25_000_000.0,
        change_24h_pct=1.2,
        volatility_24h=0.005,
        timestamp=datetime.now(timezone.utc),
    )

    decision = meta.evaluate(snap)
    assert decision.asset == "POL/USDT"
    assert decision.regime is not None
    assert decision.confidence >= 0.0
    assert decision.confidence <= 1.0
    # Expected net edge should be calculated
    assert hasattr(decision, "net_edge_pct")
