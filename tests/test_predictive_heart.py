"""Unit tests for Predictive Heart Engine and Calibration (Closure 1)."""
from __future__ import annotations

import tempfile
from pathlib import Path
from fastapi.testclient import TestClient

from src.agents.predictive_heart import PredictiveHeartEngine
from src.api.app import app
from src.data.mock_feed import MockMarketDataProvider
from src.storage.db import DatabaseManager


def test_predictive_heart_forecast_generation():
    """Verify that Predictive Heart produces white history and red P50 trajectory with confidence bounds."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_heart.db"
        db = DatabaseManager(db_path=db_path)
        mock_provider = MockMarketDataProvider()
        engine = PredictiveHeartEngine(market_provider=mock_provider, db=db)

        forecast = engine.generate_forecast(symbol="POL/USDT", timeframe="15m", history_points=25, future_steps=12)

        assert forecast["asset"] == "POL/USDT"
        assert forecast["timeframe"] == "15m"
        assert len(forecast["history_white"]) == 25
        assert len(forecast["future_p50_red"]) == 12
        assert len(forecast["future_p10"]) == 12
        assert len(forecast["future_p90"]) == 12
        assert forecast["now_price"] > 0
        assert forecast["direction"] in ["LONG", "SHORT", "NO_TRADE"]
        assert 50.0 <= forecast["confidence_pct"] <= 100.0
        assert forecast["cortex_status"] in ["PASS (CLEAR)", "VETO (HIGH VOLATILITY)", "VETO (WIDE SPREAD)"]
        assert len(forecast["models_evidence"]) == 7
        assert "forecast_id" in forecast

        # Verify DB insertion
        recent = db.get_recent_forecasts(asset="POL/USDT", limit=5)
        assert len(recent) == 1
        assert recent[0]["id"] == forecast["forecast_id"]
        assert recent[0]["is_calibrated"] == 0


def test_predictive_heart_calibration_workflow():
    """Verify that expired forecasts are properly evaluated and calibrated with Brier scores."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_heart_calib.db"
        db = DatabaseManager(db_path=db_path)
        mock_provider = MockMarketDataProvider()
        engine = PredictiveHeartEngine(market_provider=mock_provider, db=db)

        # Record a simulated past forecast that has already expired
        expired_forecast = {
            "id": "test-f1",
            "asset": "POL/USDT",
            "timeframe": "15m",
            "target_timestamp": "2020-01-01T00:00:00+00:00",  # Definitely expired
            "now_price": 0.30,
            "predicted_p50": 0.32,
            "predicted_p10": 0.28,
            "predicted_p90": 0.34,
            "direction": "LONG",
            "expected_return_pct": 6.67,
            "confidence_pct": 80.0,
            "regime": "EXPANSION_BULL",
            "models_evidence": {},
        }
        db.record_forecast(expired_forecast)

        # Run evaluation
        eval_result = engine.evaluate_pending_forecasts()
        assert eval_result["newly_calibrated"] >= 1

        stats = db.get_calibration_stats("POL/USDT")
        assert stats["total_calibrated"] >= 1
        assert stats["status"] == "CALIBRATED_ACTIVE"
        assert 0.0 <= stats["avg_brier_score"] <= 1.0


def test_predictive_heart_api_routes():
    """Verify REST API endpoints for Predictive Heart."""
    client = TestClient(app)

    # 1. GET /api/v1/heart/forecast
    resp = client.get("/api/v1/heart/forecast?symbol=POL/USDT&timeframe=15m")
    assert resp.status_code == 200
    data = resp.json()
    assert data["asset"] == "POL/USDT"
    assert "history_white" in data
    assert "future_p50_red" in data
    assert "direction" in data
    assert "confidence_pct" in data
    assert "cortex_status" in data

    # 2. GET /api/v1/heart/calibration
    resp_calib = client.get("/api/v1/heart/calibration?asset=POL/USDT")
    assert resp_calib.status_code == 200
    calib_data = resp_calib.json()
    assert "total_calibrated" in calib_data
    assert "status" in calib_data

    # 3. POST /api/v1/heart/evaluate
    resp_eval = client.post("/api/v1/heart/evaluate")
    assert resp_eval.status_code == 200
    eval_data = resp_eval.json()
    assert "newly_calibrated" in eval_data
