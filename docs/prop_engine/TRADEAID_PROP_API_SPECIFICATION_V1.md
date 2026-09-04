# TRADEAID PROP & AUTOTRADE API SPECIFICATION — V1.1
**Architettura a 4 Domini, Event-Driven, Idempotente con Multi-Ledger Contabile**  
**Versione:** 1.1.0  
**Base URL:** `https://trade.cryptoaid.support/api/v1` (o `http://localhost:8000/api/v1`)  
**Ecosistema:** 81+ GLOBAL MASTER / Blockchain Plus Federation  

---

## 1. I Quattro Domini API & I Quattro Soldi Diversi

La piattaforma opera suddividendo nettamente la logica in **4 Domini API Indipendenti** e trattando **4 nature di denaro differenti** che non devono mai essere confuse a livello di database, API o interfaccia utente.

### Matrice delle 4 Nature di Denaro ("I Quattro Soldi Diversi"):

| Valuta / Moneta | Natura Finanziaria | Prelevabile? | Tabella DB / Ledger | Note Operative |
| :--- | :--- | :--- | :--- | :--- |
| **1. 10,000 USDT PAPER** | Simulazione pura | **NO** | `paper_accounts` / `autotrade_runs_v1` / `challenges` | Capitale virtuale usato per testare le strategie senza rischio per l'utente. |
| **2. Challenge Fee / Run Fee** | Denaro Reale (10 POL o USDT) | **NO** | `onchain_events` / `user_financial_profile` | Versato dall'utente per attivare la Challenge o il Run. In caso di fail genera TAC. |
| **3. Trading Credit (TAC)** | Credito Margine Interno | **NO** | `ledger_trading_credits` | Generato da fee convertite (`1 TAC = $1 USDT Margin`). Usabile per retry e sconti. |
| **4. POL / USDT Reward** | Guadagno Reale Certificato | **SÌ** | `ledger_withdrawable_rewards` / `reward_reservations` | Pagato unicamente dal budget allocato nel Reward Pool mensile (no debito fantasma). |

---

## 2. Dominio 1: AUTOTRADE (10 POL → 1 Run → 2 POL Reward)

Modello economico del run:
`USER → 10 POL (On-Chain) → B+ DAO/Treasury → AUTOTRADE RUN #123 → PAPER EXECUTION → RESULT`
- Se `WIN` (P&L netto positivo dopo tutti i costi simulati di gas, DEX fee e slippage): **2 POL Reward Reale**.
- Se `LOSS`: **0 POL**.

### `POST /api/v1/autotrade/runs`
Avvia una sessione di Autotrade. Ingesta il pagamento di 10 POL, prenota 2 POL dal pool ed emette il run id.
*   **Request Body (`application/json`):**
    ```json
    {
      "user_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
      "wallet": "0x71C3FB99A2f342898B681ab3cDDFd132d7877B29",
      "activation_tx_hash": "0x4a8f9c...",
      "activation_amount_atomic": "10000000000000000000",
      "strategy": "BALANCED",
      "idempotency_key": "run_01"
    }
    ```
*   **Response `200 OK`:**
    ```json
    {
      "status": "RUN_INITIALIZED",
      "run": {
        "run_id": "8f3b201a-6d12-4c20-a7d1-0f72782bcf21",
        "paper_start_balance": 10000.0,
        "result": "RUNNING",
        "reward_status": "RESERVED"
      },
      "contract_model": "10 POL -> 10,000 USDT PAPER -> IF NET WIN: 2 POL REWARD"
    }
    ```

### `GET /api/v1/autotrade/runs/{run_id}`
Stato, saldo paper corrente e progresso del run.

### `POST /api/v1/autotrade/{run_id}/stop`
Conclusione della sessione di autotrade.
*   **Request Body:**
    ```json
    {
      "gross_pnl": 150.25,
      "execution_costs": 12.50,
      "net_pnl": 137.75,
      "result": "WIN",
      "strategy_final": "TREND_FOLLOWING_V3"
    }
    ```
*   **Response `200 OK`:** Sblocca i 2 POL in `ledger_withdrawable_rewards` o rilascia la prenotazione se `LOSS`.

### `GET /api/v1/autotrade/{run_id}/decisions`
Audit trail di tutte le decisioni CORTEX, Meta Agent e switch di strategia eseguiti durante il run.

### `GET /api/v1/autotrade/{run_id}/trades`
Tutti i trade eseguiti con relative metriche di execution economics (`quoted_price`, `simulated_fill_price`, `gas_usdt`, `dex_fee_usdt`, `slippage_bps`).

---

## 3. Dominio 2: PROP (Challenge Tiers, Lifecycle, DD Violations)

### `GET /api/v1/prop/tiers`
Restituisce i 4 Tiers ufficiali (STARTER $10k, PRO $50k, ELITE $100k, BLACK $150k).

### `POST /api/v1/prop/challenges`
Inizializza una nuova istanza di Prop Challenge.
*   **Request Body:**
    ```json
    {
      "user_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
      "tier_id": 2
    }
    ```

### `GET /api/v1/prop/challenges/{id}`
Dettaglio completo dello stato macchina della challenge.

### `GET /api/v1/prop/challenges/{id}/progress`
Metriche in tempo reale:
- Percentuale di profitto rispetto al target (+8%).
- Percentuale di Daily DD rispetto al limite (5.00%).
- Percentuale di Total DD rispetto al limite (10.00%).

### `GET /api/v1/prop/challenges/{id}/violations`
Audit di eventuali violazioni che hanno provocato lo stato `FAILED` (`DAILY_DD`, `TOTAL_DD`, `CORTEX_VETO`).

---

## 4. Dominio 3: HEART (Predictive Heart & Spiegazione Decisioni)

### `GET /api/v1/heart/{asset}/forecast`
Previsione a 1s / 1m / 5m generata dal Predictive Heart (direzione, confidenza, expected return, bounds).

### `GET /api/v1/heart/{asset}/history`
Storico delle previsioni con calibrazione statistica, Brier Score e hit rate di direzione.

### `GET /api/v1/heart/{asset}/why`
Spiegazione trasparente della filiera decisionale:
**WHITE (Previsione) → RED (CORTEX Risk Gate) → DECISION (Position Sizing & Leva)**.
Restituisce evidenze, pesi degli agenti e motivi di eventuale ridimensionamento della size o veto.

---

## 5. Dominio 4: FINANCE (Contabilità a 4 Valute, Ledgers, Payouts)

### `GET /api/v1/wallet?identifier=0x...`
Riepilogo profilo finanziario utente (ID, wallet Polygon, federazione SIC-ID, stato KYC).

### `GET /api/v1/credits?identifier=0x...`
Estratto conto del Ledger 2: crediti di margine TAC non prelevabili (`1 TAC = $1 USDT Margin`) generati da fee convertite.

### `GET /api/v1/rewards?identifier=0x...`
Estratto conto del Ledger 3: premi reali prelevabili, hash transazioni on-chain e stato vesting/lock.

### `GET /api/v1/ledger?identifier=0x...`
Prospetto consolidato delle 4 nature di denaro per auditing contabile.

### `POST /api/v1/rewards/withdraw`
Richiesta prelievo premi reali maturati.
*   **Request Body:**
    ```json
    {
      "user_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
      "amount": 250.00,
      "destination_wallet": "0x71C3FB99A2f342898B681ab3cDDFd132d7877B29",
      "idempotency_key": "with_9b1deb4d_001"
    }
    ```

---

## 6. Sicurezza, Idempotenza & On-Chain Ingestion

1. **Idempotenza On-Chain (`onchain_events`)**:
   Ogni pagamento o reward registrato sulla blockchain Polygon viene indicizzato con vincolo di unicità `(chain_id, tx_hash, log_index)`. Tentativi multipli di replay attack o retry di rete vengono neutralizzati automaticamente.
2. **Reward Reservation Engine (`reward_reservations`)**:
   Prima che l'utente veda la promessa dei 2 POL nel proprio cockpit, il sistema riserva l'importo atomico dal `reward_pools`. Se il pool ha disponibilità insufficiente, l'attivazione della modalità con premio reale viene interrotta con codice d'errore trasparente.
3. **Audit Immutabile**:
   Nessuna cancellazione o sovrascrittura di record contabili. Ogni rettifica o conversione di credito genera una nuova transazione nel ledger append-only con riferimento alla causale (`source_event_id`).
