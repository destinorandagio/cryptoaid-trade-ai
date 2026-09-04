"""
TradeAID Prop Challenge Engine — Multi-Tier System (50k, 100k, 150k)
With "No-Loss" Internal Trading Credit Recovery Guarantee (Option A).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger("trade_ai.prop_challenge")

PROP_TIERS = {
    "50K": {
        "tier_name": "50K STARTER PROP",
        "account_size": 50000.0,
        "challenge_fee_usdt": 50.0,
        "target_pct": 8.0,
        "target_profit_usdt": 4000.0,
        "max_total_dd_pct": 8.0,
        "max_total_dd_usdt": 4000.0,
        "max_daily_dd_pct": 4.0,
        "max_daily_dd_usdt": 2000.0,
        "min_days": 5,
        "popular": False,
    },
    "100K": {
        "tier_name": "100K PRO PROP",
        "account_size": 100000.0,
        "challenge_fee_usdt": 100.0,
        "target_pct": 8.0,
        "target_profit_usdt": 8000.0,
        "max_total_dd_pct": 8.0,
        "max_total_dd_usdt": 8000.0,
        "max_daily_dd_pct": 4.0,
        "max_daily_dd_usdt": 4000.0,
        "min_days": 5,
        "popular": True,
    },
    "150K": {
        "tier_name": "150K ELITE PROP",
        "account_size": 150000.0,
        "challenge_fee_usdt": 1500.0,
        "target_pct": 8.0,
        "target_profit_usdt": 12000.0,
        "max_total_dd_pct": 8.0,
        "max_total_dd_usdt": 12000.0,
        "max_daily_dd_pct": 4.0,
        "max_daily_dd_usdt": 6000.0,
        "min_days": 5,
        "popular": False,
    },
}


@dataclass
class ChallengeStatusResult:
    challenge_id: str
    wallet: str
    tier: str
    tier_name: str
    challenge_fee_usdt: float
    mode: str
    initial_equity: float
    current_equity: float
    profit_usdt: float
    profit_pct: float
    target_pct: float
    target_profit_usdt: float
    target_achieved: bool
    current_total_dd_pct: float
    max_total_dd_pct: float
    max_total_dd_usdt: float
    total_dd_breached: bool
    current_daily_dd_pct: float
    max_daily_dd_pct: float
    max_daily_dd_usdt: float
    daily_dd_breached: bool
    cortex_violations: int
    trading_days: int
    min_trading_days: int
    status: str  # ACTIVE, QUALIFIED, FAILED
    trading_credit_usdt: float  # Credito interno se fallisce
    withdrawable_profits_usdt: float  # Guadagni generati dal credito interno
    prop_score: float
    rank_position: int
    share_text: str


class PropChallengeEngine:
    """
    Evaluates TradeAID Multi-Tier Prop Challenge progression.
    Features No-Loss Challenge Fee conversion to Internal Trading Credit.
    """

    def __init__(self):
        self.tiers = PROP_TIERS

    def get_tier_config(self, tier_key: str = "100K") -> dict[str, Any]:
        key = tier_key.upper()
        return self.tiers.get(key, self.tiers["100K"])

    def evaluate(self, challenge: dict[str, Any]) -> ChallengeStatusResult:
        tier_key = str(challenge.get("tier", "100K")).upper()
        tier_conf = self.get_tier_config(tier_key)

        initial = float(challenge.get("initial_equity", tier_conf["account_size"]))
        current = float(challenge.get("current_equity", initial))
        peak = float(challenge.get("peak_equity", initial))
        if current > peak:
            peak = current

        profit_usdt = current - initial
        profit_pct = ((current - initial) / initial) * 100.0 if initial > 0 else 0.0

        # Drawdown calculation
        total_dd = ((peak - current) / peak) * 100.0 if peak > 0 else 0.0
        daily_dd = float(challenge.get("current_daily_dd_pct", 0.0))
        cortex_violations = int(challenge.get("cortex_violations", 0))
        days = int(challenge.get("trading_days_count", 1))

        # Check breach conditions
        total_dd_breached = total_dd >= tier_conf["max_total_dd_pct"]
        daily_dd_breached = daily_dd >= tier_conf["max_daily_dd_pct"]
        cortex_breached = cortex_violations > 0

        # Status logic
        current_status = challenge.get("status", "ACTIVE")
        if total_dd_breached or daily_dd_breached or cortex_breached:
            status = "FAILED"
            # NO-LOSS GUARANTEE: Challenge Fee converts to Internal Trading Credit
            trading_credit = float(challenge.get("trading_credit_usdt", tier_conf["challenge_fee_usdt"]))
        elif profit_pct >= tier_conf["target_pct"] and days >= tier_conf["min_days"]:
            status = "QUALIFIED"
            trading_credit = 0.0
        else:
            status = current_status if current_status in ["QUALIFIED", "FAILED"] else "ACTIVE"
            trading_credit = float(challenge.get("trading_credit_usdt", 0.0))

        withdrawable_profits = float(challenge.get("withdrawable_profits_usdt", 0.0))

        # Calculate Prop Discipline Score (0-100)
        progress_factor = min(1.0, max(0.0, profit_pct / tier_conf["target_pct"])) * 40.0
        dd_buffer_factor = max(0.0, (1.0 - (total_dd / tier_conf["max_total_dd_pct"]))) * 20.0
        discipline_factor = 40.0 if cortex_violations == 0 else max(0.0, 40.0 - (cortex_violations * 15.0))
        prop_score = round(progress_factor + dd_buffer_factor + discipline_factor, 1)

        # Dynamic Rank
        rank = int(challenge.get("rank_position", 238))
        if profit_pct > 3.0:
            rank = max(12, rank - int(profit_pct * 15))

        # Viral Share Text
        share_text = (
            f"🏆 TRADEAID PROP CHALLENGE ({tier_conf['tier_name']})\n"
            f"• Capital: ${initial:,.0f} USDT (PAPER)\n"
            f"• Progress: {profit_pct:+.2f}% / +{tier_conf['target_pct']:.1f}% (${profit_usdt:+,.2f})\n"
            f"• Max DD: {total_dd:.2f}% / {tier_conf['max_total_dd_pct']:.1f}%\n"
            f"• CORTEX Violations: {cortex_violations}\n"
            f"• Prop Score: {prop_score}/100 | Rank #{rank}\n"
            f"🛡 100% Fee-Back Credit Guarantee on Failure\n"
            f"👉 Test TradeAID Prop: https://trade.cryptoaid.support/dapp.html"
        )

        return ChallengeStatusResult(
            challenge_id=challenge["id"],
            wallet=challenge["wallet"],
            tier=tier_key,
            tier_name=tier_conf["tier_name"],
            challenge_fee_usdt=tier_conf["challenge_fee_usdt"],
            mode=challenge.get("mode", "BALANCED"),
            initial_equity=initial,
            current_equity=current,
            profit_usdt=round(profit_usdt, 2),
            profit_pct=round(profit_pct, 2),
            target_pct=tier_conf["target_pct"],
            target_profit_usdt=tier_conf["target_profit_usdt"],
            target_achieved=profit_pct >= tier_conf["target_pct"],
            current_total_dd_pct=round(total_dd, 2),
            max_total_dd_pct=tier_conf["max_total_dd_pct"],
            max_total_dd_usdt=tier_conf["max_total_dd_usdt"],
            total_dd_breached=total_dd_breached,
            current_daily_dd_pct=round(daily_dd, 2),
            max_daily_dd_pct=tier_conf["max_daily_dd_pct"],
            max_daily_dd_usdt=tier_conf["max_daily_dd_usdt"],
            daily_dd_breached=daily_dd_breached,
            cortex_violations=cortex_violations,
            trading_days=days,
            min_trading_days=tier_conf["min_days"],
            status=status,
            trading_credit_usdt=trading_credit,
            withdrawable_profits_usdt=withdrawable_profits,
            prop_score=prop_score,
            rank_position=rank,
            share_text=share_text,
        )
