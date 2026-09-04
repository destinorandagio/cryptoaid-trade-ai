# TRADEAID PROP ENGINE — SPECIFICA API BACKEND V1.0
**Documento Tecnico di Architettura REST & WebSocket**  
**Versione:** 1.0.0  
**Base URL:** `https://trade.cryptoaid.support/api/v1` (o `http://localhost:8000/api/v1`)  
**Ecosistema:** 81+ GLOBAL MASTER / TradeAID Prop & Digital Twins  

---

## 1. Principi Architetturali & Standard di Sistema

1. **Separazione Rigorosa dei 3 Ledger**:
   - **Ledger 1 (Prop Virtual Equity)**: Capitale virtuale simulato per le Challenge (`$10,000` - `$150,000`).
   - **Ledger 2 (Trading Credits / TAC)**: Crediti di margine non prelevabili (`1 TAC = 1 USDT Margin`) generati automaticamente dalla conversione delle fee di challenge fallite (`CONVERSION_FROM_FEE`).
   - **Ledger 3 (Withdrawable Rewards)**: Profitti reali prelevabili, accreditati unicamente in base all'allocazione certificata del Reward Pool mensile (elimina qualsiasi debito fantasma).
2. **Doppia Autenticazione Federata (Dual Auth)**:
   - **Web3 Wallet**: Indirizzo Polygon compatibile EVM (`0x...`) con firma crittografica EIP-712/Personal Sign.
   - **Federazione SIC-ID**: Identificativo Digital Twin canonico conforme allo standard `81PLUS_GLOBAL_MASTER` (`^SIC-ID-[A-Z0-9]{12}$`, 19 caratteri in Base32 Crockford).
   - **Stati Identità**: `WALLET` (solo Web3), `SIC_ID` (solo Digital Twin), `HYBRID` (legati biunivocamente).
3. **Idempotenza & Auditabilità Immutabile**:
   - I saldi in `user_financial_profile` sono mere cache di lettura; la fonte di verità contabile sono i log transazionali append-only `ledger_trading_credits` e `ledger_withdrawable_rewards`.
4. **Enforcement Drawdown in Tempo Reale**:
   - **Daily Drawdown (5.00%)**: Calcolato rispetto all'equity registrata allo snapshot di mezzanotte UTC (`start_of_day_balance`).
   - **Max Total Drawdown (10.00%)**: Calcolato rispetto al picco massimo storico (`high_water_mark`).
   - Alla violazione: transizione immediata a `FAILED` e trigger di conversione fee in TAC.

---

## 2. Tabella Sinottica degli Endpoints

| Metodo | Endpoint | Descrizione | Autenticazione |
| :--- | :--- | :--- | :--- |
| `POST` | `/auth/session` | Login/Registrazione con Web3 Wallet o `SIC-ID` | Pubblico |
| `POST` | `/auth/link-sic-id` | Associazione di un Web3 Wallet a un SIC-ID (Stato `HYBRID`) | Sessione Attiva |
| `GET` | `/auth/user/{identifier}` | Profilo utente tramite UUID, Wallet o `SIC-ID` | Pubblico / Bearer |
| `GET` | `/prop/tiers` | Configurazione dei 4 Challenge Tier istituzionali | Pubblico |
| `POST` | `/prop/challenge/create` | Iscrizione e creazione nuova Challenge | Bearer / User ID |
| `GET` | `/prop/challenge/{id}` | Stato Challenge, metriche DD e stato macchina | Bearer / User ID |
| `POST` | `/prop/challenge/{id}/trade` | Esecuzione trade AI/Paper e mark-to-market | Internal Worker / Bot |
| `POST` | `/prop/challenge/{id}/snapshot` | Snapshot giornaliero UTC e verifica Daily DD | Midnight Cron / Worker |
| `GET` | `/prop/ledgers/{identifier}` | Estratto conto consolidato dei 3 Ledger | Bearer / User ID |
| `POST` | `/prop/payout/request` | Richiesta prelievo premi reali dal Reward Pool | Bearer (Stato `HYBRID`) |
| `GET` | `/prop/leaderboard/current` | Classifica mensile e capienza Reward Pool | Pubblico |
| `WS` | `/ws/prop/challenge/{id}` | Stream WebSocket in tempo reale (Tick, PnL, Alert DD) | Session Token |

---

## 3. Specifica Dettagliata delle API

### 3.1 Autenticazione & Identità Federata

#### `POST /auth/session`
Inizializza una sessione utente. Accetta in alternativa o congiuntamente un wallet Polygon o un `SIC-ID`.

**Request Body (`application/json`):**
```json
{
  "wallet_address": "0x71C...B29",         // Opzionale se sic_id fornito
  "signature": "0x4a8f...",                 // Opzionale (firma crittografica Web3)
  "sic_id": "SIC-ID-NRBVE3T5E5NX",         // Opzionale se wallet fornito (Regex: ^SIC-ID-[A-Z0-9]{12}$)
  "email": "trader@example.com",            // Opzionale
  "telegram_id": 123456789                  // Opzionale
}
```

**Response `200 OK`:**
```json
{
  "status": "AUTHENTICATED",
  "user": {
    "user_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
    "wallet_address": "0x71C...B29",
    "sic_id": "SIC-ID-NRBVE3T5E5NX",
    "auth_method": "HYBRID",
    "kyc_status": "PENDING",
    "created_at": "2026-09-04T18:00:00Z"
  },
  "financial_profile": {
    "trading_credit_balance": 150.00,
    "withdrawable_reward_balance": 500.00,
    "total_fees_paid": 650.00,
    "last_challenge_tier": "PRO",
    "status": "ACTIVE"
  },
  "auth_method": "HYBRID",
  "session_token": "sess_9b1deb4d_1788553200",
  "ecosystem": "81PLUS_BLOCKCHAIN_PLUS_FEDERATION"
}
```

---

#### `POST /auth/link-sic-id`
Associa un indirizzo on-chain Polygon a un SIC-ID Digital Twin già esistente.

**Request Body:**
```json
{
  "user_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
  "wallet_address": "0x71C3FB99A2f342898B681ab3cDDFd132d7877B29",
  "sic_id": "SIC-ID-NRBVE3T5E5NX"
}
```

---

### 3.2 Challenge & Tiers

#### `GET /prop/tiers`
Restituisce i 4 tiers ufficiali con tutti i vincoli operativi.

**Response `200 OK`:**
```json
[
  {
    "tier_id": 1,
    "name": "STARTER",
    "fee_usdt": 50.00,
    "nominal_capital": 10000.00,
    "phase1_target_pct": 8.00,
    "phase2_target_pct": 5.00,
    "max_daily_dd_pct": 5.00,
    "max_total_dd_pct": 10.00,
    "min_trading_days": 5,
    "is_active": true
  },
  {
    "tier_id": 2,
    "name": "PRO",
    "fee_usdt": 100.00,
    "nominal_capital": 50000.00,
    "phase1_target_pct": 8.00,
    "phase2_target_pct": 5.00,
    "max_daily_dd_pct": 5.00,
    "max_total_dd_pct": 10.00,
    "min_trading_days": 5,
    "is_active": true
  },
  {
    "tier_id": 3,
    "name": "ELITE",
    "fee_usdt": 500.00,
    "nominal_capital": 100000.00,
    "phase1_target_pct": 8.00,
    "phase2_target_pct": 5.00,
    "max_daily_dd_pct": 5.00,
    "max_total_dd_pct": 10.00,
    "min_trading_days": 5,
    "is_active": true
  },
  {
    "tier_id": 4,
    "name": "BLACK",
    "fee_usdt": 1500.00,
    "nominal_capital": 150000.00,
    "phase1_target_pct": 8.00,
    "phase2_target_pct": 5.00,
    "max_daily_dd_pct": 5.00,
    "max_total_dd_pct": 10.00,
    "min_trading_days": 5,
    "is_active": true
  }
]
```

---

#### `POST /prop/challenge/create`
Attiva una nuova istanza di Challenge per l'utente, scalando o registrando la fee nel profilo.

**Request Body:**
```json
{
  "user_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
  "tier_id": 2
}
```

**Response `201 Created`:**
```json
{
  "status": "CREATED",
  "challenge": {
    "challenge_id": "e4f8845c-0c15-4674-8aa7-71a221f422eb",
    "user_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
    "tier_id": 2,
    "tier": {
      "name": "PRO",
      "fee_usdt": 100.00,
      "nominal_capital": 50000.00,
      "phase1_target_pct": 8.00,
      "max_daily_dd_pct": 5.00,
      "max_total_dd_pct": 10.00,
      "min_trading_days": 5
    },
    "status": "PHASE_1_QUALIFICATION",
    "starting_balance": 50000.00,
    "current_balance": 50000.00,
    "high_water_mark": 50000.00,
    "phase1_start_date": "2026-09-04T18:00:00Z"
  },
  "message": "Challenge created under tier PRO. Starting virtual capital: $50,000.00"
}
```

---

### 3.3 Gestione Trade & Snapshot di Calcolo Drawdown

#### `POST /prop/challenge/{challenge_id}/trade`
Registra un'operazione eseguita dal bot AI o dal trader nella challenge virtuale.

**Request Body:**
```json
{
  "asset_canonical_id": "CA-L1-0001",    // BTC
  "direction": "LONG",                   // LONG o SHORT
  "entry_price": 59120.50,
  "exit_price": 60250.00,
  "quantity": 0.50000000,
  "leverage_used": 2,
  "strategy_id": "PREDICTIVE_HEART_V1",
  "ai_confidence": 0.88
}
```

**Logica Interna di Esecuzione:**
1. Calcola il PnL: `pnl_usdt = (exit_price - entry_price) * quantity * leverage`.
2. Aggiorna `current_balance` e ricalcola `high_water_mark = MAX(high_water_mark, current_balance)`.
3. Controlla `total_drawdown_pct = ((high_water_mark - current_balance) / high_water_mark) * 100`.
4. Se `total_drawdown_pct > max_total_dd_pct`:
   - Cambia status a `FAILED`.
   - Imposta `violation_type = 'TOTAL_DD'`.
   - Genera transazione in `ledger_trading_credits` convertendo la fee in crediti TAC.

---

#### `POST /prop/challenge/{challenge_id}/snapshot`
Endpoint cron/worker invocato ogni mezzanotte UTC per calcolare e archiviare il Daily Drawdown.

**Request Body:**
```json
{
  "snapshot_date": "2026-09-04",
  "start_of_day_balance": 50000.00,
  "end_of_day_balance": 47200.00,
  "daily_pnl": -2800.00,
  "daily_dd_pct": 5.60
}
```

**Comportamento Automatico di Salvaguardia:**
- `max_daily_dd_pct` per il tier PRO = `5.00%`.
- Poiché `5.60% > 5.00%`, il backend:
  1. Marca la challenge come `FAILED`.
  2. Inserisce un record in `challenge_daily_snapshots`.
  3. Inserisce un record in `ledger_trading_credits` con importo pari a `fee_usdt` ($100.00) e causale:
     `CONVERSION_FROM_FEE: Automated fee conversion from failed challenge e4f8845c (Daily DD breached: 5.60% > 5.00%)`.
  4. Aggiorna istantaneamente il saldo in `user_financial_profile.trading_credit_balance`.

**Response `200 OK`:**
```json
{
  "snapshot": {
    "snapshot_id": 42,
    "challenge_id": "e4f8845c-0c15-4674-8aa7-71a221f422eb",
    "snapshot_date": "2026-09-04",
    "daily_dd_pct": 5.60,
    "daily_pnl": -2800.00
  },
  "breached": true,
  "challenge_status": "FAILED",
  "trading_credit_granted": 100.00,
  "reason": "DAILY_DD_EXCEEDED"
}
```

---

### 3.4 Contabilità Trasparente dei 3 Ledgers

#### `GET /prop/ledgers/{identifier}`
Consolida lo stato contabile dell'utente leggendo dai 3 ledgers separati. L'`identifier` può essere `user_id`, `0x...` wallet, o `SIC-ID-...`.

**Response `200 OK`:**
```json
{
  "user": {
    "user_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
    "wallet_address": "0x71C3FB99A2f342898B681ab3cDDFd132d7877B29",
    "sic_id": "SIC-ID-NRBVE3T5E5NX",
    "auth_method": "HYBRID"
  },
  "profile": {
    "trading_credit_balance": 100.00,
    "withdrawable_reward_balance": 450.00,
    "total_fees_paid": 100.00
  },
  "ledger_1_prop_equity": {
    "description": "Virtual Paper Trading Balance & Challenges",
    "total_active_challenges": 0,
    "challenges": [
      {
        "challenge_id": "e4f8845c-0c15-4674-8aa7-71a221f422eb",
        "tier_name": "PRO",
        "nominal_capital": 50000.00,
        "status": "FAILED",
        "violation_type": "DAILY_DD"
      }
    ]
  },
  "ledger_2_trading_credits": {
    "description": "Non-Withdrawable Margin Credits (TAC) from Failed Challenge Fees",
    "balance_tac": 100.00,
    "history": [
      {
        "transaction_id": 101,
        "amount": 100.00,
        "type": "CONVERSION_FROM_FEE",
        "balance_after": 100.00,
        "description": "Automated fee conversion from failed challenge e4f8845c",
        "created_at": "2026-09-04T18:05:00Z"
      }
    ]
  },
  "ledger_3_withdrawable_rewards": {
    "description": "Real Approved Payouts & Leaderboard Rewards",
    "balance_usdt": 450.00,
    "history": [
      {
        "transaction_id": 204,
        "amount": 450.00,
        "type": "REWARD_POOL_PAYOUT",
        "status": "UNLOCKED",
        "tx_hash": "0x89ab...ef12",
        "created_at": "2026-09-01T12:00:00Z"
      }
    ]
  }
}
```

---

### 3.5 Reward Pool & Payout Reali

#### `GET /prop/leaderboard/current`
Visualizza la classifica ufficiale e il budget certificato del mese.

**Response `200 OK`:**
```json
{
  "reward_pool": {
    "pool_id": 9,
    "month": 9,
    "year": 2026,
    "total_budget_usdt": 10000.00,
    "distributed_usdt": 4500.00,
    "status": "OPEN"
  },
  "leaderboard": [
    {
      "rank": 1,
      "user_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
      "wallet_address": "0x71C...B29",
      "sic_id": "SIC-ID-NRBVE3T5E5NX",
      "total_return_pct": 14.85,
      "consistency_score": 92.40,
      "reward_amount": 2500.00
    }
  ],
  "solvency_model": "Budgeted Monthly Allocation (Anti-Ghost Debt)"
}
```

---

## 4. Specifiche WebSocket in Tempo Reale

### Canale: `ws://trade.cryptoaid.support/ws/prop/challenge/{challenge_id}`

Per alimentare il Cockpit senza barre di scorrimento e garantire feedback istantaneo ad ogni secondo di trading.

#### Flusso di Messaggi (Server -> Client):
1. **Ticker & Equity Update (`TICK_UPDATE`)**:
```json
{
  "event": "TICK_UPDATE",
  "challenge_id": "e4f8845c-0c15-4674-8aa7-71a221f422eb",
  "timestamp": "2026-09-04T18:10:01Z",
  "current_balance": 51240.50,
  "high_water_mark": 51240.50,
  "current_profit_pct": 2.48,
  "target_pct": 8.00,
  "daily_dd_current_pct": 0.45,
  "daily_dd_limit_pct": 5.00,
  "total_dd_current_pct": 0.00,
  "total_dd_limit_pct": 10.00
}
```

2. **Allerta Pre-Drawdown (`DRAWDOWN_WARNING`)**:
   Trasmesso quando `daily_dd_current_pct >= 4.00%` (80% del limite). Permette al bot AI di ridurre immediatamente la leva o chiudere posizioni speculative.
```json
{
  "event": "DRAWDOWN_WARNING",
  "severity": "HIGH",
  "message": "Daily Drawdown at 4.15% (Limit: 5.00%). AI Risk Gate enforcing deleveraging."
}
```

3. **Notifica Violazione & Conversione Fee (`CHALLENGE_FAILED_CONVERTED`)**:
```json
{
  "event": "CHALLENGE_FAILED_CONVERTED",
  "violation_type": "DAILY_DD",
  "credited_tac": 100.00,
  "new_tac_balance": 250.00,
  "message": "Challenge breached daily limit. Fee converted into 100 TAC Trading Credits."
}
```

---

## 5. Matrice di Gestione Errori & Codici HTTP

| Codice | Significato | Payload Errore Tipico |
| :--- | :--- | :--- |
| `400 Bad Request` | Formato non valido (es. regex SIC-ID errata o parametri trade incongruenti) | `{"detail": "Invalid SIC-ID format 'SIC-123'. Must be SIC-ID-XXXXXXXXXXXX"}` |
| `401 Unauthorized` | Firma Web3 o Session Token non valido | `{"detail": "Invalid or expired session credentials"}` |
| `403 Forbidden` | Richiesta prelievo reward per account senza Polygon wallet associato | `{"detail": "Wallet address required for on-chain payout. Link wallet via /auth/link-sic-id"}` |
| `404 Not Found` | Challenge, Tier o Utente inesistente | `{"detail": "Challenge 'e4f8845c' not found"}` |
| `409 Conflict` | Tentativo di legare un SIC-ID già assegnato a un altro wallet | `{"detail": "SIC-ID is already bound to another wallet address"}` |
| `422 Unprocessable` | Violazione regole (es. aprire posizioni su challenge già FAILED) | `{"detail": "Cannot execute trade on FAILED challenge"}` |
