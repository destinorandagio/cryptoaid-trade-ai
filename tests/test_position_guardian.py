"""Tests for Position Guardian, Dynamic Stops, Break-Even, Trailing, and Emergency Close."""
import pytest
from src.config import settings
from src.dex.position_guardian import PositionGuardian
from src.storage.db import DatabaseManager


def test_position_guardian_tracking_and_sl_tp():
    db = DatabaseManager()
    guardian = PositionGuardian(db=db)

    # Clean up test table
    guardian.active_positions.clear()

    # Track a test position on POL/USDT
    test_pos = {
        "id": "test_pos_pol_1",
        "asset": "POL/USDT",
        "side": "BUY",
        "entry_price": 0.3200,
        "current_price": 0.3200,
        "size": 300.0,
        "notional": 96.0,
        "sl": 0.3150,  # 1.5% SL
        "tp": 0.3320,  # ~3.75% TP
        "trailing_sl": None,
        "order_id": "test_ord_1",
    }
    guardian.track_position(test_pos)
    assert "test_pos_pol_1" in guardian.active_positions

    # Price moves slightly down, but above SL: No exit
    events = guardian.evaluate_positions(market_prices={"POL/USDT": 0.3180})
    assert len(events) == 0
    assert "test_pos_pol_1" in guardian.active_positions

    # Price hits Stop Loss (0.3140 <= 0.3150): Guardian triggers exit swap
    events = guardian.evaluate_positions(market_prices={"POL/USDT": 0.3140})
    assert len(events) == 1
    assert events[0]["event"] == "POSITION_CLOSED"
    assert "Stop Loss" in events[0]["reason"]
    assert "test_pos_pol_1" not in guardian.active_positions


def test_position_guardian_hard_5pct_emergency_ceiling():
    db = DatabaseManager()
    guardian = PositionGuardian(db=db)
    guardian.active_positions.clear()

    # Position with NO stop loss set initially
    test_pos = {
        "id": "test_pos_weth_1",
        "asset": "WETH/USDT",
        "side": "BUY",
        "entry_price": 2500.0,
        "current_price": 2500.0,
        "size": 0.04,
        "notional": 100.0,
        "sl": None,
        "tp": 2650.0,
        "trailing_sl": None,
        "order_id": "test_ord_2",
    }
    guardian.track_position(test_pos)

    # Flash crash > 5% (e.g. 2350.0 <= 2500 * 0.95 = 2375.0)
    events = guardian.evaluate_positions(market_prices={"WETH/USDT": 2360.0})
    assert len(events) == 1
    assert "Emergency 5% Stop Ceiling" in events[0]["reason"]
    assert "test_pos_weth_1" not in guardian.active_positions


def test_position_guardian_break_even_lock():
    db = DatabaseManager()
    guardian = PositionGuardian(db=db)
    guardian.active_positions.clear()

    test_pos = {
        "id": "test_pos_wbtc_1",
        "asset": "WBTC/USDT",
        "side": "BUY",
        "entry_price": 60000.0,
        "current_price": 60000.0,
        "size": 0.0016,
        "notional": 96.0,
        "sl": 59100.0,
        "tp": 63000.0,
        "trailing_sl": None,
        "order_id": "test_ord_3",
    }
    guardian.track_position(test_pos)

    # Price gains +1.5% (60,900): Break-even should activate and raise SL to entry
    guardian.evaluate_positions(market_prices={"WBTC/USDT": 60900.0})
    pos = guardian.active_positions["test_pos_wbtc_1"]
    assert pos.break_even_activated is True
    assert pos.sl >= 60000.0


def test_position_guardian_emergency_close_all():
    db = DatabaseManager()
    guardian = PositionGuardian(db=db)
    guardian.active_positions.clear()

    guardian.track_position({
        "id": "p1",
        "asset": "POL/USDT",
        "side": "BUY",
        "entry_price": 0.32,
        "current_price": 0.32,
        "size": 100.0,
        "notional": 32.0,
        "order_id": "o1",
    })
    guardian.track_position({
        "id": "p2",
        "asset": "LINK/USDT",
        "side": "BUY",
        "entry_price": 12.0,
        "current_price": 12.0,
        "size": 5.0,
        "notional": 60.0,
        "order_id": "o2",
    })

    assert len(guardian.active_positions) == 2
    events = guardian.emergency_close_all(reason="Kill Switch Test")
    assert len(events) == 2
    assert len(guardian.active_positions) == 0
