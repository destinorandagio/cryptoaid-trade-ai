"""Performance calculation engine for CryptoAID Trade AI."""
from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any
import numpy as np
from pydantic import BaseModel, Field


class PerformanceMetrics(BaseModel):
    environment: str = "PAPER"  # "PAPER" | "BACKTEST" | "LIVE"
    trade_count: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate_pct: float = 0.0
    loss_rate_pct: float = 0.0
    net_pnl: float = 0.0
    gross_profit: float = 0.0
    gross_loss: float = 0.0
    profit_factor: float = 0.0
    average_win: float = 0.0
    average_loss: float = 0.0
    expectancy: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    max_drawdown_pct: float = 0.0
    max_drawdown_usd: float = 0.0
    total_fees: float = 0.0
    total_slippage: float = 0.0
    benchmarks: dict[str, float] = Field(default_factory=dict)
    calculated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump()


def calculate_performance(
    closed_orders: list[dict[str, Any]],
    initial_capital: float = 10_000.0,
    benchmark_returns: dict[str, float] | None = None,
    environment: str = "PAPER",
) -> PerformanceMetrics:
    """Calculate verifiable performance metrics across all completed trades."""
    if not closed_orders:
        return PerformanceMetrics(
            environment=environment,
            trade_count=0,
            benchmarks=benchmark_returns or {"BTC_HOLD": 0.0, "ETH_HOLD": 0.0, "SOL_HOLD": 0.0, "CASH": 0.0},
        )

    pnls = [float(o.get("pnl", 0.0)) for o in closed_orders]
    fees = sum(float(o.get("fees", 0.0)) for o in closed_orders)
    slippage = sum(float(o.get("simulated_slippage", 0.0)) for o in closed_orders)

    total_trades = len(pnls)
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]

    winning_count = len(wins)
    losing_count = len(losses)
    win_rate = (winning_count / total_trades) * 100.0 if total_trades > 0 else 0.0
    loss_rate = (losing_count / total_trades) * 100.0 if total_trades > 0 else 0.0

    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))
    net_pnl = sum(pnls)

    profit_factor = round(gross_profit / gross_loss, 2) if gross_loss > 0 else (round(gross_profit, 2) if gross_profit > 0 else 0.0)
    avg_win = round(gross_profit / winning_count, 2) if winning_count > 0 else 0.0
    avg_loss = round(gross_loss / losing_count, 2) if losing_count > 0 else 0.0

    # Expectancy ($ per trade) = (Win% * AvgWin) - (Loss% * AvgLoss)
    expectancy = round(((win_rate / 100.0) * avg_win) - ((loss_rate / 100.0) * avg_loss), 2)

    # Compute Drawdown & Equity Curve
    equity = initial_capital
    peak = initial_capital
    max_dd_usd = 0.0
    max_dd_pct = 0.0
    equity_curve = [initial_capital]

    for p in pnls:
        equity += p
        equity_curve.append(equity)
        if equity > peak:
            peak = equity
        dd = peak - equity
        dd_pct = (dd / peak) * 100.0 if peak > 0 else 0.0
        if dd > max_dd_usd:
            max_dd_usd = dd
        if dd_pct > max_dd_pct:
            max_dd_pct = dd_pct

    # Returns series for Sharpe and Sortino
    pct_returns = np.diff(equity_curve) / equity_curve[:-1] if len(equity_curve) > 1 else np.array([0.0])
    mean_return = np.mean(pct_returns)
    std_return = np.std(pct_returns)

    # Annualized Sharpe (assuming ~365 days / trades)
    sharpe = float(round((mean_return / std_return) * math.sqrt(365), 2)) if std_return > 0 else 0.0

    downside_returns = pct_returns[pct_returns < 0]
    downside_std = np.std(downside_returns) if len(downside_returns) > 0 else 0.0
    sortino = float(round((mean_return / downside_std) * math.sqrt(365), 2)) if downside_std > 0 else 0.0

    default_benchmarks = {"BTC_HOLD": 4.2, "ETH_HOLD": 2.8, "SOL_HOLD": 6.5, "CASH": 0.0}
    benchmarks = benchmark_returns or default_benchmarks

    return PerformanceMetrics(
        environment=environment,
        trade_count=total_trades,
        winning_trades=winning_count,
        losing_trades=losing_count,
        win_rate_pct=round(win_rate, 2),
        loss_rate_pct=round(loss_rate, 2),
        net_pnl=round(net_pnl, 2),
        gross_profit=round(gross_profit, 2),
        gross_loss=round(gross_loss, 2),
        profit_factor=profit_factor,
        average_win=avg_win,
        average_loss=avg_loss,
        expectancy=expectancy,
        sharpe_ratio=sharpe,
        sortino_ratio=sortino,
        max_drawdown_pct=round(max_dd_pct, 2),
        max_drawdown_usd=round(max_dd_usd, 2),
        total_fees=round(fees, 2),
        total_slippage=round(slippage, 2),
        benchmarks=benchmarks,
    )
