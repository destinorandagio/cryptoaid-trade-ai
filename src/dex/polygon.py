"""Polygon RPC Connection, Web3 Helpers, and ERC-20 Policy Controller."""
from __future__ import annotations

import logging
import time
from typing import Any
from web3 import Web3
from web3.exceptions import Web3Exception

from src.config import settings

logger = logging.getLogger(__name__)

# Minimal ERC-20 ABI for balance, allowance and approval
ERC20_ABI = [
    {
        "constant": True,
        "inputs": [{"name": "_owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "balance", "type": "uint256"}],
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [
            {"name": "_owner", "type": "address"},
            {"name": "_spender", "type": "address"},
        ],
        "name": "allowance",
        "outputs": [{"name": "remaining", "type": "uint256"}],
        "type": "function",
    },
    {
        "constant": False,
        "inputs": [
            {"name": "_spender", "type": "address"},
            {"name": "_value", "type": "uint256"},
        ],
        "name": "approve",
        "outputs": [{"name": "success", "type": "bool"}],
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [],
        "name": "decimals",
        "outputs": [{"name": "", "type": "uint8"}],
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [],
        "name": "symbol",
        "outputs": [{"name": "", "type": "string"}],
        "type": "function",
    },
]


class PolygonProvider:
    """Manages Polygon Web3 RPC connectivity, gas pricing, ERC-20 allowances and tx simulations."""

    def __init__(self, rpc_url: str | None = None) -> None:
        self.rpc_url = rpc_url or settings.polygon_rpc_url
        self.w3 = self._connect()

    def _connect(self) -> Web3:
        """Establish connection with primary RPC and failover to backup endpoints."""
        endpoints = [self.rpc_url] + settings.polygon_backup_rpc_urls
        for url in endpoints:
            try:
                w3 = Web3(Web3.HTTPProvider(url, request_kwargs={"timeout": 1.0}))
                if w3.is_connected():
                    logger.info("Connected to Polygon RPC: %s (Chain ID: %s)", url, w3.eth.chain_id)
                    return w3
            except Exception as exc:
                logger.debug("Polygon RPC %s unavailable (%s). Trying next...", url, exc)

        logger.info("Operating in offline/simulated Web3 mode.")
        return Web3()  # Offline/unconnected fallback instance

    def is_healthy(self) -> bool:
        """Check if Polygon RPC node is connected and responsive."""
        try:
            return self.w3.is_connected() and self.w3.eth.chain_id == settings.polygon_chain_id
        except Exception:
            return False

    def get_gas_price_gwei(self) -> float:
        """Return current Polygon gas price in Gwei."""
        try:
            if self.w3.is_connected():
                wei = self.w3.eth.gas_price
                return round(float(self.w3.from_wei(wei, "gwei")), 2)
        except Exception as exc:
            logger.debug("Error querying live Polygon gas: %s. Using default 35 Gwei.", exc)
        return 35.0  # Safe default on Polygon

    def estimate_gas_cost_usd(self, gas_units: int = settings.polygon_base_gas_units, pol_price_usd: float = 0.35) -> float:
        """Calculate USD gas cost for a transaction: (units * gas_price_gwei * 1e-9) * pol_price."""
        gwei = self.get_gas_price_gwei()
        pol_cost = gas_units * gwei * 1e-9
        return round(pol_cost * pol_price_usd, 4)

    def get_erc20_balance(self, token_address: str, wallet_address: str) -> float:
        """Get ERC-20 balance formatted to human units."""
        if not self.w3.is_connected():
            return 1_000.0 if "c2132" in token_address.lower() else 100.0  # Simulated paper balance

        try:
            checksum_token = self.w3.to_checksum_address(token_address)
            checksum_wallet = self.w3.to_checksum_address(wallet_address)
            contract = self.w3.eth.contract(address=checksum_token, abi=ERC20_ABI)
            raw_bal = contract.functions.balanceOf(checksum_wallet).call()
            decimals = contract.functions.decimals().call()
            return raw_bal / (10 ** decimals)
        except Exception as exc:
            logger.warning("Error fetching ERC20 balance for %s: %s", token_address, exc)
            return 0.0

    def get_allowance(self, token_address: str, owner_address: str, spender_address: str) -> float:
        """Get current ERC-20 allowance granted to spender."""
        if not self.w3.is_connected():
            return 0.0

        try:
            c_token = self.w3.to_checksum_address(token_address)
            c_owner = self.w3.to_checksum_address(owner_address)
            c_spender = self.w3.to_checksum_address(spender_address)
            contract = self.w3.eth.contract(address=c_token, abi=ERC20_ABI)
            raw_allowance = contract.functions.allowance(c_owner, c_spender).call()
            decimals = contract.functions.decimals().call()
            return raw_allowance / (10 ** decimals)
        except Exception as exc:
            logger.warning("Error querying allowance: %s", exc)
            return 0.0

    def simulate_transaction(self, tx_dict: dict[str, Any]) -> tuple[bool, str | None]:
        """
        Simulate transaction execution using eth_call prior to signing.
        Returns: (success: bool, revert_reason: str | None)
        """
        data = tx_dict.get("data", "0x")
        # Empty/placeholder calldata indicates paper/simulation mode -> passes
        if not data or data == "0x" or len(data) <= 2:
            return True, None

        if not self.w3.is_connected():
            # Offline / dry-run simulation passes
            return True, None

        try:
            # Build minimal call dict
            call_params = {
                "from": tx_dict.get("from"),
                "to": tx_dict.get("to"),
                "data": data,
                "value": tx_dict.get("value", 0),
            }
            self.w3.eth.call(call_params)
            return True, None
        except Web3Exception as exc:
            logger.warning("Transaction simulation reverted: %s", exc)
            return False, str(exc)
        except Exception as exc:
            logger.warning("Simulation error: %s", exc)
            return False, str(exc)

