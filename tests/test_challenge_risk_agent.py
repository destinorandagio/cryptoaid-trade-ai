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
