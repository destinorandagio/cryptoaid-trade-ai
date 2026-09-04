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
class PositionSizingResult:
    can_execute: bool
    rejection_reason: str | None
    quantity: float
    nominal_value_usdt: float
    effective_leverage: float
    risk_usdt: float
    risk_pct_balance: float
    entry_price: float
    stop_loss_price: float
    take_profit_price: float
    sl_distance_usdt: float
    tp_distance_usdt: float
    risk_reward_ratio: float
    daily_dd_budget_remaining_usdt: float


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

    def calculate_position_size(
        self,
        current_balance: float,
        start_of_day_balance: float,
        entry_price: float,
        direction: str,  # 'LONG' or 'SHORT'
        atr_14: float,
        risk_per_trade_target_pct: float = 0.75,  # Standard 0.75% risk per trade
        atr_multiplier: float = 1.8,
        min_risk_reward_ratio: float = 2.0,
        max_leverage: float = 10.0,
        current_timestamp: float | None = None,
    ) -> PositionSizingResult:
        """
        Calculates exact position size and dynamic SL/TP levels engineered to strictly
        prevent breaching the 5.0% Daily Drawdown and 10.0% Total Drawdown limits.
        """
        # 1. Check macro news blackout
        is_news, news_reason = self.is_news_window_active(current_timestamp)
        if is_news:
            return PositionSizingResult(
                can_execute=False,
                rejection_reason=news_reason,
                quantity=0.0,
                nominal_value_usdt=0.0,
                effective_leverage=0.0,
                risk_usdt=0.0,
                risk_pct_balance=0.0,
                entry_price=entry_price,
                stop_loss_price=0.0,
                take_profit_price=0.0,
                sl_distance_usdt=0.0,
                tp_distance_usdt=0.0,
                risk_reward_ratio=0.0,
                daily_dd_budget_remaining_usdt=0.0,
            )

        if current_balance <= 0 or entry_price <= 0:
            return PositionSizingResult(
                can_execute=False,
                rejection_reason="INVALID_PRICE_OR_BALANCE",
                quantity=0.0,
                nominal_value_usdt=0.0,
                effective_leverage=0.0,
                risk_usdt=0.0,
                risk_pct_balance=0.0,
                entry_price=entry_price,
                stop_loss_price=0.0,
                take_profit_price=0.0,
                sl_distance_usdt=0.0,
                tp_distance_usdt=0.0,
                risk_reward_ratio=0.0,
                daily_dd_budget_remaining_usdt=0.0,
            )

        # 2. Drawdown headroom computation
        max_daily_loss_usdt = start_of_day_balance * (self.MAX_DAILY_DD_PCT / 100.0)
        current_day_loss_usdt = max(0.0, start_of_day_balance - current_balance)
        daily_budget_remaining_usdt = max(0.0, max_daily_loss_usdt - current_day_loss_usdt)

        if daily_budget_remaining_usdt <= 0.0:
            return PositionSizingResult(
                can_execute=False,
                rejection_reason=f"DAILY_DRAWDOWN_BUDGET_EXHAUSTED (Loss: ${current_day_loss_usdt:.2f} >= Limit: ${max_daily_loss_usdt:.2f})",
                quantity=0.0,
                nominal_value_usdt=0.0,
                effective_leverage=0.0,
                risk_usdt=0.0,
                risk_pct_balance=0.0,
                entry_price=entry_price,
                stop_loss_price=0.0,
                take_profit_price=0.0,
                sl_distance_usdt=0.0,
                tp_distance_usdt=0.0,
                risk_reward_ratio=0.0,
                daily_dd_budget_remaining_usdt=0.0,
            )

        # 3. Base single-trade risk dollar allocation
        # Maximum 0.75% of current equity, and never more than 1/3 of the remaining daily DD buffer
        standard_trade_risk_usdt = current_balance * (risk_per_trade_target_pct / 100.0)
        buffer_trade_risk_usdt = daily_budget_remaining_usdt / 3.0
        allowed_risk_usdt = min(standard_trade_risk_usdt, buffer_trade_risk_usdt)

        # 4. Volatility dampeners
        # Weekend sizing: reduce risk budget by 50%
        now_dt = datetime.fromtimestamp(current_timestamp, tz=timezone.utc) if current_timestamp else datetime.now(timezone.utc)
        if self.is_weekend(now_dt):
            allowed_risk_usdt *= 0.50

        # Drawdown danger zone dampener (if daily loss > 3.0%)
        current_daily_dd_pct = (current_day_loss_usdt / start_of_day_balance) * 100.0 if start_of_day_balance > 0 else 0.0
        if current_daily_dd_pct >= 3.0:
            allowed_risk_usdt *= 0.50  # Cut size by half in yellow caution zone

        # 5. Dynamic Stop Loss distance (ATR-based with 0.8% floor)
        min_sl_distance = entry_price * 0.008  # 0.8% minimum distance to avoid market noise
        sl_distance = max(atr_14 * atr_multiplier, min_sl_distance)
        tp_distance = sl_distance * min_risk_reward_ratio

        direction_upper = direction.upper()
        if direction_upper == "LONG":
            sl_price = max(0.00000001, entry_price - sl_distance)
            tp_price = entry_price + tp_distance
        else:
            sl_price = entry_price + sl_distance
            tp_price = max(0.00000001, entry_price - tp_distance)

        # 6. Sizing math: Quantity = Allowed Risk / SL Distance
        quantity = allowed_risk_usdt / sl_distance
        nominal_val = quantity * entry_price
        effective_leverage = nominal_val / current_balance

        # 7. Leverage clamp (e.g. 10x max)
        if effective_leverage > max_leverage:
            nominal_val = current_balance * max_leverage
            quantity = nominal_val / entry_price
            allowed_risk_usdt = quantity * sl_distance
            effective_leverage = max_leverage

        # 8. Consistency Rule Cap on Take Profit
        # Single trade profit should never exceed 30% of total target profit in one swing
        total_target_profit_usdt = self.virtual_capital * (self.TARGET_PROFIT_PCT / 100.0)
        max_allowed_single_trade_tp_usdt = total_target_profit_usdt * self.MAX_SINGLE_DAY_PROFIT_RATIO
        potential_profit_usdt = quantity * tp_distance

        if potential_profit_usdt > max_allowed_single_trade_tp_usdt and potential_profit_usdt > 0:
            scale_down = max_allowed_single_trade_tp_usdt / potential_profit_usdt
            quantity *= scale_down
            nominal_val = quantity * entry_price
            allowed_risk_usdt = quantity * sl_distance
            effective_leverage = nominal_val / current_balance

        actual_risk_pct = (allowed_risk_usdt / current_balance) * 100.0 if current_balance > 0 else 0.0

        return PositionSizingResult(
            can_execute=True,
            rejection_reason=None,
            quantity=round(quantity, 8),
            nominal_value_usdt=round(nominal_val, 2),
            effective_leverage=round(effective_leverage, 2),
            risk_usdt=round(allowed_risk_usdt, 2),
            risk_pct_balance=round(actual_risk_pct, 3),
            entry_price=round(entry_price, 4),
            stop_loss_price=round(sl_price, 4),
            take_profit_price=round(tp_price, 4),
            sl_distance_usdt=round(sl_distance, 4),
            tp_distance_usdt=round(tp_distance, 4),
            risk_reward_ratio=round(tp_distance / sl_distance, 2) if sl_distance > 0 else 0.0,
            daily_dd_budget_remaining_usdt=round(daily_budget_remaining_usdt, 2),
        )

    # -------------------------------------------------------------------------
    # SPEC V1 MATHEMATICAL ENGINE (Dynamic Volatility Targeting & Survival)
    # -------------------------------------------------------------------------

    def calculate_spec_v1_sizing(
        self,
        equity_current: float,
        equity_start_of_day: float,
        atr_14: float,
        mode: str = "scalping",
        max_risk_per_trade_pct: float = 0.005,  # 0.5% Golden Rule
        daily_dd_limit_pct: float = 0.05,        # 5.0% Daily Limit
    ) -> dict[str, Any]:
        """
        Implements the exact Spec V1 Dynamic Volatility Targeting formula:
        Step A: daily_headroom = (Equity_StartOfDay * Daily_DD_Limit) - (Equity_StartOfDay - Equity_Current)
        Step B: stop_loss_distance = ATR_14 * Multiplier_SL (1.5 for Scalping, 2.5 for Swing)
        Step C: effective_risk_cap = min(Equity_Current * max_risk_pct, daily_headroom * 0.5)
        """
        # Step A: Daily Headroom
        max_daily_dd_dollars = equity_start_of_day * daily_dd_limit_pct
        current_loss_today = max(0.0, equity_start_of_day - equity_current)
        daily_headroom = max(0.0, max_daily_dd_dollars - current_loss_today)

        if daily_headroom <= 0.0:
            return {
                "can_trade": False,
                "reason": "DAILY_HEADROOM_EXHAUSTED",
                "position_size_units": 0.0,
                "effective_risk_cap": 0.0,
                "daily_headroom": 0.0,
                "stop_loss_distance": 0.0,
            }

        # Step B: Stop Loss Distance (ATR Based)
        multiplier_sl = 1.5 if mode.lower() == "scalping" else 2.5
        stop_loss_distance = atr_14 * multiplier_sl

        if stop_loss_distance <= 0:
            return {
                "can_trade": False,
                "reason": "INVALID_ATR_DISTANCE",
                "position_size_units": 0.0,
                "effective_risk_cap": 0.0,
                "daily_headroom": daily_headroom,
                "stop_loss_distance": 0.0,
            }

        # Step C: Size with Fixed Fractional Risk adjusted by Headroom
        risk_amount_usdt = equity_current * max_risk_per_trade_pct
        effective_risk_cap = min(risk_amount_usdt, daily_headroom * 0.5)
        position_size_units = effective_risk_cap / stop_loss_distance

        return {
            "can_trade": True,
            "reason": None,
            "daily_headroom": round(daily_headroom, 2),
            "multiplier_sl": multiplier_sl,
            "stop_loss_distance": round(stop_loss_distance, 4),
            "risk_amount_usdt": round(risk_amount_usdt, 2),
            "effective_risk_cap": round(effective_risk_cap, 2),
            "position_size_units": round(position_size_units, 6),
            "risk_params_used": {
                "atr_value": atr_14,
                "sl_multiplier": multiplier_sl,
                "risk_pct": max_risk_per_trade_pct * 100.0,
                "daily_headroom": round(daily_headroom, 2),
                "correlation_adjustment": 1.0,
            },
        }

    def calculate_chandelier_exit(
        self,
        highest_high_since_entry: float,
        lowest_low_since_entry: float,
        atr_14: float,
        direction: str = "LONG",
        multiplier: float = 3.0,
    ) -> float:
        """
        Chandelier Exit:
        LONG:  Trailing_SL = Highest_High_since_Entry - (3 * ATR_14)
        SHORT: Trailing_SL = Lowest_Low_since_Entry + (3 * ATR_14)
        """
        if direction.upper() == "LONG":
            return max(0.00000001, highest_high_since_entry - (multiplier * atr_14))
        else:
            return lowest_low_since_entry + (multiplier * atr_14)

    def evaluate_correlation_cap(
        self,
        target_asset: str,
        target_nominal_value: float,
        open_positions: list[dict[str, Any]],
        correlation_threshold: float = 0.70,
        max_exposure_cap_pct: float = 0.20,  # Hard Cap: max 20% correlated exposure
    ) -> tuple[bool, str | None, float]:
        """
        Enforces Section 4 Correlation & Exposure Hard Cap:
        If correlation > 0.7 with open positions, total correlated exposure must not exceed 20% nominal capital.
        """
        max_allowed_correlated_usdt = self.virtual_capital * max_exposure_cap_pct
        correlated_exposure = target_nominal_value

        # High correlation clusters (e.g. BTC, ETH, SOL, POL crypto beta)
        crypto_majors = {"BTC", "ETH", "SOL", "POL", "WBTC", "WETH"}
        target_base = target_asset.split("/")[0].upper()

        for pos in open_positions:
            pos_asset = pos.get("asset", "").split("/")[0].upper()
            pos_nominal = float(pos.get("size", 0.0)) * float(pos.get("current_price", pos.get("entry_price", 1.0)))

            # If both are in the major beta cluster, assume Pearson correlation > 0.70
            if (target_base in crypto_majors and pos_asset in crypto_majors) or target_base == pos_asset:
                correlated_exposure += pos_nominal

        if correlated_exposure > max_allowed_correlated_usdt:
            return (
                False,
                f"CORRELATED_EXPOSURE_CAP_EXCEEDED: ${correlated_exposure:,.2f} > Max 20% (${max_allowed_correlated_usdt:,.2f})",
                correlated_exposure,
            )

        return True, None, correlated_exposure

    def evaluate_circuit_breakers(
        self,
        daily_dd_pct: float,
        total_dd_pct: float,
        consecutive_losses: int,
        signal_confidence: float = 0.80,
        reward_risk_ratio: float = 2.0,
        current_timestamp: float | None = None,
    ) -> dict[str, Any]:
        """
        Enforces Section 5 Circuit Breakers:
        - Daily DD > 3.5%: Reduce size by 50%
        - Daily DD > 4.5%: Freeze new entries
        - Total DD > 8%: Survival Mode (Only R:R > 3:1 and Confidence > 0.9)
        - 3 Consecutive Losses: 4-hour pause
        - News blackout: +/- 5 min
        """
        is_news, news_reason = self.is_news_window_active(current_timestamp)
        if is_news:
            return {"action": "FREEZE", "allowed": False, "reason": news_reason, "size_multiplier": 0.0}

        if daily_dd_pct >= 4.5:
            return {"action": "FREEZE", "allowed": False, "reason": f"DAILY_DD_CRITICAL ({daily_dd_pct:.2f}% >= 4.5%)", "size_multiplier": 0.0}

        if consecutive_losses >= 3:
            return {"action": "PAUSE_4H", "allowed": False, "reason": "3_CONSECUTIVE_LOSSES_PAUSE_4H", "size_multiplier": 0.0}

        if total_dd_pct >= 8.0:
            if signal_confidence < 0.90 or reward_risk_ratio < 3.0:
                return {
                    "action": "SURVIVAL_MODE_RESTRICTION",
                    "allowed": False,
                    "reason": f"SURVIVAL_MODE (Total DD {total_dd_pct:.2f}% >= 8.0% requires R:R > 3.0 & Confidence > 0.90)",
                    "size_multiplier": 0.0,
                }

        size_multiplier = 0.50 if daily_dd_pct >= 3.5 else 1.0
        return {
            "action": "REDUCE_SIZE_50" if daily_dd_pct >= 3.5 else "NORMAL",
            "allowed": True,
            "reason": "DAILY_DD_YELLOW_ZONE (Size reduced 50%)" if daily_dd_pct >= 3.5 else None,
            "size_multiplier": size_multiplier,
        }

