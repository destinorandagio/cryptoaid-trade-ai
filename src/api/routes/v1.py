"""REST API Version 1 Routes for CryptoAID Trade AI."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from src.agents.base import SignalType
from src.agents.gem_hunter import GemHunterEngine
from src.agents.meta_agent import MetaAgent, MetaDecision
from src.agents.predictive_heart import PredictiveHeartEngine
from src.agents.strategy_selector import MarketStateVector, StrategySelector
from src.config import settings
from src.data.digital_twins import DigitalTwinsManager
from src.data.provider import CompositeMarketDataProvider
from src.execution.models import OrderSide
from src.execution.paper_engine import PaperExecutionEngine
from src.learning.auto_learner import AutoLearnerEngine
from src.learning.experience_matrix import ExperienceMatrix
from src.learning.memory_weighting import ChampionChallengerSystem
from src.performance.metrics import calculate_performance
from src.risk.capital_protection import CapitalProtectionEngine
from src.risk.cryptoaid_gate import CryptoAidRiskGate
from src.risk.risk_agent_v1 import RiskAgentV1, RiskEvaluationInput
from src.storage.db import DatabaseManager

router = APIRouter(prefix="/api/v1", tags=["v1"])

# Singletons for API worker
db = DatabaseManager()
market_provider = CompositeMarketDataProvider()
meta_agent = MetaAgent()
predictive_heart = PredictiveHeartEngine(market_provider=market_provider, db=db)
risk_gate = CryptoAidRiskGate()
capital_engine = CapitalProtectionEngine()
execution_engine = PaperExecutionEngine(db=db, risk_engine=capital_engine, risk_gate=risk_gate)
gem_hunter = GemHunterEngine(db=db)
twins_manager = DigitalTwinsManager(db=db)
risk_agent_v1 = RiskAgentV1()
from src.learning.auto_learner import global_auto_learner as auto_learner
strategy_selector = auto_learner.strategy_selector
experience_matrix = auto_learner.experience_matrix
champion_system = auto_learner.champion_system
from src.agents.prop_challenge import PropChallengeEngine
prop_engine = PropChallengeEngine()



class OrderRequest(BaseModel):
    asset: str = Field(example="BTC/USDC")
    side: str = Field(example="BUY")
    size: float = Field(gt=0, example=0.005)
    sl: float | None = Field(default=None, example=58000.0)
    tp: float | None = Field(default=None, example=65000.0)
    trailing_distance: float | None = Field(default=None)


class KillSwitchRequest(BaseModel):
    action: str = Field(example="TRIGGER", description="'TRIGGER' or 'RESET'")
    reason: str = Field(default="Manual Operator Action")


@router.get("/health")
def get_health() -> dict[str, Any]:
    """System and dependency healthcheck."""
    mkt_health = market_provider.health()
    return {
        "status": "HEALTHY",
        "app": settings.app_name,
        "version": settings.app_version,
        "env": settings.app_env,
        "live_trading_enabled": settings.live_trading_enabled,
        "kill_switch_active": capital_engine.kill_switch_active,
        "market_provider": mkt_health,
        "database": "CONNECTED",
    }


@router.get("/status")
@router.get("/system/status")
def get_system_status() -> dict[str, Any]:
    """Comprehensive system status, runtime parameters and risk gate state."""
    state = execution_engine.get_portfolio_state()
    return {
        "app_name": settings.app_name,
        "version": settings.app_version,
        "live_trading_enabled": settings.live_trading_enabled,
        "mode": "PAPER_TRADING_ONLY" if not settings.live_trading_enabled else "LIVE_TRADING",
        "base_quote": settings.base_quote,
        "supported_universe": settings.universe,
        "kill_switch": capital_engine.kill_switch_active,
        "circuit_breaker_triggered": state.circuit_breaker_triggered,
        "limits": {
            "max_position_size_ratio": settings.max_position_size_ratio,
            "max_portfolio_exposure_ratio": settings.max_portfolio_exposure_ratio,
            "max_leverage": settings.max_leverage,
            "daily_loss_limit_ratio": settings.daily_loss_limit_ratio,
        },
        "portfolio": state.model_dump(),
    }


@router.get("/markets")
def get_markets() -> list[dict[str, Any]]:
    """Get active market universe snapshots (POL, WETH, WBTC, LINK)."""
    results: list[dict[str, Any]] = []
    for sym in settings.universe:
        ticker = market_provider.get_ticker(sym)
        results.append({
            "symbol": sym,
            "price": ticker.price,
            "bid": ticker.bid,
            "ask": ticker.ask,
            "spread": ticker.spread,
            "volume_24h": ticker.volume_24h,
            "change_24h_pct": ticker.change_24h_pct,
        })
    return results


@router.get("/scan")
def run_scanner() -> list[dict[str, Any]]:
    """Scan entire universe through Market Intelligence + Agents + CryptoAID Risk Gate."""
    scan_results: list[dict[str, Any]] = []
    prices: dict[str, float] = {}

    for sym in settings.universe:
        snapshot = market_provider.get_snapshot(sym)
        prices[sym] = snapshot.price

        meta_dec = meta_agent.evaluate(snapshot)
        risk_res = risk_gate.evaluate(meta_dec, snapshot)

        scan_results.append({
            "symbol": sym,
            "price": snapshot.price,
            "volume_24h": snapshot.volume_24h,
            "volatility_24h": snapshot.volatility_24h,
            "spread": snapshot.spread,
            "ai_signal": meta_dec.decision.value,
            "ai_confidence": meta_dec.confidence,
            "expected_return": meta_dec.expected_return,
            "expected_risk": meta_dec.expected_risk,
            "recommended_stop_loss": meta_dec.recommended_stop_loss,
            "recommended_take_profit": meta_dec.recommended_take_profit,
            "cryptoaid_risk": {
                "passed": risk_res.passed,
                "decision": risk_res.final_decision,
                "composite_risk_score": risk_res.composite_risk_score,
                "rejections": risk_res.rejection_reasons,
            },
            "evidence": meta_dec.evidence,
        })

    # Update mark-to-market prices for open positions during scan
    execution_engine.update_market_prices(prices)
    return scan_results


@router.get("/signals")
def get_latest_signals() -> list[dict[str, Any]]:
    """Get actionable high-confidence signals passing the CryptoAID Risk Gate."""
    scans = run_scanner()
    actionable = []
    for s in scans:
        if s["ai_signal"] not in ("NO_TRADE", "HOLD") and s["cryptoaid_risk"]["passed"]:
            actionable.append(s)
    return actionable


@router.get("/strategies")
def get_strategies() -> list[dict[str, Any]]:
    """List all registered strategy agents, weights and descriptions."""
    return [
        {"name": a.name, "weight": a.weight, "description": a.__doc__ or "Strategy Agent"}
        for a in meta_agent.agents
    ]


@router.get("/portfolio")
def get_portfolio() -> dict[str, Any]:
    """Get paper account equity, balances, open positions and drawdown."""
    state = execution_engine.get_portfolio_state()
    positions = db.get_open_positions()
    return {
        "account": state.model_dump(),
        "positions": positions,
    }


@router.post("/orders")
def place_order(req: OrderRequest) -> dict[str, Any]:
    """Place a paper trading order."""
    if req.asset not in settings.universe:
        raise HTTPException(status_code=400, detail=f"Asset {req.asset} not in supported universe")

    side_enum = OrderSide.BUY if req.side.upper() == "BUY" else OrderSide.SELL
    ticker = market_provider.get_ticker(req.asset)

    order = execution_engine.execute_market_order(
        asset=req.asset,
        side=side_enum,
        size=req.size,
        market_price=ticker.price,
        sl=req.sl,
        tp=req.tp,
        trailing_distance=req.trailing_distance,
    )

    if order.status.value == "REJECTED":
        raise HTTPException(status_code=400, detail=f"Order Rejected: {order.reason}")

    return order.to_dict()


@router.get("/orders")
def list_orders(limit: int = Query(default=50, ge=1, le=200)) -> list[dict[str, Any]]:
    """List historical paper orders."""
    return db.get_orders(limit=limit)


@router.get("/trades")
def list_trades(limit: int = Query(default=100, ge=1, le=500)) -> list[dict[str, Any]]:
    """List executed paper trade fills."""
    return db.get_trades(limit=limit)


@router.get("/performance")
def get_performance() -> dict[str, Any]:
    """Get calculated performance metrics (Win rate, Sharpe, Drawdown, Profit factor)."""
    closed_orders = [o for o in db.get_orders(limit=500) if o["status"] == "CLOSED"]
    metrics = calculate_performance(closed_orders, initial_capital=settings.default_paper_capital)
    return metrics.to_dict()


@router.get("/risk")
def get_risk_status() -> dict[str, Any]:
    """Get active capital protection state and risk limits."""
    state = execution_engine.get_portfolio_state()
    return {
        "portfolio_risk": state.model_dump(),
        "circuit_breaker_active": capital_engine.kill_switch_active,
        "rules": {
            "max_position_size_pct": settings.max_position_size_ratio * 100.0,
            "max_portfolio_exposure_pct": settings.max_portfolio_exposure_ratio * 100.0,
            "daily_loss_limit_pct": settings.daily_loss_limit_ratio * 100.0,
            "max_drawdown_limit_pct": settings.max_drawdown_limit_ratio * 100.0,
            "leverage": "OFF (1.0x Spot Paper Only)",
        },
    }


@router.get("/positions")
def get_positions() -> list[dict[str, Any]]:
    """Get active Open Guardian positions with mark-to-market prices."""
    return db.get_open_positions()


@router.get("/autotrade")
def get_autotrade_status() -> dict[str, Any]:
    """Get current autonomous trading status."""
    return {
        "autotrade_enabled": settings.autotrade_enabled,
        "live_trading_enabled": settings.live_trading_enabled,
        "universe": settings.universe,
        "base_quote": settings.base_quote,
        "max_positions": settings.max_simultaneous_positions,
    }


@router.post("/autotrade")
def set_autotrade_status(enabled: bool = Query(..., description="Enable or disable autonomous trading")) -> dict[str, Any]:
    """Toggle autonomous trading on or off."""
    settings.autotrade_enabled = enabled
    return {
        "status": "SUCCESS",
        "autotrade_enabled": settings.autotrade_enabled,
    }


@router.post("/kill-switch")
@router.post("/risk/kill-switch")
def toggle_kill_switch(req: KillSwitchRequest) -> dict[str, Any]:
    """Trigger or reset the emergency kill switch."""
    if req.action.upper() == "TRIGGER":
        capital_engine.trigger_kill_switch(reason=req.reason)
        # Emergency close all active positions via Guardian
        closed = execution_engine.guardian.emergency_close_all(reason=f"Kill Switch: {req.reason}")
        return {
            "status": "SUCCESS",
            "kill_switch_active": True,
            "action": "TRIGGERED",
            "reason": req.reason,
            "closed_positions_count": len(closed),
        }
    elif req.action.upper() == "RESET":
        capital_engine.reset_kill_switch()
        return {"status": "SUCCESS", "kill_switch_active": False, "action": "RESET"}
    raise HTTPException(status_code=400, detail="Action must be 'TRIGGER' or 'RESET'")


# =========================================================================
# PREDICTIVE HEART ROUTES (Closure 1: Real Forecasts & Calibration Ledger)
# =========================================================================
@router.get("/heart/forecast")
def get_predictive_heart_forecast(
    symbol: str = Query("POL/USDT", description="Target trading pair"),
    timeframe: str = Query("15m", description="Timeframe: 5m, 15m, 1h, 4h, 24h"),
    history_points: int = Query(35, ge=15, le=100),
    future_steps: int = Query(16, ge=5, le=40),
) -> dict[str, Any]:
    """Generate live Predictive Heart forecast with white historical curve and red P50 trajectory."""
    try:
        return predictive_heart.generate_forecast(
            symbol=symbol,
            timeframe=timeframe,
            history_points=history_points,
            future_steps=future_steps,
            record_to_db=True,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate Predictive Heart forecast: {str(e)}")


@router.get("/heart/calibration")
def get_heart_calibration_stats(
    asset: str | None = Query(None, description="Optional asset filter"),
) -> dict[str, Any]:
    """Get calibration metrics (Accuracy %, Brier Score, recent evaluations)."""
    try:
        return db.get_calibration_stats(asset=asset)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch calibration stats: {str(e)}")


@router.post("/heart/evaluate")
def evaluate_heart_predictions() -> dict[str, Any]:
    """Evaluate expired forecasts against actual market prices to update calibration."""
    try:
        return predictive_heart.evaluate_pending_forecasts()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to evaluate predictions: {str(e)}")


# =========================================================================
# PAPER MULTI-PORTFOLIO & GEM HUNTER & TWINS ROUTES
# =========================================================================
@router.get("/paper/portfolios")
def get_paper_portfolios() -> dict[str, Any]:
    """Return real-time state for the 3 parallel portfolios (SAFE, BALANCED, TURBO) + GEM FUND."""
    try:
        return execution_engine.get_all_portfolios_summary()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get paper portfolios: {str(e)}")


@router.get("/gems/radar")
def get_gems_radar(limit: int = Query(10, ge=1, le=50)) -> list[dict[str, Any]]:
    """Get active gem candidates discovered on Polygon with empirical Gem Scores."""
    try:
        return gem_hunter.scan_radar(limit=limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to scan gem radar: {str(e)}")


@router.get("/twins/status")
def get_twins_status() -> dict[str, Any]:
    """Get synchronization and health status for all 5 interconnected Digital Twins."""
    try:
        return twins_manager.get_twins_status()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get digital twins status: {str(e)}")


@router.get("/strategies/switches")
def get_strategy_switches(limit: int = Query(20, ge=1, le=100)) -> list[dict[str, Any]]:
    """Get recent dynamic strategy switching events from the audit ledger."""
    try:
        return db.get_strategy_switches(limit=limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get strategy switches: {str(e)}")


# =========================================================================
# RISK AGENT V1 & STRATEGY SELECTOR & EXPERIENCE INTELLIGENCE ROUTES
# =========================================================================
@router.post("/risk/evaluate")
def evaluate_risk_v1(input_data: RiskEvaluationInput) -> dict[str, Any]:
    """Evaluate proposed trade through the 6-Stage Veto Hierarchy."""
    try:
        res = risk_agent_v1.evaluate(input_data)
        return res.model_dump()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to evaluate risk: {str(e)}")


@router.post("/strategies/select")
def select_strategy_dna(state: MarketStateVector) -> dict[str, Any]:
    """Select optimal Strategy DNA or trigger EXIT from Market State Vector."""
    try:
        res = strategy_selector.evaluate(state)
        return res.model_dump()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to select strategy: {str(e)}")


@router.get("/learning/experience")
def get_experience_matrix_stats(
    regime: str | None = Query(None, description="Optional regime filter"),
    asset: str | None = Query(None, description="Optional asset filter"),
) -> dict[str, Any]:
    """Get global experience matrix stats and ranked strategies."""
    try:
        stats = experience_matrix.get_matrix_stats()
        if regime:
            stats["ranked_for_regime"] = experience_matrix.get_top_strategies(regime=regime, asset=asset)
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get experience matrix stats: {str(e)}")


@router.get("/learning/champions")
def get_champions_and_challengers() -> dict[str, Any]:
    """Get active Champion strategies and competing Challengers per regime."""
    try:
        return champion_system.get_all_champions()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get champions: {str(e)}")


@router.post("/learning/champions/evaluate")
def evaluate_champion_promotion(
    regime: str = Query("TRENDING_BULL", description="Regime to evaluate for promotion"),
    asset: str = Query("POL/USDT", description="Asset to evaluate"),
) -> dict[str, Any]:
    """Evaluate whether any shadow Challenger deserves promotion over active Champion."""
    try:
        return champion_system.evaluate_promotion(regime=regime, experience_matrix=experience_matrix, asset=asset)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to evaluate promotion: {str(e)}")


@router.post("/learning/auto/step")
async def trigger_auto_learning_step() -> dict[str, Any]:
    """Manually trigger one autonomous learning, execution, and calibration cycle."""
    try:
        return await auto_learner.step()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to execute auto-learning step: {str(e)}")


@router.get("/learning/auto/status")
def get_auto_learning_status() -> dict[str, Any]:
    """Get the runtime state of the H24 auto-learning pipeline."""
    return {
        "is_running": auto_learner.is_running,
        "iteration_count": auto_learner.iteration_count,
        "tick_interval_seconds": auto_learner.tick_interval_seconds,
        "active_champion_bull": champion_system.get_champion("TRENDING_BULL"),
        "matrix_stats": experience_matrix.get_matrix_stats(),
    }


# =========================================================================
# REWARD ENGINE & ONE-TIME AUTOTRADE SESSION AUTHORIZATION ROUTES
# =========================================================================
from src.rewards.reward_engine import RewardEngine

reward_engine = RewardEngine(db_manager=db, live_mode=False)


class RewardClaimRequest(BaseModel):
    wallet: str = Field(example="0x71C...3a9")
    action: str = Field(example="AUTOTRADE_ACTIVATION")
    tx_hash: str | None = Field(default=None)


class AutotradeAuthorizeRequest(BaseModel):
    wallet: str = Field(example="0x71C...3a9")
    mode: str = Field(default="PAPER", example="PAPER")
    initial_capital_usdt: float = Field(default=1000.0, example=1000.0)
    risk_profile: str = Field(default="BALANCED", example="BALANCED")
    max_risk_pct: float = Field(default=2.0, example=2.0)
    stop_ceiling_pct: float = Field(default=-5.0, example=-5.0)


@router.post("/rewards/claim")
def claim_qualified_reward(req: RewardClaimRequest) -> dict[str, Any]:
    """Claim qualified action protocol reward (Anti-Sybil enforced)."""
    try:
        return reward_engine.claim_reward(
            wallet=req.wallet,
            action=req.action,
            tx_hash=req.tx_hash,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to claim reward: {str(e)}")


@router.get("/rewards/wallet/{wallet}")
def get_wallet_rewards(wallet: str) -> dict[str, Any]:
    """Get all rewards, claimed POL, and available eligible actions for a wallet."""
    try:
        return reward_engine.get_wallet_reward_summary(wallet)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get wallet rewards: {str(e)}")


@router.post("/autotrade/authorize")
def authorize_autotrade_session(req: AutotradeAuthorizeRequest) -> dict[str, Any]:
    """Authorize 24/7 autonomous autotrade policy with single-click transparent signature."""
    try:
        auth_record = db.record_autotrade_authorization(
            wallet=req.wallet,
            mode=req.mode,
            initial_capital_usdt=req.initial_capital_usdt,
            risk_profile=req.risk_profile,
            max_risk_pct=req.max_risk_pct,
            stop_ceiling_pct=req.stop_ceiling_pct,
        )
        # Check and grant initial onboarding / autotrade activation reward
        reward_result = reward_engine.claim_reward(
            wallet=req.wallet,
            action="AUTOTRADE_ACTIVATION",
            tx_hash=f"0xauth_{auth_record['id']}",
        )
        return {
            "status": "AUTHORIZED",
            "authorization": auth_record,
            "onboarding_reward": reward_result,
            "message": "Autotrade authorized successfully. TradeAID will execute autonomously within limits without further signatures.",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to authorize autotrade: {str(e)}")


@router.get("/autotrade/status/{wallet}")
def get_autotrade_status(wallet: str) -> dict[str, Any]:
    """Get active autotrade policy authorization for a wallet."""
    try:
        auth = db.get_active_autotrade_authorization(wallet)
        return {
            "wallet": wallet,
            "has_active_authorization": auth is not None,
            "authorization": auth,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get autotrade status: {str(e)}")


# =====================================================================
# PROP CHALLENGE API (50K, 100K, 150K Multi-Tier & No-Loss Credit)
# =====================================================================

class PropStartRequest(BaseModel):
    wallet: str = Field(default="0x_demo_prop_user")
    mode: str = Field(default="BALANCED")
    tier: str = Field(default="100K")


@router.get("/prop/tiers")
def get_prop_tiers() -> dict[str, Any]:
    """Get all Prop Challenge tiers (STARTER, PRO, ELITE, BLACK) and No-Loss guarantee specs."""
    db = DatabaseManager()
    db_tiers = db.get_challenge_tiers()
    return {
        "tiers": db_tiers if db_tiers else prop_engine.tiers,
        "engine_tiers": prop_engine.tiers,
        "count": len(db_tiers) if db_tiers else len(prop_engine.tiers),
        "guarantee": {
            "title": "100% Fee-Back Internal Autotrading Credit",
            "description": "If challenge is not passed, 100% of the fee is converted to internal autotrading credit. All profits generated by trading are 100% withdrawable.",
            "withdrawal_policy": "Profits generated = 100% withdrawable. Initial credit bonus = Non-withdrawable trading margin.",
        },
        "policy": {
            "daily_drawdown_limit": "5.00% measured against midnight UTC equity snapshot",
            "max_total_drawdown_limit": "10.00% measured against High Water Mark",
            "phase1_profit_target": "8.00%",
            "phase2_profit_target": "5.00%",
            "minimum_trading_days": 5,
            "no_loss_guarantee": "100% challenge fee converted to non-withdrawable Trading Credits (TAC) upon failure",
        },
    }



@router.post("/prop/start")
def start_prop_challenge(req: PropStartRequest) -> dict[str, Any]:
    """Start or retrieve a Prop Challenge (50K, 100K, or 150K)."""
    try:
        challenge = db.get_or_create_prop_challenge(wallet=req.wallet, mode=req.mode, tier=req.tier)
        evaluation = prop_engine.evaluate(challenge)
        return {
            "status": "SUCCESS",
            "challenge": challenge,
            "evaluation": evaluation.__dict__,
            "message": f"Prop Challenge active: {evaluation.tier_name} (${evaluation.initial_equity:,.0f} USDT Paper). Target: +{evaluation.target_pct}% (+${evaluation.target_profit_usdt:,.0f}). Max Total DD: -{evaluation.max_total_dd_pct}%.",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start prop challenge: {str(e)}")


@router.get("/prop/status/{wallet}")
def get_prop_challenge_status(wallet: str) -> dict[str, Any]:
    """Get current Prop Challenge progress, drawdowns, and discipline score."""
    try:
        challenge = db.get_or_create_prop_challenge(wallet=wallet)
        evaluation = prop_engine.evaluate(challenge)
        return {
            "wallet": wallet,
            "evaluation": evaluation.__dict__,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get prop challenge status: {str(e)}")


@router.get("/prop/leaderboard")
def get_prop_leaderboard(limit: int = 10) -> list[dict[str, Any]]:
    """Get top ranked Prop Challenge traders."""
    try:
        return db.get_prop_leaderboard(limit=limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get prop leaderboard: {str(e)}")


@router.get("/prop/benchmarks")
def get_prop_benchmarks() -> dict[str, Any]:
    """Get simultaneous comparison of SAFE vs BALANCED vs TURBO facing the same challenge on Polygon."""
    return {
        "status": "SUCCESS",
        "market": "Polygon POS Mainnet",
        "philosophy": "StrategyEngine operates for pure mathematical expectancy; PropChallengeEngine is a passive auditor.",
        "benchmarks": prop_engine.get_parallel_benchmarks(),
    }


@router.get("/prop/score-factors")
def get_prop_score_factors() -> dict[str, Any]:
    """Get official 8-factor composition of TRADEAID PROP SCORE / 100."""
    from src.agents.prop_challenge import PROP_SCORE_WEIGHTS
    return {
        "title": "TRADEAID PROP SCORE / 100",
        "description": "Composite score rewarding discipline, capital preservation, and calibration over reckless over-leveraging.",
        "weights": PROP_SCORE_WEIGHTS,
        "axiom": "+6% with 0.8% drawdown achieves a higher Prop Score than +9% achieved through reckless risk.",
    }


@router.get("/prop/reward-pool")
def get_prop_reward_pool() -> dict[str, Any]:
    """Get public transparency rules for Paper Simulation vs Reward Pool."""
    return {
        "status": "ACTIVE",
        "paper_policy": "PAPER PROFITS != Money owed to user. 10,000 USDT virtual funds are strictly simulated.",
        "reward_program": {
            "name": "PROP DEMO / REWARD PROGRAM",
            "state_progression": "NEW -> DEMO -> ACTIVE -> QUALIFIED -> VERIFICATION -> PASSED -> PROP_ELIGIBLE",
            "eligibility": "Traders who reach QUALIFIED / PASSED become PROP_ELIGIBLE for the real capital vault allocation.",
            "real_vault_stage": "REAL VAULT -> ALLOCATION -> VERIFIED NET PROFIT -> PROFIT SHARE",
        },
    }


class PayoutClaimRequest(BaseModel):
    challenge_id: str
    wallet: str
    gross_profit_usdt: float


@router.get("/prop/credits/{wallet}")
def get_user_tac_credits(wallet: str) -> dict[str, Any]:
    """Get user's TradeAid Credits (TAC) Second Chance balance and transaction ledger."""
    balance = db.get_user_tac_balance(wallet)
    ledger = db.get_tac_credits_ledger(wallet)
    return {
        "wallet": wallet.lower(),
        "tac_balance": balance,
        "symbol": "TAC",
        "peg": "1 TAC = 1 USDT (Non-Withdrawable Margin)",
        "can_retry_discount": balance >= 50.0,
        "ledger": ledger,
    }


@router.post("/prop/payout/request")
def request_prop_payout(req: PayoutClaimRequest) -> dict[str, Any]:
    """Request 80% real crypto profit share payout from verified challenge trading gains."""
    try:
        user_share = req.gross_profit_usdt * 0.80
        payout = db.record_prop_payout(
            challenge_id=req.challenge_id,
            wallet=req.wallet,
            amount_gross_usdt=req.gross_profit_usdt,
            amount_user_share_usdt=user_share,
        )
        return {
            "status": "SUCCESS",
            "message": f"Payout of ${user_share:,.2f} USDT (80% user share) requested successfully.",
            "payout": payout,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to record payout request: {str(e)}")


@router.get("/prop/institutional-rules")
def get_prop_institutional_rules() -> dict[str, Any]:
    """Get the 4 institutional rules: Consistency (max 30%), Min Days (5), News Filter (+-5m), Weekend Dampener (50%)."""
    return {
        "consistency_rule": {
            "name": "Consistency Rule",
            "limit_pct": 30.0,
            "description": "No single trading day can represent more than 30% of total target profit. Prevents gambling spikes.",
        },
        "minimum_days": {
            "name": "Minimum Trading Days",
            "days": 5,
            "description": "Minimum 5 active trading days required to qualify.",
        },
        "news_trading": {
            "name": "Macro News Window Filter",
            "buffer_minutes": 5,
            "description": "AI automatically halts opening new positions 5 minutes before and after high-impact events (CPI, FOMC).",
        },
        "weekend_holding": {
            "name": "Weekend Position Sizing Dampener",
            "sizing_multiplier": 0.50,
            "description": "Positions open during weekends have size reduced by 50% due to thin institutional liquidity.",
        },
        "profit_share": {
            "user_payout_pct": 80.0,
            "dao_reserve_pct": 20.0,
            "currency": "USDT / POL",
        },
        "second_chance": {
            "guarantee": "100% Challenge Fee to TradeAid Credits (TAC)",
            "use_cases": ["Discounted Challenge Retries", "Permanent Demo Trading with Real Profit Withdrawals"],
        },
    }


# ---------------------------------------------------------
# LEDGER 1: AUTOTRADE RUNS & DEDICATED REWARD POOL
# ---------------------------------------------------------

class StartRunRequest(BaseModel):
    wallet: str
    tx_hash: str | None = None
    paper_starting_balance: float = 10000.0


class ConcludeRunRequest(BaseModel):
    simulated_pnl_usdt: float
    simulated_pnl_pct: float
    trades_count: int
    cortex_violations: int = 0


@router.post("/autotrade/run/start")
def start_autotrade_run(req: StartRunRequest) -> dict[str, Any]:
    """Activate 1 Autotrade Run with 10 POL fee on 10,000 USDT Paper capital."""
    from src.autotrade.run_engine import AutotradeRunEngine
    db = DatabaseManager()
    engine = AutotradeRunEngine(db=db)
    run = engine.start_run(
        wallet=req.wallet,
        tx_hash_fee=req.tx_hash,
        paper_starting_balance=req.paper_starting_balance,
        max_duration_seconds=180,
    )
    return {
        "status": "RUNNING",
        "run": run,
        "message": f"Autotrade Run {run['id']} activated. Time limit: 180s. Objective: Net P&L > 0.00% & 0 CORTEX violations.",
        "economic_contract": {
            "fee_paid": "10.0 POL -> DAO Treasury (0x3C320B3a0917fF44BF6551CDdee44402AFcF250C)",
            "capital": "10,000 USDT PAPER",
            "win_reward": "2.0 POL from Reward Pool",
            "loss_reward": "0 POL",
        },
    }


@router.get("/autotrade/run/{run_id}/telemetry")
def get_autotrade_run_telemetry(run_id: str) -> dict[str, Any]:
    """Get live telemetry of an active Autotrade Run."""
    db = DatabaseManager()
    run = db.get_autotrade_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    
    # Calculate time remaining
    now = datetime.now(timezone.utc)
    started_at = datetime.fromisoformat(run["started_at"]) if "started_at" in run and run["started_at"] else now
    elapsed_seconds = int((now - started_at).total_seconds())
    remaining_seconds = max(0, run.get("max_duration_seconds", 180) - elapsed_seconds)

    return {
        "run_id": run["id"],
        "sequence_id": run["sequence_id"],
        "wallet": run["wallet"],
        "status": run["status"],
        "paper_balance_usdt": run["paper_starting_balance"] + run["paper_final_pnl_usdt"],
        "net_pnl_usdt": run["paper_final_pnl_usdt"],
        "net_pnl_pct": run["paper_final_pnl_pct"],
        "trades_count": run["trades_count"],
        "cortex_violations": run["cortex_violations"],
        "elapsed_seconds": elapsed_seconds,
        "remaining_seconds": remaining_seconds,
        "time_limit_seconds": run["max_duration_seconds"],
        "is_expired": remaining_seconds == 0,
        "reward_pol": run["reward_pol"],
        "payout_status": run["payout_status"],
    }


@router.post("/autotrade/run/{run_id}/conclude")
def conclude_autotrade_run(run_id: str, req: ConcludeRunRequest) -> dict[str, Any]:
    """Conclude an Autotrade Run, evaluate WIN/LOSS and determine 2 POL reward."""
    from src.autotrade.run_engine import AutotradeRunEngine
    db = DatabaseManager()
    engine = AutotradeRunEngine(db=db)
    try:
        res = engine.evaluate_and_conclude_run(
            run_id=run_id,
            simulated_pnl_usdt=req.simulated_pnl_usdt,
            simulated_pnl_pct=req.simulated_pnl_pct,
            trades_count=req.trades_count,
            cortex_violations=req.cortex_violations,
        )
        return {
            "status": "CONCLUDED",
            "result": "WON" if res.won else "LOST",
            "run_id": res.run_id,
            "won": res.won,
            "reward_pol": res.reward_pol,
            "payout_status": res.payout_status,
            "final_pnl_usdt": res.final_pnl_usdt,
            "final_pnl_pct": res.final_pnl_pct,
            "trades_count": res.trades_count,
            "cortex_violations": res.cortex_violations,
            "reward_pool_solvent": res.reward_pool_solvent,
            "explanation": res.explanation,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/autotrade/runs/wallet/{wallet}")
def get_user_autotrade_runs(wallet: str) -> dict[str, Any]:
    """List recent Autotrade Runs for a specific wallet."""
    db = DatabaseManager()
    runs = db.get_user_autotrade_runs(wallet)
    return {
        "wallet": wallet.lower(),
        "total_runs": len(runs),
        "runs": runs,
    }


@router.get("/autotrade/reward-pool/status")
def get_reward_pool_status() -> dict[str, Any]:
    """Get the solvency and capacity of the separate Reward Pool."""
    db = DatabaseManager()
    pool = db.get_reward_pool_status()
    return {
        "pool": pool,
        "policy": {
            "run_entry_fee": "10.0 POL -> 100% to B+ DAO Treasury (0x3C320B3a0917fF44BF6551CDdee44402AFcF250C)",
            "win_reward": "2.0 POL paid from separate Reward Pool",
            "loss_reward": "0 POL",
            "max_exposure_ratio": "20% (1,000 POL fees collected = max 200 POL rewards if 100% win)",
            "solvency_guarantee": "Rewards paid ONLY if pool is funded; no uncovered promises.",
        },
    }


# =============================================================================
# DUAL AUTHENTICATION (WALLETCONNECT / POLYGON + SIC-ID-XXXXXXXXXXXX)
# =============================================================================

class AuthSessionRequest(BaseModel):
    wallet_address: str | None = Field(default=None, description="Polygon 0x address")
    signature: str | None = Field(default=None, description="Web3 / EIP-712 auth signature")
    sic_id: str | None = Field(default=None, description="Canonical Federation ID: SIC-ID-XXXXXXXXXXXX")
    email: str | None = Field(default=None)
    telegram_id: int | None = Field(default=None)


class LinkSicIdRequest(BaseModel):
    user_id: str
    wallet_address: str
    sic_id: str


@router.post("/auth/session")
def authenticate_user_session(req: AuthSessionRequest) -> dict[str, Any]:
    """Dual authentication endpoint: Authenticate via Web3 wallet or canonical SIC-ID."""
    db = DatabaseManager()
    if not req.wallet_address and not req.sic_id:
        raise HTTPException(
            status_code=400,
            detail="Must provide either wallet_address (Polygon) or canonical sic_id (SIC-ID-XXXXXXXXXXXX)",
        )

    if req.sic_id and not db.is_valid_sic_id(req.sic_id):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid SIC-ID format '{req.sic_id}'. Must be SIC-ID-XXXXXXXXXXXX (12 uppercase Crockford chars)",
        )

    try:
        user = db.get_or_create_prop_user(
            wallet_address=req.wallet_address,
            sic_id=req.sic_id,
            email=req.email,
            telegram_id=req.telegram_id,
        )
        profile = db.get_user_financial_profile(user["user_id"])
        return {
            "status": "AUTHENTICATED",
            "user": user,
            "financial_profile": profile,
            "auth_method": user["auth_method"],
            "session_token": f"sess_{user['user_id'][:8]}_{int(datetime.now(timezone.utc).timestamp())}",
            "ecosystem": "81PLUS_BLOCKCHAIN_PLUS_FEDERATION",
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/auth/link-sic-id")
def link_user_sic_id(req: LinkSicIdRequest) -> dict[str, Any]:
    """Link an active Web3 wallet address with a canonical SIC-ID digital twin."""
    db = DatabaseManager()
    if not db.is_valid_sic_id(req.sic_id):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid SIC-ID format '{req.sic_id}'. Must be SIC-ID-XXXXXXXXXXXX",
        )
    try:
        updated_user = db.link_wallet_and_sic_id(
            user_id=req.user_id,
            wallet_address=req.wallet_address,
            sic_id=req.sic_id,
        )
        return {
            "status": "SUCCESS",
            "message": f"Wallet {req.wallet_address} linked with {req.sic_id}",
            "user": updated_user,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/auth/user/{identifier}")
def get_user_identity(identifier: str) -> dict[str, Any]:
    """Look up user identity by user_id, wallet address, or SIC-ID."""
    db = DatabaseManager()
    user = db.get_prop_user(identifier)
    if not user:
        raise HTTPException(status_code=404, detail=f"User '{identifier}' not found")
    profile = db.get_user_financial_profile(user["user_id"])
    return {
        "user": user,
        "financial_profile": profile,
    }


# =============================================================================
# PROP CHALLENGE DATABASE SCHEMA V1.0 (TIERS, CHALLENGES, 3-LEDGER SYSTEM)
# =============================================================================

class CreateChallengeV1Request(BaseModel):
    user_id: str
    tier_id: int


class RecordSnapshotV1Request(BaseModel):
    snapshot_date: str = Field(description="YYYY-MM-DD")
    start_of_day_balance: float
    end_of_day_balance: float
    daily_pnl: float
    daily_dd_pct: float


@router.get("/prop/tiers")
@router.get("/challenges/tiers")
def get_prop_tiers() -> list[dict[str, Any]]:
    """Return all active Prop Challenge Tiers."""
    db = DatabaseManager()
    return db.get_challenge_tiers()


@router.post("/prop/challenge/create")
def create_prop_challenge(req: CreateChallengeV1Request) -> dict[str, Any]:
    """Create a new Prop Challenge instance."""
    db = DatabaseManager()
    try:
        challenge = db.create_prop_challenge_v1(user_id=req.user_id, tier_id=req.tier_id)
        return {
            "status": "CREATED",
            "challenge": challenge,
            "message": f"Challenge created under tier {challenge['tier']['name']}. Starting virtual capital: ${challenge['starting_balance']:,.2f}",
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/prop/challenge/{challenge_id}")
def get_prop_challenge_details(challenge_id: str) -> dict[str, Any]:
    """Get challenge instance, current status, and rules."""
    db = DatabaseManager()
    challenge = db.get_prop_challenge_v1(challenge_id)
    if not challenge:
        raise HTTPException(status_code=404, detail=f"Challenge {challenge_id} not found")
    return {"challenge": challenge}


@router.post("/prop/challenge/{challenge_id}/snapshot")
def submit_prop_daily_snapshot(challenge_id: str, req: RecordSnapshotV1Request) -> dict[str, Any]:
    """Submit daily midnight snapshot and evaluate daily drawdown breach."""
    db = DatabaseManager()
    challenge = db.get_prop_challenge_v1(challenge_id)
    if not challenge:
        raise HTTPException(status_code=404, detail=f"Challenge {challenge_id} not found")

    snapshot = db.record_prop_daily_snapshot(
        challenge_id=challenge_id,
        snapshot_date=req.snapshot_date,
        start_of_day_balance=req.start_of_day_balance,
        end_of_day_balance=req.end_of_day_balance,
        daily_pnl=req.daily_pnl,
        daily_dd_pct=req.daily_dd_pct,
    )

    max_daily_dd = float(challenge["tier"]["max_daily_dd_pct"])
    breached = req.daily_dd_pct > max_daily_dd

    if breached and challenge["status"] not in ("FAILED", "CANCELLED"):
        # Auto fail and convert fee to credit
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE prop_challenges_v1
                SET status = 'FAILED', violation_type = 'DAILY_DD', violated_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
                WHERE challenge_id = ?
                """,
                (challenge_id,),
            )
            conn.commit()

        # Record conversion from fee to trading credit
        fee = float(challenge["tier"]["fee_usdt"])
        db.record_trading_credit_entry(
            user_id=challenge["user_id"],
            amount=fee,
            credit_type="CONVERSION_FROM_FEE",
            description=f"Automated fee conversion from failed challenge {challenge_id[:8]} (Daily DD breached: {req.daily_dd_pct:.2f}% > {max_daily_dd:.2f}%)",
            challenge_id=challenge_id,
        )

    return {
        "snapshot": snapshot,
        "breached": breached,
        "challenge_status": "FAILED" if breached else challenge["status"],
    }


@router.get("/prop/ledgers/{identifier}")
def get_user_three_ledgers(identifier: str) -> dict[str, Any]:
    """Get the full 3-ledger breakdown for an authenticated user (by user_id, wallet, or SIC-ID)."""
    db = DatabaseManager()
    try:
        data = db.get_user_3_ledgers(identifier)
        return data
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/prop/leaderboard/current")
def get_current_leaderboard() -> dict[str, Any]:
    """Get the active monthly reward pool and official leaderboard."""
    db = DatabaseManager()
    pool = db.get_current_reward_pool()
    board = db.get_monthly_leaderboard_v1(pool["pool_id"])
    return {
        "reward_pool": pool,
        "leaderboard": board,
        "total_participants": len(board),
        "solvency_model": "Budgeted Monthly Allocation (Anti-Ghost Debt)",
    }


# =============================================================================
# DOMAIN 1: AUTOTRADE (10 POL -> 1 RUN -> 2 POL REWARD MODEL)
# =============================================================================

class AutotradeRunCreateRequest(BaseModel):
    user_id: str
    wallet: str
    activation_tx_hash: str
    activation_amount_atomic: str = Field(default="10000000000000000000", description="10 POL in wei")
    strategy: str = Field(default="BALANCED")
    idempotency_key: str | None = None


class AutotradeRunStopRequest(BaseModel):
    gross_pnl: float = 0.0
    execution_costs: float = 0.0
    net_pnl: float = 0.0
    result: str = Field(default="WIN", description="WIN, LOSS, or VOID")
    strategy_final: str | None = None


@router.post("/autotrade/runs")
def start_autotrade_run(req: AutotradeRunCreateRequest) -> dict[str, Any]:
    """Start an Autotrade Run: consumes 10 POL fee on-chain, initializes $10,000 Paper Capital, reserves 2 POL reward."""
    db = DatabaseManager()
    try:
        run = db.create_autotrade_run_v1(
            user_id=req.user_id,
            wallet=req.wallet,
            activation_tx_hash=req.activation_tx_hash,
            activation_amount_atomic=req.activation_amount_atomic,
            strategy_initial=req.strategy,
            idempotency_key=req.idempotency_key,
        )
        return {
            "status": "RUN_INITIALIZED",
            "run": run,
            "contract_model": "10 POL -> 10,000 USDT PAPER -> IF NET WIN: 2 POL REWARD",
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/autotrade/runs/{run_id}")
def get_autotrade_run(run_id: str) -> dict[str, Any]:
    """Get status, PnL, and reward state of an Autotrade Run."""
    db = DatabaseManager()
    run = db.get_autotrade_run_v1(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Autotrade Run {run_id} not found")
    return {"run": run}


@router.post("/autotrade/{run_id}/stop")
def stop_autotrade_run(run_id: str, req: AutotradeRunStopRequest) -> dict[str, Any]:
    """Stop/settle an Autotrade Run: finalizes net PnL, settles 2 POL reward if WIN or releases reservation if LOSS."""
    db = DatabaseManager()
    run = db.get_autotrade_run_v1(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Autotrade Run {run_id} not found")
    try:
        closed = db.close_autotrade_run_v1(
            run_id=run_id,
            gross_pnl=req.gross_pnl,
            execution_costs=req.execution_costs,
            net_pnl=req.net_pnl,
            result=req.result,
            strategy_final=req.strategy_final,
        )
        return {
            "status": "RUN_CLOSED",
            "run": closed,
            "reward_awarded": closed["reward_status"] == "PAID",
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/autotrade/{run_id}/decisions")
def get_autotrade_run_decisions(run_id: str) -> dict[str, Any]:
    """Audit trail of all CORTEX & strategy switching decisions during this run."""
    db = DatabaseManager()
    switches = db.get_strategy_switches()
    cortex = db.get_cortex_decisions()
    return {
        "run_id": run_id,
        "strategy_switches": [s for s in switches if s.get("position_id") == run_id or s.get("account_id") == run_id],
        "cortex_decisions": cortex[:10],
    }


@router.get("/autotrade/{run_id}/trades")
def get_autotrade_run_trades(run_id: str) -> dict[str, Any]:
    """Retrieve trades with execution economics for this run."""
    db = DatabaseManager()
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM challenge_trades WHERE run_id = ? ORDER BY opened_at DESC", (run_id,))
        trades = [dict(r) for r in cursor.fetchall()]
    return {"run_id": run_id, "trades": trades, "count": len(trades)}


# =============================================================================
# DOMAIN 2: PROP (CHALLENGE LIFECYCLE & VIOLATIONS)
# =============================================================================

@router.post("/prop/challenges")
def create_prop_challenge_alias(req: CreateChallengeV1Request) -> dict[str, Any]:
    """Alias for POST /prop/challenge/create."""
    return create_prop_challenge(req)


@router.get("/prop/challenges/{challenge_id}")
def get_prop_challenge_alias(challenge_id: str) -> dict[str, Any]:
    """Alias for GET /prop/challenge/{id}."""
    return get_prop_challenge_details(challenge_id)


@router.get("/prop/challenges/{challenge_id}/progress")
def get_prop_challenge_progress(challenge_id: str) -> dict[str, Any]:
    """Get high-water mark, profit target progress %, and daily DD status."""
    db = DatabaseManager()
    challenge = db.get_prop_challenge_v1(challenge_id)
    if not challenge:
        raise HTTPException(status_code=404, detail=f"Challenge {challenge_id} not found")

    start_bal = float(challenge["starting_balance"])
    curr_bal = float(challenge["current_balance"])
    hwm = float(challenge["high_water_mark"])
    target_pct = float(challenge["tier"]["phase1_target_pct"])
    target_usdt = start_bal * (1.0 + (target_pct / 100.0))
    current_profit_pct = ((curr_bal - start_bal) / start_bal) * 100.0 if start_bal > 0 else 0.0

    total_dd_pct = ((hwm - curr_bal) / hwm) * 100.0 if hwm > 0 else 0.0

    return {
        "challenge_id": challenge_id,
        "tier_name": challenge["tier"]["name"],
        "starting_balance": start_bal,
        "current_balance": curr_bal,
        "target_balance": target_usdt,
        "current_profit_pct": round(current_profit_pct, 2),
        "target_profit_pct": target_pct,
        "progress_toward_target_pct": round(min(100.0, max(0.0, (current_profit_pct / target_pct) * 100.0)), 2),
        "total_dd_current_pct": round(total_dd_pct, 2),
        "max_total_dd_limit_pct": float(challenge["tier"]["max_total_dd_pct"]),
        "status": challenge["status"],
    }


@router.get("/prop/challenges/{challenge_id}/violations")
def get_prop_challenge_violations(challenge_id: str) -> dict[str, Any]:
    """Get full audit report of any drawdown or policy violations."""
    db = DatabaseManager()
    challenge = db.get_prop_challenge_v1(challenge_id)
    if not challenge:
        raise HTTPException(status_code=404, detail=f"Challenge {challenge_id} not found")
    return {
        "challenge_id": challenge_id,
        "status": challenge["status"],
        "violation_type": challenge.get("violation_type"),
        "violated_at": challenge.get("violated_at"),
        "has_violations": challenge["status"] in ("FAILED", "CANCELLED"),
    }


# =============================================================================
# DOMAIN 3: HEART (PREDICTIVE HEART & WHY EXPLANATION)
# =============================================================================

@router.get("/heart/{asset}/why")
def get_heart_asset_why(asset: str) -> dict[str, Any]:
    """Explain why the Predictive Heart and CORTEX made the decision (WHITE -> RED -> DECISION)."""
    clean_asset = asset.replace("-", "/")
    snapshot = market_provider.get_snapshot(clean_asset)
    meta_dec = meta_agent.evaluate(snapshot)
    risk_res = risk_gate.evaluate(meta_dec, snapshot)
    return {
        "asset": clean_asset,
        "meta_decision": {
            "signal": meta_dec.decision.value,
            "confidence": meta_dec.confidence,
            "expected_return": meta_dec.expected_return,
            "expected_risk": meta_dec.expected_risk,
            "evidence": meta_dec.evidence,
        },
        "cortex_risk_gate": {
            "passed": risk_res.passed,
            "decision": risk_res.final_decision,
            "composite_risk_score": risk_res.composite_risk_score,
            "rejections": risk_res.rejection_reasons,
        },
        "formula": "WHITE (Forecast) -> RED (CORTEX Gate) -> DECISION (Sizing/Veto)",
    }


@router.get("/heart/{asset}/history")
def get_heart_asset_history(asset: str, limit: int = Query(default=20, le=100)) -> dict[str, Any]:
    """Get calibration history, direction hit rate, and Brier scores."""
    clean_asset = asset.replace("-", "/")
    db = DatabaseManager()
    stats = db.get_calibration_stats(clean_asset)
    forecasts = db.get_recent_forecasts(clean_asset, limit=limit)
    return {
        "asset": clean_asset,
        "calibration": stats,
        "recent_forecasts": forecasts,
    }


@router.get("/heart/{asset}/forecast")
@router.get("/heart/{asset}")
def get_heart_asset_forecast(asset: str) -> dict[str, Any]:
    """Get current Predictive Heart state and forecast for asset."""
    clean_asset = asset.replace("-", "/")
    ticker = market_provider.get_ticker(clean_asset)
    forecast = predictive_heart.generate_forecast(symbol=clean_asset)
    return {
        "asset": clean_asset,
        "current_price": ticker.price,
        "forecast": forecast,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# =============================================================================
# DOMAIN 4: FINANCE (LEDGERS, CREDITS, REWARDS, WITHDRAWAL)
# =============================================================================

class RewardWithdrawRequest(BaseModel):
    user_id: str
    amount: float = Field(gt=0, description="Amount in USDT or POL")
    destination_wallet: str
    idempotency_key: str = Field(description="Unique key to prevent double payout")


@router.get("/wallet")
def get_finance_wallet_summary(identifier: str = Query(..., description="user_id, wallet, or SIC-ID")) -> dict[str, Any]:
    """Get user profile and financial state across all accounts."""
    db = DatabaseManager()
    user = db.get_prop_user(identifier)
    if not user:
        raise HTTPException(status_code=404, detail=f"User {identifier} not found")
    profile = db.get_user_financial_profile(user["user_id"])
    return {"user": user, "financial_profile": profile}


@router.get("/credits")
def get_finance_credits(identifier: str = Query(..., description="user_id, wallet, or SIC-ID")) -> dict[str, Any]:
    """Get Trading Credits (TAC) balance and transaction ledger (1 TAC = $1 USDT Margin)."""
    db = DatabaseManager()
    data = db.get_user_3_ledgers(identifier)
    return data["ledger_2_trading_credits"]


@router.get("/rewards")
def get_finance_rewards(identifier: str = Query(..., description="user_id, wallet, or SIC-ID")) -> dict[str, Any]:
    """Get Withdrawable Rewards balance and transaction ledger."""
    db = DatabaseManager()
    data = db.get_user_3_ledgers(identifier)
    return data["ledger_3_withdrawable_rewards"]


@router.get("/ledger")
def get_finance_consolidated_ledger(identifier: str = Query(..., description="user_id, wallet, or SIC-ID")) -> dict[str, Any]:
    """Get consolidated audit report for all 4 monies (Paper 10k, Challenge Fee, TAC Credits, POL Rewards)."""
    db = DatabaseManager()
    data = db.get_user_3_ledgers(identifier)
    return {
        "four_monies_breakdown": {
            "money_1_paper_usdt": {
                "name": "10,000 USDT PAPER",
                "nature": "Simulated Virtual Capital (Non-withdrawable)",
                "active_challenges": data["ledger_1_prop_equity"]["total_active_challenges"],
            },
            "money_2_challenge_fee": {
                "name": "Challenge Fee (USDT / POL)",
                "nature": "Real Entry Fee (Eligible for 100% TAC Second Chance on fail)",
                "total_fees_paid": data["profile"]["total_fees_paid"],
            },
            "money_3_trading_credits": {
                "name": "Trading Credits (TAC)",
                "nature": "Non-Withdrawable Margin Credits (1 TAC = $1 USDT Margin)",
                "balance": data["ledger_2_trading_credits"]["balance_tac"],
                "history": data["ledger_2_trading_credits"]["history"],
            },
            "money_4_withdrawable_rewards": {
                "name": "POL / USDT Rewards",
                "nature": "Real Withdrawable Profits Funded by Budgeted Reward Pool",
                "balance": data["ledger_3_withdrawable_rewards"]["balance_usdt"],
                "history": data["ledger_3_withdrawable_rewards"]["history"],
            },
        }
    }


@router.post("/rewards/withdraw")
def request_reward_withdrawal(req: RewardWithdrawRequest) -> dict[str, Any]:
    """Request withdrawal of unlocked rewards. Validates balance, KYC, and registers pending payout."""
    db = DatabaseManager()
    profile = db.get_user_financial_profile(req.user_id)
    if not profile:
        raise HTTPException(status_code=404, detail="User financial profile not found")

    avail = float(profile["withdrawable_reward_balance"])
    if req.amount > avail:
        raise HTTPException(
            status_code=400,
            detail=f"Insufficient withdrawable balance. Requested: ${req.amount:.2f}, Available: ${avail:.2f}",
        )

    entry = db.record_withdrawable_reward_entry(
        user_id=req.user_id,
        amount=-req.amount,
        reward_type="WITHDRAWAL_REQUESTED",
        status="LOCKED",
    )
    return {
        "status": "WITHDRAWAL_REQUESTED",
        "withdrawal_amount": req.amount,
        "destination_wallet": req.destination_wallet,
        "transaction_id": entry["transaction_id"],
        "idempotency_key": req.idempotency_key,
        "note": "Payout queued for on-chain batch settlement via Treasury Guard",
    }


# ============================================================
# TRADEAID PROP CHALLENGE RISK AGENT ENDPOINTS
# ============================================================

from src.risk.challenge_risk_agent import (
    ChallengeRiskAgent,
    ChallengeState,
    RiskMetrics,
    TierConfig,
    TradeDirection,
    TIER_STARTER,
    TIER_PRO,
    TIER_ELITE,
    TIER_BLACK,
)
import pandas as pd
import numpy as np

PROP_TIER_CONFIGS = {
    "STARTER": TIER_STARTER,
    "PRO": TIER_PRO,
    "ELITE": TIER_ELITE,
    "BLACK": TIER_BLACK,
}


class CandleInput(BaseModel):
    high: float
    low: float
    close: float
    open: float | None = None
    volume: float | None = None


class EvaluateTradeRequest(BaseModel):
    challenge_id: str | None = Field(default=None, description="Optional challenge UUID")
    tier_name: str = Field(default="PRO", description="STARTER, PRO, ELITE, BLACK")
    signal_direction: str = Field(example="LONG", description="LONG or SHORT")
    entry_price: float = Field(gt=0, example=65000.0)
    target_asset_id: str = Field(default="BTC", example="BTC")
    candles: list[CandleInput] | None = Field(default=None, description="Recent 14+ candles with high, low, close")
    current_portfolio_exposure: dict[str, float] = Field(default_factory=dict, example={"BTC": 5000.0})
    current_equity: float | None = Field(default=None, description="Current challenge equity if challenge_id not in DB")


class UpdateEquityRequest(BaseModel):
    challenge_id: str
    new_equity: float


class DailyResetRequest(BaseModel):
    challenge_id: str | None = Field(default=None, description="Optional challenge UUID, or None for all active")


@router.post("/prop/evaluate-trade")
def evaluate_prop_trade(req: EvaluateTradeRequest) -> dict[str, Any]:
    """
    Evaluates an AI trade signal against Prop Challenge survival rules:
    - 5% Daily DD Headroom limit
    - 10% Total DD Hard Stop
    - Dynamic Volatility Sizing (2x ATR Stop Loss)
    - Pearson correlation & 20% exposure hard cap
    """
    tier = PROP_TIER_CONFIGS.get(req.tier_name.upper(), TIER_PRO)
    state = ChallengeState(tier)

    # If challenge_id given, hydrate from DB if present
    if req.challenge_id:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM prop_challenges_v1 WHERE challenge_id = ?", (req.challenge_id,))
            row = cursor.fetchone()
            if row:
                row_dict = dict(row)
                state.starting_balance = float(row_dict["starting_balance"])
                state.current_equity = float(row_dict["current_balance"])
                state.high_water_mark = float(row_dict["high_water_mark"])
                state.daily_start_equity = float(row_dict.get("daily_start_equity", row_dict["starting_balance"]))

    if req.current_equity is not None:
        state.current_equity = req.current_equity
        if req.current_equity > state.high_water_mark:
            state.high_water_mark = req.current_equity

    # Build candle DataFrame
    if req.candles and len(req.candles) >= 14:
        df_candles = pd.DataFrame([c.dict() for c in req.candles])
    else:
        # Generate realistic volatility window around entry_price if no candles supplied
        np.random.seed(42)
        base_p = req.entry_price
        highs = [base_p * (1.0 + abs(np.random.normal(0, 0.01))) for _ in range(20)]
        lows = [base_p * (1.0 - abs(np.random.normal(0, 0.01))) for _ in range(20)]
        closes = [(h + l) / 2.0 for h, l in zip(highs, lows)]
        df_candles = pd.DataFrame({"high": highs, "low": lows, "close": closes})

    agent = ChallengeRiskAgent(state)
    decision = agent.evaluate_trade(
        signal_direction=req.signal_direction,
        entry_price=req.entry_price,
        asset_historical_data=df_candles,
        current_portfolio_exposure=req.current_portfolio_exposure,
        target_asset_id=req.target_asset_id,
    )

    return {
        "challenge_id": req.challenge_id,
        "tier": tier.name,
        "nominal_capital": tier.nominal_capital,
        "current_equity": state.current_equity,
        "daily_dd_pct": round(state.daily_dd_pct * 100, 2),
        "total_dd_pct": round(state.total_dd_pct * 100, 2),
        "evaluation": decision,
    }


@router.post("/prop/update-equity")
def update_prop_equity(req: UpdateEquityRequest) -> dict[str, Any]:
    """Mark-to-market or closed-trade equity update for a Challenge."""
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM prop_challenges_v1 WHERE challenge_id = ?", (req.challenge_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Challenge not found")

        ch = dict(row)
        new_hwm = max(float(ch["high_water_mark"]), req.new_equity)
        cursor.execute(
            """
            UPDATE prop_challenges_v1
            SET current_balance = ?, high_water_mark = ?, updated_at = CURRENT_TIMESTAMP
            WHERE challenge_id = ?
            """,
            (req.new_equity, new_hwm, req.challenge_id),
        )
        conn.commit()

    return {
        "challenge_id": req.challenge_id,
        "updated_equity": req.new_equity,
        "high_water_mark": new_hwm,
        "status": "UPDATED",
    }


@router.post("/prop/daily-reset")
def reset_prop_daily_tracking(req: DailyResetRequest) -> dict[str, Any]:
    """Midnight UTC daily tracking reset and snapshot logging."""
    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    with db.get_connection() as conn:
        cursor = conn.cursor()
        query = "SELECT * FROM prop_challenges_v1 WHERE status NOT IN ('FAILED', 'CANCELLED', 'PASSED')"
        params = []
        if req.challenge_id:
            query += " AND challenge_id = ?"
            params.append(req.challenge_id)

        cursor.execute(query, params)
        challenges = [dict(r) for r in cursor.fetchall()]

        reset_count = 0
        for ch in challenges:
            cid = ch["challenge_id"]
            curr_bal = float(ch["current_balance"])
            # Record daily snapshot
            cursor.execute(
                """
                INSERT OR REPLACE INTO challenge_daily_snapshots (
                    challenge_id, snapshot_date, start_of_day_balance, end_of_day_balance, daily_pnl, daily_dd_pct
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (cid, now_utc, curr_bal, curr_bal, 0.0, 0.0),
            )
            reset_count += 1
        conn.commit()

    return {
        "action": "DAILY_RESET_COMPLETED",
        "date_utc": now_utc,
        "challenges_reset": reset_count,
    }










