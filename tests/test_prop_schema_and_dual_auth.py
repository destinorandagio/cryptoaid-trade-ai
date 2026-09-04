"""
Test Suite for TradeAID Prop Database Schema V1.0, Dual Authentication (WalletConnect + SIC-ID),
3-Ledger Accounting and Endpoints.
"""

import pytest
from fastapi.testclient import TestClient
from pathlib import Path
import tempfile
import os

from src.api.app import app
from src.storage.db import DatabaseManager
from src.storage.migrations import apply_migrations


@pytest.fixture
def temp_db():
    fd, path = tempfile.mkstemp(suffix=".sqlite3")
    os.close(fd)
    db = DatabaseManager(db_path=path)
    yield db
    if os.path.exists(path):
        os.remove(path)


def test_sic_id_validation_and_generation():
    """Verify canonical SIC-ID validation and Crockford base32 generator."""
    assert DatabaseManager.is_valid_sic_id("SIC-ID-B5PVYYLVJRK9") is True
    assert DatabaseManager.is_valid_sic_id("SIC-ID-UGFD3Y5MABFR") is True
    assert DatabaseManager.is_valid_sic_id("SIC-ID-858JLVMJNMMK") is True
    
    # Invalid formats
    assert DatabaseManager.is_valid_sic_id("INVALID") is False
    assert DatabaseManager.is_valid_sic_id("SIC-ID-SHORT") is False
    assert DatabaseManager.is_valid_sic_id("SIC-ID-toolongcharacter12345") is False
    assert DatabaseManager.is_valid_sic_id(None) is False

    # Generator creates valid SIC-ID
    generated = DatabaseManager.generate_sic_id()
    assert DatabaseManager.is_valid_sic_id(generated) is True
    assert len(generated) == 19
    assert generated.startswith("SIC-ID-")


def test_dual_auth_user_provisioning(temp_db):
    """Test user creation and lookup via wallet only, sic_id only, and hybrid."""
    # 1. Wallet only -> auto-generates linked SIC-ID twin
    u1 = temp_db.get_or_create_prop_user(wallet_address="0x1111111111111111111111111111111111111111")
    assert u1["wallet_address"] == "0x1111111111111111111111111111111111111111"
    assert DatabaseManager.is_valid_sic_id(u1["sic_id"])
    assert u1["auth_method"] == "HYBRID"

    # 2. SIC-ID only
    canonical_sic = "SIC-ID-B5PVYYLVJRK9"
    u2 = temp_db.get_or_create_prop_user(sic_id=canonical_sic)
    assert u2["sic_id"] == canonical_sic
    assert u2["wallet_address"] is None
    assert u2["auth_method"] == "SIC_ID"

    # Lookup by SIC-ID
    found = temp_db.get_prop_user(canonical_sic)
    assert found is not None
    assert found["user_id"] == u2["user_id"]

    # 3. Link wallet to SIC-ID user
    updated = temp_db.link_wallet_and_sic_id(
        user_id=u2["user_id"],
        wallet_address="0x2222222222222222222222222222222222222222",
        sic_id=canonical_sic,
    )
    assert updated["auth_method"] == "HYBRID"
    assert updated["wallet_address"] == "0x2222222222222222222222222222222222222222"


def test_challenge_tiers_configuration(temp_db):
    """Verify all 4 canonical tiers exist with exact targets and drawdown constraints."""
    tiers = temp_db.get_challenge_tiers()
    assert len(tiers) == 4
    tier_map = {t["name"]: t for t in tiers}

    # STARTER ($50 fee / $10k nominal)
    starter = tier_map["STARTER"]
    assert starter["nominal_capital"] == 10000.0
    assert starter["fee_usdt"] == 50.0
    assert starter["phase1_target_pct"] == 8.0
    assert starter["max_daily_dd_pct"] == 5.0
    assert starter["max_total_dd_pct"] == 10.0

    # PRO ($100 fee / $50k nominal)
    pro = tier_map["PRO"]
    assert pro["nominal_capital"] == 50000.0
    assert pro["fee_usdt"] == 100.0

    # ELITE ($500 fee / $100k nominal)
    elite = tier_map["ELITE"]
    assert elite["nominal_capital"] == 100000.0
    assert elite["fee_usdt"] == 500.0

    # BLACK ($1,500 fee / $150k nominal)
    black = tier_map["BLACK"]
    assert black["nominal_capital"] == 150000.0
    assert black["fee_usdt"] == 1500.0


def test_prop_challenge_lifecycle_and_fee_conversion(temp_db):
    """Test challenge creation, snapshotting, breach detection, and fee conversion into TAC."""
    user = temp_db.get_or_create_prop_user(sic_id="SIC-ID-UGFD3Y5MABFR")
    user_id = user["user_id"]

    # Create STARTER challenge (tier 1, $50 fee, $10,000 capital)
    ch = temp_db.create_prop_challenge_v1(user_id=user_id, tier_id=1)
    assert ch["status"] == "PHASE_1_QUALIFICATION"
    assert ch["starting_balance"] == 10000.0

    # Check fee was added to total_fees_paid in profile
    prof = temp_db.get_user_financial_profile(user_id)
    assert prof["total_fees_paid"] == 50.0
    assert prof["last_challenge_tier"] == "STARTER"

    # Record trade
    trade = temp_db.record_prop_trade(
        challenge_id=ch["challenge_id"],
        asset_canonical_id="CA-L1-0001",
        direction="LONG",
        entry_price=64000.0,
        quantity=0.15,
        exit_price=63500.0,
        pnl_usdt=-75.0,
        pnl_pct=-0.78,
    )
    assert trade["direction"] == "LONG"
    assert trade["pnl_usdt"] == -75.0

    # Record safe snapshot (1.2% daily DD)
    snap1 = temp_db.record_prop_daily_snapshot(
        challenge_id=ch["challenge_id"],
        snapshot_date="2026-09-01",
        start_of_day_balance=10000.0,
        end_of_day_balance=9880.0,
        daily_pnl=-120.0,
        daily_dd_pct=1.20,
    )
    assert snap1["daily_dd_pct"] == 1.20

    # Record TAC credit entry manually
    credit = temp_db.record_trading_credit_entry(
        user_id=user_id,
        amount=50.0,
        credit_type="CONVERSION_FROM_FEE",
        description="Fail fee conversion",
        challenge_id=ch["challenge_id"],
    )
    assert credit["amount"] == 50.0

    # Check consolidated 3-ledger report
    ledgers = temp_db.get_user_3_ledgers(user_id)
    assert ledgers["ledger_1_prop_equity"]["total_active_challenges"] == 1
    assert ledgers["ledger_2_trading_credits"]["balance_tac"] == 50.0
    assert ledgers["ledger_3_withdrawable_rewards"]["balance_usdt"] == 0.0


def test_api_dual_auth_and_prop_endpoints():
    """Verify FastAPI endpoints for dual auth and prop challenge."""
    client = TestClient(app)

    # 1. Auth via fresh SIC-ID
    fresh_sic = DatabaseManager.generate_sic_id()
    r1 = client.post(
        "/api/v1/auth/session",
        json={"sic_id": fresh_sic},
    )
    assert r1.status_code == 200
    d1 = r1.json()
    assert d1["status"] == "AUTHENTICATED"
    assert d1["auth_method"] == "SIC_ID"
    user_id = d1["user"]["user_id"]

    # 2. Link Web3 wallet
    import secrets
    fresh_wallet = f"0x{secrets.token_hex(20)}"
    r2 = client.post(
        "/api/v1/auth/link-sic-id",
        json={
            "user_id": user_id,
            "wallet_address": fresh_wallet,
            "sic_id": fresh_sic,
        },
    )
    assert r2.status_code == 200
    assert r2.json()["user"]["auth_method"] == "HYBRID"

    # 3. Get Tiers
    rtiers = client.get("/api/v1/prop/tiers")
    assert rtiers.status_code == 200
    tiers_data = rtiers.json()
    assert tiers_data["count"] == 4

    # 4. Create Challenge
    r_create = client.post(
        "/api/v1/prop/challenge/create",
        json={"user_id": user_id, "tier_id": 2}, # PRO tier
    )
    assert r_create.status_code == 200
    ch_data = r_create.json()
    assert ch_data["status"] == "CREATED"
    ch_id = ch_data["challenge"]["challenge_id"]

    # 5. Snapshot with breach (> 5% Daily DD)
    r_snap = client.post(
        f"/api/v1/prop/challenge/{ch_id}/snapshot",
        json={
            "snapshot_date": "2026-09-02",
            "start_of_day_balance": 50000.0,
            "end_of_day_balance": 47000.0,
            "daily_pnl": -3000.0,
            "daily_dd_pct": 6.00,
        },
    )
    assert r_snap.status_code == 200
    snap_res = r_snap.json()
    assert snap_res["breached"] is True
    assert snap_res["challenge_status"] == "FAILED"

    # 6. Verify 3 Ledgers (TAC fee credit accrued)
    r_ledgers = client.get(f"/api/v1/prop/ledgers/{user_id}")
    assert r_ledgers.status_code == 200
    ledgers = r_ledgers.json()
    assert ledgers["ledger_2_trading_credits"]["balance_tac"] >= 100.0 # PRO fee converted

    # 7. Leaderboard & Reward Pool
    r_lb = client.get("/api/v1/prop/leaderboard/current")
    assert r_lb.status_code == 200
    assert r_lb.json()["reward_pool"]["total_budget_usdt"] >= 10000.0
