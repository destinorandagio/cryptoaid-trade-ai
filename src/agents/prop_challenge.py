"""
TradeAID Prop Challenge Engine ($10,000 Paper Demo & Progression)
Evaluates equity growth, drawdown limits, discipline rules, and viral rank.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger("trade_ai.prop_challenge")


@dataclass
class ChallengeStatusResult:
    challenge_id: str
    wallet: str
    mode: str
    initial_equity: float
    current_equity: float
    profit_pct: float
    target_pct: float
    target_achieved: bool
    current_total_dd_pct: float
    max_total_dd_pct: float
    total_dd_breached: bool
    current_daily_dd_pct: float
    max_daily_dd_pct: float
    daily_dd_breached: bool
    cortex_violations: int
    trading_days: int
    min_trading_days: int
    status: str  # ACTIVE, QUALIFIED, FAILED
    prop_score: float
    rank_position: int
    share_text: str


class PropChallengeEngine:
    """
    Evaluates TradeAID Prop Challenge progression.
    Reward Profit + Discipline, not reckless gambling.
    """

    def __init__(self, target_pct: float = 8.0, max_total_dd: float = 8.0, max_daily_dd: float = 4.0, min_days: int = 5):
        self.target_pct = target_pct
        self.max_total_dd = max_total_dd
        self.max_daily_dd = max_daily_dd
        self.min_days = min_days

    def evaluate(self, challenge: dict[str, Any]) -> ChallengeStatusResult:
        initial = float(challenge.get("initial_equity", 10000.0))
        current = float(challenge.get("current_equity", 10000.0))
        peak = float(challenge.get("peak_equity", initial))
        if current > peak:
            peak = current

        profit_pct = ((current - initial) / initial) * 100.0

        # Drawdowns
        total_dd = ((peak - current) / peak) * 100.0 if peak > 0 else 0.0
        daily_dd = float(challenge.get("current_daily_dd_pct", 0.0))
        cortex_violations = int(challenge.get("cortex_violations", 0))
        days = int(challenge.get("trading_days_count", 1))

        # Check breach conditions
        total_dd_breached = total_dd >= self.max_total_dd
        daily_dd_breached = daily_dd >= self.max_daily_dd
        cortex_breached = cortex_violations > 0

        # Status logic
        current_status = challenge.get("status", "ACTIVE")
        if total_dd_breached or daily_dd_breached or cortex_breached:
            status = "FAILED"
        elif profit_pct >= self.target_pct and days >= self.min_days:
            status = "QUALIFIED"
        else:
            status = current_status if current_status in ["QUALIFIED", "FAILED"] else "ACTIVE"

        # Calculate Prop Discipline Score (0-100)
        # Score = (Discipline 40%) + (Target Progress 40%) + (Drawdown Buffer 20%)
        progress_factor = min(1.0, max(0.0, profit_pct / self.target_pct)) * 40.0
        dd_buffer_factor = max(0.0, (1.0 - (total_dd / self.max_total_dd))) * 20.0
        discipline_factor = 40.0 if cortex_violations == 0 else max(0.0, 40.0 - (cortex_violations * 15.0))
        prop_score = round(progress_factor + dd_buffer_factor + discipline_factor, 1)

        # Dynamic Rank
        rank = int(challenge.get("rank_position", 238))
        if profit_pct > 3.0:
            rank = max(12, rank - int(profit_pct * 15))

        # Generate Share Text for Viral Loop
        share_text = (
            f"🏆 TRADEAID PROP CHALLENGE\n"
            f"• Mode: {challenge.get('mode', 'BALANCED')} AUTOTRADE\n"
            f"• Progress: {profit_pct:+.2f}% / +{self.target_pct:.1f}%\n"
            f"• Equity: ${current:,.2f} USDT (PAPER)\n"
            f"• Drawdown: {total_dd:.2f}% / {self.max_total_dd:.1f}% MAX\n"
            f"• CORTEX Violations: {cortex_violations}\n"
            f"• Prop Score: {prop_score}/100 | Rank #{rank}\n"
            f"👉 Test the AI with $10,000 Paper: https://trade.cryptoaid.support/dapp.html"
        )

        return ChallengeStatusResult(
            challenge_id=challenge["id"],
            wallet=challenge["wallet"],
            mode=challenge.get("mode", "BALANCED"),
            initial_equity=initial,
            current_equity=current,
            profit_pct=round(profit_pct, 2),
            target_pct=self.target_pct,
            target_achieved=profit_pct >= self.target_pct,
            current_total_dd_pct=round(total_dd, 2),
            max_total_dd_pct=self.max_total_dd,
            total_dd_breached=total_dd_breached,
            current_daily_dd_pct=round(daily_dd, 2),
            max_daily_dd_pct=self.max_daily_dd,
            daily_dd_breached=daily_dd_breached,
            cortex_violations=cortex_violations,
            trading_days=days,
            min_trading_days=self.min_days,
            status=status,
            prop_score=prop_score,
            rank_position=rank,
            share_text=share_text,
        )
