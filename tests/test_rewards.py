"""Unit tests for TradeAID Anti-Sybil Reward Engine and Autotrade Authorization."""
from __future__ import annotations

import tempfile
from pathlib import Path

from src.rewards.reward_engine import RewardEngine
from src.storage.db import DatabaseManager


def test_reward_engine_anti_sybil_and_eligibility():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_rewards.db"
        db = DatabaseManager(db_path=db_path)
        engine = RewardEngine(db_manager=db, live_mode=False)

        wallet = "0x71c691843364c25c480b9b0c0d4988243a4049b2"

        # 1. First claim for ONBOARDING_WALLET should succeed (10 POL)
        claim1 = engine.claim_reward(wallet=wallet, action="ONBOARDING_WALLET")
        assert claim1["status"] == "SUCCESS"
        assert claim1["claimed"] is True
        assert claim1["total_wallet_pol"] == 10.0
        assert claim1["reward_event"]["pol_reward"] == 10.0

        # 2. Duplicate claim for ONBOARDING_WALLET should be REJECTED (Anti-Sybil rule)
        claim_dup = engine.claim_reward(wallet=wallet, action="ONBOARDING_WALLET")
        assert claim_dup["status"] == "REJECTED"
        assert claim_dup["claimed"] is False
        assert "already been claimed" in claim_dup["reason"]

        # 3. Another qualified action (AUTOTRADE_ACTIVATION) should succeed
        claim2 = engine.claim_reward(wallet=wallet, action="AUTOTRADE_ACTIVATION")
        assert claim2["status"] == "SUCCESS"
        assert claim2["total_wallet_pol"] == 20.0

        # 4. Check wallet summary
        summary = engine.get_wallet_reward_summary(wallet)
        assert summary["total_pol_reward"] == 20.0
        assert summary["events_count"] == 2
        # Remaining actions
        avail = [a["action"] for a in summary["available_actions"]]
        assert "FIRST_10_PAPER_TRADES" in avail
        assert "ONBOARDING_WALLET" not in avail


def test_autotrade_session_authorization():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_auth.db"
        db = DatabaseManager(db_path=db_path)

        wallet = "0x9876543210abcdef9876543210abcdef98765432"

        # Record authorization
        auth = db.record_autotrade_authorization(
            wallet=wallet,
            mode="PAPER",
            initial_capital_usdt=1000.0,
            risk_profile="BALANCED",
            max_risk_pct=2.0,
            stop_ceiling_pct=-5.0,
        )

        assert auth["wallet"] == wallet.lower()
        assert auth["mode"] == "PAPER"
        assert auth["is_active"] == 1

        # Check active status
        active_auth = db.get_active_autotrade_authorization(wallet)
        assert active_auth is not None
        assert active_auth["id"] == auth["id"]
