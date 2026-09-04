"""Memory Weighting Model & Champion/Challenger System for TradeAID.

Balances Long-Term Baseline Evidence against Recent Performance to prevent
both chasing noisy short-term variance and holding onto dead edges.
Coordinates the Champion/Challenger Tournament promotion gate.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any
from pydantic import BaseModel, Field

from src.learning.experience_matrix import ExperienceMatrix
from src.storage.db import DatabaseManager

logger = logging.getLogger(__name__)


class MemoryWeights(BaseModel):
    long_term_weight: float = 0.30     # 30% baseline historical evidence
    recent_weight: float = 0.25        # 25% rolling 20-trade performance
    regime_similarity: float = 0.20    # 20% match between current & historical regime
    sample_confidence: float = 0.15    # 15% sample size statistical significance
    prediction_calibration: float = 0.10 # 10% Brier score accuracy calibration

    def compute_composite_weight(
        self,
        long_term_score: float,
        recent_score: float,
        regime_sim: float,
        sample_conf: float,
        calibration: float,
    ) -> float:
        """Calculate balanced composite reliability score (0.0 to 1.0)."""
        # Penalize recent score if rolling performance is in steep degradation
        effective_recent = max(0.05, recent_score)

        score = (
            (long_term_score * self.long_term_weight)
            + (effective_recent * self.recent_weight)
            + (regime_sim * self.regime_similarity)
            + (sample_conf * self.sample_confidence)
            + (calibration * self.prediction_calibration)
        )
        return round(max(0.05, min(0.99, score)), 3)


# Canonical alias
MemoryWeightingModel = MemoryWeights



class ChampionState(BaseModel):
    regime: str
    champion_strategy: str
    champion_expectancy: float
    champion_sharpe: float
    challengers: list[str] = Field(default_factory=list)
    promoted_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    promotion_history: list[dict[str, Any]] = Field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump()


class ChampionChallengerSystem:
    """Manages the autonomous tournament promoting shadow Challengers to active Champions."""

    # Default initial Champions per Regime
    INITIAL_CHAMPIONS = {
        "TRENDING_BULL": ("MOMENTUM", ["TREND", "BREAKOUT", "SCALP"]),
        "TRENDING_BEAR": ("TREND", ["MOMENTUM", "BREAKOUT", "SCALP"]),
        "RANGING_LOW_VOL": ("MEAN_REVERSION", ["SCALP", "MOMENTUM"]),
        "RANGING_HIGH_VOL": ("BREAKOUT", ["SCALP", "MEAN_REVERSION"]),
        "HIGH_VOLATILITY_EXPANSION": ("SCALP", ["BREAKOUT", "MOMENTUM"]),
        "UNKNOWN": ("SCALP", ["MEAN_REVERSION"]),
    }

    def __init__(self, db_manager: DatabaseManager | None = None) -> None:
        self.db = db_manager or DatabaseManager()
        self.weights_model = MemoryWeights()
        self._states: dict[str, ChampionState] = {}
        self._load_champions()

    def _load_champions(self) -> None:
        """Load champions from SQLite or initialize defaults."""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM champions_challengers")
                rows = cursor.fetchall()
                for r in rows:
                    challengers = json.loads(r["challenger_strategies_json"]) if r["challenger_strategies_json"] else []
                    history = json.loads(r["history_json"]) if r["history_json"] else []
                    self._states[r["regime"]] = ChampionState(
                        regime=r["regime"],
                        champion_strategy=r["champion_strategy"],
                        champion_expectancy=r["champion_expectancy"],
                        champion_sharpe=r["champion_sharpe"],
                        challengers=challengers,
                        promoted_at=str(r["promoted_at"]),
                        promotion_history=history,
                    )
        except Exception as err:
            logger.warning("Could not load champions from DB: %s", err)

        # Ensure all standard regimes have a state
        for reg, (champ, chs) in self.INITIAL_CHAMPIONS.items():
            if reg not in self._states:
                self._states[reg] = ChampionState(
                    regime=reg,
                    champion_strategy=champ,
                    champion_expectancy=0.010,
                    champion_sharpe=1.60,
                    challengers=list(chs),
                )

    def get_champion(self, regime: str) -> str:
        """Return the active Champion strategy DNA for a given regime."""
        state = self._states.get(regime.upper(), self._states.get("UNKNOWN"))
        return state.champion_strategy if state else "MOMENTUM"

    def get_all_champions(self) -> dict[str, Any]:
        """Return all current champions, challengers, and promotion dates."""
        return {reg: state.to_dict() for reg, state in self._states.items()}

    def evaluate_promotion(
        self,
        regime: str,
        experience_matrix: ExperienceMatrix,
        asset: str = "POL/USDT",
    ) -> dict[str, Any]:
        """Evaluate whether any shadow Challenger deserves promotion over the active Champion.

        Promotion Gates:
        1. Minimum sample size N >= 30 observations.
        2. Challenger Expectancy exceeds Champion Expectancy by at least +0.25% (+0.0025).
        3. Challenger Max Drawdown does not exceed Champion Max Drawdown * 1.15.
        4. Statistical confidence >= 0.70.
        """
        reg_upper = regime.upper()
        state = self._states.get(reg_upper)
        if not state:
            return {"status": "NO_REGIME_STATE", "regime": regime}

        champ_strat = state.champion_strategy
        champ_cell = experience_matrix.query_cell(asset=asset, regime=reg_upper, timeframe="5m", strategy=champ_strat)

        evaluation_log = []
        promoted_challenger = None

        for challenger in state.challengers:
            chal_cell = experience_matrix.query_cell(asset=asset, regime=reg_upper, timeframe="5m", strategy=challenger)

            gate_sample = chal_cell.sample_size >= 30
            expectancy_delta = chal_cell.expectancy - champ_cell.expectancy
            gate_edge = expectancy_delta >= 0.0025  # +0.25% net edge advantage
            gate_dd = chal_cell.max_drawdown <= max(0.01, champ_cell.max_drawdown * 1.15)
            gate_conf = chal_cell.confidence_score >= 0.70

            log_entry = {
                "challenger": challenger,
                "samples": chal_cell.sample_size,
                "expectancy_pct": round(chal_cell.expectancy * 100, 2),
                "champ_expectancy_pct": round(champ_cell.expectancy * 100, 2),
                "delta_pct": round(expectancy_delta * 100, 2),
                "max_drawdown_pct": round(chal_cell.max_drawdown * 100, 2),
                "passed_all_gates": gate_sample and gate_edge and gate_dd and gate_conf,
            }
            evaluation_log.append(log_entry)

            if log_entry["passed_all_gates"] and promoted_challenger is None:
                promoted_challenger = (challenger, chal_cell)

        # Execute Promotion if criteria met
        if promoted_challenger:
            new_champ, new_cell = promoted_challenger
            old_champ = state.champion_strategy

            # Swap: Old champion moves into challengers, new challenger becomes champion
            new_challengers = [c for c in state.challengers if c != new_champ] + [old_champ]
            now_iso = datetime.now(timezone.utc).isoformat()

            promo_record = {
                "previous_champion": old_champ,
                "promoted_champion": new_champ,
                "promoted_at": now_iso,
                "new_expectancy_pct": round(new_cell.expectancy * 100, 2),
                "samples": new_cell.sample_size,
                "reason": f"Challenger {new_champ} out-performed Champion {old_champ} by +{round((new_cell.expectancy - champ_cell.expectancy)*100, 2)}% over {new_cell.sample_size} samples",
            }

            state.champion_strategy = new_champ
            state.champion_expectancy = new_cell.expectancy
            state.challengers = new_challengers
            state.promoted_at = now_iso
            state.promotion_history.append(promo_record)

            self._persist_champion(state)
            logger.info("PROMOTION EVENT in %s: %s -> %s", reg_upper, old_champ, new_champ)

            return {
                "status": "PROMOTED",
                "regime": reg_upper,
                "previous_champion": old_champ,
                "new_champion": new_champ,
                "evidence": promo_record,
                "evaluations": evaluation_log,
            }

        return {
            "status": "CHAMPION_RETAINED",
            "regime": reg_upper,
            "current_champion": champ_strat,
            "evaluations": evaluation_log,
        }

    def _persist_champion(self, state: ChampionState) -> None:
        """Persist updated champion state to SQLite."""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO champions_challengers (
                        regime, champion_strategy, champion_expectancy, champion_sharpe,
                        challenger_strategies_json, promoted_at, history_json
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(regime) DO UPDATE SET
                        champion_strategy=excluded.champion_strategy,
                        champion_expectancy=excluded.champion_expectancy,
                        champion_sharpe=excluded.champion_sharpe,
                        challenger_strategies_json=excluded.challenger_strategies_json,
                        promoted_at=excluded.promoted_at,
                        history_json=excluded.history_json
                    """,
                    (
                        state.regime,
                        state.champion_strategy,
                        state.champion_expectancy,
                        state.champion_sharpe,
                        json.dumps(state.challengers),
                        state.promoted_at,
                        json.dumps(state.promotion_history),
                    ),
                )
                conn.commit()
        except Exception as err:
            logger.error("Failed to persist champion state for %s: %s", state.regime, err)
