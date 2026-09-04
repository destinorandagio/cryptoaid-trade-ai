"""Capital Protection and Portfolio Risk Controls."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any
from pydantic import BaseModel, Field

from src.config import settings

logger = logging.getLogger(__name__)


class PortfolioRiskState(BaseModel):
    account_id: str = "default_paper"
    total_equity: float = 10_000.0
    cash_balance: float = 10_000.0
    allocated_margin: float = 0.0
    daily_realized_pnl: float = 0.0
    weekly_realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    peak_equity: float = 10_000.0
    current_drawdown_pct: float = 0.0
    active_positions_count: int = 0
    kill_switch_active: bool = False
    circuit_breaker_triggered: bool = False
    circuit_breaker_reason: str | None = None
    last_updated: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class CapitalProtectionEngine:
    """Enforces strict capital protection, sizing and circuit breakers."""

    def __init__(
        self,
        max_position_size_ratio: float = settings.max_position_size_ratio,
        max_portfolio_exposure_ratio: float = settings.max_portfolio_exposure_ratio,
        max_leverage: float = settings.max_leverage,
        daily_loss_limit_ratio: float = settings.daily_loss_limit_ratio,
        weekly_loss_limit_ratio: float = settings.weekly_loss_limit_ratio,
        max_drawdown_limit_ratio: float = settings.max_drawdown_limit_ratio,
    ) -> None:
        self.max_position_size_ratio = max_position_size_ratio
        self.max_portfolio_exposure_ratio = max_portfolio_exposure_ratio
        self.max_leverage = max_leverage
        self.daily_loss_limit_ratio = daily_loss_limit_ratio
        self.weekly_loss_limit_ratio = weekly_loss_limit_ratio
        self.max_drawdown_limit_ratio = max_drawdown_limit_ratio
        self.kill_switch_active = settings.kill_switch_active

    def check_circuit_breakers(self, state: PortfolioRiskState) -> tuple[bool, str | None]:
        """Check if any loss or drawdown limits are breached."""
        if self.kill_switch_active or state.kill_switch_active:
            return True, "Emergency Kill Switch is ACTIVE: All trading halted"

        # Check Drawdown
        if state.peak_equity > 0:
            dd = (state.peak_equity - state.total_equity) / state.peak_equity
            if dd >= self.max_drawdown_limit_ratio:
                return True, f"Max drawdown breached: {dd*100:.1f}% >= {self.max_drawdown_limit_ratio*100:.1f}% limit"

        # Check Daily Loss
        daily_loss_ratio = abs(min(0.0, state.daily_realized_pnl)) / state.total_equity if state.total_equity > 0 else 0
        if daily_loss_ratio >= self.daily_loss_limit_ratio:
            return True, f"Daily loss limit breached: {daily_loss_ratio*100:.1f}% >= {self.daily_loss_limit_ratio*100:.1f}% limit"

        # Check Weekly Loss
        weekly_loss_ratio = abs(min(0.0, state.weekly_realized_pnl)) / state.total_equity if state.total_equity > 0 else 0
        if weekly_loss_ratio >= self.weekly_loss_limit_ratio:
            return True, f"Weekly loss limit breached: {weekly_loss_ratio*100:.1f}% >= {self.weekly_loss_limit_ratio*100:.1f}% limit"

        return False, None

    def calculate_position_size(
        self,
        equity: float,
        entry_price: float,
        stop_loss_price: float | None = None,
        volatility_pct: float | None = None,
    ) -> float:
        """Calculate safe position size (in base asset units) using volatility/risk sizing."""
        max_notional = equity * self.max_position_size_ratio
        if entry_price <= 0:
            return 0.0

        if stop_loss_price and stop_loss_price != entry_price:
            risk_per_unit = abs(entry_price - stop_loss_price)
            # Max 1% equity at risk
            risk_budget = equity * 0.01
            units_by_risk = risk_budget / risk_per_unit
            notional = units_by_risk * entry_price
            notional = min(notional, max_notional)
            return round(notional / entry_price, 6)

        return round(max_notional / entry_price, 6)

    def validate_order(
        self,
        symbol: str,
        side: str,
        size: float,
        price: float,
        state: PortfolioRiskState,
        leverage: float = 1.0,
    ) -> tuple[bool, str, float]:
        """Validate if a proposed trade complies with all risk rules.
        Returns: (allowed: bool, reason: str, adjusted_size: float)
        """
        is_breaker, reason = self.check_circuit_breakers(state)
        if is_breaker:
            return False, f"Order Rejected by Circuit Breaker: {reason}", 0.0

        if leverage > self.max_leverage:
            return False, f"Leverage {leverage} exceeds maximum allowed ({self.max_leverage})", 0.0

        notional = size * price
        max_allowed_position = state.total_equity * self.max_position_size_ratio

        if notional > max_allowed_position * 1.01:  # Allow 1% rounding margin
            adjusted_size = round(max_allowed_position / price, 6)
            return False, f"Order notional ${notional:,.2f} exceeds position size limit ${max_allowed_position:,.2f}", adjusted_size

        total_exposure = state.allocated_margin + notional
        max_exposure = state.total_equity * self.max_portfolio_exposure_ratio
        if total_exposure > max_exposure:
            return False, f"Total portfolio exposure ${total_exposure:,.2f} would exceed limit ${max_exposure:,.2f}", 0.0

        if notional > state.cash_balance:
            return False, f"Insufficient paper cash: requires ${notional:,.2f}, available ${state.cash_balance:,.2f}", 0.0

        return True, "Order approved by Capital Protection Engine", size

    def trigger_kill_switch(self, reason: str = "Manual Admin Command") -> None:
        self.kill_switch_active = True
        logger.critical("EMERGENCY KILL SWITCH TRIGGERED: %s", reason)

    def reset_kill_switch(self) -> None:
        self.kill_switch_active = False
        logger.info("Kill switch disarmed.")
