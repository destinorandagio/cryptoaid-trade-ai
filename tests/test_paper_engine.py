"""Tests for Paper Execution Engine with Polygon USDT Accounting."""
import tempfile
from pathlib import Path
import pytest
from src.config import settings
from src.execution.models import OrderSide, OrderStatus
from src.execution.paper_engine import PaperExecutionEngine
from src.risk.capital_protection import CapitalProtectionEngine
from src.storage.db import DatabaseManager


@pytest.fixture
def temp_engine():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_trade.db"
        db = DatabaseManager(db_path=db_path)
        risk = CapitalProtectionEngine()
        engine = PaperExecutionEngine(db=db, risk_engine=risk)
        yield engine
        del engine
        del db


def test_paper_order_execution_and_close(temp_engine):
    engine = temp_engine
    state_before = engine.get_portfolio_state()
    assert state_before.cash_balance == 1_000.0

    # Execute BUY 100 POL @ $0.3200 (Notional $32.0, within 10% limit)
    order = engine.execute_market_order(
        asset="POL/USDT",
        side=OrderSide.BUY,
        size=100.0,
        market_price=0.3200,
        sl=0.3100,
        tp=0.3500,
    )
    assert order.status == OrderStatus.FILLED
    assert order.entry >= 0.3200  # Slippage applied
    assert order.fees > 0

    # Verify Open Position
    positions = engine.db.get_open_positions()
    assert len(positions) == 1
    pos = positions[0]
    assert pos["asset"] == "POL/USDT"
    assert pos["size"] == 100.0

    # Update market price favorably -> unrealized profit
    events = engine.update_market_prices({"POL/USDT": 0.3350})
    assert len(events) == 0
    pos_updated = engine.db.get_open_positions()[0]
    assert pos_updated["unrealized_pnl"] > 0

    # Manually close position
    close_res = engine.close_position(pos_updated["id"], current_price=0.3400, reason="Test Close")
    assert close_res["net_pnl"] > 0
    assert len(engine.db.get_open_positions()) == 0

    # Cash balance should now be greater than 1,000.0
    state_after = engine.get_portfolio_state()
    assert state_after.cash_balance > 1_000.0


def test_stop_loss_trigger(temp_engine):
    engine = temp_engine
    order = engine.execute_market_order(
        asset="WETH/USDT",
        side=OrderSide.BUY,
        size=0.03,
        market_price=2_500.0,
        sl=2_450.0,
        tp=2_650.0,
    )
    assert order.status == OrderStatus.FILLED

    # Price drops to $2,420 -> triggers SL
    events = engine.update_market_prices({"WETH/USDT": 2_420.0})
    assert len(events) == 1
    assert "stopped out" in events[0].lower()
    assert len(engine.db.get_open_positions()) == 0


def test_take_profit_trigger(temp_engine):
    engine = temp_engine
    order = engine.execute_market_order(
        asset="LINK/USDT",
        side=OrderSide.BUY,
        size=5.0,
        market_price=12.0,
        sl=11.5,
        tp=13.0,
    )
    assert order.status == OrderStatus.FILLED

    # Price rises to $13.50 -> triggers TP
    events = engine.update_market_prices({"LINK/USDT": 13.50})
    assert len(events) == 1
    assert "took profit" in events[0].lower()
    assert len(engine.db.get_open_positions()) == 0
