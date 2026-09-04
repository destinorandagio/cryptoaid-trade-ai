# TRADEAID HISTORICAL REPLAY — PSEUDOCODE

Version: 1.0.0
Created: 2026-09-04
Evidence state: DESIGN_SPEC

## Initialization

```python
def initialize_replay(config):
    # Load data
    btc_history = load_btc_master_history(config.dataset_version)
    top200_snapshots = load_top200_snapshots(config.dataset_version)
    canonical_registry = load_canonical_asset_registry()
    event_registry = load_event_registry()
    
    # Load engines
    market_state_builder = MarketStateBuilder(config.feature_version)
    cycle_classifier = BtcCycleClassifier()
    breadth_builder = MarketBreadthBuilder()
    relationship_builder = AssetBtcRelationshipBuilder()
    
    # Load strategies
    strategies = load_strategy_candidates(config.strategy_version)
    
    # Load risk engine
    risk_engine = RiskAgent(config.risk_limits)
    
    # Load cost model
    cost_model = load_cost_model(config.cost_model_version)
    
    # Initialize portfolio
    portfolio = Portfolio(starting_capital=config.starting_capital)
    
    # Initialize experience log
    experience_log = ExperienceLog()
    
    return ReplayContext(
        btc_history, top200_snapshots, canonical_registry, event_registry,
        market_state_builder, cycle_classifier, breadth_builder, relationship_builder,
        strategies, risk_engine, cost_model, portfolio, experience_log
    )
```

## Main Loop

```python
def run_replay(ctx, timeline):
    checkpoint = None
    
    for T in timeline:
        # STEP 1: load information available at T
        btc_data_up_to_T = ctx.btc_history.filter(timestamp <= T)
        top200_at_T = ctx.top200_snapshots.get_nearest_prior(T)
        events_up_to_T = ctx.event_registry.filter(timestamp <= T)
        
        # ASSERT: no data after T is accessible
        assert btc_data_up_to_T.max_timestamp() <= T
        assert top200_at_T.snapshot_date <= T
        
        # STEP 2: build market state
        market_state = ctx.market_state_builder.build(
            btc_data=btc_data_up_to_T,
            top200_snapshot=top200_at_T,
            timestamp=T
        )
        
        # STEP 3: identify tradeable universe
        tradeable_universe = identify_tradeable_universe(
            top200_at_T,
            liquidity_threshold=config.liquidity_threshold,
            min_data_quality='TIER_B'
        )
        
        # STEP 4: detect regime
        btc_regime = ctx.cycle_classifier.classify_regime(market_state.btc_features)
        btc_cycle_phase = ctx.cycle_classifier.classify_cycle_phase(market_state.btc_features)
        breadth_regime = ctx.breadth_builder.classify_regime(market_state.breadth_features)
        
        # STEP 5: run strategy candidates
        strategy_signals = {}
        for strategy in ctx.strategies:
            signal = strategy.generate_signal(
                market_state=market_state,
                tradeable_universe=tradeable_universe,
                timestamp=T
            )
            strategy_signals[strategy.id] = signal
        
        # STEP 6: run risk engine
        risk_check = ctx.risk_engine.check(
            portfolio=ctx.portfolio,
            signals=strategy_signals,
            market_state=market_state
        )
        
        if risk_check.veto:
            action = 'NO_TRADE'
            selected_strategy = None
            veto_reason = risk_check.reason
        else:
            # STEP 7: choose action
            selected_strategy = select_best_strategy(
                strategy_signals,
                risk_check.eligible_strategies,
                selection_method='tournament_ranking'
            )
            action = selected_strategy.action
            position_size = selected_strategy.position_size
        
        # STEP 8: record decision
        decision = Decision(
            timestamp=T,
            market_state=market_state,
            btc_regime=btc_regime,
            btc_cycle_phase=btc_cycle_phase,
            breadth_regime=breadth_regime,
            strategy_id=selected_strategy.id if selected_strategy else None,
            action=action,
            confidence=selected_strategy.confidence if selected_strategy else 0,
            position_size_pct=position_size if selected_strategy else 0
        )
        ctx.experience_log.log_decision(decision)
        
        # STEP 9: execute action (simulate fill)
        if action != 'NO_TRADE':
            execution = simulate_execution(
                action=action,
                asset=selected_strategy.asset,
                timestamp=T,
                execution_price_rule='T_plus_1_open',  # no look-ahead
                cost_model=ctx.cost_model
            )
            ctx.portfolio.apply_execution(execution)
        
        # STEP 10: advance time (implicit in loop)
        
        # STEP 11: observe outcomes (for past decisions)
        for past_decision in ctx.experience_log.get_open_decisions():
            if past_decision.timestamp + horizon <= T:
                outcomes = compute_forward_outcomes(
                    decision=past_decision,
                    current_timestamp=T,
                    btc_history=ctx.btc_history
                )
                past_decision.outcomes = outcomes
                past_decision.closed_at = T
        
        # STEP 12: score decision (after horizon closes)
        for closed_decision in ctx.experience_log.get_just_closed(T):
            counterfactuals = generate_counterfactuals(
                decision=closed_decision,
                strategy_signals_at_decision_time=closed_decision.original_signals,
                btc_history=ctx.btc_history
            )
            closed_decision.counterfactuals = counterfactuals
            ctx.experience_log.finalize(closed_decision)
        
        # Checkpoint
        if T % config.checkpoint_frequency == 0:
            checkpoint = create_checkpoint(ctx, T)
            save_checkpoint(checkpoint)
    
    return ctx.experience_log
```

## No Look-Ahead Guarantees

```python
def assert_no_look_ahead(ctx, T):
    """QA test: freeze time at T, verify all inputs <= T"""
    max_input_ts = max(
        ctx.btc_history.max_timestamp(),
        ctx.top200_snapshots.max_date(),
        ctx.event_registry.max_timestamp()
    )
    assert max_input_ts <= T, f"LOOK-AHEAD VIOLATION: {max_input_ts} > {T}"
    
    # Verify market state uses only past data
    for feature in ctx.market_state.features:
        assert feature.max_input_timestamp() <= T
    
    # Verify strategy signals use only past data
    for strategy in ctx.strategies:
        assert strategy.max_input_timestamp() <= T
```

## Counterfactual Generation

```python
def generate_counterfactuals(decision, strategy_signals_at_T, btc_history):
    counterfactuals = []
    
    # NO_TRADE counterfactual (always)
    no_trade_outcome = compute_no_trade_outcome(decision, btc_history)
    counterfactuals.append(Counterfactual(
        alternative_type='NO_TRADE',
        outcomes=no_trade_outcome
    ))
    
    # Other eligible strategies
    for strategy_id, signal in strategy_signals_at_T.items():
        if strategy_id != decision.strategy_id and signal.action != 'NO_TRADE':
            cf_outcome = compute_strategy_outcome(signal, btc_history)
            counterfactuals.append(Counterfactual(
                alternative_type='OTHER_ELIGIBLE_STRATEGY',
                alternative_strategy_id=strategy_id,
                outcomes=cf_outcome
            ))
    
    return counterfactuals
```

## Checkpoint & Resume

```python
def create_checkpoint(ctx, T):
    return Checkpoint(
        timestamp=T,
        portfolio_state=ctx.portfolio.serialize(),
        experience_log_state=ctx.experience_log.serialize(),
        strategy_states={s.id: s.serialize() for s in ctx.strategies},
        dataset_version=ctx.config.dataset_version,
        feature_version=ctx.config.feature_version,
        strategy_version=ctx.config.strategy_version,
        cost_model_version=ctx.config.cost_model_version
    )

def resume_from_checkpoint(checkpoint_path):
    checkpoint = load_checkpoint(checkpoint_path)
    ctx = initialize_replay(checkpoint.config)
    ctx.portfolio.deserialize(checkpoint.portfolio_state)
    ctx.experience_log.deserialize(checkpoint.experience_log_state)
    for s in ctx.strategies:
        s.deserialize(checkpoint.strategy_states[s.id])
    return ctx, checkpoint.timestamp
```
