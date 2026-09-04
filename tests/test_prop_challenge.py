import pytest
from src.agents.prop_challenge import PropChallengeEngine, ChallengeStatusResult, PROP_TIERS
from src.storage.db import DatabaseManager


def test_prop_challenge_tiers_and_no_loss_guarantee():
    engine = PropChallengeEngine()

    # 1. 100K PRO PROP Tier (Default)
    active_100k = {
        "id": "prop_100k_1",
        "wallet": "0x123",
        "tier": "100K",
        "mode": "BALANCED",
        "initial_equity": 100000.0,
        "current_equity": 102830.0,
        "peak_equity": 103000.0,
        "current_daily_dd_pct": 0.5,
        "cortex_violations": 0,
        "trading_days_count": 2,
        "status": "ACTIVE",
    }
    res = engine.evaluate(active_100k)
    assert res.tier == "100K"
    assert res.initial_equity == 100000.0
    assert res.challenge_fee_usdt == 100.0
    assert res.status == "ACTIVE"
    assert res.profit_pct == 2.83
    assert res.profit_usdt == 2830.0
    assert not res.total_dd_breached
    assert res.prop_score > 70.0

    # 2. 50K STARTER Tier — Failed -> Converts Fee (50 USDT) to Trading Credit
    failed_50k = {
        "id": "prop_50k_fail",
        "wallet": "0x456",
        "tier": "50K",
        "mode": "SAFE",
        "initial_equity": 50000.0,
        "current_equity": 45000.0,
        "peak_equity": 50000.0,
        "current_daily_dd_pct": 4.5,
        "cortex_violations": 0,
        "trading_days_count": 3,
        "status": "ACTIVE",
    }
    res_fail = engine.evaluate(failed_50k)
    assert res_fail.status == "FAILED"
    assert res_fail.daily_dd_breached is True
    # No-Loss guarantee: 50 USDT credited as internal autotrading credit
    assert res_fail.trading_credit_usdt == 50.0

    # 3. 150K ELITE Tier — Qualified State
    qualified_150k = {
        "id": "prop_150k_pass",
        "wallet": "0x789",
        "tier": "150K",
        "mode": "TURBO",
        "initial_equity": 150000.0,
        "current_equity": 162500.0,  # +8.33%
        "peak_equity": 162500.0,
        "current_daily_dd_pct": 0.3,
        "cortex_violations": 0,
        "trading_days_count": 5,
        "status": "ACTIVE",
    }
    res_pass = engine.evaluate(qualified_150k)
    assert res_pass.status == "QUALIFIED"
    assert res_pass.target_achieved is True
    assert res_pass.profit_usdt == 12500.0
    assert res_pass.prop_score >= 85.0
    assert "score_breakdown" in res_pass.__dict__
    assert res_pass.score_breakdown["max_drawdown"] == 20.0  # Zero DD = max 20 pts


def test_prop_score_8_factors_discipline_over_reckless_risk():
    from src.agents.prop_challenge import PropScoreEngine

    # Scenario 1: Disciplined trader with +6.0% profit and only 0.8% DD, 0 CORTEX violations
    score_disciplined = PropScoreEngine.calculate(
        profit_pct=6.0,
        target_pct=8.0,
        total_dd_pct=0.8,
        max_dd_pct=8.0,
        cortex_violations=0,
        expectancy_bps=45.0,
        profit_factor=2.4,
    )

    # Scenario 2: Reckless trader with +9.0% profit (overshot target) but 7.5% DD and 2 CORTEX violations
    score_reckless = PropScoreEngine.calculate(
        profit_pct=9.0,
        target_pct=8.0,
        total_dd_pct=7.5,
        max_dd_pct=8.0,
        cortex_violations=2,
        expectancy_bps=20.0,
        profit_factor=1.2,
    )

    # Core rule: +6% with minimum drawdown MUST beat +9% obtained by risking everything!
    assert score_disciplined.total_score > score_reckless.total_score
    assert score_disciplined.max_drawdown_score > score_reckless.max_drawdown_score
    assert score_disciplined.cortex_discipline_score > score_reckless.cortex_discipline_score


def test_prop_challenge_multi_profile_benchmarks():
    engine = PropChallengeEngine()
    benchmarks = engine.get_parallel_benchmarks()

    assert "SAFE" in benchmarks
    assert "BALANCED" in benchmarks
    assert "TURBO" in benchmarks

    # SAFE has the lowest DD and highest discipline score
    assert benchmarks["SAFE"]["max_drawdown_pct"] < benchmarks["TURBO"]["max_drawdown_pct"]
    assert benchmarks["SAFE"]["prop_score"] > benchmarks["TURBO"]["prop_score"]
    # TURBO has the highest nominal return
    assert benchmarks["TURBO"]["profit_pct"] > benchmarks["SAFE"]["profit_pct"]


def test_prop_challenge_db_tiers(tmp_path):
    db_file = tmp_path / "test_tradeaid.db"
    db = DatabaseManager(db_path=db_file)

    # Create 50k challenge
    c50 = db.get_or_create_prop_challenge("0x50k_trader", mode="SAFE", tier="50K")
    assert c50["tier"] == "50K"
    assert c50["initial_equity"] == 50000.0
    assert c50["challenge_fee_usdt"] == 50.0

    # Create 150k challenge
    c150 = db.get_or_create_prop_challenge("0x150k_trader", mode="TURBO", tier="150K")
    assert c150["tier"] == "150K"
    assert c150["initial_equity"] == 150000.0
    assert c150["challenge_fee_usdt"] == 1500.0
