"""CLI Backtest Runner for CryptoAID Trade AI."""
from __future__ import annotations

import json
import sys
from pathlib import Path

# Bootstrap project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.data.mock_feed import MockMarketDataProvider
from src.performance.backtest import BacktestEngine


def main() -> None:
    print("=" * 65)
    print("  CRYPTOAID TRADE AI — HISTORICAL BACKTEST RUNNER")
    print("=" * 65)

    symbol = "BTC/USDC"
    mkt = MockMarketDataProvider(seed=42, regime="trend_bull")
    candles = mkt.get_candles(symbol, timeframe="1h", limit=120)

    engine = BacktestEngine(initial_capital=10_000.0)
    report = engine.run_backtest(candles, symbol=symbol, timeframe="1h", train_ratio=0.70)

    print(f"\nAsset: {report.symbol} | Candles: {report.total_candles} (Train: {report.train_candles}, Test: {report.test_candles})")
    print(f"Initial Capital: ${report.initial_capital:,.2f} -> Final Equity: ${report.final_equity:,.2f}")
    print(f"Net P&L: ${report.total_performance.net_pnl:+,.2f}")
    print(f"Win Rate: {report.total_performance.win_rate_pct:.1f}% ({report.total_performance.winning_trades}W / {report.total_performance.losing_trades}L)")
    print(f"Profit Factor: {report.total_performance.profit_factor:.2f}")
    print(f"Expectancy: ${report.total_performance.expectancy:.2f} / trade")
    print(f"Sharpe Ratio: {report.total_performance.sharpe_ratio:.2f}")
    print(f"Max Drawdown: {report.total_performance.max_drawdown_pct:.1f}% (${report.total_performance.max_drawdown_usd:,.2f})")
    print(f"Benchmark (Buy & Hold): {report.benchmark_buy_and_hold_pct:+.2f}%")

    out_file = "backtest_report.json"
    with open(out_file, "w") as f:
        json.dump(report.to_dict(), f, indent=2)
    print(f"\nMachine-readable JSON report written to: {out_file}")


if __name__ == "__main__":
    main()
