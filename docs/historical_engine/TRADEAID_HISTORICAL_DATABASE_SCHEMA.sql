-- TRADEAID HISTORICAL DATABASE SCHEMA
-- Version: 1.0.0
-- Created: 2026-09-04
-- Target: PostgreSQL 15+
-- Evidence state: DESIGN_SPEC

-- ============================================================
-- EXTENSIONS
-- ============================================================
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- ============================================================
-- DATASETS & VERSIONING
-- ============================================================
CREATE TABLE datasets (
    dataset_id          TEXT PRIMARY KEY,
    name                TEXT NOT NULL,
    description         TEXT,
    source_provider     TEXT,
    license             TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE dataset_versions (
    version_id          TEXT PRIMARY KEY,
    dataset_id          TEXT NOT NULL REFERENCES datasets(dataset_id),
    version             TEXT NOT NULL,
    released_at         TIMESTAMPTZ NOT NULL,
    checksum            TEXT,
    notes               TEXT,
    UNIQUE (dataset_id, version)
);

-- ============================================================
-- CANONICAL ASSETS & IDENTITY
-- ============================================================
CREATE TABLE canonical_assets (
    canonical_asset_id      TEXT PRIMARY KEY,
    family                  TEXT NOT NULL,
    current_symbol          TEXT NOT NULL,
    current_name            TEXT NOT NULL,
    birth_date              DATE,
    first_market_data       DATE,
    first_reliable_market_data DATE,
    chain                   TEXT,
    status                  TEXT NOT NULL CHECK (status IN ('BIRTH','LISTED','ACTIVE','DELISTED','MIGRATED','RENAMED','DEAD')),
    parent_canonical_id     TEXT REFERENCES canonical_assets(canonical_asset_id),
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE asset_identity_events (
    event_id            TEXT PRIMARY KEY,
    canonical_asset_id  TEXT NOT NULL REFERENCES canonical_assets(canonical_asset_id),
    event_type          TEXT NOT NULL,
    effective_date      DATE NOT NULL,
    from_symbol         TEXT,
    to_symbol           TEXT,
    from_name           TEXT,
    to_name             TEXT,
    ratio               TEXT,
    new_canonical_id    TEXT REFERENCES canonical_assets(canonical_asset_id),
    source              TEXT,
    evidence_state      TEXT NOT NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE asset_symbol_aliases (
    canonical_asset_id  TEXT NOT NULL REFERENCES canonical_assets(canonical_asset_id),
    symbol              TEXT NOT NULL,
    valid_from          DATE,
    valid_to            DATE,
    PRIMARY KEY (canonical_asset_id, symbol, COALESCE(valid_from, '1900-01-01'::DATE))
);

CREATE INDEX idx_symbol_aliases_symbol ON asset_symbol_aliases(symbol);
CREATE INDEX idx_symbol_aliases_dates ON asset_symbol_aliases(valid_from, valid_to);

-- ============================================================
-- BTC MASTER HISTORY
-- ============================================================
CREATE TABLE btc_observations_raw (
    observation_id      BIGSERIAL PRIMARY KEY,
    timestamp           TIMESTAMPTZ NOT NULL,
    interval            TEXT NOT NULL CHECK (interval IN ('1m','5m','15m','1h','4h','1d')),
    open                NUMERIC NOT NULL,
    high                NUMERIC NOT NULL,
    low                 NUMERIC NOT NULL,
    close               NUMERIC NOT NULL,
    volume_btc          NUMERIC,
    volume_usd          NUMERIC,
    source_id           TEXT NOT NULL,
    source_tier         TEXT NOT NULL,
    era_id              TEXT NOT NULL,
    dataset_version_id  TEXT NOT NULL REFERENCES dataset_versions(version_id),
    UNIQUE (timestamp, interval, source_id)
);

CREATE INDEX idx_btc_raw_ts ON btc_observations_raw(timestamp, interval);

CREATE TABLE btc_observations_curated (
    timestamp               TIMESTAMPTZ NOT NULL,
    interval                TEXT NOT NULL,
    open                    NUMERIC NOT NULL,
    high                    NUMERIC NOT NULL,
    low                     NUMERIC NOT NULL,
    close                   NUMERIC NOT NULL,
    volume_usd              NUMERIC,
    consensus_source_count  INT,
    consensus_divergence_pct NUMERIC,
    quality_tier            TEXT NOT NULL,
    era_id                  TEXT NOT NULL,
    data_flags              TEXT[],
    feature_version         TEXT NOT NULL,
    PRIMARY KEY (timestamp, interval, feature_version)
);

CREATE TABLE btc_derived_features (
    timestamp               TIMESTAMPTZ NOT NULL,
    feature_version         TEXT NOT NULL,
    return_1d               NUMERIC,
    volatility_7d           NUMERIC,
    volatility_30d          NUMERIC,
    atr_14d                 NUMERIC,
    rsi_14d                 NUMERIC,
    sma_50                  NUMERIC,
    sma_200                 NUMERIC,
    price_vs_sma200_pct     NUMERIC,
    drawdown_from_ath       NUMERIC,
    momentum_14d            NUMERIC,
    momentum_30d            NUMERIC,
    momentum_90d            NUMERIC,
    PRIMARY KEY (timestamp, feature_version)
);

-- ============================================================
-- TOP-200 SNAPSHOTS
-- ============================================================
CREATE TABLE historical_top200_snapshot (
    snapshot_date       DATE NOT NULL,
    snapshot_version    TEXT NOT NULL,
    snapshot_quality    TEXT NOT NULL,
    source_count        INT,
    methodology_version TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (snapshot_date, snapshot_version)
);

CREATE TABLE historical_top200_asset (
    snapshot_date       DATE NOT NULL,
    snapshot_version    TEXT NOT NULL,
    rank                INT NOT NULL,
    canonical_asset_id  TEXT NOT NULL REFERENCES canonical_assets(canonical_asset_id),
    symbol_at_date      TEXT,
    name_at_date        TEXT,
    market_cap_usd      NUMERIC,
    price_usd           NUMERIC,
    volume_24h_usd      NUMERIC,
    available_supply    NUMERIC,
    chain               TEXT,
    status_at_date      TEXT,
    data_quality        TEXT NOT NULL,
    source_ids          TEXT[],
    PRIMARY KEY (snapshot_date, snapshot_version, rank),
    FOREIGN KEY (snapshot_date, snapshot_version) REFERENCES historical_top200_snapshot(snapshot_date, snapshot_version)
);

CREATE INDEX idx_top200_asset_canonical ON historical_top200_asset(canonical_asset_id, snapshot_date);

-- ============================================================
-- BTC CYCLE & MARKET STATE
-- ============================================================
CREATE TABLE btc_cycle_states (
    timestamp           TIMESTAMPTZ NOT NULL,
    feature_version     TEXT NOT NULL,
    regime              TEXT NOT NULL,
    cycle_phase         TEXT NOT NULL,
    confidence          NUMERIC,
    days_since_halving  INT,
    days_to_next_halving INT,
    PRIMARY KEY (timestamp, feature_version)
);

CREATE TABLE market_breadth_states (
    snapshot_date                   DATE NOT NULL,
    snapshot_version                TEXT NOT NULL,
    feature_version                 TEXT NOT NULL,
    pct_top200_above_sma50          NUMERIC,
    pct_top200_positive_return_7d   NUMERIC,
    pct_top200_outperforming_btc_7d NUMERIC,
    median_alt_return_7d            NUMERIC,
    median_alt_return_30d           NUMERIC,
    alt_dispersion_7d               NUMERIC,
    market_breadth_index            NUMERIC,
    market_cap_concentration_top10  NUMERIC,
    btc_dominance                   NUMERIC,
    btc_dominance_change_30d        NUMERIC,
    stablecoin_share                NUMERIC,
    market_regime                   TEXT,
    PRIMARY KEY (snapshot_date, snapshot_version, feature_version)
);

CREATE TABLE market_state_vectors (
    state_id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    timestamp           TIMESTAMPTZ NOT NULL,
    feature_version     TEXT NOT NULL,
    state_hash          TEXT NOT NULL,
    btc_features        JSONB,
    breadth_features    JSONB,
    structural_context  JSONB,
    UNIQUE (timestamp, feature_version)
);

CREATE INDEX idx_msv_hash ON market_state_vectors(state_hash);
CREATE INDEX idx_msv_ts ON market_state_vectors(timestamp);

-- ============================================================
-- HISTORICAL REPLAY RUNS
-- ============================================================
CREATE TABLE historical_replay_runs (
    run_id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    run_name            TEXT NOT NULL,
    mode                TEXT NOT NULL,
    started_at          TIMESTAMPTZ NOT NULL,
    finished_at         TIMESTAMPTZ,
    dataset_version     TEXT NOT NULL,
    feature_version     TEXT NOT NULL,
    strategy_version    TEXT NOT NULL,
    cost_model_version  TEXT NOT NULL,
    starting_capital    NUMERIC,
    final_capital       NUMERIC,
    status              TEXT NOT NULL,
    notes               TEXT
);

CREATE TABLE historical_decisions (
    decision_id         UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    run_id              UUID NOT NULL REFERENCES historical_replay_runs(run_id),
    timestamp           TIMESTAMPTZ NOT NULL,
    state_id            UUID REFERENCES market_state_vectors(state_id),
    strategy_id         TEXT NOT NULL,
    action              TEXT NOT NULL,
    confidence          NUMERIC,
    position_size_pct   NUMERIC,
    entry_price         NUMERIC
);

CREATE INDEX idx_hist_decisions_run ON historical_decisions(run_id, timestamp);

-- ============================================================
-- EXPERIENCE RECORDS
-- ============================================================
CREATE TABLE experience_records (
    experience_id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source_label            TEXT NOT NULL CHECK (source_label IN ('HISTORICAL_REPLAY','FORWARD_PAPER_SHADOW','LIVE')),
    timestamp               TIMESTAMPTZ NOT NULL,
    dataset_version         TEXT NOT NULL,
    feature_version         TEXT NOT NULL,
    strategy_version        TEXT NOT NULL,
    cost_model_version      TEXT NOT NULL,
    state_id                UUID REFERENCES market_state_vectors(state_id),
    btc_cycle_phase         TEXT,
    btc_regime              TEXT,
    market_breadth_regime   TEXT,
    asset_canonical_id      TEXT REFERENCES canonical_assets(canonical_asset_id),
    asset_rank_at_t         INT,
    asset_class             TEXT,
    btc_correlation_bucket  TEXT,
    volatility_bucket       TEXT,
    liquidity_bucket        TEXT,
    strategy_id             TEXT NOT NULL,
    action                  TEXT NOT NULL,
    confidence              NUMERIC,
    position_size_pct       NUMERIC,
    entry_price             NUMERIC,
    expected_return         NUMERIC,
    expected_risk           NUMERIC,
    expected_cost           NUMERIC,
    actual_cost             NUMERIC,
    return_1h               NUMERIC,
    return_4h               NUMERIC,
    return_1d               NUMERIC,
    return_3d               NUMERIC,
    return_7d               NUMERIC,
    return_14d              NUMERIC,
    return_30d              NUMERIC,
    max_favorable_excursion NUMERIC,
    max_adverse_excursion   NUMERIC,
    realized_pnl            NUMERIC,
    realized_pnl_pct        NUMERIC,
    error_attribution       TEXT,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    closed_at               TIMESTAMPTZ
);

CREATE INDEX idx_exp_source ON experience_records(source_label, timestamp);
CREATE INDEX idx_exp_strategy ON experience_records(strategy_id, timestamp);
CREATE INDEX idx_exp_state ON experience_records(state_id);

CREATE TABLE no_trade_records (
    experience_id               UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source_label                TEXT NOT NULL,
    timestamp                   TIMESTAMPTZ NOT NULL,
    state_id                    UUID REFERENCES market_state_vectors(state_id),
    strategy_id                 TEXT NOT NULL,
    reason                      TEXT,
    what_would_have_happened_1d NUMERIC,
    what_would_have_happened_7d NUMERIC,
    what_would_have_happened_30d NUMERIC,
    classification              TEXT CHECK (classification IN ('GOOD_NO_TRADE','MISSED_OPPORTUNITY'))
);

CREATE TABLE counterfactual_records (
    counterfactual_id       UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    parent_experience_id    UUID NOT NULL REFERENCES experience_records(experience_id),
    timestamp               TIMESTAMPTZ NOT NULL,
    alternative_type        TEXT NOT NULL,
    alternative_strategy_id TEXT,
    alternative_action      TEXT,
    alternative_position_size_pct NUMERIC,
    alternative_entry_price NUMERIC,
    return_1d               NUMERIC,
    return_7d               NUMERIC,
    return_30d              NUMERIC,
    mfe                     NUMERIC,
    mae                     NUMERIC,
    realized_pnl            NUMERIC,
    would_have_been_better  BOOLEAN,
    delta_vs_actual_pnl     NUMERIC
);

-- ============================================================
-- ANALOG QUERIES & MATCHES
-- ============================================================
CREATE TABLE analog_queries (
    query_id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    query_timestamp     TIMESTAMPTZ NOT NULL,
    horizon             TEXT NOT NULL,
    state_id            UUID REFERENCES market_state_vectors(state_id),
    novelty_flag        BOOLEAN,
    max_similarity_score NUMERIC,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE analog_matches (
    match_id                UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    query_id                UUID NOT NULL REFERENCES analog_queries(query_id),
    historical_timestamp    TIMESTAMPTZ NOT NULL,
    similarity_score        NUMERIC NOT NULL,
    similarity_method       TEXT NOT NULL,
    feature_similarities    JSONB,
    feature_differences     JSONB,
    regime_match            BOOLEAN,
    liquidity_match         TEXT,
    structural_compatibility TEXT,
    data_quality            TEXT,
    confidence              NUMERIC,
    forward_return_nd       NUMERIC,
    forward_max_drawdown_nd NUMERIC,
    forward_volatility_nd   NUMERIC
);

CREATE INDEX idx_analog_match_query ON analog_matches(query_id);

-- ============================================================
-- SCENARIO FORECASTS & CALIBRATION
-- ============================================================
CREATE TABLE scenario_forecasts (
    forecast_id         UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    query_timestamp     TIMESTAMPTZ NOT NULL,
    horizon             TEXT NOT NULL,
    state_id            UUID REFERENCES market_state_vectors(state_id),
    scenarios_json      JSONB NOT NULL,
    overall_confidence  NUMERIC,
    dominant_scenario   TEXT,
    dominant_probability NUMERIC,
    novel_state_flag    BOOLEAN,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE forecast_calibration (
    calibration_id      UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    forecast_id         UUID NOT NULL REFERENCES scenario_forecasts(forecast_id),
    horizon             TEXT NOT NULL,
    scenario_name       TEXT NOT NULL,
    predicted_probability NUMERIC NOT NULL,
    actualized          BOOLEAN NOT NULL,
    brier_component     NUMERIC,
    measured_at         TIMESTAMPTZ NOT NULL
);

CREATE INDEX idx_calib_forecast ON forecast_calibration(forecast_id);

-- ============================================================
-- STRATEGY EXPERIENCE AGGREGATES
-- ============================================================
CREATE TABLE strategy_experience (
    aggregate_id        UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    strategy_id         TEXT NOT NULL,
    btc_regime          TEXT,
    btc_cycle_phase     TEXT,
    analog_cluster_id   TEXT,
    sample_size         INT NOT NULL,
    net_expectancy      NUMERIC,
    win_rate            NUMERIC,
    profit_factor       NUMERIC,
    max_drawdown        NUMERIC,
    mfe_mean            NUMERIC,
    mae_mean            NUMERIC,
    stability_score     NUMERIC,
    computed_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    source_label        TEXT NOT NULL
);

CREATE INDEX idx_strat_exp_strategy ON strategy_experience(strategy_id, source_label);

-- ============================================================
-- MEMORY VERSIONS
-- ============================================================
CREATE TABLE memory_versions (
    version_id          TEXT PRIMARY KEY,
    released_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    weights_json        JSONB NOT NULL,
    strategy_scores_json JSONB NOT NULL,
    analog_weights_json JSONB,
    calibration_metrics_json JSONB,
    notes               TEXT
);

-- ============================================================
-- EVENT REGISTRY
-- ============================================================
CREATE TABLE event_registry (
    event_id            TEXT PRIMARY KEY,
    timestamp           TIMESTAMPTZ NOT NULL,
    event_type          TEXT NOT NULL,
    source              TEXT,
    affected_assets     TEXT[],
    description         TEXT,
    evidence_state      TEXT NOT NULL
);

CREATE INDEX idx_event_ts ON event_registry(timestamp);
