"""Market Regime Detector for CryptoAID Trade AI."""
from __future__ import annotations

from enum import Enum
import numpy as np
from pydantic import BaseModel, Field

from src.data.base import MarketSnapshot


class MarketRegime(str, Enum):
    TRENDING = "TRENDING"
    RANGING = "RANGING"
    HIGH_VOLATILITY = "HIGH_VOLATILITY"
    LOW_VOLATILITY = "LOW_VOLATILITY"
    LOW_LIQUIDITY = "LOW_LIQUIDITY"
    RISK_OFF = "RISK_OFF"


class RegimeAssessment(BaseModel):
    regime: MarketRegime
    confidence: float = Field(ge=0.0, le=1.0)
    volatility_pct: float
    trend_strength: float
    liquidity_score: float
    suitable_strategies: list[str]
    notes: str


class MarketRegimeDetector:
    """Classifies the market into operational regimes to guide strategy selection and risk."""

    def __init__(self, high_vol_threshold: float = 0.05, low_vol_threshold: float = 0.012) -> None:
        self.high_vol_threshold = high_vol_threshold
        self.low_vol_threshold = low_vol_threshold

    def detect(self, snapshot: MarketSnapshot) -> RegimeAssessment:
        vol = snapshot.volatility_24h or 0.02
        vol_ratio = vol / (snapshot.price if snapshot.price > 0 else 1.0)
        
        # Trend strength proxy from 24h change & high-low range
        change_pct = abs(snapshot.change_24h_pct or 0.0)
        spread = snapshot.spread or (snapshot.price * 0.001)
        spread_ratio = spread / (snapshot.price if snapshot.price > 0 else 1.0)
        volume = snapshot.volume_24h or 0.0

        # Regime evaluation hierarchy
        # 1. Check for Low Liquidity or Wide Spreads (Spread > 0.3% or very low volume)
        if spread_ratio > 0.003 or (volume < 50_000 and snapshot.price > 0):
            return RegimeAssessment(
                regime=MarketRegime.LOW_LIQUIDITY,
                confidence=0.88,
                volatility_pct=round(vol_ratio * 100, 2),
                trend_strength=round(change_pct, 2),
                liquidity_score=0.25,
                suitable_strategies=[],  # No strategies suitable in low liquidity
                notes="Wide spread or low 24h volume. Trading gated for safety.",
            )

        # 2. Check for Extreme Volatility / Risk-Off (Daily move > 10% or Volatility > 8%)
        if change_pct > 10.0 or vol_ratio > 0.08:
            return RegimeAssessment(
                regime=MarketRegime.HIGH_VOLATILITY,
                confidence=0.85,
                volatility_pct=round(vol_ratio * 100, 2),
                trend_strength=round(change_pct, 2),
                liquidity_score=0.80,
                suitable_strategies=["Breakout", "Volatility", "Trend"],
                notes="High volatility detected. Require wider profit targets and reduced sizing.",
            )

        # 3. Check for Strong Trend (Daily move > 3.5% with healthy volume)
        if change_pct >= 3.5:
            return RegimeAssessment(
                regime=MarketRegime.TRENDING,
                confidence=0.80,
                volatility_pct=round(vol_ratio * 100, 2),
                trend_strength=round(change_pct, 2),
                liquidity_score=0.90,
                suitable_strategies=["Trend", "Momentum", "Breakout"],
                notes="Directional expansion detected. Momentum and Trend following favored.",
            )

        # 4. Check for Low Volatility Compression (Volatility < 1.5% and change < 1.0%)
        if vol_ratio < self.low_vol_threshold and change_pct < 1.0:
            return RegimeAssessment(
                regime=MarketRegime.LOW_VOLATILITY,
                confidence=0.75,
                volatility_pct=round(vol_ratio * 100, 2),
                trend_strength=round(change_pct, 2),
                liquidity_score=0.85,
                suitable_strategies=["Scalping", "MeanReversion"],
                notes="Low volatility consolidation. Scalping and Mean Reversion active.",
            )

        # 5. Default Healthy Ranging Market
        return RegimeAssessment(
            regime=MarketRegime.RANGING,
            confidence=0.78,
            volatility_pct=round(vol_ratio * 100, 2),
            trend_strength=round(change_pct, 2),
            liquidity_score=0.90,
            suitable_strategies=["Scalping", "MeanReversion", "Momentum"],
            notes="Standard oscillating range. Scalping and mean reversion favored.",
        )
