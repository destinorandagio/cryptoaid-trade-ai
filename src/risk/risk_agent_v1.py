"""Risk Agent V1 for TradeAID.

Enforces the 6-Stage Veto Hierarchy:
1. SYSTEM HEALTH: RPC/data/signer/Guardian healthy.
2. ASSET SAFETY: Contract/liquidity/scam/CryptoAid risk.
3. EXECUTION ECONOMICS: Predicted edge must survive gas + 0.3% fee + slippage + price impact.
4. PORTFOLIO RISK: Exposure cap and max concurrent positions.
5. DRAWDOWN STATE: Daily and global drawdown circuit breakers.
6. TRADE RISK: Volatility/ATR-adjusted sizing, dynamic stop loss, and hard 5% emergency ceiling.
"""
from __future__ import annotations

import logging
from enum import Enum
from typing import Any
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class RiskDecision(str, Enum):
    PASS = "PASS"
    REDUCE = "REDUCE"
    REJECT = "REJECT"
    EXIT_ALL = "EXIT_ALL"


class VetoStage(str, Enum):
    SYSTEM_HEALTH = "SYSTEM_HEALTH"
    ASSET_SAFETY = "ASSET_SAFETY"
    EXECUTION_ECONOMICS = "EXECUTION_ECONOMICS"
    PORTFOLIO_RISK = "PORTFOLIO_RISK"
    DRAWDOWN_STATE = "DRAWDOWN_STATE"
    TRADE_RISK = "TRADE_RISK"


class RiskEvaluationInput(BaseModel):
    equity: float = 1_000.0
    open_positions: list[dict[str, Any]] = Field(default_factory=list)
    asset: str = "POL/USDT"
    prediction: float = 0.015  # expected return (+1.5%)
    confidence: float = 0.75   # 0.0 to 1.0
    regime: str = "TRENDING_BULL"
    strategy: str = "MOMENTUM"
    volatility: float = 2.5    # 24h volatility % (e.g. 2.5%)
    liquidity: float = 250_000.0  # USD depth / volume
    slippage: float = 0.001    # 10 bps (0.1%)
    price_impact: float = 0.0005  # 5 bps (0.05%)
    gas: float = 0.02          # gas estimate in USD
    token_risk: dict[str, Any] = Field(default_factory=dict)
    current_drawdown_pct: float = 0.0  # e.g. 0.01 for 1%
    daily_loss_pct: float = 0.0        # e.g. 0.005 for 0.5%
    entry_price: float = 1.0
    is_scalp: bool = False
    system_healthy: bool = True
    account_tier: str = "BALANCED"     # SAFE | BALANCED | TURBO | GEM


class RiskEvaluationResult(BaseModel):
    decision: RiskDecision
    position_size_usdt: float = 0.0
    position_units: float = 0.0
    stop_loss_pct: float = 0.0
    stop_loss_price: float = 0.0
    take_profit_pct: float = 0.0
    take_profit_price: float = 0.0
    trailing_pct: float = 0.0
    max_hold_seconds: int = 1800
    reason: str = ""
    veto_stage: VetoStage | None = None
    veto_details: dict[str, Any] = Field(default_factory=dict)


class RiskAgentV1:
    """Quantitative Risk Guardian enforcing the 6-stage veto hierarchy."""

    # Portfolio Limits per account tier
    TIER_LIMITS = {
        "SAFE": {
            "max_positions": 3,
            "max_exposure_ratio": 0.25,
            "max_pos_ratio": 0.05,     # 5% max size ($50 on $1000)
            "daily_loss_limit": 0.02,  # 2% daily loss cap
            "max_dd_limit": 0.05,      # 5% max drawdown
            "min_confidence": 0.80,
            "emergency_stop_ceiling": 0.035, # 3.5%
        },
        "BALANCED": {
            "max_positions": 5,
            "max_exposure_ratio": 0.40,
            "max_pos_ratio": 0.10,     # 10% max size ($100 on $1000)
            "daily_loss_limit": 0.03,  # 3% daily loss cap
            "max_dd_limit": 0.08,      # 8% max drawdown
            "min_confidence": 0.70,
            "emergency_stop_ceiling": 0.05, # 5.0% HARD CEILING
        },
        "TURBO": {
            "max_positions": 8,
            "max_exposure_ratio": 0.60,
            "max_pos_ratio": 0.15,     # 15% max size ($150 on $1000)
            "daily_loss_limit": 0.05,  # 5% daily loss cap
            "max_dd_limit": 0.12,      # 12% max drawdown
            "min_confidence": 0.60,
            "emergency_stop_ceiling": 0.05, # 5.0% HARD CEILING
        },
        "GEM": {
            "max_positions": 10,
            "max_exposure_ratio": 0.30,
            "max_pos_ratio": 0.03,     # 3% max size ($30 on $1000)
            "daily_loss_limit": 0.04,  # 4% daily loss cap
            "max_dd_limit": 0.15,      # 15% max drawdown
            "min_confidence": 0.65,
            "emergency_stop_ceiling": 0.25, # Microcap gem threshold
        },
    }

    # Strategy Hold Durations (seconds)
    HOLD_DURATIONS = {
        "SCALP": 300,        # 5 minutes
        "MOMENTUM": 1800,    # 30 minutes
        "BREAKOUT": 3600,    # 1 hour
        "MEAN_REVERSION": 1200, # 20 minutes
        "TREND": 14400,      # 4 hours
        "GEM": 86400,        # 24 hours
    }

    def evaluate(self, inp: RiskEvaluationInput) -> RiskEvaluationResult:
        tier_cfg = self.TIER_LIMITS.get(inp.account_tier, self.TIER_LIMITS["BALANCED"])

        # =========================================================================
        # STAGE 1: SYSTEM HEALTH
        # =========================================================================
        if not inp.system_healthy:
            return RiskEvaluationResult(
                decision=RiskDecision.REJECT,
                reason="System Health Veto: RPC node latency or guardian anomaly detected",
                veto_stage=VetoStage.SYSTEM_HEALTH,
                veto_details={"system_healthy": False},
            )

        # =========================================================================
        # STAGE 2: ASSET SAFETY
        # =========================================================================
        # Liquidity Check
        min_liquidity = 15_000.0 if inp.account_tier == "GEM" else 50_000.0
        if inp.liquidity < min_liquidity:
            return RiskEvaluationResult(
                decision=RiskDecision.REJECT,
                reason=f"Asset Safety Veto: Pool liquidity ${inp.liquidity:,.0f} below safety threshold ${min_liquidity:,.0f}",
                veto_stage=VetoStage.ASSET_SAFETY,
                veto_details={"liquidity": inp.liquidity, "min_required": min_liquidity},
            )

        # Token Contract & Honeypot Check
        if inp.token_risk.get("is_honeypot", False) or inp.token_risk.get("scam_score", 0) > 40:
            return RiskEvaluationResult(
                decision=RiskDecision.REJECT,
                reason="Asset Safety Veto: Honeypot risk or scam signature detected in bytecode",
                veto_stage=VetoStage.ASSET_SAFETY,
                veto_details=inp.token_risk,
            )

        # =========================================================================
        # STAGE 3: EXECUTION ECONOMICS
        # =========================================================================
        # Predicted edge must survive DEX fee (0.3%), slippage, price impact, and gas
        dex_fee_ratio = 0.0030  # 0.30%
        nominal_test_size = inp.equity * tier_cfg["max_pos_ratio"]
        gas_ratio = inp.gas / nominal_test_size if nominal_test_size > 0 else 0.002
        total_costs_ratio = dex_fee_ratio + inp.slippage + inp.price_impact + gas_ratio

        # Probability-weighted expected edge
        expected_raw_edge = inp.prediction * inp.confidence
        margin_of_safety = 0.0015  # +15 bps buffer
        net_edge = expected_raw_edge - total_costs_ratio

        if net_edge < margin_of_safety:
            return RiskEvaluationResult(
                decision=RiskDecision.REJECT,
                reason=(
                    f"Execution Economics Veto: Net expected edge ({net_edge*100:+.2f}%) "
                    f"does not clear costs ({total_costs_ratio*100:.2f}%) + 15 bps buffer"
                ),
                veto_stage=VetoStage.EXECUTION_ECONOMICS,
                veto_details={
                    "expected_raw_edge_pct": round(expected_raw_edge * 100, 3),
                    "total_costs_pct": round(total_costs_ratio * 100, 3),
                    "net_edge_pct": round(net_edge * 100, 3),
                },
            )

        # Confidence Gate
        if inp.confidence < tier_cfg["min_confidence"]:
            return RiskEvaluationResult(
                decision=RiskDecision.REJECT,
                reason=f"Confidence Veto: Model confidence {inp.confidence*100:.1f}% below tier minimum {tier_cfg['min_confidence']*100:.1f}%",
                veto_stage=VetoStage.EXECUTION_ECONOMICS,
                veto_details={"confidence": inp.confidence, "min_confidence": tier_cfg["min_confidence"]},
            )

        # =========================================================================
        # STAGE 4: PORTFOLIO RISK
        # =========================================================================
        # Max open positions count
        if len(inp.open_positions) >= tier_cfg["max_positions"]:
            return RiskEvaluationResult(
                decision=RiskDecision.REJECT,
                reason=f"Portfolio Risk Veto: Max concurrent positions ({tier_cfg['max_positions']}) reached",
                veto_stage=VetoStage.PORTFOLIO_RISK,
                veto_details={"open_positions_count": len(inp.open_positions), "limit": tier_cfg["max_positions"]},
            )

        # Current total exposure calculation
        current_exposure = sum(p.get("size", 0.0) * p.get("entry", 0.0) for p in inp.open_positions)
        max_allowed_exposure = inp.equity * tier_cfg["max_exposure_ratio"]
        remaining_capacity = max(0.0, max_allowed_exposure - current_exposure)

        if remaining_capacity <= 5.0:  # Under $5 capacity
            return RiskEvaluationResult(
                decision=RiskDecision.REJECT,
                reason=f"Portfolio Risk Veto: Account exposure cap ${max_allowed_exposure:,.2f} saturated",
                veto_stage=VetoStage.PORTFOLIO_RISK,
                veto_details={"current_exposure": current_exposure, "cap": max_allowed_exposure},
            )

        # =========================================================================
        # STAGE 5: DRAWDOWN STATE
        # =========================================================================
        # Daily loss circuit breaker
        if inp.daily_loss_pct >= tier_cfg["daily_loss_limit"]:
            return RiskEvaluationResult(
                decision=RiskDecision.REJECT,
                reason=f"Drawdown State Veto: Daily loss limit {tier_cfg['daily_loss_limit']*100:.1f}% breached ({inp.daily_loss_pct*100:.2f}%)",
                veto_stage=VetoStage.DRAWDOWN_STATE,
                veto_details={"daily_loss_pct": inp.daily_loss_pct, "limit": tier_cfg["daily_loss_limit"]},
            )

        # Global drawdown circuit breaker
        if inp.current_drawdown_pct >= tier_cfg["max_dd_limit"]:
            return RiskEvaluationResult(
                decision=RiskDecision.EXIT_ALL,
                reason=f"Drawdown State Veto: Emergency Account Drawdown breached ({inp.current_drawdown_pct*100:.1f}% >= {tier_cfg['max_dd_limit']*100:.1f}%) — Halting all trading",
                veto_stage=VetoStage.DRAWDOWN_STATE,
                veto_details={"drawdown_pct": inp.current_drawdown_pct, "limit": tier_cfg["max_dd_limit"]},
            )

        # =========================================================================
        # STAGE 6: TRADE RISK & VOLATILITY-ADJUSTED SIZING
        # =========================================================================
        # Dynamic Stop Loss calculation (ATR / Volatility based)
        vol = max(0.5, inp.volatility)
        is_scalp = inp.is_scalp or inp.strategy.upper() == "SCALP"

        if is_scalp:
            # Scalp: tight stop 0.6% - 1.2%
            dynamic_stop_pct = min(0.012, max(0.006, (vol / 100.0) * 0.35))
        elif inp.account_tier == "GEM":
            # Gem: wider microcap boundary (max 25%)
            dynamic_stop_pct = 0.25
        else:
            # Standard: 1.5% - 3.5%
            dynamic_stop_pct = min(0.035, max(0.015, (vol / 100.0) * 0.60))

        # HARD 5% EMERGENCY STOP CEILING (Unless explicitly GEM account)
        hard_ceiling = tier_cfg["emergency_stop_ceiling"]
        if dynamic_stop_pct > hard_ceiling:
            dynamic_stop_pct = hard_ceiling

        # Position Sizing based on 1.0% Equity Risk Budget
        risk_budget_usdt = inp.equity * 0.01  # 1% risk per trade
        calculated_size_usdt = risk_budget_usdt / dynamic_stop_pct

        # Cap by tier max position size
        tier_max_size = inp.equity * tier_cfg["max_pos_ratio"]
        target_size_usdt = min(calculated_size_usdt, tier_max_size)

        # Cap by remaining exposure capacity
        decision = RiskDecision.PASS
        reason = "Pass: All 6 Risk Stages Cleared"

        if target_size_usdt > remaining_capacity:
            target_size_usdt = remaining_capacity
            decision = RiskDecision.REDUCE if target_size_usdt >= 10.0 else RiskDecision.REJECT
            if decision == RiskDecision.REDUCE:
                reason = "Reduce: Position size trimmed to stay within portfolio exposure ceiling"
            else:
                return RiskEvaluationResult(
                    decision=RiskDecision.REJECT,
                    reason="Portfolio Risk Veto: Insufficient exposure capacity for minimum viable trade ($10)",
                    veto_stage=VetoStage.PORTFOLIO_RISK,
                )

        target_size_usdt = round(target_size_usdt, 2)
        entry_p = max(0.000001, inp.entry_price)
        units = round(target_size_usdt / entry_p, 6)

        # Take-profit & Trailing calculations
        reward_risk_ratio = 2.0 if not is_scalp else 1.8
        take_profit_pct = dynamic_stop_pct * reward_risk_ratio
        trailing_pct = dynamic_stop_pct * 0.70

        stop_price = round(entry_p * (1.0 - dynamic_stop_pct), 6)
        tp_price = round(entry_p * (1.0 + take_profit_pct), 6)
        max_hold = self.HOLD_DURATIONS.get(inp.strategy.upper(), 1800)

        return RiskEvaluationResult(
            decision=decision,
            position_size_usdt=target_size_usdt,
            position_units=units,
            stop_loss_pct=round(dynamic_stop_pct, 4),
            stop_loss_price=stop_price,
            take_profit_pct=round(take_profit_pct, 4),
            take_profit_price=tp_price,
            trailing_pct=round(trailing_pct, 4),
            max_hold_seconds=max_hold,
            reason=reason,
            veto_stage=None,
            veto_details={
                "risk_budget_usdt": risk_budget_usdt,
                "dynamic_stop_pct": dynamic_stop_pct,
                "reward_risk_ratio": reward_risk_ratio,
                "net_edge_pct": round(net_edge * 100, 3),
            },
        )
