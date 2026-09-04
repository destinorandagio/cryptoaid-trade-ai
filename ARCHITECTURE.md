# TRADEAID — GOLDEN MASTER ARCHITECTURE SPECIFICATION
**Version:** 1.0.0-GOLDEN-MASTER  
**Security / Governance:** Strict Non-Custodial · CORTEX Protected · Native on Polygon (Chain ID 137)  
**Brand Mandate:**
- **TRADEAID**
- **Powered by BLOCKCHAIN+ (B+)**
- **Engineered by NEURALOG**
- **CORTEX — Risk / Security / Audit Layer**
- **Native on Polygon**

*(Note: "Audited & Certified by CORTEX" is strictly reserved as a future public claim once formal live audit verification is executed. The operational layer designation is CORTEX — Risk / Security / Audit Layer).*

---

## 1. The Canonical Unified Macro Architecture Flow

```text
       [ MARKET DATA + ON-CHAIN + SENTIMENT + CRYPTOAID INTELLIGENCE ]
                                      │
                                      ▼
             [ PREDICTIVE HEART — White Reality × Red Prediction ]
                                      │
                                      ▼
                              [ REGIME ENGINE ]
                                      │
                                      ▼
                               [ STRATEGY DNA ]
                                      │
                                      ▼
                        [ MULTI-AGENT COUNCIL ]
      (Scalping · Trend · Momentum · Breakout · Mean Reversion ·
       Volatility · Arbitrage · On-chain · Sentiment · Liquidity)
                                      │
                                      ▼
                               [ META STRATEGY ]
                                      │
                                      ▼
                           [ CORTEX RISK VETO ]
                                      │
                                      ▼
                            [ CAPITAL ALLOCATOR ]
                                      │
                                      ▼
                        [ SMART POLYGON DEX ROUTER ]
                                      │
                                      ▼
                  [ SIMULATION + SLIPPAGE/IMPACT/MEV GATES ]
                                      │
                                      ▼
                         [ AUTOMATIC WALLET SIGNER ]
                                      │
                                      ▼
                          [ POSITION GUARDIAN H24 ]
                                      │
                                      ▼
                   [ PERFORMANCE + PREDICTION CALIBRATION ]
                                      │
                                      ▼
                      [ STRATEGY TOURNAMENT / LEARNING ]
                                      │
                                      └───► ↺ (Feedback loop into Predictive Heart)
```

---

## 2. Core Functional Responsibilities

| Subsystem | Functional Role & Mandate |
|---|---|
| **PREDICTIVE HEART** | **The Predictive Brain.** Ingests real market history (White Line), fuses 7+ sub-models via Dynamic Time Warping (DTW), Mahalanobis distance, and cosine analogs to produce a probabilistic forward trajectory (Red Line P50) with confidence cone (P10–P90). |
| **META STRATEGY** | **The Decision Engine.** Evaluates the Predictive Heart's trajectory against market regime, candidate strategy recommendations, expected net edge, and portfolio state to synthesize the primary intent (`LONG`, `SHORT`, or `NO_TRADE`). |
| **CORTEX RISK VETO** | **The Absolute Veto & Security Layer.** Non-negotiable guardian. Enforces the -5.0% hard stop ceiling, daily drawdown halts, smart-contract anti-scam / anti-honeypot filters, and treasury constraints. |
| **SMART ROUTER** | **The Execution Optimizer.** Quotes, splits, and routes swaps across Polygon DEXes (Uniswap V3, QuickSwap, 1inch) with tight slippage gates and pre-flight Bor RPC simulation. |
| **POSITION GUARDIAN H24** | **Capital Protector.** 24/7 autonomous daemon. Priority: *protect existing capital before discovering new trades*. Enforces break-even locks, dynamic trailing stops, partial take-profits, and emergency liquidation. |
| **PERFORMANCE & LEARNING** | **Continuous Calibration Ledger.** Records `Expected vs Actual`, attributes errors (Regime, Sizing, Slippage), scores decision quality (`CORRECT_DECISION`, `CORRECT_NO_TRADE`, `GOOD_LOSS`, `MISSED_OPPORTUNITY`, `LUCKY_WIN`), and updates weights for the next cycle. |

---

## 3. Specialized Intelligence Domains

1. **Sentiment & Narrative Intelligence Engine:** Continuous monitoring of sentiment signals, narrative shifts, and social velocity for actionable market regime context.
2. **On-Chain / Flow Intelligence:** Mempool inspection, whale wallet tracking, DEX liquidity shifts, and bridge inflow/outflow metrics on Polygon.
3. **Gem Hunter & Liquidity Scanner:** Early pool detection, bytecode verification, rug-pull heuristics, and liquidity lock analysis.
4. **Multi-DEX & Triangular Arbitrage:** Cross-venue spatial spreads (QuickSwap vs Uniswap V3) and triangular arbitrage circuits on Polygon POS.
5. **Digital Twin Modeling:** Shadow-simulation mirroring real trader profiles and algorithmic software bots to stress-test candidate strategies before capital allocation.
6. **Strategy DNA & Strategy Tournament:** Multi-tier strategy ranking (`PROMOTED`, `WATCH`, `DEMOTED`, `REJECTED`) evaluated on walk-forward out-of-sample data with full cost modeling.

---

## 4. PWA Cockpit Specification (HOME IS HEART)

The TradeAID PWA cockpit (`trade.cryptoaid.support`) is purpose-built around the **HEART** experience:

### A. Above Chart (Top Telemetry Bar)
Five continuous high-visibility metrics:
1. `PREDICTION`: E.g., `↑ +1.84% (P50)`
2. `CONFIDENCE`: E.g., `78% (HIGH)`
3. `REGIME`: E.g., `EXPANSION / MOMENTUM`
4. `NET EDGE`: E.g., `+1.12% NET`
5. `CORTEX`: E.g., `VETO: CLEAR (PASS)`

### B. The Predictive Heart Canvas
- **White Line:** Historical observed reality (immutable memory).
- **Red Line:** Future probabilistic trajectory (P50).
- **Confidence Band:** Probabilistic cone (P10 to P90).
- **NOW Pulsing Boundary:** Real-time marker dividing observed history from forward projection.
- **Dynamic Price Markers:** Entry price, Stop-Loss (Dynamic SL), and Target Take-Profits (TP1, TP2).

### C. Below Chart (Decision Callout & Explainability)
- **Primary Signal Badges:** `LONG` · `SHORT` · `NO TRADE` (active status highlighted).
- **`WHY?` Inspector:** Transparent Explainability modal disclosing the Multi-Agent Council weights and full execution pipeline.
- **Scenarios & Calibration:** Multi-scenario distribution (Base P50, Surge, Mean Reversion) and historical directional accuracy ledger.

### D. The Six Canonical Navigation Sections
1. **HEART:** The core predictive cockpit (Home view).
2. **MARKETS:** Monitored Polygon pairs, liquidity depth, spread monitoring, narrative intelligence.
3. **POSITIONS:** Active watches, break-even locks, trailing stops, capital allocation.
4. **STRATEGIES:** Strategy DNA catalog, Multi-Agent Council breakdown, tournament rankings.
5. **PERFORMANCE:** Predicted vs Actual learning ledger, error attribution, decision quality scoring.
6. **CORTEX:** Security posture, -5.0% hard stop watchdog, Treasury 100 USDT DAO quota, 10 POL trade quote, emergency kill switch.

---

## 5. Frozen Brand & Credentials

```text
TRADEAID
Powered by BLOCKCHAIN+ (B+)
Engineered by NEURALOG
CORTEX — Risk / Security / Audit Layer
Native on Polygon
```

- Non-Custodial: All funds remain in the user's wallet.
- Treasury Address: `0x3C320B3a0917fF44BF6551CDdee44402AFcF250C`
- Network: Polygon POS (Chain ID 137, Gas: POL, Base: USDT)
- Hard Stop Ceiling: 5.0% Maximum Drawdown per Trade.

---

## 6. Open-Source Foundations & 10 P0 Critical Components

Per la documentazione dettagliata di implementazione, consultare [STACK_RATIONALIZATION_P0.md](file:///c:/81PLUS_GLOBAL_MASTER/cryptoaid.support/cryptoaid-trade-ai/docs/STACK_RATIONALIZATION_P0.md).

### I 10 Pezzi Indispensabili (P0):
1. **DEX Execution Middleware:** `Hummingbot Gateway` (Polygon POS + wallet + 0x + Uniswap connectors).
2. **DEX Aggregator Primario:** `0x Swap API v2` (Quote ottimali, gasless, Permit2).
   - *Regola Invalicabile:* MAI concedere allowance a `Settler`, SOLO a `Permit2` / `AllowanceHolder`.
3. **Second Router & Fallback:** `Uniswap Router / SOR` (Quote comparator e failover).
4. **Meta-Router Pattern:** `DexGuru Meta Aggregation` (Pattern FastAPI `VIEW -> SERVICE -> PROVIDERS`).
5. **Transaction Simulation:** `Router Protocol Simulator + RPC eth_call` (Pre-sign safety check su Chain 137).
6. **Wallet & EVM Signer:** `web3.py / eth-account` (Firma transazione non-custodiale).
7. **Strategy Research & Format:** `Freqtrade / FreqAI` (Formati standard, hyperopt, dry-run adattivo).
8. **DEX Trading Patterns:** `Hummingbot Core` (Pattern Arbitraggio / Market Making).
9. **Backtest Tournament Engine:** `vectorbt + Optuna + backtest-truth` (Anti-overfitting & look-ahead bias linter).
10. **Performance & Calibration:** `QuantStats + TradeAID Ledger` (Sharpe, Calmar, MaxDD e Brier Score calibrazione).

### Repository Architecture:
- **GitHub (`destinorandagio/cryptoaid-trade-ai`):** Control plane primario di sviluppo e runtime.
- **Forgejo:** Mirror sovrano, self-hosted backup e CI secondaria offline (NON nel critical path di trading).
- **3 Repo Canonici:** `cryptoaidsupport` (Risk/Knowledge), `cryptoaid-trade-ai` (Runtime/PWA/Engine), `tradeaid-research` (Digital Twin/DNA/Warehouse).

