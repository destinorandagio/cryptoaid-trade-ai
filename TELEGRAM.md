# CryptoAID Trade AI — Telegram Bot Specification

## 1. Bot & Channel Identity

- **Target Trade Bot**: `@CryptoAidTradeAIbot`
- **Existing Support Bot**: `@CryptoAIDsupportBOT` (Kept intact, not replaced)
- **Official Group**: [https://t.me/cryptoAIDsupporter](https://t.me/cryptoAIDsupporter)
- **Official Channel**: [https://t.me/cryptoaidsup](https://t.me/cryptoaidsup)

---

## 2. Topic Architecture & Routing Matrix

> [!IMPORTANT]
> **STRICT RULE**: The bot never creates, deletes, resets, or renames Telegram topics. All outbound messages are strictly dispatched to the pre-existing official topics using thread IDs.

| Event Type | Destination Topic | Description |
| :--- | :--- | :--- |
| **Trade Status, Orders, Settlements, Guardian** | **`🤖 TRADE AI`** | Paper/Live execution fills, SL/TP triggers, break-even locks, portfolio updates. |
| **High-Confidence Validated Signals** | **`📡 AI SIGNALS`** | Filtered signals passing all strategy, regime, net-edge, and risk gates. Low-noise. |
| **Scam Rejections & Security Alerts** | **`🚨 SECURITY & SCAM`** | Token contract rejections, honeypot alerts, circuit breaker trip notifications. |
| **Dev Tests, Migrations & Diagnostics** | **`🧪 CRYPTOAID LAB`** | System boot, automated test runs, Watchdog health status pings. |
| **Ecosystem & Community Announcements** | **`🏠 GENERAL`** | Global system announcements, periodic summaries. |

---

## 3. Bot Command Set

The bot supports 14 interactive slash commands:

- `/start`: Welcome banner, operational status, quick interactive action menu.
- `/status`: Real-time system health, Polygon Bor RPC status, DB connectivity, wallet mode.
- `/scan`: Execute immediate scanner run across Polygon universe (`POL`, `WETH`, `WBTC`, `LINK`).
- `/signals`: Display active signals that have passed the CryptoAID Risk Gate.
- `/portfolio`: Show current cash balance, total equity, open positions count, and 24h P&L.
- `/positions`: Display open positions with mark-to-market prices, unrealized P&L, SL, and TP.
- `/trades`: List recent executed trade settlements and historical returns.
- `/performance`: Summary metrics (Win rate, Sharpe ratio, Profit Factor, Max Drawdown).
- `/strategies`: Show active strategy agents (Scalp, Trend, Momentum, Breakout, Mean Rev, Volatility).
- `/risk`: Display circuit breaker state, daily loss limit, and security audit status.
- `/autotrade`: Toggle autonomous trading daemon (`ON` or `OFF`).
- `/stop`: Emergency halt trading engine and engage kill switch.
- `/resume`: Reset kill switch and resume standard monitoring operations.
- `/health`: Diagnostic check verifying provider latencies and Position Guardian state.

---

## 4. Interactive Inline Keyboard Controls

The `/start` dashboard displays 8 quick-action inline buttons:
1. `⚡ AUTOTRADE: [ON/OFF]`
2. `💰 BALANCE`
3. `📈 POSITIONS`
4. `📡 SIGNALS`
5. `🧠 STRATEGIES`
6. `🛡 RISK STATUS`
7. `📊 PERFORMANCE`
8. `🛑 KILL SWITCH`

---

## 5. Standardized Signal Dispatch Format

Every published signal includes complete contextual fields:
- `SIGNAL_ID`
- Asset (with Polygon tag)
- Signal direction (`LONG` / `SHORT`)
- Confidence percentage
- Strategy name & detected regime
- Timeframe
- Precise Entry, Stop Loss (with 5% ceiling note), and Take Profit
- Trailing Stop status
- Expected Net Edge percentage
- Estimated Slippage and Price Impact
- Gas estimate in USD
- CryptoAID Risk Gate status
- Execution Mode (`PAPER` / `LIVE`)
- Top evidence bullet points
- UTC Timestamp
