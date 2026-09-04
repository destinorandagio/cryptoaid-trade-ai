# TRADEAID V1 — LE 7 CHIUSURE OPERATIVE (END-TO-END)
**Milestone:** TRADEAID V1 Closed-Loop Machine  
**Status:** ARCHITETTURA CONGELATA — FASE DI CHIUSURA OPERATIVA  
**Asset Target Pilota:** POL/USDT (Polygon POS - Chain 137)  
**Data:** 2026-09-04  

---

## 1. La Dichiarazione di Congelamento

> **Stop all'espansione dell'architettura.**  
> Non si aggiungono altri repository o astrazioni. I pezzi infrastrutturali sono stati individuati e razionalizzati nei 10 componenti P0.  
> L'unico obiettivo ora è **trasformarli in una macchina end-to-end che dimostri di funzionare**.

### Il Ciclo Unico da Chiudere:
```text
POL/USDT reale sul grafico 
   ↓
Predictive Heart genera linea rossa (P10/P50/P90) 
   ↓
Strategy Council decide il consensus 
   ↓
CORTEX valuta e dà via libera (Risk Veto) 
   ↓
Smart Router trova la migliore esecuzione (0x / Uniswap / QuickSwap) 
   ↓
Paper Trade / Execution Engine 
   ↓
Position Guardian H24 gestisce (Break-even + Trailing + Hard Stop -5%) 
   ↓
Prediction vs Actual viene misurata (Brier Score & Calibration) 
   ↓
Telegram + PWA Cockpit mostrano l'intero ciclo in tempo reale.
```

---

## 2. Le 7 Chiusure Sequenziali

```text
 ┌─────────────────────────────────────────────────────────────┐
 │ 1. PREDICTIVE HEART V1 REALE                                │
 │    Serie tick reali → Traiettoria Rossa → Forecast Logging  │
 └──────────────────────────────┬──────────────────────────────┘
                                │
                                ▼
 ┌─────────────────────────────────────────────────────────────┐
 │ 2. STRATEGY FACTORY & REGIME ROUTER                         │
 │    Council 10 Agenti → Regime Engine → MetaStrategy DNA     │
 └──────────────────────────────┬──────────────────────────────┘
                                │
                                ▼
 ┌─────────────────────────────────────────────────────────────┐
 │ 3. TOURNAMENT AUTOMATICO & ANTI-BIAS LINTER                 │
 │    Backtest → OOS → Walk-Forward → Costi DEX → Paper        │
 └──────────────────────────────┬──────────────────────────────┘
                                │
                                ▼
 ┌─────────────────────────────────────────────────────────────┐
 │ 4. POLYGON EXECUTION STACK                                  │
 │    Router → Quotes → Slippage Gate → Simulazione → Signer   │
 └──────────────────────────────┬──────────────────────────────┘
                                │
                                ▼
 ┌─────────────────────────────────────────────────────────────┐
 │ 5. POSITION GUARDIAN H24                                    │
 │    SL / TP / Trailing / Break-even lock / Invalidation      │
 └──────────────────────────────┬──────────────────────────────┘
                                │
                                ▼
 ┌─────────────────────────────────────────────────────────────┐
 │ 6. COCKPIT PWA + TELEGRAM TELECOMANDO                       │
 │    Home = HEART · Dashboard reattiva · Bot comandi rapidi   │
 └──────────────────────────────┬──────────────────────────────┘
                                │
                                ▼
 ┌─────────────────────────────────────────────────────────────┐
 │ 7. LIVE GATE (TRANSAZIONE REALE MINIMA)                     │
 │    Wallet dedicato → Cifra test → Ciclo completo → Audit    │
 └─────────────────────────────────────────────────────────────┘
```

---

### Dettaglio delle 7 Chiusure

### Chiusura 1: Predictive Heart V1 Reale
- **Cosa fa:** Costruire il modulo Python di forecast probabilistico che ingerisce le serie storiche reali POL/USDT (da Polygon RPC / DexScreener / Binance feed) e produce:
  - Linea bianca: storico consolidato.
  - Punto NOW: confine temporale tick corrente.
  - Linea rossa (P50): traiettoria consensuale a 5m, 15m, 1h, 4h, 24h.
  - Fascia P10 - P90: corridoio di volatilità/incertezza.
- **Validatore Forecast vs Actual:** Ogni proiezione emessa viene salvata in SQLite/JSON con timestamp di scadenza. All'avverarsi del tempo, il worker confronta il prezzo effettivo con la proiezione, calcolando errore assoluto, direzione indovinata e Brier score.
- **Obiettivo:** Sapere matematicamente se il cervello predice o se dipinge curve estetiche.

### Chiusura 2: Strategy Factory & MetaStrategy
- **Cosa fa:** Connettere i moduli di strategia (Scalping, Trend, Momentum, Breakout, Mean Reversion, Volatility, Sentiment, On-chain) con il `Regime Engine` (Trending Up, Trending Down, Ranging Tight, Volatile Expansion).
- **MetaStrategy:** Seleziona la combinazione ottimale di DNA e pesi in base al regime attivo.

### Chiusura 3: Tournament Automatico
- **Cosa fa:** Pipeline continuativa per selezionare le strategie che meritano allocazione:
  `BACKTEST → OUT-OF-SAMPLE → WALK-FORWARD → COSTI DEX (gas + 0.30% slippage) → PAPER → PROMOTE/DEMOTE/KILL`.
- **CORTEX Research Gate:** Integrazione del linter anti-bias (`backtest-truth`) per stroncare look-ahead bias e overfitting da hyperopt.

### Chiusura 4: Polygon Execution Stack
- **Cosa fa:** Chiusura della pipeline d'ordine per POL/USDT:
  `USDT → Smart Router → Quote 0x vs Uniswap vs QuickSwap → Slippage & Price Impact Check (< 0.30%) → Simulazione pre-firma (RPC eth_call) → CORTEX Veto Pass → Automatic Wallet Signer (web3.py) → Swap on-chain → Receipt`.
- **Regola di Sicurezza:** 5% è l'hard emergency stop della posizione nel Guardian, **NON lo slippage ammesso** (che resta rigorosamente `< 0.30%`).

### Chiusura 5: Position Guardian H24
- **Cosa fa:** Il demone che vigila 24/7 su ogni posizione aperta:
  - Break-even lock: sposta lo Stop Loss al prezzo di carico non appena il PnL tocca `+1.0%`.
  - Trailing stop dinamico: si attiva a `+1.8%` per catturare trend estesi.
  - Invalidation trigger: chiude la posizione se la traiettoria del Predictive Heart si capovolge.
  - Hard stop loss: liquidazione a mercato istantanea al `-5.0%`.

### Chiusura 6: Cockpit PWA + Telegram
- **Cosa fa:**
  - PWA (`trade.cryptoaid.support`): **Home = HEART** (Grafico bianco/rosso, telemetria 5 metriche, `WHY?` modal con pesi Council, 6 sezioni).
  - Telegram: Notifiche istantanee all'apertura trade, chiusura Guardian, report di calibrazione e comandi di emergenza (`/status`, `/kill`, `/positions`).

### Chiusura 7: Live Gate
- **Cosa fa:** Solo dopo che il ciclo in paper ha accumulato calibrazione positiva:
  - Configurazione wallet di trading dedicato (non il vault principale).
  - Deposito minimo iniziale (es. 25-50 POL/USDT, non 1.000 USDT).
  - Esecuzione primo trade live end-to-end con firma reale on-chain.
  - Monitoraggio del Position Guardian sul trade live.
  - Chiusura a target o a trailing stop.
  - Contabilizzazione nel ledger e test del Kill-Switch.

---
**Congelato e Approvato:**  
*TradeAID Operational Team — NEURALOG / BLOCKCHAIN+*
