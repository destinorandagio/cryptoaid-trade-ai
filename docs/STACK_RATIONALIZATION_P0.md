# TRADEAID — STACK RATIONALIZATION & 10 COMPONENTI P0
**Document Version:** 1.0.0-GOLDEN-MASTER  
**Security & Architecture Standard:** NEURALOG / BLOCKCHAIN+ / CORTEX  
**Data di Congelamento:** 2026-09-04  

---

## 1. Visione Strategica: Dal "Caos dei 100 Repository" ai 10 Componenti P0

Non costruiamo 100 micro-repository e non reinventiamo la ruota infrastrutturale. Il framework si articola su:
- **P0 (10 Componenti Critici):** Esecuzione live, routing, simulazione, signing e backtesting.
- **P1 (~8 Componenti di Ricerca):** Predictive Heart (5 motori analitici + fusion), scanner arbitraggio on-chain, ranking dinamico.
- **P2 (10–20 Candidati di Magazzino):** Materiale scientifico/benchmark tenuto nel warehouse (`tradeaid-research`) senza inquinare il runtime di trading.

### Ruolo di Forgejo vs GitHub
- **GitHub (`destinorandagio/cryptoaid-trade-ai`):** Control plane primario, sviluppo attivo, trigger CI/CD e audit team.
- **Forgejo:** **NON è un motore di trading**. È il mirror sovrano, self-hosted Git, backup distribuito e secondario CI offline. Non è nel critical path operativo del bot.
- **I 3 Repository Canonici:**
  1. `cryptoaidsupport`: Risk rules, Knowledge items, Security specifications, shared utilities.
  2. `cryptoaid-trade-ai`: Runtime di produzione, Predictive Heart, PWA, Smart Router, Signer, Guardian.
  3. `tradeaid-research`: Digital Twin di trader/software, Strategy DNA, dataset storici, esperimenti tournament.

---

## 2. La Matrice dei 10 Componenti P0

| # | Dominio Funzionale | Scelta Open-Source / Pattern | Utilizzo Esatto in TRADEAID |
|---|---|---|---|
| **1** | **DEX Execution Middleware** | **Hummingbot Gateway** | Connettore unificato Polygon POS (Chain 137). Gestione wallet, balance, allowance, 0x e Uniswap execution nativa. |
| **2** | **DEX Aggregator Primario** | **0x Swap API v2** | Algoritmo di routing primario con quote ottimali, gasless e Permit2 integration. |
| **3** | **Second Router & Fallback** | **Uniswap Router / SOR** | Smart Order Router per confronto quote, pool concentrate V3 e failover. |
| **4** | **Meta-Router Architetturale** | **DexGuru Meta Aggregation** | Pattern architetturale FastAPI `VIEW -> SERVICE -> PROVIDERS` per normalizzare 1inch/0x/Uniswap/ParaSwap. |
| **5** | **Transaction Simulation** | **Router Protocol Simulator + RPC** | Simulazione pre-firma su Chain 137 con whitelist token e controllo revert/state override. |
| **6** | **Wallet & EVM Signer** | **web3.py / eth-account** | Firma crittografica transazioni non-custodiale, calcolo nonce atomico e priority fee. |
| **7** | **Strategy Research & Format** | **Freqtrade / FreqAI** | Standardizzazione formati strategia, hyperopt, dry-run adattivo e persistence SQLite. |
| **8** | **DEX Trading Patterns** | **Hummingbot Core** | Pattern architetturali di Arbitraggio, Market Making, controller e order lifecycle. |
| **9** | **Backtest Tournament Engine** | **vectorbt + Optuna + backtest-truth** | Simulazioni vettorializzate ad altissima velocità + linter contro look-ahead bias e overfitting. |
| **10**| **Performance & Calibration** | **QuantStats + Ledger TradeAID** | Metriche istituzionali (Sharpe, Calmar, Max Drawdown) + Brier Score per calibrazione forecast. |

---

## 3. Regole Tecniche Invalicabili

### 3.1 0x Swap API v2 & Sicurezza Allowance (Permit2)
> [!CAUTION]
> **REGOLA AUREA PER AGY E DEVELOPERS:**  
> **MAI concedere allowance al contratto `Settler`**.  
> L'approvazione token ERC20 (USDT / WETH / POL) deve essere indirizzata **ESCLUSIVAMENTE** a `Permit2` o all'`AllowanceHolder` esplicitamente restituito dalla risposta Swap API v2. Qualsiasi deviazione costituisce una vulnerabilità critica di sicurezza e viene bloccata da CORTEX.

### 3.2 La Sequenza di Esecuzione Pre-Firma
Nessuna transazione può essere firmata senza superare la gate di simulazione e il veto CORTEX:
```text
[QUOTE RICEVUTA] 
      ↓
[BUILD TRANSACTION RAW]
      ↓
[SIMULAZIONE ON-CHAIN (Router Protocol / eth_call)]
      ↓
[CORTEX RISK VETO CHECK (Slippage < 0.30%, Max Drawdown, Destinazione)]
      ↓
[FIRMA ED INVIO RPC (Automatic Signer)]
```
*(Mai passare direttamente da Quote a Signer).*

### 3.3 Meta-Router Pattern (DexGuru Inspiration)
Normalizzatore agnostico delle quote:
```text
TRADEAID SMART ROUTER
├── 0x Swap API v2 Quote
├── Uniswap V3 SOR Quote
└── QuickSwap V3 Direct Quote
       ↓
QUOTE NORMALIZER (FastAPI Service Layer)
       ↓
NET EXECUTION COMPARATOR
(Output Net = Gross Output - Gas Cost - Dex Fees - Est. Slippage - MEV Buffer)
       ↓
MIGLIOR ROUTE CERTIFICATA
```

### 3.4 CORTEX Research Gate: `backtest-truth`
Ogni strategia proposta dal Multi-Agent Council o importata dall'ecosistema Freqtrade/open-source non viene inserita nel Tournament senza passare il linter `backtest-truth`:
1. Rilevamento di **Look-Ahead Bias** (accesso a barre future nei calcoli).
2. Verifica di **Costi Irrealistici** (slippage zero, gas nullo su Polygon).
3. Rilevamento di **Overfitting da Hyperopt** (test su finestre Out-Of-Sample e Walk-Forward Analysis).

### 3.5 Arbitraggio Polygon: Pattern Rust
- **Scanner Attivo (P1):** Comparatore bidirezionale Uniswap V3 vs QuickSwap V3 basato su prezzi on-chain tick-by-tick e threshold di profitto netto coprente il gas.
- **Esecuzione Flash-Loan Live:** Differita a fase P2 post-certificazione audit.

---

## 4. Proprietà Intellettuale TradeAID vs Componenti Open Source

| Cosa Riusiamo da Open Source | Cosa è Proprietà Esclusiva TRADEAID |
|---|---|
| • Connettività DEX (Hummingbot Gateway) | • **PREDICTIVE HEART** (traiettoria bianca/rossa P10-P90) |
| • Algoritmi di Quote (0x API v2, Uniswap SOR) | • **Prediction Fusion Engine** (7 modelli fusi) |
| • Framework di Simulazione (Router Protocol) | • **Strategy DNA** (codice genetico dei 10 agenti) |
| • Calcolo vettoriale backtesting (vectorbt) | • **Regime Engine** (classificazione probabilistica) |
| • Linter anti-bias (`backtest-truth`) | • **CORTEX Risk Veto** (regole non-custodiali Polygon) |
| • Reporting statistico (QuantStats) | • **Capital Allocator & Position Guardian H24** |
| • Architettura normalizzatore (DexGuru) | • **UI/UX Cyberpunk Mobile PWA (HOME = HEART)** |

---
**Firmato e Registrato:**  
*TradeAID Engineering Team — NEURALOG / BLOCKCHAIN+*
