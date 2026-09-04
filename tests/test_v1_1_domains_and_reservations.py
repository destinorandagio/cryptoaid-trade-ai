import pytest
from fastapi.testclient import TestClient
from src.api.app import app
from src.storage.db import DatabaseManager

client = TestClient(app)


def test_onchain_events_idempotency(tmp_path):
    db_file = tmp_path / "test_onchain.db"
    db = DatabaseManager(db_path=db_file)

    tx_hash = "0x9876543210abcdef1234567890abcdef1234567890abcdef1234567890abcdef"
    payload = {"amount": "10000000000000000000", "sender": "0xuser1"}

    # 1. Ingest event first time
    res1 = db.ingest_onchain_event(
        chain_id=137,
        tx_hash=tx_hash,
        log_index=0,
        block_number=50000000,
        contract_address="0xContractAddress1",
        event_name="AutotradeRunPaid",
        payload=payload,
    )
    assert res1["status"] == "PROCESSED"
    assert res1["event"]["tx_hash"] == tx_hash

    # 2. Ingest duplicate event (same chain, tx, log_index) -> Must return ALREADY_PROCESSED
    res2 = db.ingest_onchain_event(
        chain_id=137,
        tx_hash=tx_hash,
        log_index=0,
        block_number=50000000,
        contract_address="0xContractAddress1",
        event_name="AutotradeRunPaid",
        payload=payload,
    )
    assert res2["status"] == "ALREADY_PROCESSED"
    assert res2["event"]["tx_hash"] == tx_hash


def test_reward_reservation_and_autotrade_win_settlement(tmp_path):
    db_file = tmp_path / "test_runs.db"
    db = DatabaseManager(db_path=db_file)

    user = db.get_or_create_prop_user(wallet_address="0xwallet_autotrade_1")
    user_id = user["user_id"]

    # 1. Start Autotrade Run (10 POL activation -> 10,000 USDT Paper -> 2 POL reserved)
    run = db.create_autotrade_run_v1(
        user_id=user_id,
        wallet="0xwallet_autotrade_1",
        activation_tx_hash="0xact_tx_12345",
        activation_amount_atomic="10000000000000000000",
        strategy_initial="BALANCED",
        idempotency_key="run_idemp_001",
    )
    assert run["run_id"] is not None
    assert run["paper_start_balance"] == 10000.0
    assert run["reward_status"] == "RESERVED"

    # Verify idempotency on run creation
    run_dup = db.create_autotrade_run_v1(
        user_id=user_id,
        wallet="0xwallet_autotrade_1",
        activation_tx_hash="0xact_tx_12345",
        idempotency_key="run_idemp_001",
    )
    assert run_dup["run_id"] == run["run_id"]

    # 2. Close run with WIN (+150 USDT gross, -12 USDT costs, +138 USDT net)
    closed = db.close_autotrade_run_v1(
        run_id=run["run_id"],
        gross_pnl=150.0,
        execution_costs=12.0,
        net_pnl=138.0,
        result="WIN",
        strategy_final="TREND_FOLLOWING_V3",
    )
    assert closed["result"] == "WIN"
    assert closed["reward_status"] == "PAID"
    assert closed["reward_eligible"] == 1

    # Verify withdrawable reward was credited
    profile = db.get_user_financial_profile(user_id)
    assert float(profile["withdrawable_reward_balance"]) == 2.0


def test_autotrade_loss_releases_reward_reservation(tmp_path):
    db_file = tmp_path / "test_loss.db"
    db = DatabaseManager(db_path=db_file)

    user = db.get_or_create_prop_user(wallet_address="0xwallet_autotrade_loss")
    user_id = user["user_id"]

    run = db.create_autotrade_run_v1(
        user_id=user_id,
        wallet="0xwallet_autotrade_loss",
        activation_tx_hash="0xact_tx_loss_999",
    )
    assert run["reward_status"] == "RESERVED"

    # Close with LOSS
    closed = db.close_autotrade_run_v1(
        run_id=run["run_id"],
        gross_pnl=-50.0,
        execution_costs=8.0,
        net_pnl=-58.0,
        result="LOSS",
    )
    assert closed["result"] == "LOSS"
    assert closed["reward_status"] == "RELEASED_UNEARNED"
    assert closed["reward_eligible"] == 0

    # Withdrawable reward must remain 0
    profile = db.get_user_financial_profile(user_id)
    assert float(profile["withdrawable_reward_balance"]) == 0.0


def test_four_api_domains():
    # 1. Autotrade Domain
    resp_auth = client.post("/api/v1/auth/session", json={"wallet_address": "0xdomain_user_1"})
    assert resp_auth.status_code == 200
    user_id = resp_auth.json()["user"]["user_id"]

    resp_run = client.post(
        "/api/v1/autotrade/runs",
        json={
            "user_id": user_id,
            "wallet": "0xdomain_user_1",
            "activation_tx_hash": "0xdomain_tx_001",
            "strategy": "BALANCED",
        },
    )
    assert resp_run.status_code == 200
    run_id = resp_run.json()["run"]["run_id"]

    resp_get_run = client.get(f"/api/v1/autotrade/runs/{run_id}")
    assert resp_get_run.status_code == 200
    assert resp_get_run.json()["run"]["paper_start_balance"] == 10000.0

    # 2. Prop Domain
    resp_tiers = client.get("/api/v1/prop/tiers")
    assert resp_tiers.status_code == 200
    tiers_data = resp_tiers.json()
    tiers_list = tiers_data if isinstance(tiers_data, list) else tiers_data.get("tiers", [])
    assert len(tiers_list) == 4

    resp_chal = client.post("/api/v1/prop/challenges", json={"user_id": user_id, "tier_id": 2})
    assert resp_chal.status_code == 200
    challenge_id = resp_chal.json()["challenge"]["challenge_id"]

    resp_progress = client.get(f"/api/v1/prop/challenges/{challenge_id}/progress")
    assert resp_progress.status_code == 200
    assert resp_progress.json()["tier_name"] == "PRO"
    assert resp_progress.json()["target_profit_pct"] == 8.0

    resp_violations = client.get(f"/api/v1/prop/challenges/{challenge_id}/violations")
    assert resp_violations.status_code == 200
    assert resp_violations.json()["has_violations"] is False

    # 3. Heart Domain
    resp_forecast = client.get("/api/v1/heart/POL-USDT/forecast")
    assert resp_forecast.status_code == 200
    assert "forecast" in resp_forecast.json()

    resp_why = client.get("/api/v1/heart/POL-USDT/why")
    assert resp_why.status_code == 200
    assert "cortex_risk_gate" in resp_why.json()
    assert "formula" in resp_why.json()

    # 4. Finance Domain (4 Monies breakdown)
    resp_ledger = client.get(f"/api/v1/ledger?identifier={user_id}")
    assert resp_ledger.status_code == 200
    breakdown = resp_ledger.json()["four_monies_breakdown"]
    assert "money_1_paper_usdt" in breakdown
    assert "money_2_challenge_fee" in breakdown
    assert "money_3_trading_credits" in breakdown
    assert "money_4_withdrawable_rewards" in breakdown
