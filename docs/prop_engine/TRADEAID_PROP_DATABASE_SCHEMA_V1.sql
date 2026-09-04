-- =============================================================================
-- TRADEAID PROP & AUTOTRADE DATABASE SCHEMA — V1.1 (POSTGRESQL 15+)
-- Enterprise Multi-Ledger, Event-Driven, Idempotent Engine
-- =============================================================================

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- =============================================================================
-- 1. USERS & FEDERATED IDENTITY (DUAL AUTH: WALLET + SIC-ID)
-- =============================================================================

CREATE TABLE IF NOT EXISTS users (
    user_id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    wallet_address      VARCHAR(42) UNIQUE, -- Polygon Address 0x... (nullable se registrato via SIC-ID)
    sic_id              VARCHAR(20) UNIQUE, -- Protocollo Federato 81+: SIC-ID-XXXXXXXXXXXX (12 chars Crockford Base32)
    auth_method         VARCHAR(20) NOT NULL DEFAULT 'WALLET', -- WALLET, SIC_ID, HYBRID
    email               VARCHAR(255),
    telegram_id         BIGINT,
    kyc_status          VARCHAR(20) NOT NULL DEFAULT 'PENDING', -- PENDING, VERIFIED, REJECTED
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_auth_identity CHECK (wallet_address IS NOT NULL OR sic_id IS NOT NULL),
    CONSTRAINT chk_sic_id_format CHECK (sic_id IS NULL OR sic_id ~ '^SIC-ID-[A-Z0-9]{12}$')
);

-- Cache di sola lettura dei saldi (Fonte di verità: append-only ledgers)
CREATE TABLE IF NOT EXISTS user_financial_profile (
    user_id                     UUID PRIMARY KEY REFERENCES users(user_id) ON DELETE CASCADE,
    trading_credit_balance      NUMERIC(18, 4) NOT NULL DEFAULT 0.0000, -- Credito non prelevabile (1 TAC = $1 USDT Margin)
    withdrawable_reward_balance NUMERIC(18, 4) NOT NULL DEFAULT 0.0000, -- Reward reali maturati da Pool certificato
    total_fees_paid             NUMERIC(18, 4) NOT NULL DEFAULT 0.0000,
    last_challenge_tier         VARCHAR(20),
    status                      VARCHAR(20) NOT NULL DEFAULT 'ACTIVE', -- ACTIVE, BANNED, WITHDRAWAL_PENDING
    updated_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- =============================================================================
-- 2. ON-CHAIN EVENT INGESTION & IDEMPOTENCY
-- =============================================================================

CREATE TABLE IF NOT EXISTS onchain_events (
    event_id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    chain_id            INTEGER NOT NULL DEFAULT 137, -- 137 = Polygon Mainnet
    tx_hash             VARCHAR(66) NOT NULL,
    log_index           INTEGER NOT NULL DEFAULT 0,
    block_number        BIGINT NOT NULL,
    contract_address    VARCHAR(42) NOT NULL,
    event_name          VARCHAR(100) NOT NULL, -- e.g. AutotradeActivated, ChallengeFeePaid, PayoutClaimed
    payload_json        JSONB NOT NULL,
    processed_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    status              VARCHAR(20) NOT NULL DEFAULT 'PROCESSED', -- PENDING, PROCESSED, FAILED
    UNIQUE(chain_id, tx_hash, log_index)
);

CREATE INDEX IF NOT EXISTS idx_onchain_events_tx ON onchain_events(tx_hash);

-- =============================================================================
-- 3. AUTOTRADE ENGINE (10 POL → 1 RUN → 2 POL REWARD MODEL)
-- =============================================================================

CREATE TABLE IF NOT EXISTS autotrade_runs (
    run_id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id                 UUID NOT NULL REFERENCES users(user_id),
    wallet                  VARCHAR(42) NOT NULL,
    activation_tx_hash      VARCHAR(66) UNIQUE NOT NULL,
    activation_amount_atomic NUMERIC(78, 0) NOT NULL, -- 10 * 10^18 wei (10 POL)
    decimals                INTEGER NOT NULL DEFAULT 18,
    paper_start_balance     NUMERIC(18, 2) NOT NULL DEFAULT 10000.00, -- 10,000 USDT PAPER
    started_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    closed_at               TIMESTAMPTZ,
    strategy_initial        VARCHAR(50) NOT NULL DEFAULT 'BALANCED',
    strategy_final          VARCHAR(50),
    gross_pnl               NUMERIC(18, 4) DEFAULT 0.0000,
    execution_costs         NUMERIC(18, 4) DEFAULT 0.0000, -- Gas stimato + DEX fees + Slippage
    net_pnl                 NUMERIC(18, 4) DEFAULT 0.0000,
    result                  VARCHAR(20) NOT NULL DEFAULT 'RUNNING', -- RUNNING, WIN, LOSS, VOID
    reward_eligible         BOOLEAN NOT NULL DEFAULT FALSE,
    reward_amount_atomic    NUMERIC(78, 0) NOT NULL DEFAULT 0, -- 2 * 10^18 wei (2 POL) se WIN
    reward_status           VARCHAR(30) NOT NULL DEFAULT 'NONE', -- NONE, RESERVED, PAID, RELEASED_UNEARNED
    idempotency_key         VARCHAR(128) UNIQUE NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_autotrade_user ON autotrade_runs(user_id, started_at);

-- =============================================================================
-- 4. REWARD RESERVATIONS & POOL ALLOCATION
-- =============================================================================

CREATE TABLE IF NOT EXISTS reward_pools (
    pool_id             SERIAL PRIMARY KEY,
    month               INT NOT NULL,
    year                INT NOT NULL,
    total_budget_usdt   NUMERIC(18, 4) NOT NULL,
    distributed_usdt    NUMERIC(18, 4) NOT NULL DEFAULT 0.0000,
    reserved_usdt       NUMERIC(18, 4) NOT NULL DEFAULT 0.0000,
    status              VARCHAR(20) NOT NULL DEFAULT 'OPEN', -- OPEN, CALCULATING, CLOSED
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(month, year)
);

CREATE TABLE IF NOT EXISTS reward_reservations (
    reservation_id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pool_id             INTEGER NOT NULL REFERENCES reward_pools(pool_id),
    run_id              UUID REFERENCES autotrade_runs(run_id),
    challenge_id        UUID, -- Referenza polimorfica se legata a Prop
    amount_atomic       NUMERIC(78, 0) NOT NULL, -- es. 2 * 10^18 wei (2 POL)
    decimals            INTEGER NOT NULL DEFAULT 18,
    currency            VARCHAR(10) NOT NULL DEFAULT 'POL',
    status              VARCHAR(20) NOT NULL DEFAULT 'RESERVED', -- RESERVED, COMMITTED, RELEASED
    reserved_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    settled_at          TIMESTAMPTZ,
    idempotency_key     VARCHAR(128) UNIQUE NOT NULL
);

-- =============================================================================
-- 5. CHALLENGE TIERS & INSTANCES (PROP ENGINE)
-- =============================================================================

CREATE TABLE IF NOT EXISTS challenge_tiers (
    tier_id             SERIAL PRIMARY KEY,
    name                VARCHAR(50) NOT NULL UNIQUE, -- STARTER, PRO, ELITE, BLACK
    fee_usdt            NUMERIC(15, 2) NOT NULL,
    nominal_capital     NUMERIC(15, 2) NOT NULL, -- 10k, 50k, 100k, 150k
    phase1_target_pct   NUMERIC(5, 2) NOT NULL DEFAULT 8.00,
    phase2_target_pct   NUMERIC(5, 2) NOT NULL DEFAULT 5.00,
    max_daily_dd_pct    NUMERIC(5, 2) NOT NULL DEFAULT 5.00,
    max_total_dd_pct    NUMERIC(5, 2) NOT NULL DEFAULT 10.00,
    min_trading_days    INTEGER NOT NULL DEFAULT 5,
    is_active           BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS challenges (
    challenge_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID NOT NULL REFERENCES users(user_id),
    tier_id             INTEGER NOT NULL REFERENCES challenge_tiers(tier_id),
    status              VARCHAR(30) NOT NULL DEFAULT 'PHASE_1_QUALIFICATION',
    -- PHASE_1_QUALIFICATION, PHASE_2_VERIFICATION, QUALIFIED, FAILED, CANCELLED
    starting_balance    NUMERIC(15, 2) NOT NULL,
    current_balance     NUMERIC(15, 2) NOT NULL,
    high_water_mark     NUMERIC(15, 2) NOT NULL,
    phase1_start_date   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    phase1_end_date     TIMESTAMPTZ,
    phase2_start_date   TIMESTAMPTZ,
    violation_type      VARCHAR(50), -- DAILY_DD, TOTAL_DD, CORTEX_VETO
    violated_at         TIMESTAMPTZ,
    idempotency_key     VARCHAR(128) UNIQUE NOT NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS challenge_daily_snapshots (
    snapshot_id         BIGSERIAL PRIMARY KEY,
    challenge_id        UUID NOT NULL REFERENCES challenges(challenge_id) ON DELETE CASCADE,
    snapshot_date       DATE NOT NULL,
    start_of_day_balance NUMERIC(15, 2) NOT NULL,
    end_of_day_balance   NUMERIC(15, 2) NOT NULL,
    daily_pnl           NUMERIC(15, 2) NOT NULL,
    daily_dd_pct        NUMERIC(5, 2) NOT NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(challenge_id, snapshot_date)
);

-- =============================================================================
-- 6. PREDICTIVE HEART & CORTEX AUDIT TRAIL
-- (WHITE → RED → DECISION → TRADE → ACTUAL → LEARNING)
-- =============================================================================

CREATE TABLE IF NOT EXISTS market_observations (
    observation_id      BIGSERIAL PRIMARY KEY,
    asset               VARCHAR(30) NOT NULL,
    price               NUMERIC(18, 8) NOT NULL,
    bid                 NUMERIC(18, 8),
    ask                 NUMERIC(18, 8),
    spread              NUMERIC(18, 8),
    volume_24h          NUMERIC(24, 4),
    volatility_24h      NUMERIC(10, 6),
    raw_features_json   JSONB,
    observed_at         TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS forecasts (
    forecast_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    asset               VARCHAR(30) NOT NULL,
    timeframe           VARCHAR(20) NOT NULL, -- 1s, 1m, 5m, 1h
    direction           VARCHAR(10) NOT NULL, -- UP, DOWN, NEUTRAL
    confidence          NUMERIC(5, 4) NOT NULL,
    expected_return     NUMERIC(8, 4),
    expected_risk       NUMERIC(8, 4),
    brier_score         NUMERIC(6, 4),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS forecast_paths (
    path_id             BIGSERIAL PRIMARY KEY,
    forecast_id         UUID NOT NULL REFERENCES forecasts(forecast_id) ON DELETE CASCADE,
    step_index          INTEGER NOT NULL,
    predicted_price     NUMERIC(18, 8) NOT NULL,
    upper_bound         NUMERIC(18, 8),
    lower_bound         NUMERIC(18, 8)
);

CREATE TABLE IF NOT EXISTS forecast_evaluations (
    eval_id             BIGSERIAL PRIMARY KEY,
    forecast_id         UUID NOT NULL REFERENCES forecasts(forecast_id) ON DELETE CASCADE,
    actual_price        NUMERIC(18, 8) NOT NULL,
    actual_return       NUMERIC(8, 4) NOT NULL,
    direction_hit       INTEGER NOT NULL, -- 1 if hit, 0 if missed
    error_pct           NUMERIC(8, 4) NOT NULL,
    brier_score         NUMERIC(6, 4) NOT NULL,
    evaluated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS regime_decisions (
    regime_id           BIGSERIAL PRIMARY KEY,
    asset               VARCHAR(30) NOT NULL,
    regime_type         VARCHAR(40) NOT NULL, -- LOW_VOLATILITY, HIGH_VOLATILITY, TRENDING, CHOPPY
    transition_prob     NUMERIC(5, 4),
    features_json       JSONB,
    decided_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS cortex_decisions (
    decision_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    asset               VARCHAR(30) NOT NULL,
    forecast_id         UUID REFERENCES forecasts(forecast_id),
    regime_id           BIGINT REFERENCES regime_decisions(regime_id),
    composite_risk_score NUMERIC(5, 2) NOT NULL,
    passed              BOOLEAN NOT NULL,
    final_decision      VARCHAR(30) NOT NULL, -- APPROVED, VETOED, RESIZED
    rejection_reasons   JSONB,
    max_allowed_leverage NUMERIC(4, 2) DEFAULT 1.0,
    decided_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS strategy_transitions (
    transition_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    context_id          VARCHAR(64) NOT NULL, -- run_id o challenge_id
    asset               VARCHAR(30) NOT NULL,
    from_strategy       VARCHAR(50) NOT NULL,
    to_strategy         VARCHAR(50) NOT NULL,
    reason              TEXT NOT NULL,
    pnl_pct_at_switch   NUMERIC(8, 4) NOT NULL,
    entry_price         NUMERIC(18, 8) NOT NULL,
    current_price       NUMERIC(18, 8) NOT NULL,
    switched_at         TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- =============================================================================
-- 7. EXECUTION TRADES WITH COMPLETE EXECUTION ECONOMICS
-- =============================================================================

CREATE TABLE IF NOT EXISTS challenge_trades (
    trade_id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    challenge_id        UUID REFERENCES challenges(challenge_id) ON DELETE CASCADE,
    run_id              UUID REFERENCES autotrade_runs(run_id) ON DELETE CASCADE,
    
    asset_canonical_id  VARCHAR(50) NOT NULL,
    direction           VARCHAR(10) NOT NULL, -- LONG, SHORT
    
    -- Execution Economics Reali vs Simulate
    quoted_price        NUMERIC(18, 8) NOT NULL,
    simulated_fill_price NUMERIC(18, 8) NOT NULL,
    exit_price          NUMERIC(18, 8),
    quantity            NUMERIC(18, 8) NOT NULL,
    leverage_used       INTEGER NOT NULL DEFAULT 1,
    
    gas_usdt            NUMERIC(15, 4) NOT NULL DEFAULT 0.0000,
    dex_fee_usdt        NUMERIC(15, 4) NOT NULL DEFAULT 0.0000,
    slippage_bps        INTEGER NOT NULL DEFAULT 0,
    price_impact_bps    INTEGER NOT NULL DEFAULT 0,
    
    gross_pnl_usdt      NUMERIC(15, 2),
    net_pnl_usdt        NUMERIC(15, 2),
    pnl_pct             NUMERIC(5, 2),
    
    opened_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    closed_at           TIMESTAMPTZ,
    
    strategy_id         VARCHAR(50) NOT NULL,
    entry_forecast_id   UUID REFERENCES forecasts(forecast_id),
    cortex_decision_id  UUID REFERENCES cortex_decisions(decision_id),
    strategy_transition_count INTEGER NOT NULL DEFAULT 0,
    ai_confidence       NUMERIC(5, 2)
);

-- =============================================================================
-- 8. AUDITABLE LEDGER SYSTEM (STRICT SEPARATION OF THE 4 MONIES)
-- =============================================================================

-- Ledger 2: Trading Credits TAC (Crediti di margine interni, non prelevabili)
CREATE TABLE IF NOT EXISTS ledger_trading_credits (
    transaction_id      BIGSERIAL PRIMARY KEY,
    user_id             UUID NOT NULL REFERENCES users(user_id),
    challenge_id        UUID REFERENCES challenges(challenge_id),
    run_id              UUID REFERENCES autotrade_runs(run_id),
    
    amount              NUMERIC(15, 2) NOT NULL,
    currency            VARCHAR(10) NOT NULL DEFAULT 'TAC', -- 1 TAC = 1 USDT Margin
    type                VARCHAR(30) NOT NULL, -- CONVERSION_FROM_FEE, PROFIT_ACCRUAL, USAGE_FEE
    balance_after       NUMERIC(15, 2) NOT NULL,
    
    chain_id            INTEGER DEFAULT 137,
    token_address       VARCHAR(42),
    source_event_id     VARCHAR(64),
    idempotency_key     VARCHAR(128) UNIQUE NOT NULL,
    
    description         TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Ledger 3: Withdrawable Rewards (Valore reale prelevabile certificato da Reward Pool)
CREATE TABLE IF NOT EXISTS ledger_withdrawable_rewards (
    transaction_id      BIGSERIAL PRIMARY KEY,
    user_id             UUID NOT NULL REFERENCES users(user_id),
    pool_id             INTEGER REFERENCES reward_pools(pool_id),
    run_id              UUID REFERENCES autotrade_runs(run_id),
    
    amount_atomic       NUMERIC(78, 0) NOT NULL, -- Importo in wei per valuta on-chain
    decimals            INTEGER NOT NULL DEFAULT 18,
    currency            VARCHAR(10) NOT NULL DEFAULT 'POL', -- POL o USDT
    
    amount_display      NUMERIC(15, 2) NOT NULL, -- Calcolato per dashboard contabile
    type                VARCHAR(30) NOT NULL, -- REWARD_POOL_PAYOUT, AUTOTRADE_WIN_PAYOUT, REFERRAL_BONUS
    status              VARCHAR(20) NOT NULL DEFAULT 'LOCKED', -- LOCKED, UNLOCKED, WITHDRAWN
    
    locked_until        TIMESTAMPTZ,
    withdrawn_at        TIMESTAMPTZ,
    tx_hash             VARCHAR(66), -- Hash transazione Polygon reale
    chain_id            INTEGER NOT NULL DEFAULT 137,
    token_address       VARCHAR(42),
    source_event_id     VARCHAR(64),
    idempotency_key     VARCHAR(128) UNIQUE NOT NULL,
    
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- =============================================================================
-- 9. MONTHLY LEADERBOARD
-- =============================================================================

CREATE TABLE IF NOT EXISTS monthly_leaderboard (
    leaderboard_id      BIGSERIAL PRIMARY KEY,
    user_id             UUID NOT NULL REFERENCES users(user_id),
    challenge_id        UUID REFERENCES challenges(challenge_id),
    pool_id             INTEGER NOT NULL REFERENCES reward_pools(pool_id),
    total_return_pct    NUMERIC(5, 2) NOT NULL,
    consistency_score   NUMERIC(5, 2) NOT NULL,
    reward_amount       NUMERIC(15, 2) NOT NULL DEFAULT 0.00,
    rank                INTEGER NOT NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(user_id, pool_id)
);

-- Seed Initial Tier Configuration
INSERT INTO challenge_tiers (tier_id, name, fee_usdt, nominal_capital, phase1_target_pct, phase2_target_pct, max_daily_dd_pct, max_total_dd_pct, min_trading_days, is_active)
VALUES 
(1, 'STARTER', 50.00, 10000.00, 8.00, 5.00, 5.00, 10.00, 5, TRUE),
(2, 'PRO', 100.00, 50000.00, 8.00, 5.00, 5.00, 10.00, 5, TRUE),
(3, 'ELITE', 500.00, 100000.00, 8.00, 5.00, 5.00, 10.00, 5, TRUE),
(4, 'BLACK', 1500.00, 150000.00, 8.00, 5.00, 5.00, 10.00, 5, TRUE)
ON CONFLICT (tier_id) DO NOTHING;
