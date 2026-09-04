"""Paper Trading Daemon for Mark-to-Market updates and SL/TP execution."""
from __future__ import annotations

import time
import logging
import sys
from pathlib import Path

# Bootstrap project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.config import settings
from src.data.provider import CompositeMarketDataProvider
from src.execution.paper_engine import PaperExecutionEngine

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("paper_daemon")


def run_single_cycle(engine: PaperExecutionEngine, mkt: CompositeMarketDataProvider) -> None:
    prices = {}
    for sym in settings.universe:
        ticker = mkt.get_ticker(sym)
        prices[sym] = ticker.price

    events = engine.update_market_prices(prices)
    for ev in events:
        logger.info("[EVENT] %s", ev)

    state = engine.get_portfolio_state()
    logger.info(
        "Equity: $%.2f | Cash: $%.2f | Open Positions: %d | Realized: $%.2f",
        state.total_equity,
        state.cash_balance,
        state.active_positions_count,
        state.daily_realized_pnl,
    )


def main() -> None:
    logger.info("Starting CryptoAID Paper Trading Daemon (Interval: 10s)...")
    engine = PaperExecutionEngine()
    mkt = CompositeMarketDataProvider()

    # Run one cycle by default
    run_single_cycle(engine, mkt)
    logger.info("Initial daemon cycle completed successfully.")


if __name__ == "__main__":
    main()
