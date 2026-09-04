"""Database connection and repository for CryptoAID Trade AI."""
from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
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

    # Predictive Heart Forecast & Calibration Ledger (Closure 1)
    def record_forecast(self, forecast: dict[str, Any]) -> str:
        fid = forecast.get("id") or str(uuid.uuid4())
        forecast_data = {
            "id": fid,
            "asset": forecast["asset"],
            "timeframe": forecast["timeframe"],
            "target_timestamp": forecast["target_timestamp"],
            "now_price": float(forecast["now_price"]),
            "predicted_p50": float(forecast["predicted_p50"]),
            "predicted_p10": float(forecast["predicted_p10"]),
            "predicted_p90": float(forecast["predicted_p90"]),
            "direction": forecast["direction"],
            "expected_return_pct": float(forecast.get("expected_return_pct", 0.0)),
            "confidence_pct": float(forecast.get("confidence_pct", 0.0)),
            "regime": forecast.get("regime", "UNKNOWN"),
            "models_evidence_json": json.dumps(forecast.get("models_evidence", {})),
            "actual_price": None,
            "error_pct": None,
            "direction_hit": None,
            "brier_score": None,
            "is_calibrated": 0,
            "calibrated_at": None,
        }
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO predictive_heart_forecasts (
                    id, asset, timeframe, target_timestamp, now_price,
                    predicted_p50, predicted_p10, predicted_p90, direction,
                    expected_return_pct, confidence_pct, regime, models_evidence_json,
                    actual_price, error_pct, direction_hit, brier_score, is_calibrated, calibrated_at
                ) VALUES (
                    :id, :asset, :timeframe, :target_timestamp, :now_price,
                    :predicted_p50, :predicted_p10, :predicted_p90, :direction,
                    :expected_return_pct, :confidence_pct, :regime, :models_evidence_json,
                    :actual_price, :error_pct, :direction_hit, :brier_score, :is_calibrated, :calibrated_at
                )
                """,
                forecast_data,
            )
            conn.commit()
        return fid

    def get_uncalibrated_forecasts(self, max_timestamp: str | None = None) -> list[dict[str, Any]]:
        now_iso = max_timestamp or datetime.now(timezone.utc).isoformat()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM predictive_heart_forecasts
                WHERE is_calibrated = 0 AND target_timestamp <= ?
                ORDER BY target_timestamp ASC
                LIMIT 100
                """,
                (now_iso,),
            )
            return [dict(r) for r in cursor.fetchall()]

    def calibrate_forecast(
        self,
        forecast_id: str,
        actual_price: float,
        error_pct: float,
        direction_hit: int,
        brier_score: float,
    ) -> None:
        now_iso = datetime.now(timezone.utc).isoformat()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE predictive_heart_forecasts
                SET actual_price = ?, error_pct = ?, direction_hit = ?,
                    brier_score = ?, is_calibrated = 1, calibrated_at = ?
                WHERE id = ?
                """,
                (actual_price, error_pct, direction_hit, brier_score, now_iso, forecast_id),
            )
            conn.commit()

    def get_calibration_stats(self, asset: str | None = None) -> dict[str, Any]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            query = "SELECT * FROM predictive_heart_forecasts WHERE is_calibrated = 1"
            params = []
            if asset:
                query += " AND asset = ?"
                params.append(asset)
            query += " ORDER BY calibrated_at DESC LIMIT 500"
            cursor.execute(query, tuple(params))
            rows = [dict(r) for r in cursor.fetchall()]

            if not rows:
                return {
                    "total_calibrated": 0,
                    "accuracy_direction_pct": 0.0,
                    "avg_error_pct": 0.0,
                    "avg_brier_score": 0.0,
                    "status": "INITIALIZING_CALIBRATION",
                    "recent_evaluations": [],
                }

            hits = sum(1 for r in rows if r.get("direction_hit") == 1)
            accuracy = (hits / len(rows)) * 100.0
            avg_err = sum(abs(float(r.get("error_pct") or 0.0)) for r in rows) / len(rows)
            avg_brier = sum(float(r.get("brier_score") or 0.0) for r in rows) / len(rows)

            return {
                "total_calibrated": len(rows),
                "accuracy_direction_pct": round(accuracy, 2),
                "avg_error_pct": round(avg_err, 4),
                "avg_brier_score": round(avg_brier, 4),
                "status": "CALIBRATED_ACTIVE",
                "recent_evaluations": rows[:10],
            }

    def get_recent_forecasts(self, asset: str = "POL/USDT", limit: int = 10) -> list[dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM predictive_heart_forecasts
                WHERE asset = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (asset, limit),
            )
            return [dict(r) for r in cursor.fetchall()]

    # Strategy Switching Audit Trail
    def record_strategy_switch(self, switch_data: dict[str, Any]) -> str:
        sid = switch_data.get("id") or str(uuid.uuid4())
        record = {
            "id": sid,
            "position_id": switch_data["position_id"],
            "account_id": switch_data.get("account_id", "paper_balanced"),
            "asset": switch_data["asset"],
            "from_strategy": switch_data["from_strategy"],
            "to_strategy": switch_data["to_strategy"],
            "reason": switch_data["reason"],
            "pnl_pct_at_switch": float(switch_data["pnl_pct_at_switch"]),
            "entry_price": float(switch_data["entry_price"]),
            "current_price": float(switch_data["current_price"]),
            "new_sl": float(switch_data["new_sl"]) if switch_data.get("new_sl") is not None else None,
            "new_tp": float(switch_data["new_tp"]) if switch_data.get("new_tp") is not None else None,
            "switched_at": switch_data.get("switched_at", datetime.now(timezone.utc).isoformat()),
        }
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO strategy_switches (
                    id, position_id, account_id, asset, from_strategy, to_strategy,
                    reason, pnl_pct_at_switch, entry_price, current_price, new_sl, new_tp, switched_at
                ) VALUES (
                    :id, :position_id, :account_id, :asset, :from_strategy, :to_strategy,
                    :reason, :pnl_pct_at_switch, :entry_price, :current_price, :new_sl, :new_tp, :switched_at
                )
                """,
                record,
            )
            conn.commit()
        return sid

    def get_strategy_switches(self, position_id: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if position_id:
                cursor.execute(
                    "SELECT * FROM strategy_switches WHERE position_id = ? ORDER BY switched_at DESC LIMIT ?",
                    (position_id, limit),
                )
            else:
                cursor.execute("SELECT * FROM strategy_switches ORDER BY switched_at DESC LIMIT ?", (limit,))
            return [dict(r) for r in cursor.fetchall()]

    # Gem Hunter Radar & Candidates
    def upsert_gem_candidate(self, gem: dict[str, Any]) -> str:
        gid = gem.get("id") or str(uuid.uuid4())
        record = {
            "id": gid,
            "token_address": gem["token_address"].lower(),
            "symbol": gem["symbol"].upper(),
            "name": gem["name"],
            "score": float(gem.get("score", 0.0)),
            "classification": gem.get("classification", "WATCH"),
            "stage": gem.get("stage", "DISCOVERED"),
            "liquidity_usd": float(gem.get("liquidity_usd", 0.0)),
            "volume_24h": float(gem.get("volume_24h", 0.0)),
            "holder_count": int(gem.get("holder_count", 0)),
            "honeypot_safe": int(gem.get("honeypot_safe", 1)),
            "metrics_json": json.dumps(gem.get("metrics", {})),
            "discovered_at": gem.get("discovered_at", datetime.now(timezone.utc).isoformat()),
            "last_updated": datetime.now(timezone.utc).isoformat(),
        }
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO gem_candidates (
                    id, token_address, symbol, name, score, classification, stage,
                    liquidity_usd, volume_24h, holder_count, honeypot_safe, metrics_json,
                    discovered_at, last_updated
                ) VALUES (
                    :id, :token_address, :symbol, :name, :score, :classification, :stage,
                    :liquidity_usd, :volume_24h, :holder_count, :honeypot_safe, :metrics_json,
                    :discovered_at, :last_updated
                )
                """,
                record,
            )
            conn.commit()
        return gid

    def get_gem_candidates(self, min_score: float = 0.0, limit: int = 50) -> list[dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM gem_candidates WHERE score >= ? ORDER BY score DESC, liquidity_usd DESC LIMIT ?",
                (min_score, limit),
            )
            return [dict(r) for r in cursor.fetchall()]

    # 5 Digital Twins Event Logging
    def record_digital_twin_event(self, twin_type: str, event_type: str, payload: dict[str, Any]) -> str:
        eid = str(uuid.uuid4())
        record = {
            "id": eid,
            "twin_type": twin_type.upper(),
            "event_type": event_type.upper(),
            "payload_json": json.dumps(payload),
            "recorded_at": datetime.now(timezone.utc).isoformat(),
        }
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO digital_twin_events (id, twin_type, event_type, payload_json, recorded_at) VALUES (:id, :twin_type, :event_type, :payload_json, :recorded_at)",
                record,
            )
            conn.commit()
        return eid

    def get_digital_twin_events(self, twin_type: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if twin_type:
                cursor.execute("SELECT * FROM digital_twin_events WHERE twin_type = ? ORDER BY recorded_at DESC LIMIT ?", (twin_type.upper(), limit))
            else:
                cursor.execute("SELECT * FROM digital_twin_events ORDER BY recorded_at DESC LIMIT ?", (limit,))
            return [dict(r) for r in cursor.fetchall()]

    # Multi-Portfolio Account Helpers
    def get_all_paper_accounts(self) -> list[dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM paper_accounts ORDER BY id ASC")
            return [dict(r) for r in cursor.fetchall()]

    # Reward Ledger Operations (Anti-Sybil Qualified Actions)
    def record_reward_event(
        self,
        wallet: str,
        qualified_action: str,
        tx_hash: str | None = None,
        pol_reward: float = 10.0,
        sybil_score: float = 0.0,
        status: str = "CLAIMED",
    ) -> dict[str, Any]:
        eid = f"REW-{uuid.uuid4().hex[:12].upper()}"
        now_str = datetime.now(timezone.utc).isoformat()
        record = {
            "reward_event_id": eid,
            "wallet": wallet.lower(),
            "qualified_action": qualified_action.upper(),
            "tx_hash": tx_hash,
            "pol_reward": pol_reward,
            "sybil_score": sybil_score,
            "status": status.upper(),
            "claimed_at": now_str,
        }
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO rewards_ledger (reward_event_id, wallet, qualified_action, tx_hash, pol_reward, sybil_score, status, claimed_at)
                VALUES (:reward_event_id, :wallet, :qualified_action, :tx_hash, :pol_reward, :sybil_score, :status, :claimed_at)
                """,
                record,
            )
            conn.commit()
        return record

    def get_wallet_rewards(self, wallet: str) -> dict[str, Any]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM rewards_ledger WHERE wallet = ? ORDER BY claimed_at DESC",
                (wallet.lower(),),
            )
            rows = [dict(r) for r in cursor.fetchall()]

        total_pol = sum(r["pol_reward"] for r in rows if r["status"] == "CLAIMED")
        return {
            "wallet": wallet.lower(),
            "total_pol_reward": total_pol,
            "events_count": len(rows),
            "events": rows,
        }

    # Autotrade Session Authorization (Single Sign & 24/7 Autonomous Policy)
    def record_autotrade_authorization(
        self,
        wallet: str,
        mode: str = "PAPER",
        initial_capital_usdt: float = 1000.0,
        risk_profile: str = "BALANCED",
        max_risk_pct: float = 2.0,
        stop_ceiling_pct: float = -5.0,
        policy_hash: str | None = None,
    ) -> dict[str, Any]:
        aid = f"AUTH-{uuid.uuid4().hex[:10].upper()}"
        now_str = datetime.now(timezone.utc).isoformat()
        record = {
            "id": aid,
            "wallet": wallet.lower(),
            "mode": mode.upper(),
            "initial_capital_usdt": initial_capital_usdt,
            "risk_profile": risk_profile.upper(),
            "max_risk_pct": max_risk_pct,
            "stop_ceiling_pct": stop_ceiling_pct,
            "authorized_at": now_str,
            "is_active": 1,
            "policy_hash": policy_hash or f"0x{uuid.uuid4().hex}",
        }
        with self.get_connection() as conn:
            cursor = conn.cursor()
            # Deactivate previous active authorizations for this wallet
            cursor.execute("UPDATE autotrade_authorizations SET is_active = 0 WHERE wallet = ?", (wallet.lower(),))
            cursor.execute(
                """
                INSERT INTO autotrade_authorizations (id, wallet, mode, initial_capital_usdt, risk_profile, max_risk_pct, stop_ceiling_pct, authorized_at, is_active, policy_hash)
                VALUES (:id, :wallet, :mode, :initial_capital_usdt, :risk_profile, :max_risk_pct, :stop_ceiling_pct, :authorized_at, :is_active, :policy_hash)
                """,
                record,
            )
            conn.commit()
        return record

    def get_active_autotrade_authorization(self, wallet: str) -> dict[str, Any] | None:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM autotrade_authorizations WHERE wallet = ? AND is_active = 1 ORDER BY authorized_at DESC LIMIT 1",
                (wallet.lower(),),
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    # =========================================================================
    # Prop Challenge Operations ($10,000 Paper Demo & Progression)
    # =========================================================================

    def get_or_create_prop_challenge(self, wallet: str, mode: str = "BALANCED", tier: str = "100K") -> dict[str, Any]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM prop_challenges WHERE wallet = ? AND status = 'ACTIVE' ORDER BY created_at DESC LIMIT 1",
                (wallet.lower(),),
            )
            row = cursor.fetchone()
            if row:
                return dict(row)

            tier_key = tier.upper()
            tier_sizes = {"50K": (50000.0, 50.0), "100K": (100000.0, 100.0), "150K": (150000.0, 1500.0)}
            initial_equity, fee = tier_sizes.get(tier_key, (100000.0, 100.0))

            challenge_id = f"prop_{uuid.uuid4().hex[:12]}"
            now_iso = datetime.now(timezone.utc).isoformat()
            cursor.execute(
                """
                INSERT INTO prop_challenges (
                    id, wallet, tier, challenge_fee_usdt, mode, initial_equity, current_equity, peak_equity,
                    profit_target_pct, max_total_dd_pct, max_daily_dd_pct,
                    current_total_dd_pct, current_daily_dd_pct, cortex_violations,
                    min_trading_days, trading_days_count, status, trading_credit_usdt, withdrawable_profits_usdt,
                    prop_score, rank_position, created_at, updated_at
                ) VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?,
                    8.0, 8.0, 4.0,
                    0.0, 0.0, 0,
                    5, 1, 'ACTIVE', 0.0, 0.0,
                    85.0, 238, ?, ?
                )
                """,
                (challenge_id, wallet.lower(), tier_key, fee, mode, initial_equity, initial_equity, initial_equity, now_iso, now_iso),
            )
            conn.commit()
            cursor.execute("SELECT * FROM prop_challenges WHERE id = ?", (challenge_id,))
            return dict(cursor.fetchone())

    def update_prop_challenge(
        self,
        challenge_id: str,
        current_equity: float,
        current_daily_dd_pct: float,
        current_total_dd_pct: float,
        cortex_violations: int,
        trading_days_count: int,
        status: str,
        prop_score: float,
    ) -> dict[str, Any] | None:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT peak_equity FROM prop_challenges WHERE id = ?", (challenge_id,))
            row = cursor.fetchone()
            peak = max(current_equity, row["peak_equity"] if row else current_equity)
            now_iso = datetime.now(timezone.utc).isoformat()

            cursor.execute(
                """
                UPDATE prop_challenges
                SET current_equity = ?,
                    peak_equity = ?,
                    current_daily_dd_pct = ?,
                    current_total_dd_pct = ?,
                    cortex_violations = ?,
                    trading_days_count = ?,
                    status = ?,
                    prop_score = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    current_equity,
                    peak,
                    current_daily_dd_pct,
                    current_total_dd_pct,
                    cortex_violations,
                    trading_days_count,
                    status,
                    prop_score,
                    now_iso,
                    challenge_id,
                ),
            )
            conn.commit()
            cursor.execute("SELECT * FROM prop_challenges WHERE id = ?", (challenge_id,))
            res = cursor.fetchone()
            return dict(res) if res else None

    def get_prop_leaderboard(self, limit: int = 10) -> list[dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, wallet, mode, current_equity, 
                       ((current_equity - initial_equity) / initial_equity * 100.0) as return_pct,
                       current_total_dd_pct, cortex_violations, prop_score, rank_position, status
                FROM prop_challenges
                ORDER BY return_pct DESC, current_total_dd_pct ASC
                LIMIT ?
                """,
                (limit,),
            )
            return [dict(r) for r in cursor.fetchall()]

    # =========================================================================
    # Prop Option A: Payouts & TradeAid Credits (TAC) Wallet Operations
    # =========================================================================

    def record_prop_payout(
        self,
        challenge_id: str,
        wallet: str,
        amount_gross_usdt: float,
        amount_user_share_usdt: float,
        tx_hash: str | None = None,
    ) -> dict[str, Any]:
        payout_id = f"payout_{uuid.uuid4().hex[:12]}"
        now_iso = datetime.now(timezone.utc).isoformat()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO prop_payouts (
                    id, challenge_id, wallet, amount_gross_usdt, amount_user_share_usdt,
                    payout_share_pct, tx_hash, status, created_at
                ) VALUES (?, ?, ?, ?, ?, 80.0, ?, 'REQUESTED', ?)
                """,
                (payout_id, challenge_id, wallet.lower(), amount_gross_usdt, amount_user_share_usdt, tx_hash, now_iso),
            )
            conn.commit()
            cursor.execute("SELECT * FROM prop_payouts WHERE id = ?", (payout_id,))
            return dict(cursor.fetchone())

    def get_user_prop_payouts(self, wallet: str) -> list[dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM prop_payouts WHERE wallet = ? ORDER BY created_at DESC",
                (wallet.lower(),),
            )
            return [dict(r) for r in cursor.fetchall()]

    def award_tac_credits(
        self,
        wallet: str,
        delta_tac: float,
        reason: str,
        ref_challenge_id: str | None = None,
    ) -> float:
        """Award or deduct TradeAid Credits (TAC) in user's internal Second Chance wallet."""
        record_id = f"tac_{uuid.uuid4().hex[:12]}"
        now_iso = datetime.now(timezone.utc).isoformat()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT COALESCE(SUM(delta_tac), 0.0) as balance FROM tac_credits_ledger WHERE wallet = ?",
                (wallet.lower(),),
            )
            current_balance = float(cursor.fetchone()["balance"])
            new_balance = current_balance + delta_tac

            cursor.execute(
                """
                INSERT INTO tac_credits_ledger (
                    id, wallet, delta_tac, new_balance, reason, ref_challenge_id, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (record_id, wallet.lower(), delta_tac, new_balance, reason, ref_challenge_id, now_iso),
            )
            conn.commit()
            return new_balance

    def get_user_tac_balance(self, wallet: str) -> float:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT COALESCE(SUM(delta_tac), 0.0) as balance FROM tac_credits_ledger WHERE wallet = ?",
                (wallet.lower(),),
            )
            row = cursor.fetchone()
            return float(row["balance"]) if row else 0.0

    def get_tac_credits_ledger(self, wallet: str) -> list[dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM tac_credits_ledger WHERE wallet = ? ORDER BY created_at DESC",
                (wallet.lower(),),
            )
            return [dict(r) for r in cursor.fetchall()]

    # ---------------------------------------------------------
    # LEDGER 1: AUTOTRADE RUNS & DEDICATED REWARD POOL
    # ---------------------------------------------------------

    def create_autotrade_run(
        self,
        run_id: str,
        sequence_id: int,
        wallet: str,
        tx_hash_fee: str | None = None,
        fee_pol: float = 10.0,
        paper_starting_balance: float = 10000.0,
        max_duration_seconds: int = 180,
    ) -> dict[str, Any]:
        """Record the start of an Autotrade Run upon payment of 10 POL fee."""
        now = datetime.now(timezone.utc)
        expires_at = (now + timedelta(seconds=max_duration_seconds)).isoformat()
        now_iso = now.isoformat()

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO autotrade_runs (
                    id, sequence_id, wallet, tx_hash_fee, fee_pol,
                    paper_starting_balance, paper_final_pnl_usdt, paper_final_pnl_pct,
                    trades_count, cortex_violations, max_duration_seconds,
                    status, reward_pol, payout_status, started_at, expires_at
                ) VALUES (?, ?, ?, ?, ?, ?, 0.0, 0.0, 0, 0, ?, 'RUNNING', 2.0, 'PENDING', ?, ?)
                """,
                (
                    run_id,
                    sequence_id,
                    wallet.lower(),
                    tx_hash_fee,
                    fee_pol,
                    paper_starting_balance,
                    max_duration_seconds,
                    now_iso,
                    expires_at,
                ),
            )
            conn.commit()
            return self.get_autotrade_run(run_id) or {}

    def get_autotrade_run(self, run_id: str) -> dict[str, Any] | None:
        """Fetch details of a single Autotrade Run."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM autotrade_runs WHERE id = ?", (run_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def update_autotrade_run_progress(
        self,
        run_id: str,
        pnl_usdt: float,
        pnl_pct: float,
        trades_count: int,
        cortex_violations: int = 0,
    ) -> None:
        """Update live running metrics of an ongoing Autotrade Run."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE autotrade_runs
                SET paper_final_pnl_usdt = ?,
                    paper_final_pnl_pct = ?,
                    trades_count = ?,
                    cortex_violations = ?
                WHERE id = ? AND status = 'RUNNING'
                """,
                (pnl_usdt, pnl_pct, trades_count, cortex_violations, run_id),
            )
            conn.commit()

    def conclude_autotrade_run(
        self,
        run_id: str,
        won: bool,
        pnl_usdt: float,
        pnl_pct: float,
        trades_count: int,
        cortex_violations: int,
        payout_status: str,
        payout_tx_hash: str | None = None,
    ) -> dict[str, Any] | None:
        """Finalize an Autotrade Run as WON or LOST and record payout status."""
        status = "WON" if won else "LOST"
        now_iso = datetime.now(timezone.utc).isoformat()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE autotrade_runs
                SET status = ?,
                    paper_final_pnl_usdt = ?,
                    paper_final_pnl_pct = ?,
                    trades_count = ?,
                    cortex_violations = ?,
                    payout_status = ?,
                    payout_tx_hash = ?,
                    closed_at = ?
                WHERE id = ?
                """,
                (
                    status,
                    pnl_usdt,
                    pnl_pct,
                    trades_count,
                    cortex_violations,
                    payout_status,
                    payout_tx_hash,
                    now_iso,
                    run_id,
                ),
            )
            conn.commit()
            return self.get_autotrade_run(run_id)

    def get_user_autotrade_runs(self, wallet: str, limit: int = 20) -> list[dict[str, Any]]:
        """Retrieve recent Autotrade Runs for a specific wallet."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM autotrade_runs
                WHERE wallet = ?
                ORDER BY started_at DESC
                LIMIT ?
                """,
                (wallet.lower(), limit),
            )
            return [dict(r) for r in cursor.fetchall()]

    def get_reward_pool_status(self) -> dict[str, Any]:
        """Fetch current Reward Pool solvency and capacity."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM autotrade_reward_pool WHERE id = 1")
            row = cursor.fetchone()
            if not row:
                return {
                    "balance_pol": 500.0,
                    "total_funded_pol": 500.0,
                    "total_paid_pol": 0.0,
                    "payout_enabled": 0,
                    "is_solvent": True,
                    "backed_payouts": 250,
                }
            d = dict(row)
            d["is_solvent"] = d["balance_pol"] >= 2.0
            d["backed_payouts"] = int(d["balance_pol"] // 2.0)
            return d

    def fund_reward_pool(self, amount_pol: float) -> dict[str, Any]:
        """Add funding to the separate Reward Pool."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE autotrade_reward_pool
                SET balance_pol = balance_pol + ?,
                    total_funded_pol = total_funded_pol + ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = 1
                """,
                (amount_pol, amount_pol),
            )
            conn.commit()
            return self.get_reward_pool_status()

    def pay_reward_from_pool(self, amount_pol: float = 2.0) -> bool:
        """Deduct reward from pool if solvent."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT balance_pol FROM autotrade_reward_pool WHERE id = 1")
            row = cursor.fetchone()
            if not row or float(row["balance_pol"]) < amount_pol:
                return False
            cursor.execute(
                """
                UPDATE autotrade_reward_pool
                SET balance_pol = balance_pol - ?,
                    total_paid_pol = total_paid_pol + ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = 1
                """,
                (amount_pol, amount_pol),
            )
            conn.commit()
            return True

    def set_reward_payout_enabled(self, enabled: bool) -> None:
        """Toggle the legal/compliance feature-flag for real on-chain reward dispatch."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE autotrade_reward_pool SET payout_enabled = ?, updated_at = CURRENT_TIMESTAMP WHERE id = 1",
                (1 if enabled else 0,),
            )
            conn.commit()





