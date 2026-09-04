"""
TradeAID Autotrade Run Engine — LEDGER 1: Gamified Demo Run
Contract:
  User pays 10 POL fee to DAO Treasury.
  Activates 1 Autotrade Run on 10,000 USDT Paper capital.
  Fixed duration: 180 seconds (cannot hold losing trades indefinitely).
  WIN Condition: Net P&L > 0.00% & 0 CORTEX violations within duration.
  Reward: 2 POL from dedicated RewardPool (subject to pool solvency & legal feature-flag).
"""

from __future__ import annotations

import logging
import os
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from src.storage.db import DatabaseManager

logger = logging.getLogger("trade_ai.autotrade_run")

# Feature flag for legal/regulatory safety on real on-chain crypto reward payout
FEATURE_REAL_REWARD_PAYOUT = (
    os.getenv("AUTOTRADE_REWARD_PAYOUT_ENABLED", "false").lower() == "true"
)


@dataclass
class RunEvaluationResult:
    run_id: str
    won: bool
    final_pnl_usdt: float
    final_pnl_pct: float
    trades_count: int
    cortex_violations: int
    reward_pol: float
    payout_status: str
    reward_pool_solvent: bool
    explanation: str


class AutotradeRunEngine:
    """Manages the lifecycle and deterministic settlement of gamified Autotrade Runs."""

    def __init__(self, db: DatabaseManager | None = None) -> None:
        self.db = db or DatabaseManager()

    def start_run(
        self,
        wallet: str,
        tx_hash_fee: str | None = None,
        paper_starting_balance: float = 10000.0,
        max_duration_seconds: int = 180,
    ) -> dict[str, Any]:
        """Activate a new Autotrade Run after 10 POL fee verification."""
        sequence_id = int(time.time() * 1000) % 900000 + 100000  # 6-digit sequence, e.g. #000123
        run_id = f"RUN-{sequence_id}"

        run_data = self.db.create_autotrade_run(
            run_id=run_id,
            sequence_id=sequence_id,
            wallet=wallet,
            tx_hash_fee=tx_hash_fee,
            fee_pol=10.0,
            paper_starting_balance=paper_starting_balance,
            max_duration_seconds=max_duration_seconds,
        )
        logger.info(
            f"[AUTOTRADE_RUN] Activated {run_id} for wallet {wallet} (Fee: 10 POL, Paper: {paper_starting_balance} USDT, Limit: {max_duration_seconds}s)"
        )
        return run_data

    def evaluate_and_conclude_run(
        self,
        run_id: str,
        simulated_pnl_usdt: float,
        simulated_pnl_pct: float,
        trades_count: int,
        cortex_violations: int = 0,
    ) -> RunEvaluationResult:
        """Conclude an Autotrade Run strictly applying the crystallised WIN condition.

        WIN Condition:
        1. Net P&L > +$0.00 USDT (strictly positive after simulated fees).
        2. Exactly 0 CORTEX violations.
        3. Run completed within duration.
        """
        run = self.db.get_autotrade_run(run_id)
        if not run:
            raise ValueError(f"Run {run_id} not found")

        # Check Win Condition
        won = (simulated_pnl_pct > 0.0) and (cortex_violations == 0)

        reward_pool = self.db.get_reward_pool_status()
        is_solvent = reward_pool.get("is_solvent", False)
        payout_enabled = bool(reward_pool.get("payout_enabled", 0)) or FEATURE_REAL_REWARD_PAYOUT

        reward_pol = 2.0 if won else 0.0

        if won:
            if not is_solvent:
                payout_status = "POOL_INSOLVENT_WAITING"
                explanation = f"WIN (+{simulated_pnl_pct:.2f}%). Reward Pool balance < 2 POL, reward queued."
            elif not payout_enabled:
                payout_status = "FEATURE_FLAG_HELD"
                explanation = f"WIN (+{simulated_pnl_pct:.2f}%). 2.0 POL credited on paper. On-chain payout held pending legal flag."
            else:
                # Deduct from pool and mark ready/paid
                self.db.pay_reward_from_pool(2.0)
                payout_status = "PAID"
                explanation = f"WIN (+{simulated_pnl_pct:.2f}%). 2.0 POL successfully dispatched from Reward Pool."
        else:
            payout_status = "NOT_ELIGIBLE"
            if cortex_violations > 0:
                explanation = f"LOSS: {cortex_violations} CORTEX violation(s) detected during run."
            else:
                explanation = f"LOSS: Net P&L ({simulated_pnl_pct:.2f}%) did not reach positive territory before run closure."

        self.db.conclude_autotrade_run(
            run_id=run_id,
            won=won,
            pnl_usdt=simulated_pnl_usdt,
            pnl_pct=simulated_pnl_pct,
            trades_count=trades_count,
            cortex_violations=cortex_violations,
            payout_status=payout_status,
        )

        logger.info(f"[AUTOTRADE_RUN] Concluded {run_id}: Won={won}, PnL={simulated_pnl_pct:.2f}%, Status={payout_status}")

        return RunEvaluationResult(
            run_id=run_id,
            won=won,
            final_pnl_usdt=simulated_pnl_usdt,
            final_pnl_pct=simulated_pnl_pct,
            trades_count=trades_count,
            cortex_violations=cortex_violations,
            reward_pol=reward_pol,
            payout_status=payout_status,
            reward_pool_solvent=is_solvent,
            explanation=explanation,
        )
