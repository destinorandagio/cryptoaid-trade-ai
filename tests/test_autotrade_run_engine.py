"""
Unit tests for Autotrade Run Engine & Dedicated Reward Pool (Ledger 1).
"""

import os
import tempfile
import pytest
from src.autotrade.run_engine import AutotradeRunEngine
from src.storage.db import DatabaseManager
from src.storage.migrations import apply_migrations


@pytest.fixture
def test_db():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    apply_migrations(db_path)
    db = DatabaseManager(db_path=db_path)
    yield db
    if os.path.exists(db_path):
        os.remove(db_path)


def test_autotrade_run_start(test_db):
    engine = AutotradeRunEngine(db=test_db)
    wallet = "0x1111111111111111111111111111111111111111"

    run = engine.start_run(wallet=wallet, tx_hash_fee="0xabc123")
    assert run["wallet"] == wallet.lower()
    assert run["fee_pol"] == 10.0
    assert run["paper_starting_balance"] == 10000.0
    assert run["status"] == "RUNNING"
    assert run["max_duration_seconds"] == 180


def test_autotrade_run_win_condition(test_db):
    engine = AutotradeRunEngine(db=test_db)
    wallet = "0x2222222222222222222222222222222222222222"

    run = engine.start_run(wallet=wallet)
    run_id = run["id"]

    # Positive P&L and 0 CORTEX violations -> WIN
    res = engine.evaluate_and_conclude_run(
        run_id=run_id,
        simulated_pnl_usdt=85.50,
        simulated_pnl_pct=0.855,
        trades_count=4,
        cortex_violations=0,
    )
    assert res.won is True
    assert res.reward_pol == 2.0
    assert "WIN" in res.explanation

    # Check DB updated
    closed_run = test_db.get_autotrade_run(run_id)
    assert closed_run["status"] == "WON"
    assert closed_run["trades_count"] == 4


def test_autotrade_run_loss_condition_negative_pnl(test_db):
    engine = AutotradeRunEngine(db=test_db)
    wallet = "0x3333333333333333333333333333333333333333"

    run = engine.start_run(wallet=wallet)
    run_id = run["id"]

    # Negative P&L -> LOSS
    res = engine.evaluate_and_conclude_run(
        run_id=run_id,
        simulated_pnl_usdt=-42.00,
        simulated_pnl_pct=-0.42,
        trades_count=3,
        cortex_violations=0,
    )
    assert res.won is False
    assert res.reward_pol == 0.0
    assert res.payout_status == "NOT_ELIGIBLE"
    assert "LOSS" in res.explanation


def test_autotrade_run_loss_condition_cortex_violation(test_db):
    engine = AutotradeRunEngine(db=test_db)
    wallet = "0x4444444444444444444444444444444444444444"

    run = engine.start_run(wallet=wallet)
    run_id = run["id"]

    # Positive P&L but CORTEX violation -> LOSS
    res = engine.evaluate_and_conclude_run(
        run_id=run_id,
        simulated_pnl_usdt=150.00,
        simulated_pnl_pct=1.5,
        trades_count=5,
        cortex_violations=1,
    )
    assert res.won is False
    assert res.reward_pol == 0.0
    assert "CORTEX violation" in res.explanation


def test_reward_pool_solvency_and_deduction(test_db):
    pool_status = test_db.get_reward_pool_status()
    assert pool_status["is_solvent"] is True
    assert pool_status["balance_pol"] >= 500.0

    # Test payment deduction
    initial_bal = pool_status["balance_pol"]
    success = test_db.pay_reward_from_pool(2.0)
    assert success is True

    updated_status = test_db.get_reward_pool_status()
    assert updated_status["balance_pol"] == initial_bal - 2.0
    assert updated_status["total_paid_pol"] == 2.0
