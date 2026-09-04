# CryptoAID Trade AI — REST API Reference (v1)

**Base URL**: `http://localhost:8000` (or `https://trade.cryptoaid.support/api/v1` when proxied)  
**Specification**: OpenAPI 3.0 / FastAPI Swagger interactive docs at `/docs`

---

## Endpoints

### 1. System & Health

#### `GET /api/v1/health`
Returns quick liveness check.
```json
{
  "status": "HEALTHY",
  "app": "CryptoAID Trade AI",
  "version": "1.0.0",
  "timestamp": "2026-09-04T11:45:00Z"
}
```

#### `GET /api/v1/status`
Comprehensive operational status of all subsystems.
```json
{
  "status": "OPERATIONAL",
  "app": "CryptoAID Trade AI",
  "version": "1.0.0",
  "live_trading_enabled": false,
  "autotrade_enabled": true,
  "kill_switch_active": false,
  "base_quote": "USDT",
  "chain_id": 137,
  "universe": ["POL/USDT", "WETH/USDT", "WBTC/USDT", "LINK/USDT"],
  "active_positions_count": 0,
  "timestamp": "2026-09-04T11:45:00Z"
}
```

---

### 2. Market Data & Scanner

#### `GET /api/v1/markets`
List supported trading pairs, active prices, 24h volume, spread and status.

#### `GET /api/v1/scan`
Executes real-time multi-agent scan across all pairs in universe with regime classification and risk audit findings.

#### `GET /api/v1/signals`
Returns only actionable signals with high confidence passing the CryptoAID Risk Gate.

---

### 3. Execution & Portfolio

#### `GET /api/v1/portfolio`
Returns current paper/live equity, cash balance, active positions count, and 24h P&L.

#### `GET /api/v1/positions`
Returns all open positions with mark-to-market prices, unrealized P&L, stop loss, and take profit.

#### `POST /api/v1/orders`
Place a paper order.
```json
{
  "asset": "POL/USDT",
  "side": "BUY",
  "size": 100.0,
  "sl": 0.3100,
  "tp": 0.3500,
  "trailing_distance": 0.005
}
```

#### `GET /api/v1/orders`
List historical orders with fill status.

#### `GET /api/v1/trades`
List historical trade settlement records.

#### `GET /api/v1/performance`
Calculated analytics: win rate, total trades, net P&L, profit factor, max drawdown, and buy-and-hold benchmark comparisons.

---

### 4. Control & Risk Gates

#### `GET /api/v1/strategies`
Lists registered strategy agents, active weights, and operational descriptions.

#### `GET /api/v1/risk`
Current risk parameters, daily loss limit, max drawdown threshold, and circuit breaker trip state.

#### `GET /api/v1/autotrade` / `POST /api/v1/autotrade`
Inspect or toggle autonomous paper trading loop.

#### `POST /api/v1/kill-switch`
Emergency panic button: closes open positions and halts all new orders.
```json
{
  "action": "TRIGGER"
}
```
