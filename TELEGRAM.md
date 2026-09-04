# CryptoAID Trade AI — Telegram SuperBot Architecture (V1.1)

Comprehensive Telegram Integration replicating and adapting top-tier Telegram AI trading bot capabilities (`@SuperTradingAIbot` standard) directly to `cryptoaid.support`.

---

## 1. Tri-Pillar Ecosystem Topology

The Telegram ecosystem of CryptoAID consists of three interconnected layers operating with strict fail-closed safety:

```
                  ┌────────────────────────────────────────────────────────┐
                  │          CRYPTOAID TELEGRAM ECOSYSTEM                  │
                  └────────────────────────────────────────────────────────┘
                                              │
         ┌────────────────────────────────────┼────────────────────────────────────┐
         ▼                                    ▼                                    ▼
┌──────────────────┐               ┌───────────────────────┐              ┌──────────────────┐
│  OFFICIAL BOT    │               │    OFFICIAL GROUP     │              │ OFFICIAL CHANNEL │
│  @CryptoAidTrade │               │  @cryptoAIDsupporter  │              │  @cryptoaidsup   │
│  AIbot           │               │  (5 Native Topics)    │              │  (Broadcasting)  │
└──────────────────┘               └───────────────────────┘              └──────────────────┘
         │                                    │                                    │
         ▼                                    ▼                                    ▼
• 1-on-1 Trading Terminal          • 🤖 TRADE AI: Autotrade/Prop          • VIP High-Edge Signals
• WebApp Cockpit Launcher          • 📡 AI SIGNALS: Heart dual-line       • Autotrade Win Payouts
• Autotrade 10 POL Runs            • 🚨 SECURITY & SCAM: Risk audits      • Hall of Fame Traders
• Prop Challenges ($10k-$150k)     • 🧪 CRYPTOAID LAB: Telemetry/Logs     • Daily Market Summary
• 4-Monies Account Ledger          • 🏠 GENERAL: Community / Chat
• Federated Identity Linker
```

---

## 2. Topic Architecture & Zero-Destruction Guarantee

> [!IMPORTANT]
> **STRICT IMMUTABILITY RULE**: The bot never creates, deletes, resets, or renames Telegram topics. All outbound messages are strictly dispatched to pre-existing official topics using thread IDs.

| Event Type | Destination | Topic Thread / Scope | Description |
| :--- | :--- | :--- | :--- |
| `AUTOTRADE_RUN_STARTED` / `WON` / `LOST` | Group | **`🤖 TRADE AI`** | Real-time notifications of 10 POL runs, paper execution, win/loss, and reward accrual. |
| `PROP_CHALLENGE_CREATED` / `PROGRESS` | Group | **`🤖 TRADE AI`** | Prop challenge activations, target progress gauges, and funded trader milestones. |
| `PAPER_TRADE_OPENED` / `CLOSED` | Group | **`🤖 TRADE AI`** | Fill events, Stop Loss, Take Profit, and Guardian settlements into USDT. |
| `PREDICTIVE_HEART_FORECAST` / `SIGNAL` | Group | **`📡 AI SIGNALS`** | High-conviction signals with White Line (historical) vs Red Line (P50 forecast). |
| `CHANNEL_VIP_SIGNAL` | Channel | **`@cryptoaidsup`** | High-edge broadcast (confidence ≥ 75%) with direct WebApp trade link. |
| `CHANNEL_WIN_ANNOUNCEMENT` | Channel | **`@cryptoaidsup`** | Public reward payout announcements from Protocol Treasury pool. |
| `SECURITY_REJECTION` / `HONEYPOT` | Group | **`🚨 SECURITY & SCAM`** | Token contract rejections, honeypot alerts, circuit breaker trips. |
| `CORTEX_AUDIT` / `DEV_LOG` / `HEALTH` | Group | **`🧪 CRYPTOAID LAB`** | System boot, CORTEX regime transitions, Bor RPC telemetry. |
| `COMMUNITY_ANNOUNCEMENT` | Group | **`🏠 GENERAL`** | Global announcements, educational recaps, and community leaderboards. |

---

## 3. Telegram WebApp Cockpit Integration

The bot integrates the full WebApp Cockpit directly within Telegram:
- **Button**: `🚀 OPEN TRADEAID COCKPIT (WEBAPP)`
- **Target URL**: `https://trade.cryptoaid.support/dapp.html`
- **Features inside Telegram WebApp**:
  1. Live 1-second Oscilloscope chart with Predictive Heart dual-line.
  2. One-tap Autotrade activation (10 POL).
  3. Interactive Prop Challenge tier selection and real-time DD gauges.
  4. Web3 Polygon Wallet connection (`0x...`) + Federated Digital Twin (`SIC-ID-XXXXXXXXXXXX`).
  5. 4 Monies isolation display (Paper 10k USDT, Challenge fee, TAC credits, Withdrawable Rewards).

---

## 4. Bot Command Suite (24 Commands)

### Primary Trading & WebApp Commands:
- `/start`: Main HUD dashboard with WebApp button, 4 Monies account balances, and action keyboard.
- `/run` or `/autotrade_run`: Activate a 10 POL Autotrade run (paper execution, +2 POL reward if target met).
- `/prop` or `/challenge`: Explore the 4 Prop tiers ($10k, $50k, $100k, $150k) and check active challenge progress.
- `/heart [asset]`: Render Predictive Heart dual line (White line real price vs Red line P50 forecast envelope).
- `/gem` or `/snipe`: Run Polygon DEX gem scanner with liquidity depth and honeypot audit.
- `/wallet` or `/balance`: View 4-monies ledger breakdown and linked identity.
- `/link [0x... | SIC-ID-...]`: Link Telegram user to Polygon Wallet or Digital Twin.
- `/rewards` or `/claim`: Check accrued withdrawable rewards and trigger on-chain withdrawal.

### System & Risk Controls:
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
- `/stop`: Emergency halt trading engine and engage fail-closed kill switch.
- `/resume`: Reset kill switch and resume standard monitoring operations.
- `/health`: Diagnostic check verifying provider latencies and Position Guardian state.

---

## 5. Interactive Inline Keyboard HUD

The `/start` dashboard features a 7-tier responsive inline keyboard:
1. `[🚀 OPEN TRADEAID COCKPIT (WEBAPP)]`
2. `[⚡ RUN AUTOTRADE (10 POL)]` `[🏆 PROP CHALLENGES]`
3. `[📈 PREDICTIVE HEART]` `[📡 AI SIGNALS]`
4. `[💎 GEM RADAR / SNIPER]` `[📊 POSITIONS & PNL]`
5. `[💼 4-MONIES WALLET]` `[🛡 RISK & CORTEX]`
6. `[🎁 REWARDS & CLAIM]` `[🔗 LINK IDENTITY]`
7. `[🟢 AUTOTRADE: ON/OFF]` `[🛡 KILL SWITCH]`
