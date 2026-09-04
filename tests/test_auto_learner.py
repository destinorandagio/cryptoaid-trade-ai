"""Unit & Integration test for the AutoLearnerEngine."""
from __future__ import annotations

import pytest
from pathlib import Path

from src.learning.auto_learner import AutoLearnerEngine
from src.storage.db import DatabaseManager
from src.data.mock_feed import MockMarketDataProvider


@pytest.fixture
def temp_db(tmp_path: Path) -> DatabaseManager:
    db_file = tmp_path / "test_auto_learner.db"
    return DatabaseManager(db_path=db_file)


import asyncio

def test_auto_learner_step_execution(temp_db: DatabaseManager):
    mock_provider = MockMarketDataProvider()
    engine = AutoLearnerEngine(db_manager=temp_db, market_provider=mock_provider, tick_interval_seconds=60)

    # Execute one full autonomous learning cycle
    report = asyncio.run(engine.step())

    assert report["cycle"] == 1
    assert "timestamp" in report
    assert "matrix_observations" in report
    assert report["bull_champion"] in ["MOMENTUM", "TREND", "BREAKOUT", "SCALP"]
    assert "portfolios" in report

    # Verify state after step
    stats = engine.experience_matrix.get_matrix_stats()
    assert isinstance(stats, dict)
    assert "total_cells_tracked" in stats

