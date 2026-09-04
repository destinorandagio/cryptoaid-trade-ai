"""API Integration Tests for CryptoAID Trade AI."""
import pytest
from fastapi.testclient import TestClient
from src.api.app import app

client = TestClient(app)


def test_api_health():
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "HEALTHY"
    assert data["live_trading_enabled"] is False


def test_api_system_status():
    resp = client.get("/api/v1/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "supported_universe" in data
    assert "POL/USDT" in data["supported_universe"]
    assert "WETH/USDT" in data["supported_universe"]
    assert data["base_quote"] == "USDT"


def test_api_markets():
    resp = client.get("/api/v1/markets")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 3
    symbols = [m["symbol"] for m in data]
    assert "POL/USDT" in symbols
    assert "WETH/USDT" in symbols


def test_api_scan():
    resp = client.get("/api/v1/scan")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 3
    for item in data:
        assert "symbol" in item
        assert "ai_signal" in item
        assert "cryptoaid_risk" in item
        assert "composite_risk_score" in item["cryptoaid_risk"]


def test_api_portfolio_orders_and_positions():
    resp = client.get("/api/v1/portfolio")
    assert resp.status_code == 200
    data = resp.json()
    assert "account" in data
    assert data["account"]["cash_balance"] > 0

    # Place a small valid paper order on POL/USDT
    order_req = {
        "asset": "POL/USDT",
        "side": "BUY",
        "size": 100.0,
        "sl": 0.3100,
        "tp": 0.3500,
    }
    order_resp = client.post("/api/v1/orders", json=order_req)
    assert order_resp.status_code == 200
    order_data = order_resp.json()
    assert order_data["status"] == "FILLED"
    assert order_data["asset"] == "POL/USDT"

    # Verify position is present in /api/v1/positions
    pos_resp = client.get("/api/v1/positions")
    assert pos_resp.status_code == 200
    pos_data = pos_resp.json()
    assert any(p["asset"] == "POL/USDT" for p in pos_data)


def test_api_performance():
    resp = client.get("/api/v1/performance")
    assert resp.status_code == 200
    data = resp.json()
    assert "environment" in data
    assert "win_rate_pct" in data


def test_api_autotrade_controls():
    # GET status
    resp = client.get("/api/v1/autotrade")
    assert resp.status_code == 200
    assert "autotrade_enabled" in resp.json()

    # POST toggle
    toggle_resp = client.post("/api/v1/autotrade?enabled=false")
    assert toggle_resp.status_code == 200
    assert toggle_resp.json()["autotrade_enabled"] is False

    # Restore
    client.post("/api/v1/autotrade?enabled=true")


def test_api_risk_and_kill_switch():
    resp = client.get("/api/v1/risk")
    assert resp.status_code == 200
    data = resp.json()
    assert "rules" in data

    # Trigger kill switch via /api/v1/kill-switch
    ks_resp = client.post("/api/v1/kill-switch", json={"action": "TRIGGER", "reason": "War Mode Test"})
    assert ks_resp.status_code == 200
    assert ks_resp.json()["kill_switch_active"] is True

    # Order should now be rejected
    order_req = {
        "asset": "POL/USDT",
        "side": "BUY",
        "size": 50.0,
    }
    rejected_resp = client.post("/api/v1/orders", json=order_req)
    assert rejected_resp.status_code == 400

    # Reset kill switch
    reset_resp = client.post("/api/v1/kill-switch", json={"action": "RESET", "reason": "Test Reset"})
    assert reset_resp.status_code == 200
    assert reset_resp.json()["kill_switch_active"] is False


def test_pwa_root_and_static():
    resp = client.get("/")
    assert resp.status_code == 200
    assert "CryptoAID Trade AI" in resp.text

    # Check manifest
    manifest_resp = client.get("/static/manifest.json")
    assert manifest_resp.status_code == 200
    assert manifest_resp.json()["name"] == "CryptoAID Trade AI"
