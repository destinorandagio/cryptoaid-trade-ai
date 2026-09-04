"""SQLite Schema Migrations for CryptoAID Trade AI."""
from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

logger = logging.getLogger(__name__)

MIGRATION_V1 = """
-- Schema Migrations Tracking
CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Users
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    username TEXT,
    role TEXT DEFAULT 'trader',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Paper Accounts
CREATE TABLE IF NOT EXISTS paper_accounts (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    currency TEXT DEFAULT 'USDC',
    initial_balance REAL NOT NULL,
    cash_balance REAL NOT NULL,
    equity REAL NOT NULL,
    realized_pnl REAL DEFAULT 0.0,
    peak_equity REAL NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(user_id) REFERENCES users(id)
);

-- Strategies
CREATE TABLE IF NOT EXISTS strategies (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    version TEXT NOT NULL,
    parameters_json TEXT,
    is_active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Signals
CREATE TABLE IF NOT EXISTS signals (
    id TEXT PRIMARY KEY,
    asset TEXT NOT NULL,
    signal TEXT NOT NULL,
    confidence REAL NOT NULL,
    expected_return REAL,
    expected_risk REAL,
    time_horizon TEXT,
    invalidation TEXT,
    evidence_json TEXT,
    status TEXT DEFAULT 'ACTIVE',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Orders
CREATE TABLE IF NOT EXISTS orders (
    order_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    account_id TEXT NOT NULL,
    asset TEXT NOT NULL,
    side TEXT NOT NULL,
    type TEXT NOT NULL,
    entry REAL NOT NULL,
    size REAL NOT NULL,
    sl REAL,
    tp REAL,
    trailing_distance REAL,
    fees REAL DEFAULT 0.0,
    simulated_slippage REAL DEFAULT 0.0,
    open_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    close_time TIMESTAMP,
    exit_price REAL,
    pnl REAL DEFAULT 0.0,
    pnl_percent REAL DEFAULT 0.0,
    status TEXT NOT NULL,
    strategy TEXT,
    confidence REAL,
    risk_score REAL,
    reason TEXT
);

-- Trades (Filled execution records)
CREATE TABLE IF NOT EXISTS trades (
    id TEXT PRIMARY KEY,
    order_id TEXT NOT NULL,
    asset TEXT NOT NULL,
    side TEXT NOT NULL,
    price REAL NOT NULL,
    size REAL NOT NULL,
    fees REAL NOT NULL,
    slippage REAL NOT NULL,
    executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(order_id) REFERENCES orders(order_id)
);

-- Positions (Active Open Holdings)
CREATE TABLE IF NOT EXISTS positions (
    id TEXT PRIMARY KEY,
    account_id TEXT NOT NULL,
    asset TEXT NOT NULL,
    side TEXT NOT NULL,
    entry_price REAL NOT NULL,
    current_price REAL NOT NULL,
    size REAL NOT NULL,
    notional REAL NOT NULL,
    sl REAL,
    tp REAL,
    trailing_sl REAL,
    unrealized_pnl REAL DEFAULT 0.0,
    unrealized_pnl_pct REAL DEFAULT 0.0,
    opened_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    order_id TEXT,
    FOREIGN KEY(order_id) REFERENCES orders(order_id)
);

-- Portfolio Snapshots
CREATE TABLE IF NOT EXISTS portfolio_snapshots (
    id TEXT PRIMARY KEY,
    account_id TEXT NOT NULL,
    total_equity REAL NOT NULL,
    cash_balance REAL NOT NULL,
    unrealized_pnl REAL NOT NULL,
    realized_pnl REAL NOT NULL,
    drawdown_pct REAL NOT NULL,
    positions_count INTEGER NOT NULL,
    snapshot_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Market Snapshots
CREATE TABLE IF NOT EXISTS market_snapshots (
    id TEXT PRIMARY KEY,
    symbol TEXT NOT NULL,
    price REAL NOT NULL,
    bid REAL,
    ask REAL,
    spread REAL,
    volume_24h REAL,
    change_24h_pct REAL,
    volatility_24h REAL,
    provider TEXT,
    snapshot_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Risk Decisions
CREATE TABLE IF NOT EXISTS risk_decisions (
    id TEXT PRIMARY KEY,
    asset TEXT NOT NULL,
    decision TEXT NOT NULL,
    composite_risk_score REAL NOT NULL,
    details_json TEXT,
    reasons_json TEXT,
    decided_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Agent Decisions
CREATE TABLE IF NOT EXISTS agent_decisions (
    id TEXT PRIMARY KEY,
    asset TEXT NOT NULL,
    agent_name TEXT NOT NULL,
    signal TEXT NOT NULL,
    confidence REAL NOT NULL,
    evidence_json TEXT,
    decided_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Performance Snapshots
CREATE TABLE IF NOT EXISTS performance_snapshots (
    id TEXT PRIMARY KEY,
    account_id TEXT NOT NULL,
    net_pnl REAL NOT NULL,
    win_rate REAL NOT NULL,
    profit_factor REAL NOT NULL,
    sharpe_ratio REAL NOT NULL,
    sortino_ratio REAL NOT NULL,
    max_drawdown REAL NOT NULL,
    total_trades INTEGER NOT NULL,
    calculated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Audit Events
CREATE TABLE IF NOT EXISTS audit_events (
    id TEXT PRIMARY KEY,
    event_type TEXT NOT NULL,
    severity TEXT NOT NULL,
    payload_json TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

MIGRATION_V2 = """
-- System State (Persistent engine state, kill switch, active regime)
CREATE TABLE IF NOT EXISTS system_state (
    key TEXT PRIMARY KEY,
    value_json TEXT NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Token Registry (Discovered/supported Polygon tokens and risk status)
CREATE TABLE IF NOT EXISTS token_registry (
    address TEXT PRIMARY KEY,
    symbol TEXT NOT NULL,
    name TEXT,
    decimals INTEGER NOT NULL,
    is_supported INTEGER DEFAULT 1,
    is_honeypot INTEGER DEFAULT 0,
    liquidity_usd REAL DEFAULT 0.0,
    volume_24h_usd REAL DEFAULT 0.0,
    risk_score REAL DEFAULT 0.0,
    last_verified TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Route Quotes (Audited DEX quotes across Uniswap V3, QuickSwap, etc.)
CREATE TABLE IF NOT EXISTS route_quotes (
    quote_id TEXT PRIMARY KEY,
    asset TEXT NOT NULL,
    dex TEXT NOT NULL,
    in_token TEXT NOT NULL,
    out_token TEXT NOT NULL,
    amount_in REAL NOT NULL,
    expected_out REAL NOT NULL,
    amount_out_min REAL NOT NULL,
    price_impact_pct REAL NOT NULL,
    estimated_gas_gwei REAL NOT NULL,
    estimated_gas_cost_usd REAL NOT NULL,
    net_edge_pct REAL NOT NULL,
    is_stale INTEGER DEFAULT 0,
    quoted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Strategy Decisions (Per-agent outputs: Scalp, Trend, Momentum, Breakout, MeanReversion)
CREATE TABLE IF NOT EXISTS strategy_decisions (
    id TEXT PRIMARY KEY,
    strategy_name TEXT NOT NULL,
    asset TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    signal TEXT NOT NULL,
    confidence REAL NOT NULL,
    expected_return REAL,
    expected_risk REAL,
    entry_zone_json TEXT,
    invalidation TEXT,
    evidence_json TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Meta Decisions (Aggregated consensus, active regime, and net edge calculation)
CREATE TABLE IF NOT EXISTS meta_decisions (
    id TEXT PRIMARY KEY,
    asset TEXT NOT NULL,
    regime TEXT NOT NULL,
    decision TEXT NOT NULL,
    confidence REAL NOT NULL,
    net_edge_pct REAL NOT NULL,
    gas_cost_usd REAL NOT NULL,
    dex_fee_pct REAL NOT NULL,
    slippage_pct REAL NOT NULL,
    price_impact_pct REAL NOT NULL,
    selected_strategies_json TEXT,
    evidence_json TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Transactions (On-chain Polygon transactions, tx hashes, gas used, simulation outcome)
CREATE TABLE IF NOT EXISTS transactions (
    tx_hash TEXT PRIMARY KEY,
    order_id TEXT,
    position_id TEXT,
    chain_id INTEGER DEFAULT 137,
    from_address TEXT NOT NULL,
    to_address TEXT NOT NULL,
    value_wei TEXT,
    data_hex TEXT,
    nonce INTEGER,
    gas_limit INTEGER,
    gas_price_gwei REAL,
    gas_used INTEGER,
    status TEXT NOT NULL, -- 'PENDING', 'CONFIRMED', 'FAILED', 'SIMULATED'
    revert_reason TEXT,
    simulation_passed INTEGER DEFAULT 1,
    submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    confirmed_at TIMESTAMP,
    FOREIGN KEY(order_id) REFERENCES orders(order_id)
);

-- Wallet Events (Signer balance changes, allowances, approvals, revokes)
CREATE TABLE IF NOT EXISTS wallet_events (
    id TEXT PRIMARY KEY,
    wallet_address TEXT NOT NULL,
    event_type TEXT NOT NULL, -- 'BALANCE_UPDATE', 'APPROVAL_GRANTED', 'APPROVAL_REVOKED', 'POLICY_BREACH'
    token_address TEXT,
    amount REAL,
    details_json TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

MIGRATION_V3 = """
-- Predictive Heart Forecasts & Calibration Ledger (Closure 1)
CREATE TABLE IF NOT EXISTS predictive_heart_forecasts (
    id TEXT PRIMARY KEY,
    asset TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    target_timestamp TIMESTAMP NOT NULL,
    now_price REAL NOT NULL,
    predicted_p50 REAL NOT NULL,
    predicted_p10 REAL NOT NULL,
    predicted_p90 REAL NOT NULL,
    direction TEXT NOT NULL, -- 'LONG', 'SHORT', 'NO_TRADE'
    expected_return_pct REAL NOT NULL,
    confidence_pct REAL NOT NULL,
    regime TEXT NOT NULL,
    models_evidence_json TEXT,
    actual_price REAL,
    error_pct REAL,
    direction_hit INTEGER, -- 1 if predicted direction matches sign(actual - now), 0 otherwise
    brier_score REAL,
    is_calibrated INTEGER DEFAULT 0,
    calibrated_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_forecasts_uncalibrated ON predictive_heart_forecasts (is_calibrated, target_timestamp);
CREATE INDEX IF NOT EXISTS idx_forecasts_asset ON predictive_heart_forecasts (asset, timeframe);
"""

MIGRATION_V4 = """
-- Strategy Switching Audit Trail
CREATE TABLE IF NOT EXISTS strategy_switches (
    id TEXT PRIMARY KEY,
    position_id TEXT NOT NULL,
    account_id TEXT NOT NULL,
    asset TEXT NOT NULL,
    from_strategy TEXT NOT NULL,
    to_strategy TEXT NOT NULL,
    reason TEXT NOT NULL,
    pnl_pct_at_switch REAL NOT NULL,
    entry_price REAL NOT NULL,
    current_price REAL NOT NULL,
    new_sl REAL,
    new_tp REAL,
    switched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_strat_switches_pos ON strategy_switches (position_id);
CREATE INDEX IF NOT EXISTS idx_strat_switches_acc ON strategy_switches (account_id);

-- Gem Hunter Radar & Lifecycle
CREATE TABLE IF NOT EXISTS gem_candidates (
    id TEXT PRIMARY KEY,
    token_address TEXT NOT NULL UNIQUE,
    symbol TEXT NOT NULL,
    name TEXT NOT NULL,
    score REAL NOT NULL,
    classification TEXT NOT NULL, -- 'WATCH', 'EMERGING', 'HIGH_POTENTIAL', 'EXTREME_SPECULATION', 'REJECT'
    stage TEXT NOT NULL DEFAULT 'DISCOVERED', -- 'DISCOVERED', 'WATCH', 'QUALIFIED', 'PAPER_ENTRY', 'MOMENTUM', 'TREND', 'EXITED'
    liquidity_usd REAL NOT NULL,
    volume_24h REAL NOT NULL,
    holder_count INTEGER NOT NULL,
    honeypot_safe INTEGER DEFAULT 1,
    metrics_json TEXT,
    discovered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_gem_score ON gem_candidates (score, classification);

-- 5 Interconnected Digital Twins Event Log
CREATE TABLE IF NOT EXISTS digital_twin_events (
    id TEXT PRIMARY KEY,
    twin_type TEXT NOT NULL, -- 'MARKET', 'PREDICTION', 'STRATEGY', 'POSITION', 'GEM'
    event_type TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_twin_type ON digital_twin_events (twin_type, recorded_at);

-- Initialize the 4 parallel paper accounts (1000 USDT each)
INSERT OR IGNORE INTO users (id, username, role) VALUES ('paper_master', 'TradeAID Paper Master', 'system');

INSERT OR IGNORE INTO paper_accounts (id, user_id, currency, initial_balance, cash_balance, equity, realized_pnl, peak_equity)
VALUES
    ('paper_safe', 'paper_master', 'USDT', 1000.0, 1000.0, 1000.0, 0.0, 1000.0),
    ('paper_balanced', 'paper_master', 'USDT', 1000.0, 1000.0, 1000.0, 0.0, 1000.0),
    ('paper_turbo', 'paper_master', 'USDT', 1000.0, 1000.0, 1000.0, 0.0, 1000.0),
    ('gem_paper_fund', 'paper_master', 'USDT', 1000.0, 1000.0, 1000.0, 0.0, 1000.0);
"""



MIGRATION_V5 = """
-- Experience Matrix Multidimensional Knowledge Base
CREATE TABLE IF NOT EXISTS experience_matrix (
    matrix_key TEXT PRIMARY KEY,
    asset TEXT NOT NULL,
    regime TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    strategy TEXT NOT NULL,
    prediction_model TEXT NOT NULL,
    sentiment_state TEXT NOT NULL,
    liquidity_state TEXT NOT NULL,
    volatility_state TEXT NOT NULL,
    expectancy REAL NOT NULL DEFAULT 0.0,
    max_drawdown REAL NOT NULL DEFAULT 0.0,
    win_rate REAL NOT NULL DEFAULT 0.0,
    profit_factor REAL NOT NULL DEFAULT 1.0,
    avg_net_costs REAL NOT NULL DEFAULT 0.0,
    sample_size INTEGER NOT NULL DEFAULT 0,
    confidence_score REAL NOT NULL DEFAULT 0.5,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_exp_regime_strat ON experience_matrix (regime, strategy);
CREATE INDEX IF NOT EXISTS idx_exp_asset_regime ON experience_matrix (asset, regime);

-- Strategy Tournament Champions & Challengers
CREATE TABLE IF NOT EXISTS champions_challengers (
    regime TEXT PRIMARY KEY,
    champion_strategy TEXT NOT NULL,
    champion_expectancy REAL NOT NULL DEFAULT 0.0,
    champion_sharpe REAL NOT NULL DEFAULT 1.0,
    challenger_strategies_json TEXT NOT NULL DEFAULT '[]',
    promoted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    history_json TEXT NOT NULL DEFAULT '[]'
);

-- Seed initial regime champions
INSERT OR IGNORE INTO champions_challengers (regime, champion_strategy, champion_expectancy, champion_sharpe, challenger_strategies_json)
VALUES
    ('TRENDING_BULL', 'MOMENTUM', 0.0125, 1.85, '["TREND", "BREAKOUT", "SCALP"]'),
    ('TRENDING_BEAR', 'TREND', 0.0095, 1.45, '["MOMENTUM", "BREAKOUT", "SCALP"]'),
    ('RANGING_LOW_VOL', 'MEAN_REVERSION', 0.0078, 1.62, '["SCALP", "MOMENTUM"]'),
    ('RANGING_HIGH_VOL', 'BREAKOUT', 0.0110, 1.40, '["SCALP", "MEAN_REVERSION"]'),
    ('HIGH_VOLATILITY_EXPANSION', 'SCALP', 0.0085, 1.35, '["BREAKOUT", "MOMENTUM"]'),
    ('UNKNOWN', 'SCALP', 0.0050, 1.10, '["MEAN_REVERSION"]');
"""

MIGRATION_V6 = """
-- Rewards Ledger (Anti-Sybil Qualified Actions)
CREATE TABLE IF NOT EXISTS rewards_ledger (
    reward_event_id TEXT PRIMARY KEY,
    wallet TEXT NOT NULL,
    qualified_action TEXT NOT NULL,
    tx_hash TEXT,
    pol_reward REAL NOT NULL DEFAULT 10.0,
    sybil_score REAL NOT NULL DEFAULT 0.0,
    status TEXT NOT NULL DEFAULT 'CLAIMED',
    claimed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_rewards_wallet ON rewards_ledger (wallet);
CREATE INDEX IF NOT EXISTS idx_rewards_action ON rewards_ledger (qualified_action);

-- Autotrade One-Time Session Authorizations
CREATE TABLE IF NOT EXISTS autotrade_authorizations (
    id TEXT PRIMARY KEY,
    wallet TEXT NOT NULL,
    mode TEXT NOT NULL DEFAULT 'PAPER',
    initial_capital_usdt REAL NOT NULL DEFAULT 1000.0,
    risk_profile TEXT NOT NULL DEFAULT 'BALANCED',
    max_risk_pct REAL NOT NULL DEFAULT 2.0,
    stop_ceiling_pct REAL NOT NULL DEFAULT -5.0,
    authorized_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active INTEGER DEFAULT 1,
    policy_hash TEXT
);

CREATE INDEX IF NOT EXISTS idx_autotrade_wallet ON autotrade_authorizations (wallet);
"""


MIGRATION_V7 = """
-- TradeAID Prop Challenge Engine (50K, 100K, 150K Multi-Tier & No-Loss Credit)
CREATE TABLE IF NOT EXISTS prop_challenges (
    id TEXT PRIMARY KEY,
    wallet TEXT NOT NULL,
    tier TEXT NOT NULL DEFAULT '100K',
    challenge_fee_usdt REAL NOT NULL DEFAULT 100.0,
    mode TEXT NOT NULL DEFAULT 'BALANCED',
    initial_equity REAL NOT NULL DEFAULT 100000.0,
    current_equity REAL NOT NULL DEFAULT 100000.0,
    peak_equity REAL NOT NULL DEFAULT 100000.0,
    profit_target_pct REAL NOT NULL DEFAULT 8.0,
    max_total_dd_pct REAL NOT NULL DEFAULT 8.0,
    max_daily_dd_pct REAL NOT NULL DEFAULT 4.0,
    current_total_dd_pct REAL NOT NULL DEFAULT 0.0,
    current_daily_dd_pct REAL NOT NULL DEFAULT 0.0,
    cortex_violations INTEGER NOT NULL DEFAULT 0,
    min_trading_days INTEGER NOT NULL DEFAULT 5,
    trading_days_count INTEGER NOT NULL DEFAULT 1,
    status TEXT NOT NULL DEFAULT 'ACTIVE',
    trading_credit_usdt REAL NOT NULL DEFAULT 0.0,
    withdrawable_profits_usdt REAL NOT NULL DEFAULT 0.0,
    prop_score REAL NOT NULL DEFAULT 85.0,
    rank_position INTEGER DEFAULT 238,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_prop_wallet ON prop_challenges (wallet);
CREATE INDEX IF NOT EXISTS idx_prop_status ON prop_challenges (status);
"""


def apply_migrations(db_path: Path | str) -> None:
    """Run migrations to ensure all database tables are up to date."""
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    try:
        cursor.execute("CREATE TABLE IF NOT EXISTS schema_migrations (version INTEGER PRIMARY KEY, applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
        cursor.execute("SELECT MAX(version) FROM schema_migrations")
        res = cursor.fetchone()
        current_version = res[0] if (res and res[0] is not None) else 0

        if current_version < 1:
            logger.info("Applying database migration V1...")
            cursor.executescript(MIGRATION_V1)
            cursor.execute("INSERT INTO schema_migrations (version) VALUES (1)")
            conn.commit()
            logger.info("Database migration V1 applied successfully.")

        if current_version < 2:
            logger.info("Applying database migration V2 (Trade AI Polygon Ecosystem)...")
            cursor.executescript(MIGRATION_V2)
            cursor.execute("INSERT INTO schema_migrations (version) VALUES (2)")
            conn.commit()
            logger.info("Database migration V2 applied successfully.")

        if current_version < 3:
            logger.info("Applying database migration V3 (Predictive Heart Forecasts & Calibration)...")
            cursor.executescript(MIGRATION_V3)
            cursor.execute("INSERT INTO schema_migrations (version) VALUES (3)")
            conn.commit()
            logger.info("Database migration V3 applied successfully.")

        if current_version < 4:
            logger.info("Applying database migration V4 (Strategy Switches, Gem Hunter & 4 Paper Funds)...")
            cursor.executescript(MIGRATION_V4)
            cursor.execute("INSERT INTO schema_migrations (version) VALUES (4)")
            conn.commit()
            logger.info("Database migration V4 applied successfully.")

        if current_version < 5:
            logger.info("Applying database migration V5 (Experience Matrix & Champions/Challengers)...")
            cursor.executescript(MIGRATION_V5)
            cursor.execute("INSERT INTO schema_migrations (version) VALUES (5)")
            conn.commit()
            logger.info("Database migration V5 applied successfully.")

        if current_version < 6:
            logger.info("Applying database migration V6 (Rewards Ledger & Autotrade Authorizations)...")
            cursor.executescript(MIGRATION_V6)
            cursor.execute("INSERT INTO schema_migrations (version) VALUES (6)")
            conn.commit()
            logger.info("Database migration V6 applied successfully.")

        if current_version < 7:
            logger.info("Applying database migration V7 (Prop Challenge Engine $10k Paper)...")
            cursor.executescript(MIGRATION_V7)
            cursor.execute("INSERT INTO schema_migrations (version) VALUES (7)")
            conn.commit()
            logger.info("Database migration V7 applied successfully.")
    finally:
        conn.close()




