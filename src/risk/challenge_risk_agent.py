"""
Challenge Risk Agent — Top-Tier Institutional Prop Firm Risk Rules (Option A)
Enforces Consistency Rule, News Trading Filter, Weekend Sizing Reduction,
Drawdown Gates, and 80% Real Payout Calculations.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger("trade_ai.challenge_risk_agent")


@dataclass
class MacroEvent:
    name: str
    timestamp_utc: float
    window_minutes: int = 5  # 5 min before and after


@dataclass
class ChallengeRiskDecision:
    can_trade: bool
    position_size_multiplier: float  # 1.0 standard, 0.5 on weekends
    veto_reason: str | None
    current_total_dd_pct: float
    current_daily_dd_pct: float
    is_consistency_satisfied: bool
    highest_day_profit_ratio: float  # Must be <= 0.30 (30%)
    status: str  # ACTIVE, PASSED, FAILED
    tac_credits_awarded: float
    withdrawable_payout_usdt: float  # 80% of verified profits


class ChallengeRiskAgent:
    """
    Institutional Prop Risk Guardian for TradeAID Option A Challenges.
    """

    TARGET_PROFIT_PCT = 8.0          # +8% target
    MAX_TOTAL_DD_PCT = 10.0          # -10% max total drawdown
    MAX_DAILY_DD_PCT = 5.0           # -5% max daily drawdown
    MIN_TRADING_DAYS = 5             # Minimum 5 days
    MAX_SINGLE_DAY_PROFIT_RATIO = 0.30  # Consistency Rule: max 30% on a single day
    PAYOUT_SHARE_PCT = 0.80          # 80% profit share to user

    # Known high-impact macro events calendar (CPI, FOMC, NFP)
    SCHEDULED_EVENTS: list[MacroEvent] = [
        MacroEvent(name="US CPI Release", timestamp_utc=1788547200.0, window_minutes=5),
        MacroEvent(name="FOMC Rate Decision", timestamp_utc=1788633600.0, window_minutes=10),
    ]

    def __init__(self, tier_fee_usdt: float = 100.0, virtual_capital: float = 100000.0):
        self.tier_fee_usdt = tier_fee_usdt
        self.virtual_capital = virtual_capital

    def is_news_window_active(self, current_timestamp: float | None = None) -> tuple[bool, str | None]:
        """Checks if current time is within +-5 min of a major macro event."""
        now = current_timestamp if current_timestamp is not None else datetime.now(timezone.utc).timestamp()
        for ev in self.SCHEDULED_EVENTS:
            diff_minutes = abs(now - ev.timestamp_utc) / 60.0
            if diff_minutes <= ev.window_minutes:
                return True, f"NEWS FILTER ACTIVE: {ev.name} (+/- {ev.window_minutes}m window)"
        return False, None

    def is_weekend(self, dt: datetime | None = None) -> bool:
        """Checks if current time is weekend (Saturday=5, Sunday=6)."""
        check_dt = dt if dt is not None else datetime.now(timezone.utc)
        return check_dt.weekday() in [5, 6]

    def check_consistency(self, daily_profits_usdt: list[float], total_target_profit_usdt: float) -> tuple[bool, float]:
        """
        Consistency Rule: No single day can represent > 30% of total target profit.
        Prevents lucky single-trade gambling spikes.
        """
        if not daily_profits_usdt or total_target_profit_usdt <= 0:
            return True, 0.0

        max_day = max(daily_profits_usdt)
        if max_day <= 0:
            return True, 0.0

        ratio = max_day / total_target_profit_usdt
        is_consistent = ratio <= self.MAX_SINGLE_DAY_PROFIT_RATIO
        return is_consistent, round(ratio, 4)

    def evaluate_challenge(
        self,
        current_equity: float,
        peak_equity: float,
        daily_loss_pct: float,
        trading_days_count: int,
        daily_profits_usdt: list[float],
        cortex_violations: int = 0,
        current_timestamp: float | None = None,
    ) -> ChallengeRiskDecision:
        """
        Full evaluation of the challenge state, enforcing all 4 rules:
        1. Drawdown Gates (-10% Total, -5% Daily)
        2. Consistency Rule (max 30% per day)
        3. News Filter (5m buffer)
        4. Weekend Sizing (50% reduction)
        """
        initial = self.virtual_capital
        target_profit_usdt = initial * (self.TARGET_PROFIT_PCT / 100.0)

        # Drawdowns
        total_dd = ((peak_equity - current_equity) / peak_equity) * 100.0 if peak_equity > 0 else 0.0
        profit_usdt = current_equity - initial
        profit_pct = (profit_usdt / initial) * 100.0 if initial > 0 else 0.0

        # Check breach conditions
        total_dd_breached = total_dd >= self.MAX_TOTAL_DD_PCT
        daily_dd_breached = daily_loss_pct >= self.MAX_DAILY_DD_PCT
        cortex_breached = cortex_violations > 0

        # Consistency check
        is_consistent, highest_day_ratio = self.check_consistency(daily_profits_usdt, target_profit_usdt)

        # News & Weekend sizing
        is_news, news_reason = self.is_news_window_active(current_timestamp)
        now_dt = datetime.fromtimestamp(current_timestamp, tz=timezone.utc) if current_timestamp else datetime.now(timezone.utc)
        is_wknd = self.is_weekend(now_dt)
        size_multiplier = 0.50 if is_wknd else 1.0

        # Failure logic (Drawdowns or Risk Gate Breaches)
        if total_dd_breached or daily_dd_breached or cortex_breached:
            veto = "DRAWDOWN OR CORTEX BREACH"
            if total_dd_breached:
                veto = f"MAX TOTAL DRAWDOWN BREACHED: -{total_dd:.2f}% (Limit -{self.MAX_TOTAL_DD_PCT:.1f}%)"
            elif daily_dd_breached:
                veto = f"MAX DAILY DRAWDOWN BREACHED: -{daily_loss_pct:.2f}% (Limit -{self.MAX_DAILY_DD_PCT:.1f}%)"
            elif cortex_breached:
                veto = f"CORTEX VIOLATIONS DETECTED: {cortex_violations} (Zero Tolerance)"

            # Second Chance: fee converted to TAC credits
            return ChallengeRiskDecision(
                can_trade=False,
                position_size_multiplier=0.0,
                veto_reason=veto,
                current_total_dd_pct=round(total_dd, 2),
                current_daily_dd_pct=round(daily_loss_pct, 2),
                is_consistency_satisfied=is_consistent,
                highest_day_profit_ratio=highest_day_ratio,
                status="FAILED",
                tac_credits_awarded=self.tier_fee_usdt,
                withdrawable_payout_usdt=0.0,
            )

        # Passing logic: profit >= +8%, days >= 5, consistency satisfied
        if profit_pct >= self.TARGET_PROFIT_PCT and trading_days_count >= self.MIN_TRADING_DAYS and is_consistent:
            # Payout: 80% of verified net profit
            user_payout = profit_usdt * self.PAYOUT_SHARE_PCT
            return ChallengeRiskDecision(
                can_trade=False,
                position_size_multiplier=0.0,
                veto_reason=None,
                current_total_dd_pct=round(total_dd, 2),
                current_daily_dd_pct=round(daily_loss_pct, 2),
                is_consistency_satisfied=True,
                highest_day_profit_ratio=highest_day_ratio,
                status="PASSED",
                tac_credits_awarded=0.0,
                withdrawable_payout_usdt=round(user_payout, 2),
            )

        # Active trade execution filters (News veto, weekend dampener)
        if is_news:
            return ChallengeRiskDecision(
                can_trade=False,
                position_size_multiplier=0.0,
                veto_reason=news_reason,
                current_total_dd_pct=round(total_dd, 2),
                current_daily_dd_pct=round(daily_loss_pct, 2),
                is_consistency_satisfied=is_consistent,
                highest_day_profit_ratio=highest_day_ratio,
                status="ACTIVE",
                tac_credits_awarded=0.0,
                withdrawable_payout_usdt=0.0,
            )

        veto_note = "WEEKEND SIZING DAMPENER (50% Sizing)" if is_wknd else None

        return ChallengeRiskDecision(
            can_trade=True,
            position_size_multiplier=size_multiplier,
            veto_reason=veto_note,
            current_total_dd_pct=round(total_dd, 2),
            current_daily_dd_pct=round(daily_loss_pct, 2),
            is_consistency_satisfied=is_consistent,
            highest_day_profit_ratio=highest_day_ratio,
            status="ACTIVE",
            tac_credits_awarded=0.0,
            withdrawable_payout_usdt=0.0,
        )
