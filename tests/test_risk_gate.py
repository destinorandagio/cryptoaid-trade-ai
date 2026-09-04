"""Tests for CryptoAID Risk Gate and Capital Protection."""
from src.agents.base import SignalType
from src.agents.meta_agent import MetaDecision
from src.data.mock_feed import MockMarketDataProvider
from src.risk.capital_protection import CapitalProtectionEngine, PortfolioRiskState
from src.risk.cryptoaid_gate import CryptoAidRiskGate


def test_cryptoaid_risk_gate_passes_verified_signal():
    gate = CryptoAidRiskGate()
    provider = MockMarketDataProvider(seed=42)
    snapshot = provider.get_snapshot("BTC/USDC")

    meta_dec = MetaDecision(
        asset="BTC/USDC",
        decision=SignalType.LONG,
        confidence=0.85,
        entry_price=snapshot.price,
        recommended_stop_loss=snapshot.price * 0.98,
        recommended_take_profit=snapshot.price * 1.04,
    )

    result = gate.evaluate(meta_dec, snapshot)
    assert result.passed is True
    assert result.final_decision == "PASS"
    assert result.composite_risk_score <= 35.0
    assert len(result.rejection_reasons) == 0


def test_cryptoaid_risk_gate_rejects_unverified_or_scam_asset():
    gate = CryptoAidRiskGate()
    provider = MockMarketDataProvider(seed=42)
    snapshot = provider.get_snapshot("BTC/USDC")

    # Unverified token
    meta_dec = MetaDecision(
        asset="SHADY_MOON_INU/USDC",
        decision=SignalType.LONG,
        confidence=0.90,
        entry_price=1.0,
    )
    result = gate.evaluate(meta_dec, snapshot)
    assert result.passed is False
    assert result.final_decision == "REJECT"
    assert any("scam" in r.lower() or "unverified" in r.lower() for r in result.rejection_reasons)


def test_capital_protection_limits():
    engine = CapitalProtectionEngine(
        max_position_size_ratio=0.05,
        max_portfolio_exposure_ratio=0.40,
        max_leverage=1.0,
    )

    state = PortfolioRiskState(
        total_equity=10_000.0,
        cash_balance=10_000.0,
        allocated_margin=0.0,
        peak_equity=10_000.0,
    )

    # 1. Test sizing: max position is 5% of $10,000 = $500
    size = engine.calculate_position_size(
        equity=state.total_equity,
        entry_price=50_000.0,
        stop_loss_price=49_000.0,
    )
    # 1% risk = $100. $100 / $1000 diff = 0.1 BTC = $5,000. But max notional is $500 -> 0.01 BTC
    assert size == 0.01
    assert size * 50_000.0 <= 500.0

    # 2. Test rejection on oversized order
    allowed, reason, _ = engine.validate_order(
        symbol="BTC/USDC",
        side="BUY",
        size=0.1,  # $5,000 > $500 max
        price=50_000.0,
        state=state,
    )
    assert allowed is False
    assert "exceeds position size limit" in reason

    # 3. Test kill switch
    engine.trigger_kill_switch("Manual test")
    allowed_ks, reason_ks, _ = engine.validate_order(
        symbol="BTC/USDC",
        side="BUY",
        size=0.005,
        price=50_000.0,
        state=state,
    )
    assert allowed_ks is False
    assert "Kill Switch" in reason_ks
