"""Database connection and repository for CryptoAID Trade AI."""
from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.config import settings
from src.storage.migrations import apply_migrations


class DatabaseManager:
    """Manages SQLite connection, queries and transactions."""

    def __init__(self, db_path: Path | str | None = None) -> None:
        self.db_path = Path(db_path or settings.db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        apply_migrations(self.db_path)

    @contextmanager
    def get_connection(self):
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    # Paper Account Operations
    def get_or_create_account(self, account_id: str = "default_paper", initial_balance: float = 1_000.0) -> dict[str, Any]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM paper_accounts WHERE id = ?", (account_id,))
            row = cursor.fetchone()
            if row:
                return dict(row)

            # Create default user if not exists
            cursor.execute("INSERT OR IGNORE INTO users (id, username, role) VALUES ('default_user', 'CryptoAidTrader', 'trader')")
            cursor.execute(
                """
                INSERT INTO paper_accounts (id, user_id, currency, initial_balance, cash_balance, equity, peak_equity)
                VALUES (?, 'default_user', 'USDT', ?, ?, ?, ?)
                """,
                (account_id, initial_balance, initial_balance, initial_balance, initial_balance),
            )
            conn.commit()
            cursor.execute("SELECT * FROM paper_accounts WHERE id = ?", (account_id,))
            return dict(cursor.fetchone())

    def update_account_balances(self, account_id: str, cash_balance: float, equity: float, realized_pnl: float) -> None:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT peak_equity FROM paper_accounts WHERE id = ?", (account_id,))
            row = cursor.fetchone()
            peak = max(equity, row["peak_equity"] if row else equity)
            cursor.execute(
                """
                UPDATE paper_accounts
                SET cash_balance = ?, equity = ?, realized_pnl = ?, peak_equity = ?
                WHERE id = ?
                """,
                (cash_balance, equity, realized_pnl, peak, account_id),
            )
            conn.commit()

    # Order Operations
    def insert_order(self, order_data: dict[str, Any]) -> None:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO orders (
                    order_id, user_id, account_id, asset, side, type, entry, size,
                    sl, tp, trailing_distance, fees, simulated_slippage, open_time,
                    close_time, exit_price, pnl, pnl_percent, status, strategy,
                    confidence, risk_score, reason
                ) VALUES (
                    :order_id, :user_id, :account_id, :asset, :side, :type, :entry, :size,
                    :sl, :tp, :trailing_distance, :fees, :simulated_slippage, :open_time,
                    :close_time, :exit_price, :pnl, :pnl_percent, :status, :strategy,
                    :confidence, :risk_score, :reason
                )
                """,
                order_data,
            )
            conn.commit()

    def update_order(self, order_id: str, status: str, exit_price: float | None = None, pnl: float = 0.0, pnl_percent: float = 0.0, reason: str | None = None) -> None:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            close_time = datetime.now(timezone.utc).isoformat() if status in ("CLOSED", "CANCELLED", "FILLED") else None
            cursor.execute(
                """
                UPDATE orders
                SET status = ?, exit_price = ?, pnl = ?, pnl_percent = ?, close_time = COALESCE(?, close_time), reason = COALESCE(?, reason)
                WHERE order_id = ?
                """,
                (status, exit_price, pnl, pnl_percent, close_time, reason, order_id),
            )
            conn.commit()

    def get_orders(self, account_id: str = "default_paper", limit: int = 50) -> list[dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM orders WHERE account_id = ? ORDER BY open_time DESC LIMIT ?", (account_id, limit))
            return [dict(r) for r in cursor.fetchall()]

    # Position Operations
    def upsert_position(self, pos: dict[str, Any]) -> None:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO positions (
                    id, account_id, asset, side, entry_price, current_price, size, notional,
                    sl, tp, trailing_sl, unrealized_pnl, unrealized_pnl_pct, last_updated, order_id
                ) VALUES (
                    :id, :account_id, :asset, :side, :entry_price, :current_price, :size, :notional,
                    :sl, :tp, :trailing_sl, :unrealized_pnl, :unrealized_pnl_pct, :last_updated, :order_id
                )
                """,
                pos,
            )
            conn.commit()

    def remove_position(self, position_id: str) -> None:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM positions WHERE id = ?", (position_id,))
            conn.commit()

    def get_open_positions(self, account_id: str = "default_paper") -> list[dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM positions WHERE account_id = ? ORDER BY opened_at DESC", (account_id,))
            return [dict(r) for r in cursor.fetchall()]

    # Trades Operations
    def insert_trade(self, trade_data: dict[str, Any]) -> None:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO trades (id, order_id, asset, side, price, size, fees, slippage, executed_at)
                VALUES (:id, :order_id, :asset, :side, :price, :size, :fees, :slippage, :executed_at)
                """,
                trade_data,
            )
            conn.commit()

    def get_trades(self, limit: int = 100) -> list[dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM trades ORDER BY executed_at DESC LIMIT ?", (limit,))
            return [dict(r) for r in cursor.fetchall()]

    # Audit & Observability
    def record_audit_event(self, event_type: str, severity: str, payload: dict[str, Any]) -> None:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            event_id = f"aud_{uuid.uuid4().hex[:12]}"
            cursor.execute(
                "INSERT INTO audit_events (id, event_type, severity, payload_json) VALUES (?, ?, ?, ?)",
                (event_id, event_type, severity, json.dumps(payload)),
            )
            conn.commit()

    def record_risk_decision(self, asset: str, decision: str, score: float, details: dict[str, Any], reasons: list[str]) -> None:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            dec_id = f"risk_{uuid.uuid4().hex[:12]}"
            cursor.execute(
                "INSERT INTO risk_decisions (id, asset, decision, composite_risk_score, details_json, reasons_json) VALUES (?, ?, ?, ?, ?, ?)",
                (dec_id, asset, decision, score, json.dumps(details), json.dumps(reasons)),
            )
            conn.commit()

    # System State
    def set_system_state(self, key: str, value: Any) -> None:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO system_state (key, value_json, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)",
                (key, json.dumps(value)),
            )
            conn.commit()

    def get_system_state(self, key: str) -> Any | None:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT value_json FROM system_state WHERE key = ?", (key,))
            row = cursor.fetchone()
            return json.loads(row["value_json"]) if row else None

    # Token Registry
    def upsert_token(self, token_data: dict[str, Any]) -> None:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO token_registry (
                    address, symbol, name, decimals, is_supported, is_honeypot,
                    liquidity_usd, volume_24h_usd, risk_score, last_verified
                ) VALUES (
                    :address, :symbol, :name, :decimals, :is_supported, :is_honeypot,
                    :liquidity_usd, :volume_24h_usd, :risk_score, CURRENT_TIMESTAMP
                )
                """,
                token_data,
            )
            conn.commit()

    def get_tokens(self) -> list[dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM token_registry ORDER BY volume_24h_usd DESC")
            return [dict(r) for r in cursor.fetchall()]

    # Route Quotes
    def record_route_quote(self, quote_data: dict[str, Any]) -> None:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO route_quotes (
                    quote_id, asset, dex, in_token, out_token, amount_in, expected_out,
                    amount_out_min, price_impact_pct, estimated_gas_gwei, estimated_gas_cost_usd,
                    net_edge_pct, is_stale, quoted_at
                ) VALUES (
                    :quote_id, :asset, :dex, :in_token, :out_token, :amount_in, :expected_out,
                    :amount_out_min, :price_impact_pct, :estimated_gas_gwei, :estimated_gas_cost_usd,
                    :net_edge_pct, :is_stale, CURRENT_TIMESTAMP
                )
                """,
                quote_data,
            )
            conn.commit()

    def get_recent_quotes(self, asset: str | None = None, limit: int = 20) -> list[dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if asset:
                cursor.execute("SELECT * FROM route_quotes WHERE asset = ? ORDER BY quoted_at DESC LIMIT ?", (asset, limit))
            else:
                cursor.execute("SELECT * FROM route_quotes ORDER BY quoted_at DESC LIMIT ?", (limit,))
            return [dict(r) for r in cursor.fetchall()]

    # Strategy Decisions
    def record_strategy_decision(self, dec: dict[str, Any]) -> None:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO strategy_decisions (
                    id, strategy_name, asset, timeframe, signal, confidence,
                    expected_return, expected_risk, entry_zone_json, invalidation, evidence_json
                ) VALUES (
                    :id, :strategy_name, :asset, :timeframe, :signal, :confidence,
                    :expected_return, :expected_risk, :entry_zone_json, :invalidation, :evidence_json
                )
                """,
                dec,
            )
            conn.commit()

    # Meta Decisions
    def record_meta_decision(self, meta: dict[str, Any]) -> None:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO meta_decisions (
                    id, asset, regime, decision, confidence, net_edge_pct,
                    gas_cost_usd, dex_fee_pct, slippage_pct, price_impact_pct,
                    selected_strategies_json, evidence_json
                ) VALUES (
                    :id, :asset, :regime, :decision, :confidence, :net_edge_pct,
                    :gas_cost_usd, :dex_fee_pct, :slippage_pct, :price_impact_pct,
                    :selected_strategies_json, :evidence_json
                )
                """,
                meta,
            )
            conn.commit()

    # Transactions & Wallet Events
    def record_transaction(self, tx: dict[str, Any]) -> None:
        now_str = datetime.now(timezone.utc).isoformat()
        tx.setdefault("submitted_at", now_str)
        tx.setdefault("confirmed_at", now_str)
        tx.setdefault("order_id", None)
        tx.setdefault("position_id", None)
        tx.setdefault("chain_id", 137)
        tx.setdefault("from_address", "")
        tx.setdefault("to_address", "")
        tx.setdefault("value_wei", "0")
        tx.setdefault("data_hex", "0x")
        tx.setdefault("nonce", 0)
        tx.setdefault("gas_limit", 180000)
        tx.setdefault("gas_price_gwei", 35.0)
        tx.setdefault("gas_used", 180000)
        tx.setdefault("status", "CONFIRMED")
        tx.setdefault("revert_reason", None)
        tx.setdefault("simulation_passed", 1)

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO transactions (
                    tx_hash, order_id, position_id, chain_id, from_address, to_address,
                    value_wei, data_hex, nonce, gas_limit, gas_price_gwei, gas_used,
                    status, revert_reason, simulation_passed, submitted_at, confirmed_at
                ) VALUES (
                    :tx_hash, :order_id, :position_id, :chain_id, :from_address, :to_address,
                    :value_wei, :data_hex, :nonce, :gas_limit, :gas_price_gwei, :gas_used,
                    :status, :revert_reason, :simulation_passed, :submitted_at, :confirmed_at
                )
                """,
                tx,
            )
            conn.commit()

    def get_transactions(self, limit: int = 50) -> list[dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM transactions ORDER BY submitted_at DESC LIMIT ?", (limit,))
            return [dict(r) for r in cursor.fetchall()]

    def record_wallet_event(self, evt: dict[str, Any]) -> None:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO wallet_events (
                    id, wallet_address, event_type, token_address, amount, details_json
                ) VALUES (
                    :id, :wallet_address, :event_type, :token_address, :amount, :details_json
                )
                """,
                evt,
            )
            conn.commit()

