"""Unified Master Runner for CryptoAID Trade AI."""
from __future__ import annotations

import logging
import sys
import uvicorn
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.config import settings
from src.storage.db import DatabaseManager
from src.storage.migrations import apply_migrations

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("trade_ai_runner")


def main() -> None:
    logger.info("Initializing %s v%s...", settings.app_name, settings.app_version)
    logger.info("Database path: %s", settings.db_path)
    apply_migrations(settings.db_path)
    logger.info("Base settlement currency: %s", settings.base_quote)
    logger.info("Universe: %s", ", ".join(settings.universe))
    logger.info("Live trading enabled: %s (Fail-Closed Default)", settings.live_trading_enabled)

    # Start FastAPI Web Server & PWA
    uvicorn.run("src.api.app:app", host="0.0.0.0", port=8000, reload=False)


if __name__ == "__main__":
    main()
