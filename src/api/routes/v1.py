"""REST API Version 1 Routes for CryptoAID Trade AI."""
from __future__ import annotations

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






