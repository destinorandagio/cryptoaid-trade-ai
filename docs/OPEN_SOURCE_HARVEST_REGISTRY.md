# TRADEAID — CANONICAL OPEN-SOURCE HARVEST REGISTRY (32 REPOSITORIES)
**Document Version:** 1.0.0-GOLDEN-MASTER  
**Target:** AGY / Qwen / Antigravity Orchestrator  
**Regola di Sicurezza:** MAX 8–12 Dipendenze nel Runtime. Nessun `pip install` selvaggio.  
**Protocollo Tassativo:** `CLONE/READ → LICENSE → SECURITY → EXTRACT DNA → ADAPT → TEST`  
**Data di Congelamento:** 2026-09-04  

---

## 1. Direttiva di Acquisizione per AGY

1. **Non clonare alla cieca 100 repository**: Abbiamo selezionato esattamente **32 repository canonici**, suddivisi per ruolo strategico.
2. **Runtime Diet**: Nel runtime operativo `cryptoaid-trade-ai` entreranno al massimo **8–12 dipendenze reali**. Tutto il resto serve unicamente per studio, estrazione di DNA algoritmico e benchmark nel Tournament.
3. **Cartella Warehouse**: I repository clonati per studio risiedono in `01_OPEN_SOURCE_HARVEST/` (esclusa dal tracciamento Git principale tramite `.gitignore`).
4. **Licenze & Protezione Legale**:
   - Repository **MIT / Apache-2.0**: Riusabili ed estraibili direttamente.
   - Repository **GPL-3.0 / AGPL-3.0** (es. *Uniswap SOR, Permit2, Freqtrade*): **VIETATO copiare codice alla cieca nel core proprietario TradeAID**. Utilizzabili solo come reference architetturale, benchmark esterno o container indipendente (pattern clean-room).
5. **Regola Aurea di Sicurezza (Permit2)**:  
   Nell'uso di 0x Swap API v2, **MAI concedere allowance al contratto `Settler`**, ma esclusivamente a `Permit2` o all'`AllowanceHolder` restituito dalla risposta API.

---

## 2. Ordine di Esecuzione (2 Ondate di Download)

### ONDATA 1 — PRIMA ORA (12 Priorità Immediate)
1. `gateway` (Hummingbot Gateway)
2. `0x-examples` (0x Project)
3. `web3.py` (Ethereum)
4. `eth-account` (Ethereum)
5. `viem` (wevm)
6. `quantstats` (ranaroussi)
7. `freqtrade` (freqtrade)
8. `freqtrade-strategies` (freqtrade)
9. `polygon_arbitrage` (shandilyabh)
10. `multimodal-crypto-forecasting-xai-sentiments` (atishay2411)
11. `crypto-agentic-trader` (weijuinlee)
12. `market-regime-detection` (taylorjmellon)

### ONDATA 2 — SECONDA ONDATA (I Restanti 20)
13. `hummingbot` · 14. `smart-order-router` · 15. `universal-router` · 16. `permit2` · 17. `meta-aggregation-api` · 18. `TRANSACTION_SIMULATION` · 19. `vectorbt` · 20. `backtrader` · 21. `optuna` · 22. `FinRL` · 23. `FinRL-Meta` · 24. `alcyone-trading-bot` · 25. `crypto-trading-bot` · 26. `crypto-regime-trading` · 27. `backtest-strategy-scanner-skill` · 28. `arb-bot` · 29. `dex-arbitrage` · 30. `mev-chaser` · 31. `polygon-mcp` · 32. `0x-ai`.

---

## 3. Matrice Completa dei 32 Repository

### GRUPPO A: CORE (8 da Acquisire Adesso)
| # | Componente | Repository GitHub | Licenza | Ruolo Esatto in TradeAID | Azione AGY |
|---|---|---|---|---|---|
| 1 | **Hummingbot Gateway** | `https://github.com/hummingbot/gateway` | Apache-2.0 | Middleware esecuzione Polygon (137), connettori 0x & Uniswap, allowance, balance. | `ACQUIRE_CORE` (P0) |
| 2 | **Hummingbot Core** | `https://github.com/hummingbot/hummingbot` | Apache-2.0 | Pattern arbitraggio, market making, lifecycle ordini e controller. | `ACQUIRE_CORE` (P0) |
| 3 | **0x Examples** | `https://github.com/0xProject/0x-examples` | MIT | Swap API v2, Permit2, AllowanceHolder, headless execution. (*No Settler allowance!*). | `ACQUIRE_CORE` (P0) |
| 4 | **0x AI** | `https://github.com/0xProject/0x-ai` | Apache-2.0 | Tooling/skills 0x per agenti AI, prompt templates e signing workflows. | `ACQUIRE_CORE` (P0) |
| 5 | **web3.py** | `https://github.com/ethereum/web3.py` | MIT | Base Python per RPC Polygon (137), EIP-1559 gas calculation e transazioni. | `ACQUIRE_CORE` (P0) |
| 6 | **eth-account** | `https://github.com/ethereum/eth-account` | MIT | Gestione chiavi crittografiche non-custodiali e firma atomica transazioni. | `ACQUIRE_CORE` (P0) |
| 7 | **viem** | `https://github.com/wevm/viem` | MIT | Client EVM ultra-leggero per TypeScript, PWA Cockpit e script web3. | `ACQUIRE_CORE` (P0) |
| 8 | **QuantStats** | `https://github.com/ranaroussi/quantstats` | Apache-2.0 | Analisi metrica di portafoglio (Sharpe, Calmar, MaxDD, Brier validation). | `ACQUIRE_CORE` (P0) |

---

### GRUPPO B: ROUTING & EXECUTION (5 da Clonare per Confronto & Design)
| # | Componente | Repository GitHub | Licenza | Ruolo Esatto in TradeAID | Azione AGY |
|---|---|---|---|---|---|
| 9 | **Uniswap SOR** | `https://github.com/Uniswap/smart-order-router` | GPL-3.0 | Route splitting, gas-aware routing su Polygon. *Non copiare codice per via di GPL*. | `STUDY_BENCHMARK` |
| 10| **Universal Router**| `https://github.com/Uniswap/universal-router` | GPL-3.0 / BSL | Routing moderno multihop/multitoken Uniswap V3. | `STUDY_BENCHMARK` |
| 11| **Uniswap Permit2** | `https://github.com/Uniswap/permit2` | AGPL-3.0 | Standard contrattuale per allowance atomica e signature transfers. | `STUDY_SECURITY` |
| 12| **DexGuru Meta Aggregator** | `https://github.com/dex-guru/meta-aggregation-api` | MIT / Custom | Pattern architetturale FastAPI `VIEW -> SERVICE -> PROVIDERS` (0x, 1inch, Uniswap). | `EXTRACT_PATTERN` |
| 13| **Transaction Simulation** | `https://github.com/router-protocol/TRANSACTION_SIMULATION` | MIT | Pipeline pre-firma su Chain 137: `BUILD TX -> SIMULATE -> CORTEX -> SIGN`. | `EXTRACT_PATTERN` |

---

### GRUPPO C: STRATEGY / BACKTEST / TOURNAMENT (7)
| # | Componente | Repository GitHub | Licenza | Ruolo Esatto in TradeAID | Azione AGY |
|---|---|---|---|---|---|
| 14| **Freqtrade** | `https://github.com/freqtrade/freqtrade` | GPL-3.0 | Framework per formati strategia, dry-run adattivo, hyperopt e protezioni. | `EXTRACT_PATTERN` |
| 15| **Freqtrade Strategies** | `https://github.com/freqtrade/freqtrade-strategies` | GPL-3.0 | Materia prima per il Strategy Tournament (da testare in OOS e cost model). | `WAREHOUSE_INPUT` |
| 16| **vectorbt** | `https://github.com/polakowo/vectorbt` | Apache-2.0 / CC | Backtest vettorializzato ultra-veloce per decine di migliaia di combinazioni DNA. | `RESEARCH_ONLY` |
| 17| **Backtrader** | `https://github.com/mementum/backtrader` | GPL-3.0 | Secondo engine indipendente per validazione incrociata delle strategie. | `RESEARCH_ONLY` |
| 18| **Optuna** | `https://github.com/optuna/optuna` | MIT | Motore bayesiano di ottimizzazione iperparametri e pesi del Council. | `INTEGRATE_OPT` |
| 19| **FinRL** | `https://github.com/AI4Finance-Foundation/FinRL` | MIT | Framework di ricerca per Deep Reinforcement Learning applicato al trading. | `RESEARCH_ONLY` |
| 20| **FinRL-Meta** | `https://github.com/AI4Finance-Foundation/FinRL-Meta` | MIT | Data layer e simulatore di mercato per addestramento modelli RL. | `RESEARCH_ONLY` |

---

### GRUPPO D: PREDICTIVE HEART (7 Reference Quantitative)
| # | Componente | Repository GitHub | Licenza | Ruolo Esatto in TradeAID | Azione AGY |
|---|---|---|---|---|---|
| 21| **Alcyone Trading Bot** | `https://github.com/msbel5/alcyone-trading-bot` | MIT | Architettura a 9 layer (trend, momentum, volatility, volume, sentiment, ML, Ichimoku). | `EXTRACT_DNA` |
| 22| **Enhanced Multi-Signal Bot** | `https://github.com/hamlou/crypto-trading-bot` | GPL-3.0 | Multi-strategy ensemble e multi-agent confirmation basato su regime. | `EXTRACT_DNA` |
| 23| **Crypto Regime Trading** | `https://github.com/jakejk1285/crypto-regime-trading` | MIT | PCA, K-Means per regime detection e dimensionamento dinamico della posizione. | `EXTRACT_DNA` |
| 24| **Market Regime Detection** | `https://github.com/taylorjmellon/market-regime-detection` | MIT | K-Means + Hidden Markov Models (HMM) per il nostro Regime Engine. | `EXTRACT_DNA` |
| 25| **Multimodal Forecasting + XAI** | `https://github.com/atishay2411/multimodal-crypto-forecasting-xai-sentiments` | MIT | Fusione OHLCV + Sentiment con N-BEATS/TFT e explainability (fondamento `WHY?`). | `EXTRACT_DNA` |
| 26| **Crypto Agentic Trader** | `https://github.com/weijuinlee/crypto-agentic-trader` | MIT | Struttura council: trend + momentum + mean reversion + FinBERT + cooldown. | `EXTRACT_DNA` |
| 27| **Backtest Strategy Scanner** | `https://github.com/ozik1967/backtest-strategy-scanner-skill` | MIT | Pipeline Market → Regime → Strategy Selection → Backtest. | `EXTRACT_DNA` |

---

### GRUPPO E: POLYGON / ARBITRAGE / MEV (4)
| # | Componente | Repository GitHub | Licenza | Ruolo Esatto in TradeAID | Azione AGY |
|---|---|---|---|---|---|
| 28| **Polygon Arbitrage (Rust)** | `https://github.com/shandilyabh/polygon_arbitrage` | MIT | Specifico Polygon 137, Uniswap V3 vs QuickSwap V3, prezzi on-chain, gas check. | `EXTRACT_DNA` |
| 29| **EVM Arbitrage Bot** | `https://github.com/shaspitz/arb-bot` | MIT | Pattern event-driven (DEX event -> spread -> direction -> profitability -> execute). | `EXTRACT_DNA` |
| 30| **DEX Arbitrage** | `https://github.com/alextcn/dex-arbitrage` | MIT | Concetti di routing multi-DEX e calcolo dimensione ottimale dello swap. | `RESEARCH_ONLY` |
| 31| **MEV Chaser** | `https://github.com/CorrM/mev-chaser` | MIT | Research ad alto rischio con `debug_trace_call` e WebSocket RPC su Chain 137. | `RESEARCH_ONLY` |

---

### GRUPPO F: POLYGON TOOLING (1)
| # | Componente | Repository GitHub | Licenza | Ruolo Esatto in TradeAID | Azione AGY |
|---|---|---|---|---|---|
| 32| **Polygon MCP** | `https://github.com/Dbillionaer/polygon-mcp` | MIT | Connettore MCP per quote Uniswap V3, gas estimation e simulazione Polygon. | `TOOLING_MCP` |

---

## 4. Cosa Costituisce la "Ciccia Proprietaria" di TRADEAID

Il 70–80% dell'infrastruttura commodity (connettori DEX, RPC, parser matematici) viene riusato e orchestrato da questi 32 progetti.  
**Il valore proprietario esclusivo di TRADEAID rimane:**
1. **PREDICTIVE HEART**: Proiezione dinamica della doppia traiettoria (linea bianca storica + linea rossa P50 + fascia probabilistica P10-P90).
2. **Prediction Fusion Engine**: Il combinatore dei 7 modelli quantitativi con spiegabilità `WHY?`.
3. **Continuous Calibration Ledger**: Il validatore forecast vs actual che misura il Brier Score per ogni previsione.
4. **Strategy DNA & 10-Agent Council**: Il set di agenti specializzati orchestrati da MetaStrategy.
5. **CORTEX Risk Veto**: Regole inviolabili non-custodiali, slippage gate `< 0.30%` e hard emergency stop `-5.0%`.
6. **Position Guardian H24**: Il supervisore h24 con break-even lock a `+1.0%` e trailing stop a `+1.8%`.
7. **PWA Mobile Cyberpunk Cockpit**: Interfaccia dove **HOME = HEART**.
