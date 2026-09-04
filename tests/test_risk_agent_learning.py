"""Unit & Integration tests for Risk Agent V1, Strategy Selector, Experience Matrix, and Champion/Challenger System."""
from __future__ import annotations

import pytest
from pathlib import Path

from src.agents.strategy_selector import MarketStateVector, StrategySelector
from src.learning.experience_matrix import ExperienceMatrix
from src.learning.memory_weighting import ChampionChallengerSystem, MemoryWeights
from src.risk.risk_agent_v1 import (
    RiskAgentV1,
    RiskDecision,
    RiskEvaluationInput,
    VetoStage,
)
from src.storage.db import DatabaseManager


@pytest.fixture
def temp_db(tmp_path: Path) -> DatabaseManager:
    db_file = tmp_path / "test_trade_ai.db"
    return DatabaseManager(db_path=db_file)


# =========================================================================
# 1. RISK AGENT V1 TESTS (6-STAGE VETO HIERARCHY)
# =========================================================================
def test_risk_agent_stage1_system_health():
    agent = RiskAgentV1()
    inp = RiskEvaluationInput(system_healthy=False)
    res = agent.evaluate(inp)
    assert res.decision == RiskDecision.REJECT
    assert res.veto_stage == VetoStage.SYSTEM_HEALTH
    assert "System Health Veto" in res.reason


def test_risk_agent_stage2_asset_safety_liquidity():
    agent = RiskAgentV1()
    inp = RiskEvaluationInput(liquidity=10_000.0)  # Below 50k
    res = agent.evaluate(inp)
    assert res.decision == RiskDecision.REJECT
    assert res.veto_stage == VetoStage.ASSET_SAFETY
    assert "liquidity" in res.reason.lower()


def test_risk_agent_stage2_asset_safety_honeypot():
    agent = RiskAgentV1()
    inp = RiskEvaluationInput(token_risk={"is_honeypot": True})
    res = agent.evaluate(inp)
    assert res.decision == RiskDecision.REJECT
    assert res.veto_stage == VetoStage.ASSET_SAFETY
    assert "Honeypot" in res.reason


def test_risk_agent_stage3_execution_economics():
    agent = RiskAgentV1()
    # Tiny prediction that cannot clear DEX fee + slippage + gas
    inp = RiskEvaluationInput(
        prediction=0.002,  # +0.20%
        confidence=0.60,
        slippage=0.002,
        price_impact=0.001,
        gas=0.50,
    )
    res = agent.evaluate(inp)
    assert res.decision == RiskDecision.REJECT
    assert res.veto_stage == VetoStage.EXECUTION_ECONOMICS
    assert "Execution Economics Veto" in res.reason


def test_risk_agent_stage4_portfolio_risk_max_positions():
    agent = RiskAgentV1()
    # 5 positions already open on balanced
    existing = [{"size": 10.0, "entry": 1.0} for _ in range(5)]
    inp = RiskEvaluationInput(open_positions=existing)
    res = agent.evaluate(inp)
    assert res.decision == RiskDecision.REJECT
    assert res.veto_stage == VetoStage.PORTFOLIO_RISK
    assert "Max concurrent positions" in res.reason


def test_risk_agent_stage5_drawdown_daily_breaker():
    agent = RiskAgentV1()
    inp = RiskEvaluationInput(daily_loss_pct=0.035)  # 3.5% > 3% limit
    res = agent.evaluate(inp)
    assert res.decision == RiskDecision.REJECT
    assert res.veto_stage == VetoStage.DRAWDOWN_STATE
    assert "Daily loss limit" in res.reason


def test_risk_agent_stage5_emergency_drawdown_exit_all():
    agent = RiskAgentV1()
    inp = RiskEvaluationInput(current_drawdown_pct=0.09)  # 9% > 8% limit
    res = agent.evaluate(inp)
    assert res.decision == RiskDecision.EXIT_ALL
    assert res.veto_stage == VetoStage.DRAWDOWN_STATE
    assert "Halting all trading" in res.reason


def test_risk_agent_stage6_pass_and_dynamic_sizing():
    agent = RiskAgentV1()
    inp = RiskEvaluationInput(
        equity=1000.0,
        prediction=0.025,  # +2.5%
        confidence=0.85,
        regime="TRENDING_BULL",
        strategy="MOMENTUM",
        volatility=2.0,
        liquidity=500_000.0,
        entry_price=0.50,
    )
    res = agent.evaluate(inp)
    assert res.decision == RiskDecision.PASS
    assert res.veto_stage is None
    assert res.position_size_usdt > 0
    assert res.stop_loss_pct <= 0.05  # Hard emergency ceiling respected
    assert res.stop_loss_price < 0.50
    assert res.take_profit_price > 0.50


def test_risk_agent_scalp_tight_stop():
    agent = RiskAgentV1()
    inp = RiskEvaluationInput(
        equity=1000.0,
        prediction=0.015,
        confidence=0.85,
        strategy="SCALP",
        volatility=1.5,
        liquidity=500_000.0,
        is_scalp=True,
    )
    res = agent.evaluate(inp)
    assert res.decision == RiskDecision.PASS
    # Scalp dynamic stop is tight (between 0.6% and 1.2%)
    assert res.stop_loss_pct <= 0.012
    assert res.max_hold_seconds == 300  # 5 min max hold


# =========================================================================
# 2. STRATEGY SELECTOR TESTS (MARKET STATE VECTOR & EXPLICIT EXIT)
# =========================================================================
def test_strategy_selector_trending_bull():
    selector = StrategySelector()
    state = MarketStateVector(
        regime="TRENDING_BULL",
        predictive_forecast_pct=0.020,
        forecast_confidence=0.80,
        adx=32.0,
        rsi_14=62.0,
        is_overextended=False,
    )
    res = selector.evaluate(state)
    assert res.action == "ENTER"
    assert res.selected_strategy in ["MOMENTUM", "TREND", "BREAKOUT"]
    assert res.strategy_scores["MOMENTUM"] >= 0.70
    assert res.strategy_scores["EXIT"] < 0.20


def test_strategy_selector_overextended_exit():
    selector = StrategySelector()
    # Active position in an overextended market with negative forecast
    state = MarketStateVector(
        regime="TRENDING_BULL",
        predictive_forecast_pct=-0.008,  # Negative forecast
        forecast_confidence=0.70,
        is_overextended=True,            # Overextended
        in_active_position=True,         # In active trade
    )
    res = selector.evaluate(state)
    assert res.action == "EXIT"
    assert res.selected_strategy == "EXIT"
    assert res.strategy_scores["EXIT"] >= 0.70


# =========================================================================
# 3. EXPERIENCE MATRIX TESTS (MULTIDIMENSIONAL LEARNING)
# =========================================================================
def test_experience_matrix_record_and_query(temp_db: DatabaseManager):
    matrix = ExperienceMatrix(db_manager=temp_db)

    # Initial query on unobserved cell returns smoothed default
    cell = matrix.query_cell(asset="POL/USDT", regime="TRENDING_BULL", timeframe="5m", strategy="MOMENTUM")
    assert cell.sample_size == 0
    assert cell.confidence_score == 0.40

    # Record 3 successful trades
    matrix.record_trade_outcome(
        asset="POL/USDT",
        regime="TRENDING_BULL",
        timeframe="5m",
        strategy="MOMENTUM",
        net_return_pct=0.015,
        costs_pct=0.003,
    )
    matrix.record_trade_outcome(
        asset="POL/USDT",
        regime="TRENDING_BULL",
        timeframe="5m",
        strategy="MOMENTUM",
        net_return_pct=0.008,
        costs_pct=0.003,
    )
    updated = matrix.record_trade_outcome(
        asset="POL/USDT",
        regime="TRENDING_BULL",
        timeframe="5m",
        strategy="MOMENTUM",
        net_return_pct=-0.004,
        costs_pct=0.003,
    )

    assert updated.sample_size == 3
    assert updated.win_rate > 0.60
    assert updated.expectancy > 0
    assert updated.confidence_score > 0.40

    # Check ranked strategies
    ranked = matrix.get_top_strategies(regime="TRENDING_BULL", asset="POL/USDT")
    assert len(ranked) >= 1
    assert ranked[0]["strategy"] == "MOMENTUM"


# =========================================================================
# 4. MEMORY WEIGHTING & CHAMPION/CHALLENGER SYSTEM
# =========================================================================
def test_memory_weighting_calculation():
    weights = MemoryWeights()
    score = weights.compute_composite_weight(
        long_term_score=0.80,
        recent_score=0.75,
        regime_sim=0.90,
        sample_conf=0.70,
        calibration=0.85,
    )
    assert 0.70 <= score <= 0.90


def test_champion_challenger_promotion(temp_db: DatabaseManager):
    matrix = ExperienceMatrix(db_manager=temp_db)
    system = ChampionChallengerSystem(db_manager=temp_db)

    # Initially MOMENTUM is Champion for TRENDING_BULL
    assert system.get_champion("TRENDING_BULL") == "MOMENTUM"

    # Simulate Challenger (BREAKOUT) crushing Champion with 35 samples and +2.5% expectancy
    for _ in range(35):
        matrix.record_trade_outcome(
            asset="POL/USDT",
            regime="TRENDING_BULL",
            timeframe="5m",
            strategy="BREAKOUT",
            net_return_pct=0.025,
            costs_pct=0.003,
        )

    # Evaluate promotion gate
    promo_result = system.evaluate_promotion(regime="TRENDING_BULL", experience_matrix=matrix, asset="POL/USDT")
    assert promo_result["status"] == "PROMOTED"
    assert promo_result["new_champion"] == "BREAKOUT"
    assert promo_result["previous_champion"] == "MOMENTUM"

    # Verify state reflects promotion
    assert system.get_champion("TRENDING_BULL") == "BREAKOUT"
