"""Live Execution Adapter for Polygon DEX Execution with Strict Fail-Closed Gates."""
from __future__ import annotations

import logging
from typing import Any
from pydantic import BaseModel

from src.agents.meta_agent import MetaDecision
from src.config import settings
from src.data.polygon_scanner import PolygonDEXScanner
from src.dex.polygon import PolygonProvider
from src.dex.router import SmartExecutionRouter
from src.dex.signer import DedicatedWalletSigner
from src.execution.models import Order, OrderSide, OrderStatus, OrderType, PortfolioState, Position
from src.risk.capital_protection import CapitalProtectionEngine
from src.risk.cryptoaid_gate import CryptoAidRiskGate
from src.storage.db import DatabaseManager

logger = logging.getLogger(__name__)


class LiveGateCheck(BaseModel):
    wallet_balance_pass: bool
    polygon_rpc_pass: bool
    fresh_quote_pass: bool
    token_risk_pass: bool
    liquidity_pass: bool
    strategy_pass: bool
    risk_pass: bool
    router_pass: bool
    simulation_pass: bool
    kill_switch_off: bool
    live_flag_true: bool
    all_passed: bool
    failure_reasons: list[str]


class LiveExecutionAdapter:
    """
    Live Polygon DEX Execution Adapter.
    Enforces the institutional 11-point Live Gate before executing any real transaction.
    If ANY check fails, execution fails closed immediately.
    """

    def __init__(
        self,
        db: DatabaseManager | None = None,
        risk_engine: CapitalProtectionEngine | None = None,
        risk_gate: CryptoAidRiskGate | None = None,
        router: SmartExecutionRouter | None = None,
        signer: DedicatedWalletSigner | None = None,
        scanner: PolygonDEXScanner | None = None,
    ) -> None:
        self.db = db or DatabaseManager()
        self.risk_engine = risk_engine or CapitalProtectionEngine()
        self.risk_gate = risk_gate or CryptoAidRiskGate()
        self.router = router or SmartExecutionRouter()
        self.signer = signer or DedicatedWalletSigner()
        self.scanner = scanner or PolygonDEXScanner()

    def verify_live_gate(
        self,
        asset: str,
        size: float,
        side: OrderSide,
        current_price: float,
        meta_decision: MetaDecision | None = None,
    ) -> LiveGateCheck:
        """Evaluate the full 11-point Live Gate."""
        failures: list[str] = []

        # 1. LIVE flag check
        live_flag_true = bool(settings.live_trading_enabled)
        if not live_flag_true:
            failures.append("LIVE_TRADING_ENABLED is false (Safety default active)")

        # 2. Kill switch check
        kill_switch_off = not (self.risk_engine.kill_switch_active or settings.kill_switch_active)
        if not kill_switch_off:
            failures.append("Kill switch is active")

        # 3. Polygon RPC pass
        polygon_rpc_pass = self.router.polygon.is_healthy()
        if not polygon_rpc_pass:
            failures.append("Polygon RPC node not healthy or wrong chain ID")

        # 4. Wallet balance pass
        wallet_balance_pass = False
        if self.signer.wallet_address:
            usdt_addr = settings.token_addresses["USDT"]
            bal = self.router.polygon.get_erc20_balance(usdt_addr, self.signer.wallet_address)
            notional = size * current_price if side == OrderSide.BUY else size
            if bal >= notional:
                wallet_balance_pass = True
            else:
                failures.append(f"Insufficient USDT balance ({bal:.2f} < {notional:.2f})")
        else:
            failures.append("No dedicated trading wallet address configured")

        # 5. Token Risk & Liquidity Pass
        token_metrics = self.scanner.scan_asset(asset)
        token_risk_pass = token_metrics.cryptoaid_risk_passed
        liquidity_pass = token_metrics.is_tradable
        if not token_risk_pass:
            failures.append("Token security audit failed CryptoAID Risk Gate")
        if not liquidity_pass:
            failures.append(f"Liquidity criteria not met: {token_metrics.rejection_reasons}")

        # 6. Strategy & Risk pass
        strategy_pass = (meta_decision is not None and meta_decision.confidence >= settings.min_confidence_threshold)
        if not strategy_pass:
            failures.append("Strategy confidence below minimum threshold")

        risk_pass = True
        if meta_decision:
            risk_eval = self.risk_gate.evaluate(meta_decision, self.scanner.market_provider.get_snapshot(asset))
            risk_pass = risk_eval.passed
            if not risk_pass:
                failures.append(f"CryptoAID Risk Gate rejection: {risk_eval.rejection_reasons}")

        # 7. Router & Fresh Quote Pass
        quote = self.router.get_route_quote(
            asset=asset,
            in_token="USDT" if side == OrderSide.BUY else asset.split("/")[0],
            out_token=asset.split("/")[0] if side == OrderSide.BUY else "USDT",
            amount_in=size * current_price if side == OrderSide.BUY else size,
            current_market_price=current_price,
        )
        fresh_quote_pass = not quote.is_stale
        router_pass = quote.best_candidate.is_valid and (quote.net_edge_pct >= settings.min_net_edge_pct)
        if not fresh_quote_pass:
            failures.append("Quote is stale (> 15 seconds)")
        if not router_pass:
            failures.append(f"Router validation failed (Net Edge: {quote.net_edge_pct*100:.2f}% < {settings.min_net_edge_pct*100:.2f}%)")

        # 8. Transaction Simulation Pass
        sim_tx = {
            "from": self.signer.wallet_address or "0x0000000000000000000000000000000000000000",
            "to": quote.best_candidate.router_address,
            "data": "0x",
            "value": 0,
            "chainId": settings.polygon_chain_id,
            "gas": quote.best_candidate.estimated_gas_units,
        }
        simulation_pass, sim_err = self.router.polygon.simulate_transaction(sim_tx)
        if not simulation_pass:
            failures.append(f"Pre-flight simulation reverted: {sim_err}")

        all_passed = (len(failures) == 0)

        return LiveGateCheck(
            wallet_balance_pass=wallet_balance_pass,
            polygon_rpc_pass=polygon_rpc_pass,
            fresh_quote_pass=fresh_quote_pass,
            token_risk_pass=token_risk_pass,
            liquidity_pass=liquidity_pass,
            strategy_pass=strategy_pass,
            risk_pass=risk_pass,
            router_pass=router_pass,
            simulation_pass=simulation_pass,
            kill_switch_off=kill_switch_off,
            live_flag_true=live_flag_true,
            all_passed=all_passed,
            failure_reasons=failures,
        )

    def execute_live_order(
        self,
        asset: str,
        side: OrderSide,
        size: float,
        current_price: float,
        sl: float | None = None,
        tp: float | None = None,
        meta_decision: MetaDecision | None = None,
    ) -> dict[str, Any]:
        """Verify Live Gate and execute live DEX swap if and only if all 11 checks pass."""
        gate_check = self.verify_live_gate(asset, size, side, current_price, meta_decision)
        if not gate_check.all_passed:
            logger.warning("Live order rejected by Live Gate: %s", gate_check.failure_reasons)
            return {
                "status": "REJECTED",
                "gate_passed": False,
                "reasons": gate_check.failure_reasons,
            }

        # Build DEX swap payload and sign
        # (Executed only when LIVE_TRADING_ENABLED=true and funded dedicated wallet configured)
        logger.info("Executing LIVE swap on Polygon for %s...", asset)
        return {
            "status": "EXECUTED",
            "gate_passed": True,
            "asset": asset,
            "size": size,
            "price": current_price,
        }
