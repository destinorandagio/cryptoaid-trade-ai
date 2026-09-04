"""Tests for Telegram Routing, Deduplication and Message Formatting."""
from src.telegram.dedupe import SignalDeduplicator
from src.telegram.formatter import format_ai_signal, format_paper_trade_event, format_security_rejection
from src.telegram.router import TelegramTopicRouter


def test_telegram_signal_formatting():
    msg = format_ai_signal(
        signal_id="sig_btc_001",
        asset="BTC/USDC",
        signal="LONG",
        confidence=0.82,
        timeframe="4H",
        entry=64500.0,
        sl=63200.0,
        tp=67100.0,
        risk_pct=2.0,
        evidence=["EMA(12) crossed above EMA(26)", "RSI rising"],
        timestamp="2026-09-04 08:30:00 UTC",
        risk_gate_status="PASS",
    )
    assert "CRYPTOAID TRADE AI" in msg
    assert "sig_btc_001" in msg
    assert "BTC/USDC" in msg
    assert "LONG" in msg
    assert "82%" in msg
    assert "PAPER" in msg
    assert "PASS" in msg


def test_telegram_security_rejection_formatting():
    msg = format_security_rejection("SCAM_TOKEN/USDC", ["Token matches known honeypot bytecode"])
    assert "CRYPTOAID RISK GATE — REJECTION" in msg
    assert "TRADE REJECTED" in msg
    assert "honeypot" in msg


def test_telegram_deduplicator():
    deduper = SignalDeduplicator(cooldown_seconds=3600, price_delta_threshold_pct=2.0)
    # First time -> not duplicate
    assert deduper.is_duplicate("BTC/USDC", "LONG", 60_000.0) is False
    # Immediately after with minimal price shift -> duplicate
    assert deduper.is_duplicate("BTC/USDC", "LONG", 60_200.0) is True
    # Opposite direction -> not duplicate
    assert deduper.is_duplicate("BTC/USDC", "SHORT", 60_200.0) is False
    # Large price shift (> 2%) -> allowed
    assert deduper.is_duplicate("BTC/USDC", "LONG", 62_000.0) is False


def test_telegram_topic_router_dry_run():
    router = TelegramTopicRouter(bot_token=None)

    res1 = router.publish("VERIFIED_AI_SIGNAL", "Test Signal", dry_run=True)
    assert res1["status"] == "SIMULATED"
    assert res1["chat_id"] == "@cryptoAIDsupporter"

    res2 = router.publish("PAPER_TRADE_OPENED", "Trade Open", dry_run=True)
    assert res2["status"] == "SIMULATED"

    res3 = router.publish("SECURITY_REJECTION", "Security Rejection", dry_run=True)
    assert res3["status"] == "SIMULATED"
