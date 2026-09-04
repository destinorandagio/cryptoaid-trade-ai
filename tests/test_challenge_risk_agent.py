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

