"""Tests for Polygon DEX Execution, Smart Router, and Signer Safety Gates."""
import pytest
from src.config import settings
from src.dex.polygon import PolygonProvider
from src.dex.router import SmartExecutionRouter
from src.dex.signer import DedicatedWalletSigner, SigningPolicyError


def test_polygon_provider_gas_and_simulation():
    provider = PolygonProvider()
    gas_gwei = provider.get_gas_price_gwei()
    assert gas_gwei > 0

    gas_usd = provider.estimate_gas_cost_usd(gas_units=180_000, pol_price_usd=0.35)
    assert gas_usd > 0
    assert gas_usd < 0.50  # Typical Polygon gas cost is fractions of a dollar

    # Test offline simulation
    sim_tx = {
        "from": "0x1111111111111111111111111111111111111111",
        "to": settings.uniswap_v3_router,
        "data": "0x",
        "value": 0,
    }
    passed, err = provider.simulate_transaction(sim_tx)
    assert passed is True


def test_smart_execution_router_quote_and_net_edge():
    router = SmartExecutionRouter()
    quote = router.get_route_quote(
        asset="POL/USDT",
        in_token="USDT",
        out_token="POL",
        amount_in=100.0,
        current_market_price=0.325,
        expected_move_pct=0.035,
    )

    assert quote.asset == "POL/USDT"
    assert quote.in_token == "USDT"
    assert quote.out_token == "POL"
    assert quote.best_candidate is not None
    assert quote.best_candidate.dex in ("Uniswap_V3", "QuickSwap_V3")
    assert quote.best_candidate.expected_output > 0
    assert quote.best_candidate.amount_out_min > 0
    assert quote.best_candidate.amount_out_min <= quote.best_candidate.expected_output
    assert quote.best_candidate.slippage_bps <= settings.hard_max_slippage_bps
    assert quote.is_stale is False
    assert quote.net_edge_pct > 0


def test_dedicated_wallet_signer_policy_gates():
    signer = DedicatedWalletSigner()

    valid_tx = {
        "from": "0x1111111111111111111111111111111111111111",
        "to": settings.uniswap_v3_router,
        "data": "0x",
        "value": 0,
        "chainId": 137,
    }

    # Should sign/simulate successfully within limits
    res = signer.sign_and_send_transaction(valid_tx, trade_notional_usd=100.0, kill_switch_active=False)
    assert "tx_hash" in res

    # Gate 1: Kill switch active should reject
    with pytest.raises(SigningPolicyError, match="Kill switch is ACTIVE"):
        signer.sign_and_send_transaction(valid_tx, trade_notional_usd=100.0, kill_switch_active=True)

    # Gate 2: Wrong chain ID should reject
    invalid_chain_tx = dict(valid_tx, chainId=1)  # Ethereum mainnet instead of Polygon 137
    with pytest.raises(SigningPolicyError, match="Target chain ID"):
        signer.sign_and_send_transaction(invalid_chain_tx, trade_notional_usd=100.0, kill_switch_active=False)

    # Gate 3: Exceeding max transaction size should reject
    with pytest.raises(SigningPolicyError, match="Trade notional"):
        signer.sign_and_send_transaction(valid_tx, trade_notional_usd=5_000.0, kill_switch_active=False)
