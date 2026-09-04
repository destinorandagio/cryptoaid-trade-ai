# CryptoAID Trade AI

> **AI Trading + Web3 Intelligence + Risk Intelligence + Multi-Agent Decision + Capital Protection + Verifiable Performance**

CryptoAID Trade AI is an institutional-grade, multi-agent paper trading and market intelligence system built for the CryptoAID ecosystem. It integrates continuous market telemetry across the top liquid assets (`BTC/USDC`, `ETH/USDC`, `SOL/USDC`), passes all decisions through the fail-closed **CryptoAID Risk Gate** (Digital Twin + Smart Contract Security + Anti-Scam Verification), and enforces rigorous mathematical capital protection before executing any paper order.

---

## Key Principles & Guardrails

- 🧪 **Paper Trading Only**: Zero private keys or real capital required. Real trading is strictly disabled (`LIVE_TRADING_ENABLED=false`).
- 🛡 **Fail-Closed Risk Gate**: Every directional impulse must pass Project Identity, Smart Contract audit status, Honeypot/Scam checks, and Liquidity corridors. If unverified, `TRADE = REJECTED`.
- 🧠 **Multi-Agent Consensus**: 6 specialized quantitative agents (`Trend`, `Momentum`, `MeanReversion`, `Breakout`, `Volatility`, `Risk`) aggregated by a `MetaAgent`. Default safe decision is always `NO_TRADE`.
- 🔒 **Capital Protection**: Strict 5% max position sizing, 40% portfolio exposure limit, leverage disabled by default (1.0x spot paper), daily/weekly loss limits, and emergency kill switches.
- 📱 **Mobile-First PWA & Telegram**: Responsive PWA (`trade.cryptoaid.support`) with real-time scanner and order controls, coupled with a Telegram bot router strictly organized by official topics.

---

## Architecture Overview

```
DATA LAYER (Binance / CoinGecko / Replay Provider with Caching)
   ↓
MARKET INTELLIGENCE (OHLCV, Volatility, Spread, Funding, Volume)
   ↓
WEB3 INTELLIGENCE & CRYPTOAID RISK GATE (Digital Twin, Scam & Contract Risk)
   ↓
STRATEGY AGENTS (Trend, Momentum, MeanReversion, Breakout, Volatility, Risk)
   ↓
META AGENT (Weighted Consensus, Confidence Threshold, Safe NO_TRADE Default)
   ↓
CAPITAL PROTECTION & RISK ENGINE (Position Sizing, Drawdown Limits, Kill Switch)
   ↓
PAPER EXECUTION ENGINE (Market, Limit, Stop Loss, Take Profit, Trailing Stop)
   ↓
SQLITE DATABASE (13 Migrated Tables + Audit Events)
   ↓
PERFORMANCE & BACKTEST ENGINE (Sharpe, Sortino, MaxDD, Walk-Forward Validation)
   ↓
DELIVERY INTERFACES: REST API (FastAPI v1) + PWA + Telegram Bot (@CryptoAidTradeAIbot)
```

---

## Quickstart

### 1. Installation
```bash
git clone https://github.com/destinorandagio/cryptoaid-trade-ai.git
cd cryptoaid-trade-ai
pip install -r requirements.txt
```

### 2. Run Test Suite
```bash
pytest tests/ -v
```

### 3. Launch Local REST API & PWA
```bash
uvicorn src.api.app:app --host 0.0.0.0 --port 8000 --reload
```
- Open browser at `http://localhost:8000` to access the PWA.
- Open interactive API documentation at `http://localhost:8000/docs`.

### 4. Run CLI Scanner
```bash
python scripts/run_scanner.py
```

### 5. Run Historical Backtest
```bash
python scripts/run_backtest.py
```

### 6. Run Paper Trading Daemon
```bash
python scripts/run_paper_daemon.py
```

---

## License
MIT License. Part of the CryptoAID Open Security & Intelligence ecosystem.
