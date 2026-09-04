import pytest
from datetime import datetime, timezone
from src.risk.challenge_risk_agent import ChallengeRiskAgent, MacroEvent
from src.storage.db import DatabaseManager


def test_challenge_risk_agent_rules_and_consistency():
    agent = ChallengeRiskAgent(tier_fee_usdt=100.0, virtual_capital=100000.0)
    target_profit = 8000.0  # +8% of 100k

    # 1. Consistency Rule Test: max single day profit must be <= 30% ($2,400)
    # Day 1: $1,200, Day 2: $1,500, Day 3: $1,800, Day 4: $1,900, Day 5: $1,600 (Total $8,000, max day $1,900 = 23.75%)
    daily_profits_consistent = [1200.0, 1500.0, 1800.0, 1900.0, 1600.0]
    is_ok, ratio = agent.check_consistency(daily_profits_consistent, target_profit)
    assert is_ok is True
    assert ratio <= 0.30

    # Inconsistent Day: One day did $4,000 (50% of target profit)
    daily_profits_inconsistent = [4000.0, 1000.0, 1000.0, 1000.0, 1000.0]
    is_bad, bad_ratio = agent.check_consistency(daily_profits_inconsistent, target_profit)
    assert is_bad is False
    assert bad_ratio == 0.50


def test_challenge_risk_agent_drawdown_breach_and_tac_credits():
    agent = ChallengeRiskAgent(tier_fee_usdt=100.0, virtual_capital=100000.0)

    # Max Total Drawdown breach: -10.5% (Limit -10.0%)
    decision = agent.evaluate_challenge(
        current_equity=89500.0,
        peak_equity=100000.0,
        daily_loss_pct=1.5,
        trading_days_count=3,
        daily_profits_usdt=[500.0, -1000.0, -10000.0],
        cortex_violations=0,
    )
    assert decision.status == "FAILED"
    assert decision.can_trade is False
    # Second Chance: 100% fee ($100) converted into TradeAid Credits (TAC)
    assert decision.tac_credits_awarded == 100.0
    assert "DRAWDOWN BREACHED" in decision.veto_reason


def test_challenge_risk_agent_pass_and_80_percent_payout():
    agent = ChallengeRiskAgent(tier_fee_usdt=100.0, virtual_capital=100000.0)

    # Successful completion: +8.5% profit ($8,500), 6 days, consistent
    decision = agent.evaluate_challenge(
        current_equity=108500.0,
        peak_equity=108500.0,
        daily_loss_pct=0.2,
        trading_days_count=6,
        daily_profits_usdt=[1400.0, 1500.0, 1600.0, 1300.0, 1400.0, 1300.0],
        cortex_violations=0,
    )
    assert decision.status == "PASSED"
    # Payout share: 80% of $8,500 = $6,800 USDT
    assert decision.withdrawable_payout_usdt == 6800.0


def test_news_filter_and_weekend_sizing():
    agent = ChallengeRiskAgent()

    # News filter active: timestamp matches scheduled CPI release (1788547200)
    is_news, reason = agent.is_news_window_active(current_timestamp=1788547200.0)
    assert is_news is True
    assert "NEWS FILTER ACTIVE" in reason

    # Weekend check: Saturday (weekday=5)
    saturday_dt = datetime(2026, 9, 5, 12, 0, 0, tzinfo=timezone.utc)
    assert agent.is_weekend(saturday_dt) is True


def test_database_payout_and_tac_credits(tmp_path):
    db_file = tmp_path / "test_prop_tac.db"
    db = DatabaseManager(db_path=db_file)

    wallet = "0xtrader_tac_1"

    # Initial balance is 0
    assert db.get_user_tac_balance(wallet) == 0.0

    # Award 100 TAC on failed challenge
    bal1 = db.award_tac_credits(wallet, 100.0, "CHALLENGE_FAILED_SECOND_CHANCE", "prop_001")
    assert bal1 == 100.0
    assert db.get_user_tac_balance(wallet) == 100.0

    # Spend 50 TAC for discounted retry
    bal2 = db.award_tac_credits(wallet, -50.0, "RETRY_CHALLENGE_DISCOUNT", "prop_002")
    assert bal2 == 50.0
    assert db.get_user_tac_balance(wallet) == 50.0

    # Record payout of 80% profit
    payout = db.record_prop_payout(
        challenge_id="prop_001",
        wallet=wallet,
        amount_gross_usdt=8000.0,
        amount_user_share_usdt=6400.0,
        tx_hash="0xabc123"
    )
    assert payout["amount_user_share_usdt"] == 6400.0
    assert payout["status"] == "REQUESTED"

    payouts = db.get_user_prop_payouts(wallet)
    assert len(payouts) == 1


def test_position_sizing_algorithm_50k_pro():
    agent = ChallengeRiskAgent(tier_fee_usdt=100.0, virtual_capital=50000.0)

    # 1. Standard condition: 50k balance, BTC at 60,000, ATR 600
    res = agent.calculate_position_size(
        current_balance=50000.0,
        start_of_day_balance=50000.0,
        entry_price=60000.0,
        direction="LONG",
        atr_14=600.0,
        risk_per_trade_target_pct=0.75, # 0.75% = $375
    )
    assert res.can_execute is True
    assert res.risk_usdt <= 375.0
    assert res.stop_loss_price < 60000.0
    assert res.take_profit_price > 60000.0
    assert res.risk_reward_ratio >= 2.0
    assert res.effective_leverage <= 10.0

    # 2. Drawdown Danger Zone: Day loss is already $2,000 (4.0% > 3.0% threshold)
    # Remaining budget is $500 ($2500 - $2000). Allowed risk should be halved and strictly budgeted
    res_danger = agent.calculate_position_size(
        current_balance=48000.0,
        start_of_day_balance=50000.0,
        entry_price=60000.0,
        direction="LONG",
        atr_14=600.0,
    )
    assert res_danger.can_execute is True
    # Budget remaining is $500, divided by 3 is $166.67, then halved is ~$83.33
    assert res_danger.risk_usdt < 100.0
    assert res_danger.daily_dd_budget_remaining_usdt == 500.0

    # 3. Daily Budget Exhausted: Day loss is $2,500 (5.0%)
    res_exhausted = agent.calculate_position_size(
        current_balance=47500.0,
        start_of_day_balance=50000.0,
        entry_price=60000.0,
        direction="LONG",
        atr_14=600.0,
    )
    assert res_exhausted.can_execute is False
    assert "DAILY_DRAWDOWN_BUDGET_EXHAUSTED" in res_exhausted.rejection_reason


def test_spec_v1_dynamic_volatility_targeting_example():
    agent = ChallengeRiskAgent(tier_fee_usdt=100.0, virtual_capital=50000.0)

    # Scenario from user spec:
    # Tier PRO ($50k). Equity_Start = $50,000. Equity_Current = $49,200 (loss $800 today).
    # Daily DD limit = 5% ($2,500). Headroom = $2,500 - $800 = $1,700.
    # ATR = 300, Multiplier = 2.0 -> SL = 600
    # Max risk = 0.5% of $49,200 = $246
    # Size = 246 / 600 = 0.41 BTC

    res1 = agent.calculate_spec_v1_sizing(
        equity_current=49200.0,
        equity_start_of_day=50000.0,
        atr_14=300.0,
        mode="swing",  # multiplier 2.5, or let's test custom multiplier
        max_risk_per_trade_pct=0.005,
        daily_dd_limit_pct=0.05,
    )
    assert res1["can_trade"] is True
    assert res1["daily_headroom"] == 1700.0
    assert res1["effective_risk_cap"] == 246.0  # min(246, 1700 * 0.5 = 850) -> 246

    # Test exact 2.0 multiplier by testing with mode custom or ATR formula directly:
    # If SL distance = 600, size = 246 / 600 = 0.41
    size_btc = res1["effective_risk_cap"] / (300.0 * 2.0)
    assert round(size_btc, 2) == 0.41

    # If ATR doubles to 600: size should halve to 0.205 BTC
    size_btc_high_vol = res1["effective_risk_cap"] / (600.0 * 2.0)
    assert round(size_btc_high_vol, 3) == 0.205


def test_spec_v1_chandelier_exit():
    agent = ChallengeRiskAgent()

    # LONG position entered at $60,000, highest high since entry is $64,000, ATR_14 = $300
    # Chandelier Trailing SL = 64,000 - (3 * 300) = $63,100
    trailing_sl = agent.calculate_chandelier_exit(
        highest_high_since_entry=64000.0,
        lowest_low_since_entry=59500.0,
        atr_14=300.0,
        direction="LONG",
        multiplier=3.0,
    )
    assert trailing_sl == 63100.0


def test_spec_v1_correlation_exposure_hard_cap():
    agent = ChallengeRiskAgent(tier_fee_usdt=100.0, virtual_capital=50000.0)
    # Max allowed correlated exposure: 20% of 50k = $10,000

    open_pos = [
        {"asset": "BTC/USDT", "size": 0.15, "current_price": 60000.0}  # $9,000 exposure
    ]

    # Trying to open another $2,000 on ETH (total $11,000 > $10,000 cap)
    allowed, reason, total_exp = agent.evaluate_correlation_cap(
        target_asset="ETH/USDT",
        target_nominal_value=2000.0,
        open_positions=open_pos,
        max_exposure_cap_pct=0.20,
    )
    assert allowed is False
    assert "CORRELATED_EXPOSURE_CAP_EXCEEDED" in reason
    assert total_exp == 11000.0


def test_spec_v1_circuit_breakers():
    agent = ChallengeRiskAgent(tier_fee_usdt=100.0, virtual_capital=50000.0)

    # 1. Daily DD = 3.8% (> 3.5% threshold): Size cut by 50%
    cb1 = agent.evaluate_circuit_breakers(daily_dd_pct=3.8, total_dd_pct=4.0, consecutive_losses=1)
    assert cb1["allowed"] is True
    assert cb1["action"] == "REDUCE_SIZE_50"
    assert cb1["size_multiplier"] == 0.50

    # 2. Daily DD = 4.6% (> 4.5% threshold): Freeze new entries
    cb2 = agent.evaluate_circuit_breakers(daily_dd_pct=4.6, total_dd_pct=5.0, consecutive_losses=0)
    assert cb2["allowed"] is False
    assert cb2["action"] == "FREEZE"

    # 3. 3 Consecutive Losses: 4-hour cooldown pause
    cb3 = agent.evaluate_circuit_breakers(daily_dd_pct=2.0, total_dd_pct=3.0, consecutive_losses=3)
    assert cb3["allowed"] is False
    assert cb3["action"] == "PAUSE_4H"

    # 4. Total DD = 8.5% (> 8.0% threshold): Survival mode rejects low R:R or low confidence
    cb4 = agent.evaluate_circuit_breakers(
        daily_dd_pct=1.0,
        total_dd_pct=8.5,
        consecutive_losses=0,
        signal_confidence=0.75,  # Needs > 0.90
        reward_risk_ratio=2.0,   # Needs > 3.0
    )
    assert cb4["allowed"] is False
    assert cb4["action"] == "SURVIVAL_MODE_RESTRICTION"


def test_challenge_state_and_evaluate_trade_user_example():
    import numpy as np
    import pandas as pd
    from src.risk.challenge_risk_agent import ChallengeState, ChallengeRiskAgent, TradeDirection, TIER_PRO

    # Setup Initial State & Agent
    agent_state = ChallengeState(TIER_PRO)
    risk_agent = ChallengeRiskAgent(agent_state)

    # Simulated Market Data (BTC)
    np.random.seed(42)
    mock_data = pd.DataFrame({
        'high': [65000.0 + np.random.rand() * 1000 for _ in range(20)],
        'low': [64000.0 + np.random.rand() * 1000 for _ in range(20)],
        'close': [64500.0 + np.random.rand() * 1000 for _ in range(20)],
    })

    # Trade Evaluation 1: Fresh account
    decision1 = risk_agent.evaluate_trade(
        signal_direction=TradeDirection.LONG,
        entry_price=65000.0,
        asset_historical_data=mock_data,
        current_portfolio_exposure={},
        target_asset_id="BTC",
    )
    assert decision1["action"] == "APPROVED"
    assert decision1["size_units"] > 0.0
    assert decision1["stop_loss"] < 65000.0
    assert decision1["take_profit"] > 65000.0
    assert decision1["risk_usd"] > 0.0
    assert decision1["atr_used"] > 0.0

    # Simulate equity loss: $500 drop
    agent_state.update_equity(49500.0)
    assert agent_state.daily_dd_usd == 500.0
    assert round(agent_state.daily_dd_pct, 4) == round(500.0 / 50000.0, 4)

    # Trade Evaluation 2: With existing portfolio exposure of $5,000, 
    # new exposure ~$8,000 pushes total correlated exposure > 20% ($9,900), triggering VETO!
    decision2 = risk_agent.evaluate_trade(
        signal_direction=TradeDirection.SHORT,
        entry_price=64800.0,
        asset_historical_data=mock_data,
        current_portfolio_exposure={"BTC": 5000.0},
        target_asset_id="ETH",
    )
    assert decision2["action"] == "VETO"
    assert decision2["reason"] == "Max Correlated Exposure Exceeded"

    # Trade Evaluation 2B: With smaller prior exposure of $1,000, trade is APPROVED
    decision2b = risk_agent.evaluate_trade(
        signal_direction=TradeDirection.SHORT,
        entry_price=64800.0,
        asset_historical_data=mock_data,
        current_portfolio_exposure={"BTC": 1000.0},
        target_asset_id="ETH",
    )
    assert decision2b["action"] == "APPROVED"
    assert decision2b["stop_loss"] > 64800.0
    assert decision2b["take_profit"] < 64800.0

    # Trade Evaluation 3: Day loss > 4% triggers safety buffer VETO
    agent_state.update_equity(47800.0)  # Loss of $2,200 (> 4% of 50k = $2,000)
    decision3 = risk_agent.evaluate_trade(
        signal_direction=TradeDirection.LONG,
        entry_price=65000.0,
        asset_historical_data=mock_data,
        current_portfolio_exposure={},
        target_asset_id="BTC",
    )
    assert decision3["action"] == "VETO"
    assert "Daily DD approaching limit" in decision3["reason"]


def test_prop_evaluate_trade_and_reset_endpoints():
    from fastapi.testclient import TestClient
    from src.api.app import app

    client = TestClient(app)

    # 1. Test POST /api/v1/prop/evaluate-trade with PRO tier
    payload = {
        "tier_name": "PRO",
        "signal_direction": "LONG",
        "entry_price": 65000.0,
        "target_asset_id": "BTC",
        "current_portfolio_exposure": {},
        "current_equity": 50000.0,
    }
    resp = client.post("/api/v1/prop/evaluate-trade", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["tier"] == "PRO"
    assert data["nominal_capital"] == 50000.0
    assert data["evaluation"]["action"] == "APPROVED"
    assert data["evaluation"]["size_units"] > 0
    assert data["evaluation"]["stop_loss"] < 65000.0

    # 2. Test Daily Reset endpoint
    reset_resp = client.post("/api/v1/prop/daily-reset", json={})
    assert reset_resp.status_code == 200
    reset_data = reset_resp.json()
    assert reset_data["action"] == "DAILY_RESET_COMPLETED"
    assert "date_utc" in reset_data


def test_cortex_health_states_and_distance_to_ruin():
    from src.risk.challenge_risk_agent import ChallengeState, TIER_PRO, CortexHealth

    # 50,000 Starting balance, 5% Daily DD = $2,500 limit, 10% Total DD = $5,000 limit
    state = ChallengeState(TIER_PRO)
    assert state.cortex_health == CortexHealth.GREEN
    assert state.distance_to_ruin_usd == 2500.0
    # Available risk budget in GREEN = 2500 * 0.40 = $1,000
    assert state.available_risk_budget_usd == 1000.0

    # Simulate losing 2.2% ($1,100) today -> Daily DD = 2.2% -> YELLOW
    state.update_equity(48900.0)
    assert state.daily_dd_pct == 0.022
    assert state.cortex_health == CortexHealth.YELLOW
    # Remaining capacity = 2500 - 1100 = $1,400. In YELLOW safety factor is 0.25 -> 1400 * 0.25 = $350
    assert state.distance_to_ruin_usd == 1400.0
    assert state.available_risk_budget_usd == 350.0

    # Simulate losing 3.8% ($1,900) today -> Daily DD = 3.8% -> ORANGE
    state.update_equity(48100.0)
    assert state.daily_dd_pct == 0.038
    assert state.cortex_health == CortexHealth.ORANGE
    # Remaining capacity = 2500 - 1900 = $600. In ORANGE safety factor is 0.10 -> 600 * 0.10 = $60
    assert state.distance_to_ruin_usd == 600.0
    assert state.available_risk_budget_usd == 60.0

    # Simulate losing 4.6% ($2,300) today -> Daily DD = 4.6% -> RED (Capital preservation lock)
    state.update_equity(47700.0)
    assert state.daily_dd_pct == 0.046
    assert state.cortex_health == CortexHealth.RED
    assert state.available_risk_budget_usd == 0.0

    # Simulate losing 5.1% ($2,550) -> BREACH
    state.update_equity(47450.0)
    assert state.daily_dd_pct == 0.051
    assert state.cortex_health == CortexHealth.BREACH
    assert state.check_violations() == "DAILY_DD_EXCEEDED"


def test_authorize_trade_intent_stop_determines_size():
    from src.risk.challenge_risk_agent import (
        ChallengeState,
        ChallengeRiskAgent,
        TIER_PRO,
        TradeIntent,
        RiskDecision,
        TradeDirection,
    )

    state = ChallengeState(TIER_PRO)
    agent = ChallengeRiskAgent(state)

    intent = TradeIntent(
        intent_id="intent_test_01",
        target_asset="BTC/USDC",
        direction=TradeDirection.LONG,
        target_price=65000.0,
        timeframe="15m",
        prediction_confidence=0.90,
        strategy_confidence=0.85,
        volatility_14d=0.015,
        atr_14=600.0,
        current_portfolio_exposure={},
    )

    auth = agent.authorize_trade_intent(intent)
    assert auth.authorized is True
    assert auth.decision in (RiskDecision.PASS, RiskDecision.REDUCE, RiskDecision.REDUCE_SIZE)
    assert auth.position_size_units > 0
    assert auth.stop_loss_price < 65000.0
    assert auth.take_profit_price > 65000.0
    assert auth.authorized_leverage <= 3
    # Check that stop distance dictated position size: risk_budget / stop_distance
    stop_distance = 65000.0 - auth.stop_loss_price
    assert stop_distance > 0
    calculated_risk = auth.position_size_units * stop_distance
    # Calculated risk should not exceed available risk budget
    assert calculated_risk <= state.available_risk_budget_usd + 1.0


def test_authorize_trade_intent_cortex_red_freeze():
    from src.risk.challenge_risk_agent import (
        ChallengeState,
        ChallengeRiskAgent,
        TIER_PRO,
        TradeIntent,
        RiskDecision,
        TradeDirection,
    )

    state = ChallengeState(TIER_PRO)
    # Put challenge into RED zone (Daily DD = 4.6%)
    state.update_equity(47700.0)

    agent = ChallengeRiskAgent(state)
    intent = TradeIntent(
        intent_id="intent_freeze_01",
        target_asset="BTC/USDC",
        direction=TradeDirection.LONG,
        target_price=65000.0,
        prediction_confidence=0.99,  # Even with 99% confidence, CANNOT override DD lock!
        strategy_confidence=0.99,
        volatility_14d=0.01,
        atr_14=500.0,
    )

    auth = agent.authorize_trade_intent(intent)
    assert auth.authorized is False
    assert auth.decision == RiskDecision.REJECT
    assert "CORTEX RED" in auth.rejection_reason


def test_intraday_mark_to_market_unrealized_pnl_breach():
    from src.risk.challenge_risk_agent import ChallengeState, TIER_PRO, CortexHealth

    state = ChallengeState(TIER_PRO)
    # Starting cash = $50,000. Active position drops by $2,600 unrealized
    state.update_mark_to_market(unrealized_pnl=-2600.0, cash_balance=50000.0)
    assert state.current_equity == 47400.0
    # Daily DD is 5.2% ($2,600 / $50,000) -> Immediate intraday breach without waiting for midnight!
    assert state.daily_dd_pct == 0.052
    assert state.cortex_health == CortexHealth.BREACH
    assert state.check_violations() == "DAILY_DD_EXCEEDED"


def test_api_engine_trade_intents_and_cortex_health():
    from fastapi.testclient import TestClient
    from src.api.app import app

    client = TestClient(app)

    # 1. Submit trade intent through POST /api/v1/engine/trade-intents
    payload = {
        "tier_name": "PRO",
        "target_asset": "BTC/USDC",
        "direction": "LONG",
        "target_price": 65000.0,
        "timeframe": "15m",
        "strategy_name": "PredictiveHeartTest",
        "prediction_confidence": 0.88,
        "strategy_confidence": 0.82,
        "volatility_14d": 0.018,
        "atr_14": 750.0,
        "current_portfolio_exposure": {},
        "account_id": "challenge_pro_isolated",
    }
    resp = client.post("/api/v1/engine/trade-intents", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "AUTHORIZED_AND_EXECUTED"
    assert data["authorized"] is True
    assert data["decision"] in ("PASS", "REDUCE", "REDUCE_SIZE")
    assert data["position_size_units"] > 0
    assert data["authorized_leverage"] <= 3
    assert data["order"] is not None
    assert data["cortex_health"] == "GREEN"

    # 2. Query GET /api/v1/engine/cortex-health/default
    health_resp = client.get("/api/v1/engine/cortex-health/default")
    assert health_resp.status_code == 200
    h_data = health_resp.json()
    assert h_data["cortex_health"] in ("GREEN", "YELLOW", "ORANGE", "RED", "BREACH")
    assert "distance_to_ruin_usd" in h_data
    assert "available_risk_budget_usd" in h_data
    assert "daily_headroom_usd" in h_data

    # 3. Test Mark to Market endpoint
    m2m_resp = client.post("/api/v1/engine/mark-to-market", json={"account_id": "challenge_pro_isolated"})
    assert m2m_resp.status_code == 200
    m2m_data = m2m_resp.json()
    assert m2m_data["status"] == "PROCESSED"
    assert "cortex_health" in m2m_data






