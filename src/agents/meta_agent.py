"""Meta Agent Consensus Engine with Regime Awareness and Net Edge Calculation for CryptoAID Trade AI."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any
from pydantic import BaseModel, Field

from src.agents.base import AgentSignal, BaseStrategyAgent, SignalType
from src.agents.breakout import BreakoutAgent
from src.agents.mean_reversion import MeanReversionAgent
from src.agents.momentum import MomentumAgent
from src.agents.regime import MarketRegime, MarketRegimeDetector, RegimeAssessment
from src.agents.risk_agent import RiskAgent
from src.agents.scalp import ScalpingAgent
from src.agents.trend import TrendAgent
from src.agents.volatility import VolatilityAgent
from src.config import settings
from src.data.base import MarketSnapshot

logger = logging.getLogger(__name__)


class MetaDecision(BaseModel):
    asset: str
    decision: SignalType
    confidence: float = Field(ge=0.0, le=1.0)
    regime: MarketRegime = MarketRegime.RANGING
    expected_return: float | None = None
    expected_risk: float | None = None
    net_edge_pct: float = 0.0
    estimated_gas_usd: float = 0.015
    dex_fee_pct: float = 0.003
    slippage_pct: float = 0.002
    price_impact_pct: float = 0.001
    time_horizon: str = "4H"
    invalidation: str = ""
    evidence: list[str] = Field(default_factory=list)
    agent_signals: list[AgentSignal] = Field(default_factory=list)
    suitable_strategies: list[str] = Field(default_factory=list)
    entry_price: float
    recommended_stop_loss: float | None = None
    recommended_take_profit: float | None = None
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump()


class MetaAgent:
    """
    Multi-Strategy Consensus Engine.
    Coordinates Scalping, Trend, Momentum, Breakout, Mean Reversion, Volatility and Risk.
    Evaluates Regime and requires positive NET_EDGE before issuing any trade signal.
    """

    def __init__(
        self,
        agents: list[BaseStrategyAgent] | None = None,
        min_confidence_threshold: float = settings.min_confidence_threshold,
    ) -> None:
        self.regime_detector = MarketRegimeDetector()
        if agents is None:
            self.agents = [
                ScalpingAgent(weight=1.0),
                TrendAgent(weight=1.2),
                MomentumAgent(weight=1.1),
                MeanReversionAgent(weight=1.0),
                BreakoutAgent(weight=1.1),
                VolatilityAgent(weight=1.0),
                RiskAgent(weight=1.5),
            ]
        else:
            self.agents = agents
        self.min_confidence_threshold = min_confidence_threshold

    def evaluate(self, snapshot: MarketSnapshot, quote_data: dict[str, Any] | None = None) -> MetaDecision:
        """Run regime detection, query strategies, calculate net edge and reach consensus."""
        # Step 1: Detect Regime
        assessment: RegimeAssessment = self.regime_detector.detect(snapshot)
        regime = assessment.regime
        price = snapshot.price

        # Step 2: Gating on Regime - if LOW_LIQUIDITY or extreme RISK_OFF -> immediate NO_TRADE
        if regime == MarketRegime.LOW_LIQUIDITY:
            return MetaDecision(
                asset=snapshot.symbol,
                decision=SignalType.NO_TRADE,
                confidence=0.90,
                regime=regime,
                expected_return=0.0,
                expected_risk=0.0,
                net_edge_pct=0.0,
                time_horizon="None",
                invalidation="Market liquidity gate triggered",
                evidence=[
                    f"Regime: {regime.value} - Spread or 24h volume unacceptable.",
                    assessment.notes,
                ],
                suitable_strategies=[],
                entry_price=price,
            )

        # Step 3: Run registered agents
        agent_signals: list[AgentSignal] = []
        for agent in self.agents:
            try:
                sig = agent.evaluate(snapshot)
                agent_signals.append(sig)
            except Exception as exc:
                logger.error("Agent %s evaluation failed: %s", agent.name, exc)

        # Check for immediate safety exits from Risk Agent or any explicit EXIT signal
        exit_signals = [s for s in agent_signals if s.signal in (SignalType.EXIT, SignalType.SELL) and s.confidence >= 0.85]
        if exit_signals and (any(s.signal == SignalType.EXIT for s in exit_signals) or any("risk" in s.agent_name.lower() or "scam" in s.agent_name.lower() for s in exit_signals)):
            primary_exit = max(exit_signals, key=lambda x: x.confidence)
            return MetaDecision(
                asset=snapshot.symbol,
                decision=SignalType.EXIT,
                confidence=primary_exit.confidence,
                regime=regime,
                expected_return=0.0,
                expected_risk=primary_exit.expected_risk or 0.05,
                net_edge_pct=0.0,
                time_horizon="Immediate",
                invalidation=primary_exit.invalidation,
                evidence=[f"Safety exit enforced by {primary_exit.agent_name}: {primary_exit.evidence}"],
                agent_signals=agent_signals,
                suitable_strategies=assessment.suitable_strategies,
                entry_price=price,
                recommended_stop_loss=None,
                recommended_take_profit=None,
            )

        # Step 4: Weight agents based on suitability for current regime
        long_score = 0.0
        short_score = 0.0
        total_weight = 0.0

        for agent in self.agents:
            base_w = agent.weight
            # Boost weight if strategy is recommended for this regime
            matching = any(s.lower() in agent.name.lower() for s in assessment.suitable_strategies)
            effective_w = base_w * 1.3 if matching else base_w * 0.7
            total_weight += effective_w

            matching_sig = next((s for s in agent_signals if s.agent_name == agent.name), None)
            if matching_sig:
                if matching_sig.signal in (SignalType.BUY, SignalType.LONG):
                    long_score += matching_sig.confidence * effective_w
                elif matching_sig.signal in (SignalType.SELL, SignalType.SHORT):
                    short_score += matching_sig.confidence * effective_w

        normalized_long = long_score / total_weight if total_weight > 0 else 0.0
        normalized_short = short_score / total_weight if total_weight > 0 else 0.0

        # Step 5: Cost & Net Edge Calculation (Polygon DEX parameters)
        # Expected trade notional ~ $100 (10% of $1,000)
        trade_notional = 100.0
        gas_cost_usd = quote_data.get("estimated_gas_cost_usd", 0.015) if quote_data else 0.015
        gas_pct = gas_cost_usd / trade_notional
        dex_fee_pct = (settings.dex_fee_bps / 10_000.0) # e.g. 0.003 (0.30%)
        slippage_pct = (settings.simulated_slippage_bps / 10_000.0) # e.g. 0.0015 (0.15%)
        price_impact_pct = quote_data.get("price_impact_pct", 0.0008) if quote_data else 0.0008
        safety_buffer = 0.0025 # 0.25% required safety cushion

        # Dynamic stops & targets based on regime
        if regime == MarketRegime.LOW_VOLATILITY:
            sl_pct = 0.008  # 0.8% tight stop
            tp_pct = 0.018  # 1.8% target
            time_horizon = "15m-1H"
        elif regime == MarketRegime.HIGH_VOLATILITY:
            sl_pct = min(settings.emergency_stop_ceiling_pct, 0.025) # 2.5% stop, strictly <= 5% ceiling
            tp_pct = 0.055  # 5.5% target
            time_horizon = "4H-12H"
        else:
            sl_pct = settings.default_stop_loss_pct # 1.5%
            tp_pct = settings.default_take_profit_pct # 3.5%
            time_horizon = "1H-4H"

        # NET_EDGE formula:
        # NET_EDGE = EXPECTED_MOVE - GAS - FEES - PRICE_IMPACT - SLIPPAGE - SAFETY_BUFFER
        net_edge = tp_pct - gas_pct - dex_fee_pct - price_impact_pct - slippage_pct - safety_buffer

        # Step 6: Consensus and Gate checks
        if normalized_long >= self.min_confidence_threshold and normalized_long > (normalized_short + 0.12):
            if net_edge < settings.min_net_edge_pct:
                return MetaDecision(
                    asset=snapshot.symbol,
                    decision=SignalType.NO_TRADE,
                    confidence=round(normalized_long, 2),
                    regime=regime,
                    expected_return=tp_pct,
                    expected_risk=sl_pct,
                    net_edge_pct=round(net_edge, 5),
                    estimated_gas_usd=round(gas_cost_usd, 4),
                    dex_fee_pct=round(dex_fee_pct, 5),
                    slippage_pct=round(slippage_pct, 5),
                    price_impact_pct=round(price_impact_pct, 5),
                    time_horizon=time_horizon,
                    invalidation="Net edge below threshold after Polygon DEX costs",
                    evidence=[
                        f"Directional LONG signal detected with confidence {normalized_long:.2f}.",
                        f"GATED: Net edge ({net_edge*100:.3f}%) < Required ({settings.min_net_edge_pct*100:.2f}%).",
                        f"DEX Fee: {dex_fee_pct*100:.2f}%, Slippage: {slippage_pct*100:.2f}%, Gas: ${gas_cost_usd:.3f}",
                    ],
                    agent_signals=agent_signals,
                    suitable_strategies=assessment.suitable_strategies,
                    entry_price=price,
                )

            sl = round(price * (1.0 - sl_pct), 4 if price < 10 else 2)
            tp = round(price * (1.0 + tp_pct), 4 if price < 10 else 2)
            return MetaDecision(
                asset=snapshot.symbol,
                decision=SignalType.LONG,
                confidence=round(normalized_long, 2),
                regime=regime,
                expected_return=tp_pct,
                expected_risk=sl_pct,
                net_edge_pct=round(net_edge, 5),
                estimated_gas_usd=round(gas_cost_usd, 4),
                dex_fee_pct=round(dex_fee_pct, 5),
                slippage_pct=round(slippage_pct, 5),
                price_impact_pct=round(price_impact_pct, 5),
                time_horizon=time_horizon,
                invalidation=f"Price drops below stop loss at {sl}",
                evidence=[
                    f"Consensus BUY in regime {regime.value} with confidence {normalized_long:.2f}",
                    f"Positive net edge confirmed: {net_edge*100:+.3f}% net of gas/slippage/fees",
                    f"Recommended strategies: {', '.join(assessment.suitable_strategies)}",
                ],
                agent_signals=agent_signals,
                suitable_strategies=assessment.suitable_strategies,
                entry_price=price,
                recommended_stop_loss=sl,
                recommended_take_profit=tp,
            )

        # Default rule: No dominant consensus or insufficient edge -> NO_TRADE
        return MetaDecision(
            asset=snapshot.symbol,
            decision=SignalType.NO_TRADE,
            confidence=max(0.50, round(1.0 - abs(normalized_long - normalized_short), 2)),
            regime=regime,
            expected_return=None,
            expected_risk=None,
            net_edge_pct=0.0,
            estimated_gas_usd=round(gas_cost_usd, 4),
            dex_fee_pct=round(dex_fee_pct, 5),
            slippage_pct=round(slippage_pct, 5),
            price_impact_pct=round(price_impact_pct, 5),
            time_horizon="Session",
            invalidation="Signals remain mixed or below confidence threshold",
            evidence=[
                f"Regime: {regime.value}. No dominant consensus (LONG: {normalized_long:.2f}, SHORT: {normalized_short:.2f})",
                "Defaulting to safe state NO_TRADE to protect capital",
            ],
            agent_signals=agent_signals,
            suitable_strategies=assessment.suitable_strategies,
            entry_price=price,
            recommended_stop_loss=None,
            recommended_take_profit=None,
        )
