"""Tests for Performance and Backtest Engines."""
from src.data.mock_feed import MockMarketDataProvider
from src.performance.backtest import BacktestEngine, BacktestReport
from src.performance.metrics import calculate_performance


def test_calculate_performance_metrics():
    sample_trades = [
        {"pnl": 120.0, "fees": 2.5, "simulated_slippage": 1.0},
        {"pnl": -50.0, "fees": 2.5, "simulated_slippage": 1.0},
        {"pnl": 80.0, "fees": 2.5, "simulated_slippage": 1.0},
        {"pnl": -30.0, "fees": 2.5, "simulated_slippage": 1.0},
        {"pnl": 150.0, "fees": 2.5, "simulated_slippage": 1.0},
    ]

    metrics = calculate_performance(sample_trades, initial_capital=10_000.0)
    assert metrics.trade_count == 5
    assert metrics.winning_trades == 3
    assert metrics.losing_trades == 2
    assert metrics.win_rate_pct == 60.0
    assert metrics.net_pnl == 270.0
    assert metrics.gross_profit == 350.0
    assert metrics.gross_loss == 80.0
    assert metrics.profit_factor == 4.38
    assert metrics.expectancy > 0
    assert metrics.environment == "PAPER"
    assert "BTC_HOLD" in metrics.benchmarks


def test_backtest_engine_run():
    provider = MockMarketDataProvider(seed=42, regime="trend_bull")
    candles = provider.get_candles("BTC/USDC", timeframe="1h", limit=80)

    engine = BacktestEngine(initial_capital=10_000.0)
    report = engine.run_backtest(candles, symbol="BTC/USDC", timeframe="1h", train_ratio=0.70)

    assert isinstance(report, BacktestReport)
    assert report.total_candles == 80
    assert report.train_candles == 56
    assert report.test_candles == 24
    assert report.initial_capital == 10_000.0
    assert report.total_performance.environment == "BACKTEST"
    assert isinstance(report.to_dict(), dict)
