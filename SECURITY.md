# CryptoAID Trade AI — Security & Zero-Key-Leak Policy

## 1. Zero Private Key Leak Architecture

- **Dedicated Trading Wallet Only**: The system operates exclusively with a dedicated trading wallet specifically funded for algorithmic execution. It MUST NEVER be used with personal cold storage or main holding addresses.
- **Server-Side Key Isolation**: Private keys are injected strictly via secure environment variables (`TRADING_WALLET_PRIVATE_KEY`).
- **Zero Logging / Zero Display**: Private keys are explicitly masked and forbidden from being written to logs, stored in SQLite database tables, rendered in the PWA Cockpit, returned over REST API responses, or broadcast to Telegram.
- **Fail-Closed Default**: If no private key is provided, the signer initializes automatically in simulation/paper mode without throwing fatal exceptions, allowing harmless testing and zero accidental on-chain transactions.

---

## 2. Policy Checks & Pre-Flight Simulation

Before any transaction can be signed and broadcast by `DedicatedWalletSigner`:
1. **Chain ID Enforcement**: Strictly verifies `chain_id == 137` (Polygon POS Mainnet). Transactions targeting any unexpected chain ID are immediately rejected.
2. **Global Kill Switch Check**: If `kill_switch_active == True`, all transaction signing is aborted immediately.
3. **Transaction Size Cap**: Enforces `max_transaction_usd` ($150.00 on a $1,000 capital model).
4. **Daily Volume Cap**: Enforces `max_daily_volume_usd` ($1,000.00 cumulative).
5. **Contract Whitelist Verification**: Verifies recipient contract matches approved DEX routers (Uniswap V3 SwapRouter `0xE592427A0AEce92De3Edee1F18E0157C05861564` or QuickSwap Router `0xa5E0829CaCEd8fFDD4De3c43696c57F7D7A678ff`).
6. **Pre-Flight Simulation (`eth_call`)**: Executes dry-run against the Bor RPC node. If the EVM reverts, execution is rejected before spending gas.

---

## 3. ERC-20 Limited Approvals Policy

- **No Unlimited Approvals by Default**: The router checks allowances prior to trade execution. When approval is required, it approves only the specific notional required for the current trade batch or a bounded cap.
- **Revoke Support**: Integrated interface to revoke allowances down to 0 when positions are closed or if the kill switch is triggered.

---

## 4. Slippage & MEV Protection

- **Dynamic Slippage**: Base slippage set dynamically to 20 bps (0.20%), adjusting based on asset volatility and pool depth.
- **Hard Max Slippage Ceiling**: 100 bps (1.00%) absolute maximum. Any route quote requiring higher slippage is rejected.
- **Guaranteed `amountOutMinimum`**: Calculated and passed directly into the DEX calldata to prevent sandwich attacks.
- **Short Quote Lifespan**: Quotes older than 15 seconds are rejected as stale.

---

## 5. Position Guardian & 5% Emergency Ceiling

- The **5% Emergency Stop** is the position liquidation ceiling, NOT swap slippage.
- If an adverse price movement drops a position by 5.0%, the Position Guardian triggers an immediate market liquidation back to 100% USDT, bypassing normal strategy logic to prevent catastrophic loss.
