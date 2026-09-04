"""Execution data models for Paper Trading."""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from pydantic import BaseModel, Field


class OrderSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(str, Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP_LOSS = "STOP_LOSS"
    TAKE_PROFIT = "TAKE_PROFIT"
    TRAILING_STOP = "TRAILING_STOP"


class OrderStatus(str, Enum):
    PENDING = "PENDING"
    OPEN = "OPEN"
    FILLED = "FILLED"
    CLOSED = "CLOSED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"


class PaperOrder(BaseModel):
    order_id: str
    user_id: str = "default_user"
    account_id: str = "default_paper"
    asset: str
    side: OrderSide
    type: OrderType
    entry: float
    size: float
    sl: float | None = None
    tp: float | None = None
    trailing_distance: float | None = None
    fees: float = 0.0
    simulated_slippage: float = 0.0
    open_time: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    close_time: str | None = None
    exit_price: float | None = None
    pnl: float = 0.0
    pnl_percent: float = 0.0
    status: OrderStatus = OrderStatus.PENDING
    strategy: str = "MetaAgent"
    confidence: float | None = None
    risk_score: float | None = None
    reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d = self.model_dump()
        d["side"] = self.side.value
        d["type"] = self.type.value
        d["status"] = self.status.value
        return d


class PaperPosition(BaseModel):
    id: str
    account_id: str
    asset: str
    side: str  # "LONG" or "SHORT"
    entry_price: float
    current_price: float
    size: float
    notional: float
    sl: float | None = None
    tp: float | None = None
    trailing_sl: float | None = None
    unrealized_pnl: float = 0.0
    unrealized_pnl_pct: float = 0.0
    opened_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    last_updated: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    order_id: str

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump()
