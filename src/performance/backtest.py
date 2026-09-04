"""Backtest Engine with Train/Test Split and Walk-Forward Validation."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any
from pydantic import BaseModel, Field

from src.agents.base import SignalType
from src.agents.meta_agent import MetaAgent
from src.config import settings
from src.data.base import Candle, MarketSnapshot
from src.performance.metrics import PerformanceMetrics, calculate_performance
from src.risk.cryptoaid_gate import CryptoAidRiskGate

logger = logging.getLogger(__name__)


class BacktestReport(BaseModel):
    symbol: str
    timeframe: str
    total_candles: int
    train_candles: int
    test_candles: int
    initial_capital: float
    final_equity: float
    total_performance: PerformanceMetrics
    in_sample_performance: PerformanceMetrics
    out_of_sample_performance: PerformanceMetrics
    benchmark_buy_and_hold_pct: float
    generated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump()


class BacktestEngine:
    """Rigorous historical backtesting engine with look-ahead bias prevention."""

    def __init__(
        self,
        meta_agent: MetaAgent | None = None,
        risk_gate: CryptoAidRiskGate | None = None,
        initial_capital: float = 10_000.0,
    ) -> None:
        self.meta_agent = meta_agent or MetaAgent()
        self.risk_gate = risk_gate or CryptoAidRiskGate()
        self.initial_capital = initial_capital

    def run_backtest(
        self,
        candles: list[Candle],
        symbol: str = "BTC/USDC",
        timeframe: str = "1h",
        train_ratio: float = 0.70,
    ) -> BacktestReport:
        if len(candles) < 35:
            raise ValueError("At least 35 candles required for meaningful backtest")

        split_idx = int(len(candles) * train_ratio)
        train_candles = candles[:split_idx]
        test_candles = candles[split_idx:]

        # Execute full walk-forward sequence
        all_closed_trades, final_equity = self._simulate_sequence(candles, symbol)
        train_closed_trades, _ = self._simulate_sequence(train_candles, symbol)
        test_closed_trades, _ = self._simulate_sequence(test_candles, symbol)

        # Benchmark Buy & Hold
        start_price = candles[0].close
        end_price = candles[-1].close
        bnh_pct = round(((end_price - start_price) / start_price) * 100.0, 2)
        benchmarks = {f"{symbol.split('/')[0]}_HOLD": bnh_pct, "CASH": 0.0}

        total_perf = calculate_performance(all_closed_trades, self.initial_capital, benchmarks, environment="BACKTEST")
        in_sample_perf = calculate_performance(train_closed_trades, self.initial_capital, benchmarks, environment="BACKTEST")
        out_of_sample_perf = calculate_performance(test_closed_trades, self.initial_capital, benchmarks, environment="BACKTEST")

        return BacktestReport(
            symbol=symbol,
            timeframe=timeframe,
            total_candles=len(candles),
            train_candles=len(train_candles),
            test_candles=len(test_candles),
            initial_capital=self.initial_capital,
            final_equity=round(final_equity, 2),
            total_performance=total_perf,
            in_sample_performance=in_sample_perf,
            out_of_sample_performance=out_of_sample_perf,
            benchmark_buy_and_hold_pct=bnh_pct,
        )

    def _simulate_sequence(self, candles: list[Candle], symbol: str) -> tuple[list[dict[str, Any]], float]:
        capital = self.initial_capital
        cash = capital
        open_pos: dict[str, Any] | None = None
        closed_trades: list[dict[str, Any]] = []

        slippage_pct = settings.simulated_slippage_bps / 10_000.0
        fee_pct = settings.simulated_fee_bps / 10_000.0

        # Step through time strictly causal
        for i in range(25, len(candles)):
            history = candles[:i]
            current_bar = candles[i]
            price = current_bar.close

            # If position is open, check SL/TP/Trailing on current_bar high/low
            if open_pos:
                side = open_pos["side"]
                entry = open_pos["entry_price"]
                size = open_pos["size"]
                sl = open_pos.get("sl")
                tp = open_pos.get("tp")
                exit_price: float | None = None
                reason = "Close"

                if side == "LONG":
                    if sl and current_bar.low <= sl:
                        exit_price = sl
                        reason = "Stop Loss"
                    elif tp and current_bar.high >= tp:
                        exit_price = tp
                        reason = "Take Profit"
                elif side == "SHORT":
                    if sl and current_bar.high >= sl:
                        exit_price = sl
                        reason = "Stop Loss"
                    elif tp and current_bar.low <= tp:
                        exit_price = tp
                        reason = "Take Profit"

                if exit_price is not None:
                    # Close trade
                    gross_pnl = (exit_price - entry) * size if side == "LONG" else (entry - exit_price) * size
                    fee = (exit_price * size) * fee_pct
                    net_pnl = round(gross_pnl - fee, 2)
                    cash += open_pos["notional"] + net_pnl
                    closed_trades.append({
                        "asset": symbol,
                        "side": side,
                        "entry": entry,
                        "exit_price": exit_price,
                        "size": size,
                        "pnl": net_pnl,
                        "fees": fee,
                        "simulated_slippage": round(price * slippage_pct * size, 4),
                        "reason": reason,
                    })
                    open_pos = None

            # Generate signal if flat
            if open_pos is None:
                snapshot = MarketSnapshot(
                    symbol=symbol,
                    price=price,
                    bid=price * 0.9999,
                    ask=price * 1.0001,
                    spread=price * 0.0002,
                    volume_24h=current_bar.volume * 24,
                    volatility_24h=4.5,
                    candles_1h=history,
                    provider="backtest_simulator",
                )
                meta_dec = self.meta_agent.evaluate(snapshot)
                risk_res = self.risk_gate.evaluate(meta_dec, snapshot)

                if risk_res.passed and meta_dec.decision in (SignalType.LONG, SignalType.SHORT):
                    side_str = "LONG" if meta_dec.decision == SignalType.LONG else "SHORT"
                    fill_price = price * (1.0 + slippage_pct) if side_str == "LONG" else price * (1.0 - slippage_pct)
                    notional = capital * settings.max_position_size_ratio
                    size = round(notional / fill_price, 6)
                    fee = notional * fee_pct

                    if cash >= (notional + fee):
                        cash -= (notional + fee)
                        open_pos = {
                            "side": side_str,
                            "entry_price": fill_price,
                            "size": size,
                            "notional": notional,
                            "sl": meta_dec.recommended_stop_loss,
                            "tp": meta_dec.recommended_take_profit,
                        }

        # Liquidate remaining open position at end
        if open_pos:
            end_price = candles[-1].close
            side = open_pos["side"]
            size = open_pos["size"]
            entry = open_pos["entry_price"]
            gross_pnl = (end_price - entry) * size if side == "LONG" else (entry - end_price) * size
            fee = (end_price * size) * fee_pct
            net_pnl = round(gross_pnl - fee, 2)
            cash += open_pos["notional"] + net_pnl
            closed_trades.append({
                "asset": symbol,
                "side": side,
                "entry": entry,
                "exit_price": end_price,
                "size": size,
                "pnl": net_pnl,
                "fees": fee,
                "simulated_slippage": round(end_price * slippage_pct * size, 4),
                "reason": "Backtest End Liquidation",
            })

        return closed_trades, cash
