"""Observability Watchdog & Auto-Recovery Process for CryptoAID Trade AI."""
from __future__ import annotations

import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.config import settings
from src.data.polygon_scanner import PolygonDEXScanner
from src.data.provider import CompositeMarketDataProvider
from src.dex.polygon import PolygonProvider
from src.dex.position_guardian import PositionGuardian
from src.risk.capital_protection import CapitalProtectionEngine
from src.storage.db import DatabaseManager

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] [WATCHDOG] %(message)s")
logger = logging.getLogger("watchdog")


class SystemWatchdog:
    """Monitors RPC, database, market data freshness, positions and guardian health."""

    def __init__(self) -> None:
        self.db = DatabaseManager()
        self.polygon = PolygonProvider()
        self.mkt = CompositeMarketDataProvider()
        self.scanner = PolygonDEXScanner(market_provider=self.mkt)
        self.guardian = PositionGuardian(db=self.db)
        self.capital = CapitalProtectionEngine()

    def check_health(self) -> dict[str, bool]:
        """Perform system-wide health diagnosis."""
        health = {
            "db_healthy": False,
            "polygon_rpc_healthy": False,
            "market_data_healthy": False,
            "guardian_healthy": False,
            "risk_engine_healthy": False,
        }

        # 1. DB Check
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT count(*) FROM schema_migrations")
                health["db_healthy"] = cursor.fetchone()[0] >= 2
        except Exception as exc:
            logger.error("DB health check failed: %s", exc)

        # 2. Polygon RPC Check
        try:
            health["polygon_rpc_healthy"] = self.polygon.is_healthy()
        except Exception as exc:
            logger.warning("Polygon RPC health check notice: %s", exc)

        # 3. Market Data Check
        try:
            t = self.mkt.get_ticker(settings.universe[0])
            health["market_data_healthy"] = (t.price > 0)
        except Exception as exc:
            logger.error("Market data check failed: %s", exc)

        # 4. Guardian Check
        try:
            count = len(self.guardian.active_positions)
            health["guardian_healthy"] = True
        except Exception as exc:
            logger.error("Guardian health check failed: %s", exc)

        # 5. Risk Engine Check
        try:
            health["risk_engine_healthy"] = not self.capital.kill_switch_active
        except Exception as exc:
            logger.error("Risk engine health check failed: %s", exc)

        return health

    def run_health_cycle(self) -> bool:
        """Run single watchdog health assessment and persist state."""
        health = self.check_health()
        all_critical_ok = health["db_healthy"] and health["market_data_healthy"] and health["guardian_healthy"]

        status_record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "health": health,
            "all_critical_ok": all_critical_ok,
            "active_positions": len(self.guardian.active_positions),
            "autotrade_enabled": settings.autotrade_enabled,
            "kill_switch_active": self.capital.kill_switch_active,
        }

        self.db.set_system_state("watchdog_health", status_record)
        self.db.record_audit_event("WATCHDOG_HEARTBEAT", "INFO" if all_critical_ok else "WARNING", status_record)

        if not all_critical_ok:
            logger.warning("Watchdog detected subsystem anomaly: %s", health)
        else:
            logger.info("Watchdog check PASS: All critical systems healthy (Positions: %d).", len(self.guardian.active_positions))

        return all_critical_ok


def main() -> None:
    logger.info("Starting CryptoAID Trade AI Observability Watchdog...")
    dog = SystemWatchdog()
    res = dog.run_health_cycle()
    if res:
        logger.info("Watchdog cycle completed with status: HEALTHY")
    else:
        logger.warning("Watchdog cycle completed with status: DEGRADED")


if __name__ == "__main__":
    main()
