"""Paper Execution Engine for CryptoAID Trade AI."""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from src.config import settings
from src.dex.position_guardian import PositionGuardian
from src.dex.router import SmartExecutionRouter
from src.execution.models import OrderSide, OrderStatus, OrderType, PaperOrder, PaperPosition
from src.risk.capital_protection import CapitalProtectionEngine, PortfolioRiskState
from src.risk.cryptoaid_gate import CryptoAidRiskGate
from src.storage.db import DatabaseManager

logger = logging.getLogger(__name__)


class PaperExecutionEngine:
    """Simulates real exchange matching, fees, slippage and order lifecycle."""

    def __init__(
        self,
        db: DatabaseManager | None = None,
        risk_engine: CapitalProtectionEngine | None = None,
        risk_gate: CryptoAidRiskGate | None = None,
        router: SmartExecutionRouter | None = None,
        guardian: PositionGuardian | None = None,
    ) -> None:
        self.db = db or DatabaseManager()
        self.risk_engine = risk_engine or CapitalProtectionEngine()
        self.risk_gate = risk_gate or CryptoAidRiskGate()
        self.router = router or SmartExecutionRouter()
        self.guardian = guardian or PositionGuardian(db=self.db, router=self.router)

    def get_portfolio_state(self, account_id: str = "default_paper") -> PortfolioRiskState:
        acc = self.db.get_or_create_account(account_id)
        open_positions = self.db.get_open_positions(account_id)

        allocated_margin = sum(p["notional"] for p in open_positions)
        unrealized_pnl = sum(p["unrealized_pnl"] for p in open_positions)
        total_equity = acc["cash_balance"] + allocated_margin + unrealized_pnl

        # Calculate peak equity and current drawdown
        peak = max(acc["peak_equity"], total_equity)
        drawdown_pct = ((peak - total_equity) / peak) * 100.0 if peak > 0 else 0.0

        return PortfolioRiskState(
            account_id=account_id,
            total_equity=round(total_equity, 2),
            cash_balance=round(acc["cash_balance"], 2),
            allocated_margin=round(allocated_margin, 2),
            daily_realized_pnl=round(acc["realized_pnl"], 2),
            weekly_realized_pnl=round(acc["realized_pnl"], 2),
            unrealized_pnl=round(unrealized_pnl, 2),
            peak_equity=round(peak, 2),
            current_drawdown_pct=round(drawdown_pct, 2),
            active_positions_count=len(open_positions),
            kill_switch_active=self.risk_engine.kill_switch_active,
        )

    def execute_market_order(
        self,
        asset: str,
        side: OrderSide,
        size: float,
        market_price: float,
        sl: float | None = None,
        tp: float | None = None,
        trailing_distance: float | None = None,
        strategy: str = "MetaAgent",
        confidence: float | None = None,
        risk_score: float | None = None,
        account_id: str = "default_paper",
    ) -> PaperOrder:
        """Process and fill a paper market order with realistic slippage and fees."""
        order_id = f"ord_{uuid.uuid4().hex[:12]}"
        state = self.get_portfolio_state(account_id)

        # Validate with Capital Protection Engine
        allowed, reason, adj_size = self.risk_engine.validate_order(
            symbol=asset,
            side=side.value,
            size=size,
            price=market_price,
            state=state,
        )

        if not allowed:
            rejected_order = PaperOrder(
                order_id=order_id,
                account_id=account_id,
                asset=asset,
                side=side,
                type=OrderType.MARKET,
                entry=market_price,
                size=size,
                status=OrderStatus.REJECTED,
                strategy=strategy,
                confidence=confidence,
                risk_score=risk_score,
                reason=reason,
            )
            self.db.insert_order(rejected_order.to_dict())
            self.db.record_audit_event("ORDER_REJECTED", "WARNING", {"order_id": order_id, "reason": reason})
            logger.warning("Paper order %s rejected: %s", order_id, reason)
            return rejected_order

        # Obtain realistic quote from Smart Execution Router
        token_base = asset.split("/")[0]
        quote = self.router.get_route_quote(
            asset=asset,
            in_token="USDT" if side == OrderSide.BUY else token_base,
            out_token=token_base if side == OrderSide.BUY else "USDT",
            amount_in=market_price * size if side == OrderSide.BUY else size,
            current_market_price=market_price,
        )

        # Record route quote in database for execution quality audit
        self.db.record_route_quote({
            "quote_id": quote.quote_id,
            "asset": asset,
            "dex": quote.best_candidate.dex,
            "in_token": quote.in_token,
            "out_token": quote.out_token,
            "amount_in": quote.amount_in,
            "expected_out": quote.best_candidate.expected_output,
            "amount_out_min": quote.best_candidate.amount_out_min,
            "price_impact_pct": quote.best_candidate.price_impact_pct,
            "estimated_gas_gwei": self.router.polygon.get_gas_price_gwei(),
            "estimated_gas_cost_usd": quote.best_candidate.estimated_gas_cost_usd,
            "net_edge_pct": quote.net_edge_pct,
            "is_stale": 0,
        })

        # Apply realistic simulated slippage (bps)
        slippage_pct = quote.best_candidate.slippage_bps / 10_000.0
        dec_places = 4 if market_price < 10.0 else 2
        if side == OrderSide.BUY:
            fill_price = round(market_price * (1.0 + slippage_pct), dec_places)
        else:
            fill_price = round(market_price * (1.0 - slippage_pct), dec_places)

        notional = round(fill_price * size, 2)
        dex_fee = round(notional * quote.best_candidate.dex_fee_pct, 4)
        gas_cost = quote.best_candidate.estimated_gas_cost_usd
        total_fees = round(dex_fee + gas_cost, 4)
        slippage_cost = round(abs(fill_price - market_price) * size, 4)

        order = PaperOrder(
            order_id=order_id,
            account_id=account_id,
            asset=asset,
            side=side,
            type=OrderType.MARKET,
            entry=fill_price,
            size=size,
            sl=sl,
            tp=tp,
            trailing_distance=trailing_distance,
            fees=total_fees,
            simulated_slippage=slippage_cost,
            status=OrderStatus.FILLED,
            strategy=strategy,
            confidence=confidence,
            risk_score=risk_score,
            reason=f"Filled via {quote.best_candidate.dex} (Gas: ${gas_cost:.3f}, Slippage: {quote.best_candidate.slippage_bps:.1f}bps)",
        )
        self.db.insert_order(order.to_dict())

        # Record trade fill
        trade_id = f"tr_{uuid.uuid4().hex[:12]}"
        self.db.insert_trade({
            "id": trade_id,
            "order_id": order_id,
            "asset": asset,
            "side": side.value,
            "price": fill_price,
            "size": size,
            "fees": total_fees,
            "slippage": slippage_cost,
            "executed_at": datetime.now(timezone.utc).isoformat(),
        })

        # Open Position
        pos_id = f"pos_{uuid.uuid4().hex[:12]}"
        position = PaperPosition(
            id=pos_id,
            account_id=account_id,
            asset=asset,
            side="LONG" if side == OrderSide.BUY else "SHORT",
            entry_price=fill_price,
            current_price=fill_price,
            size=size,
            notional=notional,
            sl=sl,
            tp=tp,
            trailing_sl=(fill_price - trailing_distance) if trailing_distance and side == OrderSide.BUY else None,
            order_id=order_id,
        )
        self.db.upsert_position(position.to_dict())

        # Register position with Persistent Position Guardian
        self.guardian.track_position(position.to_dict())

        # Deduct cash & fee
        new_cash = round(state.cash_balance - notional - total_fees, 2)
        self.db.update_account_balances(account_id, new_cash, state.total_equity - total_fees, state.daily_realized_pnl)

        self.db.record_audit_event("ORDER_FILLED", "INFO", {"order_id": order_id, "asset": asset, "fill_price": fill_price, "size": size})
        logger.info("Filled paper order %s: %s %s @ %s (Fees: $%s)", order_id, side.value, asset, fill_price, total_fees)
        return order

    def update_market_prices(self, price_map: dict[str, float], account_id: str = "default_paper") -> list[str]:
        """Update mark-to-market prices on all open positions, trigger SL/TP/Trailing."""
        open_positions = self.db.get_open_positions(account_id)
        triggered_events: list[str] = []

        for pos in open_positions:
            asset = pos["asset"]
            if asset not in price_map:
                continue

            current_price = price_map[asset]
            entry_price = pos["entry_price"]
            size = pos["size"]
            side = pos["side"]

            # Calculate unrealized P&L
            if side == "LONG":
                unrealized = (current_price - entry_price) * size
                unrealized_pct = ((current_price - entry_price) / entry_price) * 100.0
            else:
                unrealized = (entry_price - current_price) * size
                unrealized_pct = ((entry_price - current_price) / entry_price) * 100.0

            pos["current_price"] = current_price
            pos["unrealized_pnl"] = round(unrealized, 2)
            pos["unrealized_pnl_pct"] = round(unrealized_pct, 2)
            pos["notional"] = round(current_price * size, 2)
            pos["last_updated"] = datetime.now(timezone.utc).isoformat()

            # Check Stop Loss
            if pos["sl"] is not None:
                sl_hit = (side == "LONG" and current_price <= pos["sl"]) or (side == "SHORT" and current_price >= pos["sl"])
                if sl_hit:
                    self.close_position(pos["id"], current_price, reason="Stop Loss Triggered", account_id=account_id)
                    triggered_events.append(f"Position {pos['id']} ({asset}) stopped out at {current_price}")
                    continue

            # Check Take Profit
            if pos["tp"] is not None:
                tp_hit = (side == "LONG" and current_price >= pos["tp"]) or (side == "SHORT" and current_price <= pos["tp"])
                if tp_hit:
                    self.close_position(pos["id"], current_price, reason="Take Profit Triggered", account_id=account_id)
                    triggered_events.append(f"Position {pos['id']} ({asset}) took profit at {current_price}")
                    continue

            # Check Trailing Stop
            if pos["trailing_sl"] is not None:
                if side == "LONG":
                    if current_price <= pos["trailing_sl"]:
                        self.close_position(pos["id"], current_price, reason="Trailing Stop Triggered", account_id=account_id)
                        triggered_events.append(f"Position {pos['id']} ({asset}) closed by trailing stop at {current_price}")
                        continue
                    # Ratchet trailing SL up
                    trailing_dist = entry_price * 0.015
                    new_trail = current_price - trailing_dist
                    if new_trail > pos["trailing_sl"]:
                        pos["trailing_sl"] = round(new_trail, 2)

            self.db.upsert_position(pos)

        # Update account balances
        state = self.get_portfolio_state(account_id)
        self.db.update_account_balances(account_id, state.cash_balance, state.total_equity, state.daily_realized_pnl)
        return triggered_events

    def close_position(
        self,
        position_id: str,
        current_price: float,
        reason: str = "Market Close",
        account_id: str = "default_paper",
    ) -> dict[str, Any]:
        """Close an open position, realize P&L, apply closing fees and credit account cash."""
        positions = self.db.get_open_positions(account_id)
        target = next((p for p in positions if p["id"] == position_id), None)
        if not target:
            raise ValueError(f"Position {position_id} not found")

        size = target["size"]
        entry = target["entry_price"]
        side = target["side"]

        # Calculate realized P&L
        if side == "LONG":
            gross_pnl = (current_price - entry) * size
            pnl_pct = ((current_price - entry) / entry) * 100.0
        else:
            gross_pnl = (entry - current_price) * size
            pnl_pct = ((entry - current_price) / entry) * 100.0

        closing_notional = current_price * size
        closing_fee = round(closing_notional * (settings.simulated_fee_bps / 10_000.0), 4)
        net_pnl = round(gross_pnl - closing_fee, 2)

        # Update Order record
        self.db.update_order(
            order_id=target["order_id"],
            status="CLOSED",
            exit_price=current_price,
            pnl=net_pnl,
            pnl_percent=round(pnl_pct, 2),
            reason=reason,
        )

        # Remove from active positions
        self.db.remove_position(position_id)

        # Update Account Balances
        acc = self.db.get_or_create_account(account_id)
        new_cash = round(acc["cash_balance"] + target["notional"] + net_pnl, 2)
        new_realized = round(acc["realized_pnl"] + net_pnl, 2)
        new_equity = round(acc["equity"] + net_pnl, 2)

        self.db.update_account_balances(account_id, new_cash, new_equity, new_realized)
        self.db.record_audit_event("POSITION_CLOSED", "INFO", {
            "position_id": position_id,
            "asset": target["asset"],
            "exit_price": current_price,
            "net_pnl": net_pnl,
            "reason": reason,
        })
        logger.info("Closed position %s on %s: PnL $%s (%s%%) - Reason: %s", position_id, target["asset"], net_pnl, round(pnl_pct, 2), reason)

        return {
            "position_id": position_id,
            "asset": target["asset"],
            "net_pnl": net_pnl,
            "pnl_percent": round(pnl_pct, 2),
            "exit_price": current_price,
            "reason": reason,
        }
