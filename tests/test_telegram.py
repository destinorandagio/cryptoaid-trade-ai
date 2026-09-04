"""Tests for Telegram Routing, Deduplication, SuperTradingAI Message Formatting, and Bot Runtime."""
import pytest
from unittest.mock import AsyncMock, MagicMock
from telegram import Update, User, Message, Chat

from src.telegram.bot import (
    build_bot_app,
    cmd_gem,
    cmd_heart,
    cmd_link,
    cmd_prop,
    cmd_rewards,
    cmd_run,
    cmd_start,
    cmd_wallet,
    get_main_menu_keyboard,
    get_user_profile,
)
from src.telegram.dedupe import SignalDeduplicator
from src.telegram.formatter import (
    format_ai_signal,
    format_autotrade_run_event,
    format_gem_radar,
    format_paper_trade_event,
    format_predictive_heart,
    format_prop_challenge_progress,
    format_prop_tiers,
    format_security_rejection,
    format_wallet_hub,
)
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


def test_telegram_autotrade_run_formatter():
    # Test WIN outcome
    win_data = {
        "run_id": "RUN_A1B2C3D4",
        "wallet": "0x3C320B3a0917fF44BF6551CDdee44402AFcF250C",
        "result": "WIN",
        "gross_pnl": 45.20,
        "execution_costs": 2.70,
        "net_pnl": 42.50,
        "reward_amount": 2.0,
        "reward_status": "RESERVED",
    }
    msg_win = format_autotrade_run_event(win_data)
    assert "AUTOTRADE RUN #RUN_A1B2" in msg_win
    assert "WINNER!" in msg_win
    assert "+2 POL REAL REWARD" in msg_win
    assert "+42.50 USDT" in msg_win
    assert "10.0 POL" in msg_win

    # Test LOSS outcome
    loss_data = {
        "run_id": "RUN_E5F6G7H8",
        "wallet": "0x3C320B3a0917fF44BF6551CDdee44402AFcF250C",
        "result": "LOSS",
        "gross_pnl": -22.50,
        "execution_costs": 2.50,
        "net_pnl": -25.00,
        "reward_amount": 0.0,
        "reward_status": "NONE",
    }
    msg_loss = format_autotrade_run_event(loss_data)
    assert "AUTOTRADE RUN #RUN_E5F6" in msg_loss
    assert "STOP TRIGGERED" in msg_loss
    assert "0 POL REWARD" in msg_loss


def test_telegram_prop_formatters():
    # Test tiers table
    tiers_text = format_prop_tiers()
    assert "TRADEAID PROP CHALLENGES" in tiers_text
    assert "STARTER TIER" in tiers_text
    assert "PRO TIER" in tiers_text
    assert "ELITE TIER" in tiers_text
    assert "BLACK TIER" in tiers_text
    assert "$10,000 NOTIONAL" in tiers_text
    assert "+8.0%" in tiers_text

    # Test progress format
    ch_data = {
        "challenge_id": "CH_998877",
        "tier": "PRO",
        "initial_balance": 50000.0,
        "current_equity": 52400.0,
        "daily_drawdown_pct": 0.85,
        "max_drawdown_pct": 1.20,
        "status": "ACTIVE",
    }
    prog_text = format_prop_challenge_progress(ch_data)
    assert "PROP CHALLENGE PROGRESS" in prog_text
    assert "PRO" in prog_text
    assert "+2,400.00 USDT" in prog_text
    assert "Daily Drawdown:" in prog_text
    assert "0.85%" in prog_text


def test_telegram_predictive_heart_formatter():
    data = {
        "current_price": 0.3850,
        "forecast_p50": 0.3980,
        "forecast_p10": 0.3800,
        "forecast_p90": 0.4050,
        "regime": "TRENDING_MOMENTUM",
        "confidence": 0.84,
        "horizon": "15m-1H",
        "cortex_veto": False,
    }
    msg = format_predictive_heart("POL/USDT", data)
    assert "PREDICTIVE HEART" in msg
    assert "POL/USDT" in msg
    assert "WHITE LINE (Real Historical):" in msg
    assert "$0.3850" in msg
    assert "RED LINE (Probabilistic P50):" in msg
    assert "$0.3980" in msg
    assert "84.0%" in msg


def test_telegram_gem_radar_formatter():
    gems = [
        {"symbol": "POL/USDT", "price": 0.385, "liquidity_usd": 12000000.0, "security_score": 99.0, "edge_pct": 1.5},
        {"symbol": "QUICK/USDT", "price": 0.042, "liquidity_usd": 2500000.0, "security_score": 96.0, "edge_pct": 2.2},
    ]
    msg = format_gem_radar(gems)
    assert "POLYGON DEX GEM RADAR & SNIPER" in msg
    assert "POL/USDT" in msg
    assert "QUICK/USDT" in msg
    assert "99/100" in msg


def test_telegram_wallet_hub_formatter():
    profile = {
        "wallet": "0x3C320B3a0917fF44BF6551CDdee44402AFcF250C",
        "sic_id": "SIC-ID-8192-A41F",
        "paper_equity": 10000.0,
        "trading_credits": 50.0,
        "pol_balance": 100.0,
        "withdrawable_rewards": 4.0,
    }
    msg = format_wallet_hub(profile)
    assert "CRYPTOAID 4-MONIES WALLET HUB" in msg
    assert "Paper Capital:" in msg
    assert "$10,000.00 USDT" in msg
    assert "50.00 TAC" in msg
    assert "100.00 POL" in msg
    assert "4.00 POL / USDT" in msg
    assert "SIC-ID-8192-A41F" in msg



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


def test_telegram_topic_router_destinations():
    router = TelegramTopicRouter(bot_token=None)

    # Standard topics
    res1 = router.publish("VERIFIED_AI_SIGNAL", "Signal text", dry_run=True)
    assert res1["status"] == "SIMULATED"
    assert res1["chat_id"] == "@cryptoAIDsupporter"

    res2 = router.publish("AUTOTRADE_RUN_WON", "Run won", dry_run=True)
    assert res2["status"] == "SIMULATED"
    assert res2["chat_id"] == "@cryptoAIDsupporter"

    res3 = router.publish("PROP_CHALLENGE_CREATED", "Challenge created", dry_run=True)
    assert res3["status"] == "SIMULATED"
    assert res3["chat_id"] == "@cryptoAIDsupporter"

    res4 = router.publish("PREDICTIVE_HEART_FORECAST", "Heart dual line", dry_run=True)
    assert res4["status"] == "SIMULATED"
    assert res4["chat_id"] == "@cryptoAIDsupporter"

    # Official Channel broadcast (@cryptoaidsup)
    res5 = router.publish("CHANNEL_VIP_SIGNAL", "VIP Signal", dry_run=True)
    assert res5["status"] == "SIMULATED"
    assert res5["chat_id"] == "@cryptoaidsup"
    assert res5["message_thread_id"] is None


def test_main_menu_keyboard_has_webapp():
    kb = get_main_menu_keyboard()
    # First row has the WebApp button
    first_btn = kb.inline_keyboard[0][0]
    assert "OPEN TRADEAID COCKPIT" in first_btn.text
    assert first_btn.web_app is not None
    assert "dapp.html" in first_btn.web_app.url


def test_bot_commands_execution():
    import asyncio

    async def _runner():
        # Setup mock message and update
        mock_msg = MagicMock()
        mock_msg.reply_text = AsyncMock()

        mock_user = MagicMock(spec=User)
        mock_user.id = 123456789

        update = MagicMock(spec=Update)
        update.effective_message = mock_msg
        update.effective_user = mock_user

        mock_context = MagicMock()
        mock_context.args = []

        # Test /start
        await cmd_start(update, mock_context)
        assert mock_msg.reply_text.called
        start_call_args = mock_msg.reply_text.call_args
        assert "CryptoAID Trade AI" in start_call_args[0][0]
        assert "4-MONIES WALLET HUD" in start_call_args[0][0]

        # Test /run (Autotrade 10 POL)
        mock_msg.reply_text.reset_mock()
        await cmd_run(update, mock_context)
        assert mock_msg.reply_text.called
        run_call_args = mock_msg.reply_text.call_args
        assert "AUTOTRADE RUN #" in run_call_args[0][0]

        # Test /prop
        mock_msg.reply_text.reset_mock()
        await cmd_prop(update, mock_context)
        assert mock_msg.reply_text.called
        prop_call_args = mock_msg.reply_text.call_args
        assert "TRADEAID PROP CHALLENGES" in prop_call_args[0][0]

        # Test /heart
        mock_msg.reply_text.reset_mock()
        mock_context.args = ["POL"]
        await cmd_heart(update, mock_context)
        assert mock_msg.reply_text.called
        heart_call_args = mock_msg.reply_text.call_args
        assert "PREDICTIVE HEART" in heart_call_args[0][0]

        # Test /gem
        mock_msg.reply_text.reset_mock()
        await cmd_gem(update, mock_context)
        assert mock_msg.reply_text.called
        gem_call_args = mock_msg.reply_text.call_args
        assert "GEM RADAR" in gem_call_args[0][0]

        # Test /wallet
        mock_msg.reply_text.reset_mock()
        await cmd_wallet(update, mock_context)
        assert mock_msg.reply_text.called
        wallet_call_args = mock_msg.reply_text.call_args
        assert "4-MONIES WALLET HUB" in wallet_call_args[0][0]

        # Test /link
        mock_msg.reply_text.reset_mock()
        mock_context.args = ["0x71C8364437F559FAf675662a550B94A6F144D3a9"]
        await cmd_link(update, mock_context)
        assert mock_msg.reply_text.called
        link_call_args = mock_msg.reply_text.call_args
        assert "Polygon Wallet Linked!" in link_call_args[0][0]

        # Test /rewards
        mock_msg.reply_text.reset_mock()
        await cmd_rewards(update, mock_context)
        assert mock_msg.reply_text.called
        rewards_call_args = mock_msg.reply_text.call_args
        assert "TRADEAID PROTOCOL REWARDS" in rewards_call_args[0][0]

    asyncio.run(_runner())



def test_bot_app_builder():
    app = build_bot_app()
    assert app is not None
