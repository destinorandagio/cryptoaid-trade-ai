import pytest
from src.agents.prop_challenge import PropChallengeEngine, ChallengeStatusResult
from src.storage.db import DatabaseManager


def test_prop_challenge_engine_progression():
    engine = PropChallengeEngine(target_pct=8.0, max_total_dd=8.0, max_daily_dd=4.0, min_days=5)

    # 1. Normal Active State
    active_data = {
        "id": "prop_test_1",
        "wallet": "0x123",
        "mode": "BALANCED",
        "initial_equity": 10000.0,
        "current_equity": 10283.0,
        "peak_equity": 10300.0,
        "current_daily_dd_pct": 0.5,
        "cortex_violations": 0,
        "trading_days_count": 2,
        "status": "ACTIVE",
    }
    res = engine.evaluate(active_data)
    assert res.status == "ACTIVE"
    assert res.profit_pct == 2.83
    assert res.current_total_dd_pct < 8.0
    assert not res.total_dd_breached
    assert res.prop_score > 70.0
    assert "TRADEAID PROP CHALLENGE" in res.share_text

    # 2. Qualified State (Profit >= 8% and Days >= 5 and no DD breach)
    qualified_data = {
        "id": "prop_test_2",
        "wallet": "0x456",
        "mode": "SAFE",
        "initial_equity": 10000.0,
        "current_equity": 10850.0,
        "peak_equity": 10850.0,
        "current_daily_dd_pct": 0.2,
        "cortex_violations": 0,
        "trading_days_count": 5,
        "status": "ACTIVE",
    }
    res_qual = engine.evaluate(qualified_data)
    assert res_qual.status == "QUALIFIED"
    assert res_qual.target_achieved is True
    assert res_qual.prop_score >= 90.0

    # 3. Failed State (Drawdown breached)
    failed_data = {
        "id": "prop_test_3",
        "wallet": "0x789",
        "mode": "TURBO",
        "initial_equity": 10000.0,
        "current_equity": 9100.0,
        "peak_equity": 10000.0,
        "current_daily_dd_pct": 4.5,
        "cortex_violations": 0,
        "trading_days_count": 3,
        "status": "ACTIVE",
    }
    res_fail = engine.evaluate(failed_data)
    assert res_fail.status == "FAILED"
    assert res_fail.daily_dd_breached is True


def test_prop_challenge_db_integration(tmp_path):
    db_file = tmp_path / "test_tradeaid.db"
    db = DatabaseManager(db_path=db_file)

    # Create challenge
    c = db.get_or_create_prop_challenge("0xabc_trader", mode="BALANCED")
    assert c["id"].startswith("prop_")
    assert c["initial_equity"] == 10000.0
    assert c["status"] == "ACTIVE"

    # Update challenge
    updated = db.update_prop_challenge(
        challenge_id=c["id"],
        current_equity=10450.0,
        current_daily_dd_pct=0.8,
        current_total_dd_pct=1.2,
        cortex_violations=0,
        trading_days_count=2,
        status="ACTIVE",
        prop_score=88.5,
    )
    assert updated["current_equity"] == 10450.0
    assert updated["peak_equity"] == 10450.0
    assert updated["prop_score"] == 88.5

    # Leaderboard
    lb = db.get_prop_leaderboard()
    assert len(lb) >= 1
    assert lb[0]["wallet"] == "0xabc_trader"
