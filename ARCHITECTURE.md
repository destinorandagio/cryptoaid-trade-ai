# CryptoAID Trade AI — Technical Architecture

## 1. High-Level Architecture Flow

```
+---------------------------------------------------------------------------------------------------+
|                                      CRYPTOAID TRADE AI ARCHITECTURE                              |
+---------------------------------------------------------------------------------------------------+
|                                                                                                   |
|  [DEDICATED TRADING WALLET] (Server-Side Isolation, Chain ID 137, Never Committed/Exposed)         |
|             |                                                                                     |
|             v                                                                                     |
|  [USDT ACCOUNTING & SETTLEMENT] ($1,000 Starting Capital Model, Max 10% Pos Size, Max 50% Exp)     |
|             |                                                                                     |
|             v                                                                                     |
|  [POLYGON SCANNER] (Volume, Spread, Depth, Volatility, Contract Freshness)                         |
|             |                                                                                     |
|             v                                                                                     |
|  [MARKET REGIME DETECTOR]                                                                         |
|     --> TRENDING | RANGING | HIGH_VOLATILITY | LOW_VOLATILITY | LOW_LIQUIDITY | RISK_OFF         |
|             |                                                                                     |
|             v                                                                                     |
|  [MULTI-STRATEGY AGENTS]                                                                          |
|     * Scalping Agent (1m/3m/5m, spread gate, micro-momentum)                                      |
|     * Trend Following Agent (EMA 12/26 cross, MACD, ADX)                                          |
|     * Momentum Agent (RSI, Stochastic, Rate of Change)                                            |
|     * Breakout Agent (Bollinger Band squeeze, 20-period High/Low)                                 |
|     * Mean Reversion Agent (Z-Score, RSI extreme reversals)                                       |
|     * Volatility Agent (ATR expansion, historical volatility)                                     |
|             |                                                                                     |
|             v                                                                                     |
|  [METASTRATEGY & MATHEMATICAL NET EDGE GATE]                                                      |
|     NET_EDGE = EXPECTED_MOVE - GAS - FEES - PRICE_IMPACT - SLIPPAGE - SAFETY_BUFFER               |
|     If NET_EDGE < 0.40%  --> STRICT NO_TRADE                                                      |
|             |                                                                                     |
|             v                                                                                     |
|  [CRYPTOAID RISK & SECURITY GATE]                                                                 |
|     * Anti-Scam Bytecode Verification (Rejects unverified contracts, honeypots, blacklist)        |
|     * Portfolio Limits: Max 10% ($100), Max 50% exposure ($500), Max 4 concurrent positions      |
|     * Circuit Breakers: -3% daily loss, -6% weekly loss, -10% max drawdown, 3 consecutive losses  |
|             |                                                                                     |
|             v                                                                                     |
|  [SMART EXECUTION ROUTER]                                                                         |
|     * Multi-route quote comparison: Uniswap V3 (Quoter V2) vs QuickSwap Router                    |
|     * Dynamic slippage tolerance: 20 bps base, 100 bps hard cap                                   |
|     * Guaranteed amountOutMinimum calculation                                                     |
|             |                                                                                     |
|             v                                                                                     |
|  [PRE-FLIGHT TRANSACTION SIMULATION] (eth_call against Bor RPC node)                              |
|     If simulation fails or reverts  --> STRICT REJECT                                             |
|             |                                                                                     |
|             v                                                                                     |
|  [AUTOMATIC DEDICATED-WALLET SIGNER]                                                              |
|     * Server-side only, Polygon Chain 137 verified, EIP-1559 gas pricing                          |
|             |                                                                                     |
|             v                                                                                     |
|  [DEX EXECUTION & ON-CHAIN CONFIRMATION]                                                          |
|             |                                                                                     |
|             v                                                                                     |
|  [PERSISTENT POSITION GUARDIAN] (24/7 Daemon, Survives Restarts via SQLite WAL)                   |
|     * Dynamic ATR/Volatility Stop Loss (Default 1.5%)                                             |
|     * Take Profit Target (Default 3.5%)                                                           |
|     * Break-even Ratchet (Locks entry +0.1% once profit reaches +1.2%)                            |
|     * Dynamic Trailing Stop (Activates at +1.8%, trails at 1.0% distance)                         |
|     * Emergency Hard Stop Ceiling: 5.0% absolute maximum (Liquidates to USDT)                     |
|             |                                                                                     |
|             v                                                                                     |
|  [100% USDT SETTLEMENT & REALIZED P&L ACCOUNTING]                                                 |
|             |                                                                                     |
|             v                                                                                     |
|  [OBSERVABILITY, TELEGRAM BROADCAST & PWA COCKPIT]                                                |
|     * Telegram @CryptoAidTradeAIbot topic routing                                                 |
|     * REST API (FastAPI)                                                                          |
|     * PWA Cockpit (13 views deployed at https://trade.cryptoaid.support)                          |
+---------------------------------------------------------------------------------------------------+
```

---

## 2. Directory Layout

```
cryptoaid-trade-ai/
├── .env.example
├── .github/
│   └── workflows/
│       ├── ci.yml                 # Automated CI test suite
│       └── paper-trading.yml      # Automated scheduled paper trading cycle
├── Dockerfile                     # Multi-stage production container
├── docker-compose.yml             # Daemon + API compose configuration
├── pyproject.toml
├── requirements.txt
├── scripts/
│   ├── run_trade_ai.py            # Master daemon startup (FastAPI + PWA)
│   ├── run_paper_daemon.py        # Independent continuous paper trading runner
│   └── run_watchdog.py            # 24/7 observability and health watchdog
├── src/
│   ├── config.py                  # Single source of configuration truth
│   ├── agents/
│   │   ├── base.py                # BaseStrategyAgent, SignalType, AgentSignal
│   │   ├── regime.py              # MarketRegimeDetector (6 market regimes)
│   │   ├── scalp.py               # ScalpingStrategyAgent (micro-timeframe)
│   │   ├── trend.py               # TrendFollowingAgent (EMA/MACD/ADX)
│   │   ├── momentum.py            # MomentumAgent (RSI/Stochastic/ROC)
│   │   ├── breakout.py            # BreakoutAgent (Bollinger/Donchian)
│   │   ├── mean_reversion.py      # MeanReversionAgent (Z-Score)
│   │   ├── volatility.py          # VolatilityAgent (ATR)
│   │   ├── risk_agent.py          # RiskAgent (Safety veto)
│   │   └── meta_agent.py          # MetaAgent (Consensus + Net Edge calculation)
│   ├── api/
│   │   ├── app.py                 # FastAPI application factory
│   │   └── routes/
│   │       └── v1.py              # REST API v1 endpoints
│   ├── data/
│   │   ├── base.py                # Data classes: Candle, Ticker, MarketSnapshot
│   │   ├── provider.py            # Composite provider with cache
│   │   ├── mock_feed.py           # Realistic stochastic feed generator
│   │   └── polygon_scanner.py     # Polygon scanner evaluating depth and spread
│   ├── dex/
│   │   ├── polygon.py             # Bor Web3 connection, gas estimators, allowances
│   │   ├── router.py              # SmartExecutionRouter (Uniswap V3 vs QuickSwap)
│   │   ├── signer.py              # DedicatedWalletSigner (Chain 137 policy checks)
│   │   └── position_guardian.py   # PersistentPositionGuardian (24/7 SL/TP/Trailing/5% stop)
│   ├── execution/
│   │   ├── paper_engine.py        # PaperExecutionEngine (Router + Guardian integration)
│   │   └── live_adapter.py        # LiveExecutionAdapter (11-point fail-closed gate)
│   ├── performance/
│   │   ├── metrics.py             # PerformanceMetrics calculation
│   │   └── backtest.py            # Walk-forward, out-of-sample backtest engine
│   ├── pwa/                       # 13-view PWA Cockpit
│   │   ├── index.html
│   │   ├── manifest.json
│   │   ├── sw.js
│   │   ├── css/app.css
│   │   └── js/app.js
│   ├── risk/
│   │   └── gate.py                # CryptoAidRiskGate (bytecode audit + capital breakers)
│   ├── storage/
│   │   ├── db.py                  # DatabaseManager (16 normalized tables)
│   │   └── migrations.py          # Schema migrations V1 & V2
│   └── telegram/
│       ├── bot.py                 # Telegram bot handler (14 commands + 8 buttons)
│       ├── dedupe.py              # Signal deduplication (cooldown + price delta)
│       ├── formatter.py           # Standardized Telegram message formatters
│       └── router.py              # Topic-based dispatcher
└── tests/                         # 37 Automated pytest unit and integration tests
```
