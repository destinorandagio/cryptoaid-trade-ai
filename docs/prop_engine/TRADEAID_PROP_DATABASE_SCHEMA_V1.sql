-- ============================================================
-- TRADEAID PROP DATABASE SCHEMA — V1.0
-- Target: PostgreSQL 15+
-- Dual Identity: Web3 WalletConnect (Polygon) + SIC-ID Federation
-- 3-Ledger Architecture: Prop Equity (Paper) / Trading Credits (TAC) / Withdrawable Rewards
-- ============================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- ============================================================
-- 1. USERS & DUAL AUTHENTICATION
-- ============================================================

-- Utenti della piattaforma (Dual Auth: Web3 Polygon + Canonical SIC-ID)
CREATE TABLE IF NOT EXISTS users (
    user_id             UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    wallet_address      VARCHAR(42) UNIQUE, -- Polygon Address (0x...), nullable if SIC-ID only initially
    sic_id              VARCHAR(20) UNIQUE, -- Format: SIC-ID-XXXXXXXXXXXX (12 Crockford/Base32 chars)
    email               VARCHAR(255),
    telegram_id         BIGINT,
    auth_method         VARCHAR(20) NOT NULL DEFAULT 'WALLET', -- WALLET, SIC_ID, HYBRID
    kyc_status          VARCHAR(20) NOT NULL DEFAULT 'PENDING', -- PENDING, VERIFIED, REJECTED
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_auth_identity CHECK (wallet_address IS NOT NULL OR sic_id IS NOT NULL),
    CONSTRAINT chk_sic_id_format CHECK (sic_id IS NULL OR sic_id ~ '^SIC-ID-[A-Z0-9]{12}$')
);

CREATE INDEX IF NOT EXISTS idx_users_wallet ON users(wallet_address);
CREATE INDEX IF NOT EXISTS idx_users_sic_id ON users(sic_id);

-- Profilo finanziario interno dell'utente (Cache aggregata dai 3 Ledgers)
CREATE TABLE IF NOT EXISTS user_financial_profile (
    user_id                     UUID PRIMARY KEY REFERENCES users(user_id) ON DELETE CASCADE,
    trading_credit_balance      DECIMAL(15, 2) NOT NULL DEFAULT 0.00, -- Credito non prelevabile (TAC)
    withdrawable_reward_balance DECIMAL(15, 2) NOT NULL DEFAULT 0.00, -- Profitti reali maturati prelevabili
    total_fees_paid             DECIMAL(15, 2) NOT NULL DEFAULT 0.00,
    last_challenge_tier         VARCHAR(50),
    status                      VARCHAR(20) NOT NULL DEFAULT 'ACTIVE', -- ACTIVE, BANNED, WITHDRAWAL_PENDING
    updated_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================
-- 2. CHALLENGE TIERS & CONFIGURATION
-- ============================================================

CREATE TABLE IF NOT EXISTS challenge_tiers (
    tier_id             SERIAL PRIMARY KEY,
    name                VARCHAR(50) UNIQUE NOT NULL, -- STARTER, PRO, ELITE, BLACK
    fee_usdt            DECIMAL(10, 2) NOT NULL,
    nominal_capital     DECIMAL(15, 2) NOT NULL, -- 10k, 50k, 100k, 150k
    phase1_target_pct   DECIMAL(5, 2) NOT NULL DEFAULT 8.00, -- 8.00%
    phase2_target_pct   DECIMAL(5, 2) NOT NULL DEFAULT 5.00, -- 5.00%
    max_daily_dd_pct    DECIMAL(5, 2) NOT NULL DEFAULT 5.00, -- 5.00%
    max_total_dd_pct    DECIMAL(5, 2) NOT NULL DEFAULT 10.00, -- 10.00%
    min_trading_days    INT NOT NULL DEFAULT 5, -- 5 days
    is_active           BOOLEAN NOT NULL DEFAULT TRUE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Seed Canonical Tiers
INSERT INTO challenge_tiers (tier_id, name, fee_usdt, nominal_capital, phase1_target_pct, phase2_target_pct, max_daily_dd_pct, max_total_dd_pct, min_trading_days, is_active)
VALUES
    (1, 'STARTER', 50.00, 10000.00, 8.00, 5.00, 5.00, 10.00, 5, TRUE),
    (2, 'PRO', 100.00, 50000.00, 8.00, 5.00, 5.00, 10.00, 5, TRUE),
    (3, 'ELITE', 500.00, 100000.00, 8.00, 5.00, 5.00, 10.00, 5, TRUE),
    (4, 'BLACK', 1500.00, 150000.00, 8.00, 5.00, 5.00, 10.00, 5, TRUE)
ON CONFLICT (tier_id) DO UPDATE SET
    name = EXCLUDED.name,
    fee_usdt = EXCLUDED.fee_usdt,
    nominal_capital = EXCLUDED.nominal_capital,
    phase1_target_pct = EXCLUDED.phase1_target_pct,
    phase2_target_pct = EXCLUDED.phase2_target_pct,
    max_daily_dd_pct = EXCLUDED.max_daily_dd_pct,
    max_total_dd_pct = EXCLUDED.max_total_dd_pct,
    min_trading_days = EXCLUDED.min_trading_days,
    is_active = EXCLUDED.is_active;

-- ============================================================
-- 3. CHALLENGE INSTANCES & SNAPSHOTS (LEDGER 1: PAPER / PROP EQUITY)
-- ============================================================

CREATE TABLE IF NOT EXISTS challenges (
    challenge_id        UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id             UUID NOT NULL REFERENCES users(user_id) ON DELETE RESTRICT,
    tier_id             INT NOT NULL REFERENCES challenge_tiers(tier_id) ON DELETE RESTRICT,
    
    -- Stato Corrente
    status              VARCHAR(30) NOT NULL DEFAULT 'PHASE_1_QUALIFICATION', 
    -- PHASE_1_QUALIFICATION, PHASE_2_VERIFICATION, QUALIFIED, FAILED, CANCELLED
    
    -- Dati Finanziari Virtuali (Ledger 1: Paper Equity)
    starting_balance    DECIMAL(15, 2) NOT NULL,
    current_balance     DECIMAL(15, 2) NOT NULL,
    high_water_mark     DECIMAL(15, 2) NOT NULL, -- Per calcolo Max Drawdown Totale
    
    -- Tracking Obiettivi & Fasi
    phase1_start_date   TIMESTAMPTZ DEFAULT NOW(),
    phase1_end_date     TIMESTAMPTZ, -- Null se ancora attiva
    phase2_start_date   TIMESTAMPTZ,
    phase2_end_date     TIMESTAMPTZ,
    
    -- Violazioni
    violation_type      VARCHAR(50), -- DAILY_DD, TOTAL_DD, MIN_DAYS_NOT_MET, CORTEX_RISK
    violated_at         TIMESTAMPTZ,
    
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_challenges_user ON challenges(user_id);
CREATE INDEX IF NOT EXISTS idx_challenges_status ON challenges(status);

-- Snapshot Giornaliera a Mezzanotte UTC per Calcolo Daily Drawdown
CREATE TABLE IF NOT EXISTS challenge_daily_snapshots (
    snapshot_id          BIGSERIAL PRIMARY KEY,
    challenge_id         UUID NOT NULL REFERENCES challenges(challenge_id) ON DELETE CASCADE,
    snapshot_date        DATE NOT NULL,
    start_of_day_balance DECIMAL(15, 2) NOT NULL,
    end_of_day_balance   DECIMAL(15, 2) NOT NULL,
    daily_pnl            DECIMAL(15, 2) NOT NULL,
    daily_dd_pct         DECIMAL(5, 2) NOT NULL,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(challenge_id, snapshot_date)
);

CREATE INDEX IF NOT EXISTS idx_snapshots_challenge ON challenge_daily_snapshots(challenge_id);
CREATE INDEX IF NOT EXISTS idx_snapshots_date ON challenge_daily_snapshots(snapshot_date);

-- ============================================================
-- 4. TRADING ACTIVITY (Paper Execution Log)
-- ============================================================

CREATE TABLE IF NOT EXISTS challenge_trades (
    trade_id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    challenge_id        UUID NOT NULL REFERENCES challenges(challenge_id) ON DELETE CASCADE,
    
    asset_canonical_id  TEXT NOT NULL, -- CA-L1-0001 (BTC), CA-L1-0002 (ETH), etc.
    direction           VARCHAR(4) NOT NULL CHECK (direction IN ('LONG', 'SHORT')),
    entry_price         DECIMAL(18, 8) NOT NULL,
    exit_price          DECIMAL(18, 8),
    quantity            DECIMAL(18, 8) NOT NULL,
    leverage_used       INT NOT NULL DEFAULT 1,
    
    pnl_usdt            DECIMAL(15, 2),
    pnl_pct             DECIMAL(5, 2),
    
    opened_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    closed_at           TIMESTAMPTZ,
    
    strategy_id         VARCHAR(50), -- TREND_FOLLOWING_V3, CORTEX_PREDICTIVE
    ai_confidence       DECIMAL(5, 2) -- 0.85
);

CREATE INDEX IF NOT EXISTS idx_trades_challenge ON challenge_trades(challenge_id);
CREATE INDEX IF NOT EXISTS idx_trades_opened_at ON challenge_trades(opened_at);

-- ============================================================
-- 5. LEDGER SYSTEM (Contabilità Separata Immutabile)
-- ============================================================

-- LEDGER 2: Movimenti dei Trading Credits (TAC non prelevabili, 1 TAC = 1 USDT Margin)
CREATE TABLE IF NOT EXISTS ledger_trading_credits (
    transaction_id      BIGSERIAL PRIMARY KEY,
    user_id             UUID NOT NULL REFERENCES users(user_id) ON DELETE RESTRICT,
    challenge_id        UUID REFERENCES challenges(challenge_id) ON DELETE SET NULL,
    
    amount              DECIMAL(15, 2) NOT NULL,
    type                VARCHAR(30) NOT NULL, -- CONVERSION_FROM_FEE, PROFIT_ACCRUAL, USAGE_FEE, RETRY_DISCOUNT
    balance_after       DECIMAL(15, 2) NOT NULL,
    description         TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_tac_ledger_user ON ledger_trading_credits(user_id);

-- LEDGER 3: Movimenti dei Withdrawable Rewards (Reali / Payout da Reward Pool)
CREATE TABLE IF NOT EXISTS ledger_withdrawable_rewards (
    transaction_id      BIGSERIAL PRIMARY KEY,
    user_id             UUID NOT NULL REFERENCES users(user_id) ON DELETE RESTRICT,
    
    amount              DECIMAL(15, 2) NOT NULL,
    type                VARCHAR(30) NOT NULL, -- REWARD_POOL_PAYOUT, REFERRAL_BONUS, CREDIT_MODE_PROFIT
    status              VARCHAR(20) NOT NULL DEFAULT 'LOCKED', -- LOCKED, UNLOCKED, WITHDRAWN
    
    locked_until        TIMESTAMPTZ, -- Periodo di vesting o verifica conformità
    withdrawn_at        TIMESTAMPTZ,
    tx_hash             VARCHAR(66), -- Hash transazione reale Polygon (0x...)
    
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_rewards_ledger_user ON ledger_withdrawable_rewards(user_id);
CREATE INDEX IF NOT EXISTS idx_rewards_ledger_status ON ledger_withdrawable_rewards(status);

-- ============================================================
-- 6. REWARD POOL & LEADERBOARD (Budget Allocato & Anti-Ghost Debt)
-- ============================================================

-- Configurazione del Reward Pool mensile garantito
CREATE TABLE IF NOT EXISTS reward_pools (
    pool_id             SERIAL PRIMARY KEY,
    month               INT NOT NULL CHECK (month BETWEEN 1 AND 12),
    year                INT NOT NULL CHECK (year >= 2024),
    total_budget_usdt   DECIMAL(15, 2) NOT NULL,
    distributed_usdt    DECIMAL(15, 2) NOT NULL DEFAULT 0.00,
    status              VARCHAR(20) NOT NULL DEFAULT 'OPEN', -- OPEN, CALCULATING, CLOSED
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(month, year)
);

-- Classifica mensile per assegnazione premi sostenibili
CREATE TABLE IF NOT EXISTS monthly_leaderboard (
    leaderboard_id      BIGSERIAL PRIMARY KEY,
    user_id             UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    challenge_id        UUID REFERENCES challenges(challenge_id) ON DELETE SET NULL,
    pool_id             INT NOT NULL REFERENCES reward_pools(pool_id) ON DELETE CASCADE,
    
    total_return_pct    DECIMAL(5, 2) NOT NULL,
    consistency_score   DECIMAL(5, 2) NOT NULL, -- Basato su Sharpe / DD / Regole Istituzionali
    reward_amount       DECIMAL(15, 2) NOT NULL DEFAULT 0.00,
    
    rank                INT NOT NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(user_id, pool_id)
);

CREATE INDEX IF NOT EXISTS idx_leaderboard_pool_rank ON monthly_leaderboard(pool_id, rank);
