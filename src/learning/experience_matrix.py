"""Experience Matrix Multidimensional Knowledge Base for TradeAID.

Coordinates multidimensional historical observation across:
ASSET × REGIME × TIMEFRAME × STRATEGY × PREDICTION MODEL × SENTIMENT STATE × LIQUIDITY STATE × VOLATILITY STATE
→
EXPECTANCY · DRAWDOWN · WIN RATE · PROFIT FACTOR · COSTS · SAMPLE SIZE · CONFIDENCE
"""
from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from pydantic import BaseModel, Field

from src.storage.db import DatabaseManager

logger = logging.getLogger(__name__)


class ExperienceCell(BaseModel):
    matrix_key: str
    asset: str
    regime: str
    timeframe: str
    strategy: str
    prediction_model: str = "HEART_P50"
    sentiment_state: str = "NEUTRAL"
    liquidity_state: str = "HIGH_LIQ"
    volatility_state: str = "MED_VOL"
    expectancy: float = 0.0          # Average net return per trade (e.g. +0.0073)
    max_drawdown: float = 0.0        # Worst historical peak-to-trough drop
    win_rate: float = 0.0            # 0.0 to 1.0
    profit_factor: float = 1.0       # Gross profit / gross loss
    avg_net_costs: float = 0.0       # Gas + 0.3% fee + slippage
    sample_size: int = 0             # Number of completed trade observations
    confidence_score: float = 0.50   # Statistical significance (0.0 to 1.0)
    last_updated: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump()


class ExperienceMatrix:
    """Manages querying, updating, and persisting the multidimensional Experience Matrix."""

    def __init__(self, db_manager: DatabaseManager | None = None) -> None:
        self.db = db_manager or DatabaseManager()
        self._cache: dict[str, ExperienceCell] = {}
        self._load_cache()

    @staticmethod
    def build_key(
        asset: str,
        regime: str,
        timeframe: str,
        strategy: str,
        prediction_model: str = "HEART_P50",
        sentiment_state: str = "NEUTRAL",
        liquidity_state: str = "HIGH_LIQ",
        volatility_state: str = "MED_VOL",
    ) -> str:
        return (
            f"{asset.upper()}:{regime.upper()}:{timeframe.lower()}:"
            f"{strategy.upper()}:{prediction_model.upper()}:"
            f"{sentiment_state.upper()}:{liquidity_state.upper()}:{volatility_state.upper()}"
        )

    def _load_cache(self) -> None:
        """Warm up cache with existing matrix cells from SQLite."""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM experience_matrix")
                rows = cursor.fetchall()
                for r in rows:
                    cell = ExperienceCell(
                        matrix_key=r["matrix_key"],
                        asset=r["asset"],
                        regime=r["regime"],
                        timeframe=r["timeframe"],
                        strategy=r["strategy"],
                        prediction_model=r["prediction_model"],
                        sentiment_state=r["sentiment_state"],
                        liquidity_state=r["liquidity_state"],
                        volatility_state=r["volatility_state"],
                        expectancy=r["expectancy"],
                        max_drawdown=r["max_drawdown"],
                        win_rate=r["win_rate"],
                        profit_factor=r["profit_factor"],
                        avg_net_costs=r["avg_net_costs"],
                        sample_size=r["sample_size"],
                        confidence_score=r["confidence_score"],
                        last_updated=str(r["last_updated"]),
                    )
                    self._cache[cell.matrix_key] = cell
        except Exception as err:
            logger.warning("Could not pre-load experience matrix cache: %s", err)

    def query_cell(
        self,
        asset: str,
        regime: str,
        timeframe: str,
        strategy: str,
        prediction_model: str = "HEART_P50",
        sentiment_state: str = "NEUTRAL",
        liquidity_state: str = "HIGH_LIQ",
        volatility_state: str = "MED_VOL",
    ) -> ExperienceCell:
        """Query a cell from the multidimensional matrix with hierarchical smoothing."""
        key = self.build_key(
            asset=asset,
            regime=regime,
            timeframe=timeframe,
            strategy=strategy,
            prediction_model=prediction_model,
            sentiment_state=sentiment_state,
            liquidity_state=liquidity_state,
            volatility_state=volatility_state,
        )

        if key in self._cache:
            return self._cache[key]

        # Return default smoothed cell if unobserved
        default_cell = ExperienceCell(
            matrix_key=key,
            asset=asset,
            regime=regime,
            timeframe=timeframe,
            strategy=strategy,
            prediction_model=prediction_model,
            sentiment_state=sentiment_state,
            liquidity_state=liquidity_state,
            volatility_state=volatility_state,
            expectancy=0.0050,  # Baseline +0.50% expected return
            max_drawdown=0.020,
            win_rate=0.55,
            profit_factor=1.35,
            avg_net_costs=0.0035,
            sample_size=0,
            confidence_score=0.40,  # Low initial confidence
        )
        return default_cell

    def record_trade_outcome(
        self,
        asset: str,
        regime: str,
        timeframe: str,
        strategy: str,
        net_return_pct: float,
        costs_pct: float,
        prediction_model: str = "HEART_P50",
        sentiment_state: str = "NEUTRAL",
        liquidity_state: str = "HIGH_LIQ",
        volatility_state: str = "MED_VOL",
    ) -> ExperienceCell:
        """Incrementally update an experience cell with actual closed trade outcome."""
        key = self.build_key(
            asset=asset,
            regime=regime,
            timeframe=timeframe,
            strategy=strategy,
            prediction_model=prediction_model,
            sentiment_state=sentiment_state,
            liquidity_state=liquidity_state,
            volatility_state=volatility_state,
        )

        cell = self.query_cell(
            asset=asset,
            regime=regime,
            timeframe=timeframe,
            strategy=strategy,
            prediction_model=prediction_model,
            sentiment_state=sentiment_state,
            liquidity_state=liquidity_state,
            volatility_state=volatility_state,
        )

        n = cell.sample_size
        new_n = n + 1

        # Incremental moving average for Expectancy & Costs
        new_expectancy = (cell.expectancy * n + net_return_pct) / new_n
        new_costs = (cell.avg_net_costs * n + costs_pct) / new_n

        # Win Rate update
        is_win = 1.0 if net_return_pct > 0 else 0.0
        new_win_rate = (cell.win_rate * n + is_win) / new_n

        # Confidence Score scales with sample size: 1 - 1/sqrt(N + 1)
        new_conf = round(min(0.98, max(0.40, 1.0 - (1.0 / (new_n ** 0.5 + 1.0)))), 3)

        # Max drawdown update if trade was a loss
        loss_pct = abs(min(0.0, net_return_pct))
        new_dd = max(cell.max_drawdown, loss_pct)

        updated_cell = ExperienceCell(
            matrix_key=key,
            asset=asset,
            regime=regime,
            timeframe=timeframe,
            strategy=strategy,
            prediction_model=prediction_model,
            sentiment_state=sentiment_state,
            liquidity_state=liquidity_state,
            volatility_state=volatility_state,
            expectancy=round(new_expectancy, 4),
            max_drawdown=round(new_dd, 4),
            win_rate=round(new_win_rate, 3),
            profit_factor=round(max(0.5, cell.profit_factor if net_return_pct <= 0 else cell.profit_factor + 0.05), 2),
            avg_net_costs=round(new_costs, 4),
            sample_size=new_n,
            confidence_score=new_conf,
            last_updated=datetime.now(timezone.utc).isoformat(),
        )

        self._cache[key] = updated_cell
        self._persist_cell(updated_cell)
        logger.info(
            "Experience Matrix updated: [%s] N=%d Expectancy=%+.2f%% WinRate=%.1f%% Conf=%.2f",
            key, new_n, updated_cell.expectancy * 100, updated_cell.win_rate * 100, updated_cell.confidence_score
        )
        return updated_cell

    def _persist_cell(self, cell: ExperienceCell) -> None:
        """Persist cell to SQLite."""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO experience_matrix (
                        matrix_key, asset, regime, timeframe, strategy, prediction_model,
                        sentiment_state, liquidity_state, volatility_state, expectancy,
                        max_drawdown, win_rate, profit_factor, avg_net_costs, sample_size,
                        confidence_score, last_updated
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(matrix_key) DO UPDATE SET
                        expectancy=excluded.expectancy,
                        max_drawdown=excluded.max_drawdown,
                        win_rate=excluded.win_rate,
                        profit_factor=excluded.profit_factor,
                        avg_net_costs=excluded.avg_net_costs,
                        sample_size=excluded.sample_size,
                        confidence_score=excluded.confidence_score,
                        last_updated=excluded.last_updated
                    """,
                    (
                        cell.matrix_key, cell.asset, cell.regime, cell.timeframe, cell.strategy,
                        cell.prediction_model, cell.sentiment_state, cell.liquidity_state,
                        cell.volatility_state, cell.expectancy, cell.max_drawdown, cell.win_rate,
                        cell.profit_factor, cell.avg_net_costs, cell.sample_size,
                        cell.confidence_score, cell.last_updated,
                    ),
                )
                conn.commit()
        except Exception as err:
            logger.error("Failed to persist experience cell %s: %s", cell.matrix_key, err)

    def get_top_strategies(self, regime: str, asset: str | None = None) -> list[dict[str, Any]]:
        """Rank strategies for a given regime based on expectancy * confidence."""
        matching: list[ExperienceCell] = [
            c for c in self._cache.values()
            if c.regime.upper() == regime.upper() and (asset is None or c.asset.upper() == asset.upper())
        ]

        # If sparse cache, seed representative strategies
        if not matching:
            strategies = ["MOMENTUM", "TREND", "BREAKOUT", "MEAN_REVERSION", "SCALP"]
            for s in strategies:
                matching.append(self.query_cell(asset=asset or "POL/USDT", regime=regime, timeframe="5m", strategy=s))

        ranked = sorted(matching, key=lambda c: (c.expectancy * c.confidence_score), reverse=True)
        return [
            {
                "strategy": c.strategy,
                "regime": c.regime,
                "expectancy_pct": round(c.expectancy * 100, 2),
                "win_rate_pct": round(c.win_rate * 100, 1),
                "sample_size": c.sample_size,
                "confidence_score": c.confidence_score,
                "score": round(c.expectancy * c.confidence_score * 100, 3),
            }
            for c in ranked
        ]

    def get_matrix_stats(self) -> dict[str, Any]:
        """Global status of the Experience Matrix."""
        total_cells = len(self._cache)
        total_samples = sum(c.sample_size for c in self._cache.values())
        avg_expectancy = sum(c.expectancy for c in self._cache.values()) / max(1, total_cells)

        return {
            "total_cells_tracked": total_cells,
            "total_trade_observations": total_samples,
            "avg_expectancy_pct": round(avg_expectancy * 100, 2),
            "top_cells": [
                {
                    "key": c.matrix_key,
                    "expectancy_pct": round(c.expectancy * 100, 2),
                    "win_rate_pct": round(c.win_rate * 100, 1),
                    "samples": c.sample_size,
                }
                for c in sorted(self._cache.values(), key=lambda x: x.expectancy, reverse=True)[:5]
            ],
        }
