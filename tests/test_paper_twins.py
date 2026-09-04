"""Comprehensive tests for Paper Digital Twins, Strategy Switching, and Gem Hunter."""
import pytest
from fastapi.testclient import TestClient

from src.agents.strategy_switcher import StrategySwitchingEngine
from src.agents.gem_hunter import GemHunterEngine
from src.data.digital_twins import DigitalTwinsManager
from src.storage.db import DatabaseManager
from src.api.app import app


@pytest.fixture
def db(tmp_path):
    db_file = tmp_path / "test_twins.db"
    manager = DatabaseManager(db_path=str(db_file))
    return manager


def test_strategy_switcher_transitions(db):
    switcher = StrategySwitchingEngine(db=db, min_switch_cooldown_seconds=1.0)

    # 1. SCALP -> MOMENTUM on +1.5% gain
    res = switcher.evaluate_position(
        pos_id="pos_1",
        asset="POL/USDT",
        current_strategy="scalping",
        entry_price=0.40,
        current_price=0.406,  # +1.5%
        side="BUY",
        pnl_pct=1.5,
        market_regime="TRENDING",
        predicted_move_pct=0.02,
    )
    assert res.switched is True
    assert res.to_strategy.upper() == "MOMENTUM"
    assert round(res.new_sl, 4) == 0.4008  # locked break-even (+0.20%)

    # 2. Invalidation cut: SCALP with -0.45% loss and negative prediction
    res_cut = switcher.evaluate_position(
        pos_id="pos_2",
        asset="POL/USDT",
        current_strategy="scalping",
        entry_price=0.40,
        current_price=0.3982,  # -0.45%
        side="BUY",
        pnl_pct=-0.45,
        market_regime="BEARISH",
        predicted_move_pct=-0.01,
    )
    assert res_cut.should_exit is True
    assert res_cut.exit_reason == "PREDICTION_INVALIDATED"

    # 3. CORTEX Risk Veto triggers emergency exit
    res_cortex = switcher.evaluate_position(
        pos_id="pos_3",
        asset="WETH/USDT",
        current_strategy="trend_following",
        entry_price=2500.0,
        current_price=2505.0,
        cortex_risk_flag=True,
    )
    assert res_cortex.should_exit is True
    assert res_cortex.exit_reason == "CORTEX_RISK_EXIT"


def test_gem_hunter_scoring_and_exit(db):
    hunter = GemHunterEngine(db=db)

    # 1. Qualified high-potential gem candidate
    candidate = hunter.evaluate_token(
        token_address="0x1111111111111111111111111111111111111111",
        symbol="GEMTEST",
        name="Gem Test Token",
        liquidity_usd=120_000.0,
        volume_24h=150_000.0,
        holder_count=2500,
        is_honeypot=False,
        top_10_holder_pct=30.0,
        has_liquidity_lock=True,
        social_velocity_score=85.0,
    )
    assert candidate.score >= 80.0
    assert candidate.classification == "HIGH_POTENTIAL"
    assert candidate.stage == "QUALIFIED"

    # 2. Honeypot rejection
    bad_candidate = hunter.evaluate_token(
        token_address="0x9999999999999999999999999999999999999999",
        symbol="SCAM",
        name="Scam Token",
        liquidity_usd=200_000.0,
        volume_24h=500_000.0,
        holder_count=100,
        is_honeypot=True,
    )
    assert bad_candidate.classification == "REJECT"
    assert bad_candidate.score == 0.0

    # 3. Asymmetric Exit Policy: Principal Recovery at 2x (+100%)
    policy_2x = hunter.compute_exit_policy(
        entry_price=0.01,
        current_price=0.02,
        initial_tokens=10_000,
        recovered_principal=False,
    )
    assert policy_2x["action"] == "RECOVER_PRINCIPAL"
    assert policy_2x["sell_pct"] == 50.0

    # 4. Asymmetric Exit Policy: Partial TP at 4x (+300%)
    policy_4x = hunter.compute_exit_policy(
        entry_price=0.01,
        current_price=0.04,
        initial_tokens=5_000,
        recovered_principal=True,
    )
    assert policy_4x["action"] == "PARTIAL_TP_MOONBAG"
    assert policy_4x["sell_pct"] == 25.0

    # 5. Radar scan returns candidates
    radar = hunter.scan_radar(limit=5)
    assert len(radar) >= 1
    assert any(c["symbol"] in ["NEURA", "GEMTEST"] for c in radar)


def test_digital_twins_sync_and_status(db):
    twins = DigitalTwinsManager(db=db)

    # Sync events across twins
    twins.sync_market_twin("POL/USDT", 0.41, 1_200_000.0, "TRENDING")
    twins.sync_prediction_twin("fc_101", "POL/USDT", "15m", 0.42, 0.418, 0.02)
    twins.sync_strategy_twin("scalp_v1", "TRENDING", 0.004, 0.68, 50)
    twins.sync_position_twin("pos_101", "GRADUATION", {"from": "SCALP", "to": "MOMENTUM"})
    twins.sync_gem_twin("0x1111", "GEMTEST", 85.0, "QUALIFIED", 2.0)

    status = twins.get_twins_status()
    assert status["status"] == "HEALTHY_SYNCHRONIZED"
    assert status["twins"]["market_twin"]["active"] is True
    assert status["twins"]["prediction_twin"]["active"] is True
    assert status["twins"]["strategy_twin"]["active"] is True
    assert status["twins"]["position_twin"]["active"] is True
    assert status["twins"]["gem_twin"]["active"] is True


def test_paper_api_endpoints():
    client = TestClient(app)

    # 1. /paper/portfolios
    resp = client.get("/api/v1/paper/portfolios")
    assert resp.status_code == 200
    data = resp.json()
    assert "paper_safe" in data
    assert "paper_balanced" in data
    assert "paper_turbo" in data
    assert "gem_paper_fund" in data
    assert data["paper_safe"]["cash_balance"] >= 0

    # 2. /gems/radar
    resp_gems = client.get("/api/v1/gems/radar")
    assert resp_gems.status_code == 200
    gems = resp_gems.json()
    assert isinstance(gems, list)
    assert len(gems) > 0

    # 3. /twins/status
    resp_twins = client.get("/api/v1/twins/status")
    assert resp_twins.status_code == 200
    twins = resp_twins.json()
    assert twins["status"] == "HEALTHY_SYNCHRONIZED"

    # 4. /strategies/switches
    resp_switches = client.get("/api/v1/strategies/switches")
    assert resp_switches.status_code == 200
    assert isinstance(resp_switches.json(), list)
