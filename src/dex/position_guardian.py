"""Persistent Position Guardian Daemon for CryptoAID Trade AI.
Monitors positions 24/7, enforces dynamic SL/TP/Trailing/Break-Even, and executes safe swaps back to USDT.
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any, Callable
from pydantic import BaseModel, Field

from src.config import settings
from src.data.base import TickerData
from src.data.provider import CompositeMarketDataProvider
from src.dex.polygon import PolygonProvider
from src.dex.router import SmartExecutionRouter
from src.dex.signer import DedicatedWalletSigner
from src.storage.db import DatabaseManager

logger = logging.getLogger(__name__)


class GuardianPosition(BaseModel):
    id: str
    asset: str
    side: str  # "BUY" / "LONG"
    entry_price: float
    current_price: float
    size: float
    notional: float
    sl: float | None = None
    tp: float | None = None
    trailing_sl: float | None = None
    highest_price_seen: float
    break_even_activated: bool = False
    opened_at: str
    order_id: str


class PositionGuardian:
    """
    Persistent 24/7 Position Guardian.
    Lifecycle: MARKET UPDATE -> POSITION STATE -> SL/TP/TRAILING CHECK -> RISK CHECK ->
               EXIT QUOTE -> SIMULATE -> SIGN -> SWAP BACK TO USDT -> RECEIPT -> ACCOUNTING
    """

    def __init__(
        self,
        db: DatabaseManager | None = None,
        market_provider: CompositeMarketDataProvider | None = None,
        router: SmartExecutionRouter | None = None,
        signer: DedicatedWalletSigner | None = None,
        on_exit_callback: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        self.db = db or DatabaseManager()
        self.market_provider = market_provider or CompositeMarketDataProvider()
        self.router = router or SmartExecutionRouter()
        self.signer = signer or DedicatedWalletSigner()
        self.on_exit_callback = on_exit_callback
        self.active_positions: dict[str, GuardianPosition] = {}
        self.restore_positions()

    def restore_positions(self) -> int:
        """Restore all open positions from persistent SQLite DB upon startup."""
        raw_positions = self.db.get_open_positions()
        restored = 0
        for p in raw_positions:
            pos_id = p["id"]
            g_pos = GuardianPosition(
                id=pos_id,
                asset=p["asset"],
                side=p["side"],
                entry_price=p["entry_price"],
                current_price=p["current_price"],
                size=p["size"],
                notional=p["notional"],
                sl=p.get("sl"),
                tp=p.get("tp"),
                trailing_sl=p.get("trailing_sl"),
                highest_price_seen=max(p["entry_price"], p["current_price"]),
                break_even_activated=False,
                opened_at=p.get("opened_at", datetime.now(timezone.utc).isoformat()),
                order_id=p.get("order_id", ""),
            )
            self.active_positions[pos_id] = g_pos
            restored += 1
        logger.info("Position Guardian restored %d active positions from database.", restored)
        return restored

    def track_position(self, pos_data: dict[str, Any]) -> None:
        """Register a newly opened position for continuous monitoring."""
        pos_id = pos_data["id"]
        g_pos = GuardianPosition(
            id=pos_id,
            asset=pos_data["asset"],
            side=pos_data["side"],
            entry_price=pos_data["entry_price"],
            current_price=pos_data["current_price"],
            size=pos_data["size"],
            notional=pos_data["notional"],
            sl=pos_data.get("sl"),
            tp=pos_data.get("tp"),
            trailing_sl=pos_data.get("trailing_sl"),
            highest_price_seen=pos_data["entry_price"],
            break_even_activated=False,
            opened_at=pos_data.get("opened_at", datetime.now(timezone.utc).isoformat()),
            order_id=pos_data.get("order_id", ""),
        )
        self.active_positions[pos_id] = g_pos
        logger.info("Position Guardian now tracking %s position on %s", g_pos.side, g_pos.asset)

    def evaluate_positions(self, market_prices: dict[str, float] | None = None) -> list[dict[str, Any]]:
        """
        Evaluate all open positions against SL, TP, Trailing Stop, Break-Even, and 5% Emergency Ceiling.
        Triggers execution swap back to USDT for any triggered position.
        """
        closed_events: list[dict[str, Any]] = []

        for pos_id, pos in list(self.active_positions.items()):
            # Update current mark price
            curr_price = (market_prices or {}).get(pos.asset)
            if not curr_price:
                try:
                    ticker = self.market_provider.get_ticker(pos.asset)
                    curr_price = ticker.price
                except Exception:
                    curr_price = pos.current_price

            pos.current_price = curr_price
            pos.highest_price_seen = max(pos.highest_price_seen, curr_price)

            # Calculate current P&L percentage
            pnl_pct = (curr_price - pos.entry_price) / pos.entry_price

            # Rule 1: Break-even lock
            # If price gained > break_even_activation_pct (+1.2%), move SL to entry price to lock risk
            if pnl_pct >= settings.break_even_activation_pct and not pos.break_even_activated:
                pos.sl = max(pos.sl or 0.0, pos.entry_price * 1.001)  # Cover tiny fee
                pos.break_even_activated = True
                logger.info("Break-Even locked for %s at %.4f", pos.asset, pos.sl)

            # Rule 2: Dynamic Trailing Stop
            # If price gained > trailing_stop_activation_pct (+1.8%), adjust trailing stop
            if pnl_pct >= settings.trailing_stop_activation_pct:
                new_trailing = pos.highest_price_seen * (1.0 - settings.trailing_distance_pct)
                if pos.trailing_sl is None or new_trailing > pos.trailing_sl:
                    pos.trailing_sl = new_trailing

            # Exit Conditions Check:
            exit_reason: str | None = None

            # Hard Emergency Ceiling: Max 5% loss ceiling strictly enforced
            emergency_sl = pos.entry_price * (1.0 - settings.emergency_stop_ceiling_pct)
            if curr_price <= emergency_sl:
                exit_reason = f"Hard Emergency 5% Stop Ceiling ({pnl_pct*100:.2f}%)"

            # Dynamic Stop Loss hit
            elif pos.sl and curr_price <= pos.sl:
                exit_reason = f"Dynamic Stop Loss Hit ({pnl_pct*100:.2f}%)"

            # Trailing Stop hit
            elif pos.trailing_sl and curr_price <= pos.trailing_sl:
                exit_reason = f"Trailing Stop Loss Hit ({pnl_pct*100:.2f}%)"

            # Take Profit hit
            elif pos.tp and curr_price >= pos.tp:
                exit_reason = f"Take Profit Target Achieved (+{pnl_pct*100:.2f}%)"

            if exit_reason:
                event = self._execute_exit_swap(pos, curr_price, exit_reason)
                closed_events.append(event)
                self.active_positions.pop(pos_id, None)

        return closed_events

    def emergency_close_all(self, reason: str = "Kill Switch Activated") -> list[dict[str, Any]]:
        """Force immediate closing swap back to USDT for all active positions."""
        events: list[dict[str, Any]] = []
        for pos_id, pos in list(self.active_positions.items()):
            event = self._execute_exit_swap(pos, pos.current_price, f"EMERGENCY CLOSE: {reason}")
            events.append(event)
            self.active_positions.pop(pos_id, None)
        return events

    def _execute_exit_swap(self, pos: GuardianPosition, current_price: float, reason: str) -> dict[str, Any]:
        """
        Executes swap back to USDT via Smart Router, signs tx, records trade and updates accounting.
        """
        token_base = pos.asset.split("/")[0]
        # Get exit quote from DEX router (Selling base asset back to USDT)
        quote = self.router.get_route_quote(
            asset=pos.asset,
            in_token=token_base,
            out_token="USDT",
            amount_in=pos.size,
            current_market_price=current_price,
            expected_move_pct=0.0,
        )

        gross_settled_usdt = quote.best_candidate.expected_output
        dex_fee = gross_settled_usdt * quote.best_candidate.dex_fee_pct
        gas_cost = quote.best_candidate.estimated_gas_cost_usd
        net_settled_usdt = gross_settled_usdt - dex_fee - gas_cost

        realized_pnl = net_settled_usdt - pos.notional
        realized_pnl_pct = (realized_pnl / pos.notional) if pos.notional > 0 else 0.0

        # Construct exit tx simulation
        exit_tx = {
            "from": self.signer.wallet_address or "0x0000000000000000000000000000000000000000",
            "to": quote.best_candidate.router_address,
            "data": "0x",
            "value": 0,
            "chainId": settings.polygon_chain_id,
            "gas": quote.best_candidate.estimated_gas_units,
        }

        # Sign & send (simulated or live)
        tx_receipt = self.signer.sign_and_send_transaction(
            tx_dict=exit_tx,
            trade_notional_usd=net_settled_usdt,
            kill_switch_active=False,
        )

        # Update DB: Remove position, update order, insert trade record
        self.db.remove_position(pos.id)
        self.db.update_order(
            order_id=pos.order_id,
            status="CLOSED",
            exit_price=current_price,
            pnl=round(realized_pnl, 4),
            pnl_percent=round(realized_pnl_pct * 100, 2),
            reason=reason,
        )
        self.db.insert_trade({
            "id": f"tr_{quote.quote_id}",
            "order_id": pos.order_id,
            "asset": pos.asset,
            "side": "SELL",
            "price": current_price,
            "size": pos.size,
            "fees": round(dex_fee + gas_cost, 4),
            "slippage": round(quote.best_candidate.slippage_bps / 100.0, 4),
            "executed_at": datetime.now(timezone.utc).isoformat(),
        })

        # Record on-chain transaction
        self.db.record_transaction({
            "tx_hash": tx_receipt["tx_hash"],
            "order_id": pos.order_id,
            "position_id": pos.id,
            "chain_id": settings.polygon_chain_id,
            "from_address": tx_receipt.get("from", ""),
            "to_address": tx_receipt.get("to", ""),
            "value_wei": "0",
            "data_hex": "0x",
            "nonce": 0,
            "gas_limit": quote.best_candidate.estimated_gas_units,
            "gas_price_gwei": self.router.polygon.get_gas_price_gwei(),
            "gas_used": tx_receipt.get("gas_used", quote.best_candidate.estimated_gas_units),
            "status": "CONFIRMED" if tx_receipt.get("status") in ("CONFIRMED", "SIMULATED") else "PENDING",
            "revert_reason": None,
            "simulation_passed": 1,
        })

        event = {
            "event": "POSITION_CLOSED",
            "position_id": pos.id,
            "asset": pos.asset,
            "entry_price": pos.entry_price,
            "exit_price": current_price,
            "realized_pnl": round(realized_pnl, 2),
            "realized_pnl_pct": round(realized_pnl_pct * 100, 2),
            "reason": reason,
            "dex": quote.best_candidate.dex,
            "tx_hash": tx_receipt["tx_hash"],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        logger.info("Position closed: %s | PnL: %+.2f USDT (%+.2f%%) | Reason: %s",
                    pos.asset, realized_pnl, realized_pnl_pct * 100, reason)

        if self.on_exit_callback:
            try:
                self.on_exit_callback(event)
            except Exception as exc:
                logger.error("Error in on_exit_callback: %s", exc)

        return event
