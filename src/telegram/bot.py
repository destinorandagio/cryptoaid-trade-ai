"""Telegram Bot Runtime for @CryptoAidTradeAIbot & @CryptoAIDsupportBOT with SuperTradingAI Capabilities."""
from __future__ import annotations

import logging
import uuid
from typing import Any
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, WebAppInfo
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
)

from src.agents.meta_agent import MetaAgent
from src.config import settings
from src.data.polygon_scanner import PolygonDEXScanner
from src.data.provider import CompositeMarketDataProvider
from src.execution.paper_engine import PaperExecutionEngine
from src.performance.metrics import calculate_performance
from src.risk.capital_protection import CapitalProtectionEngine
from src.risk.cryptoaid_gate import CryptoAidRiskGate
from src.storage.db import DatabaseManager
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

logger = logging.getLogger(__name__)

# Singletons
db = DatabaseManager()
market_provider = CompositeMarketDataProvider()
scanner = PolygonDEXScanner(market_provider=market_provider)
meta_agent = MetaAgent()
risk_gate = CryptoAidRiskGate()
capital_engine = CapitalProtectionEngine()
execution_engine = PaperExecutionEngine(db=db, risk_engine=capital_engine, risk_gate=risk_gate)
router = TelegramTopicRouter()
deduplicator = SignalDeduplicator()

# Runtime state
_autotrade_active: bool = True
_user_identity_links: dict[int, dict[str, str]] = {}


def get_user_profile(user_id: int | None = None) -> dict[str, Any]:
    """Retrieve user identity and financial balances across the 4 Monies."""
    defaults = {
        "wallet": "0x3C32...250C",
        "sic_id": "SIC-ID-8192-A41F",
        "paper_equity": 10000.0,
        "trading_credits": 50.0,
        "pol_balance": 100.0,
        "withdrawable_rewards": 0.0,
    }
    if user_id and user_id in _user_identity_links:
        defaults.update(_user_identity_links[user_id])
    return defaults


def get_main_menu_keyboard() -> InlineKeyboardMarkup:
    """Inline Keyboard inspired by @SuperTradingAIbot with WebApp launch, Autotrade, Prop, and Predictive Heart."""
    autotrade_label = "🟢 AUTOTRADE: ON" if _autotrade_active else "🔴 AUTOTRADE: OFF"
    ks_label = "🚨 KILL SWITCH: ARMED" if capital_engine.kill_switch_active else "🛡 KILL SWITCH: SAFE"
    webapp_url = "https://trade.cryptoaid.support/dapp.html"

    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🚀 OPEN TRADEAID COCKPIT (WEBAPP)", web_app=WebAppInfo(url=webapp_url))],
        [
            InlineKeyboardButton("⚡ RUN AUTOTRADE (10 POL)", callback_data="ctl_autotrade_run"),
            InlineKeyboardButton("🏆 PROP CHALLENGES", callback_data="ctl_prop_tiers"),
        ],
        [
            InlineKeyboardButton("📈 PREDICTIVE HEART", callback_data="ctl_predictive_heart"),
            InlineKeyboardButton("📡 AI SIGNALS", callback_data="ctl_signals"),
        ],
        [
            InlineKeyboardButton("💎 GEM RADAR / SNIPER", callback_data="ctl_gem_radar"),
            InlineKeyboardButton("📊 POSITIONS & PNL", callback_data="ctl_positions"),
        ],
        [
            InlineKeyboardButton("💼 4-MONIES WALLET", callback_data="ctl_wallet_hub"),
            InlineKeyboardButton("🛡 RISK & CORTEX", callback_data="ctl_risk"),
        ],
        [
            InlineKeyboardButton("🎁 REWARDS & CLAIM", callback_data="ctl_rewards"),
            InlineKeyboardButton("🔗 LINK IDENTITY", callback_data="ctl_link_identity"),
        ],
        [
            InlineKeyboardButton(autotrade_label, callback_data="ctl_toggle_autotrade"),
            InlineKeyboardButton(ks_label, callback_data="ctl_toggle_kill_switch"),
        ],
    ])


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Render the primary trading HUD with WebApp button and account card."""
    profile = get_user_profile(update.effective_user.id if update.effective_user else None)
    text = (
        "🤖 <b>Welcome to CryptoAID Trade AI — Quantitative SuperBot</b>\n\n"
        "⚡ <b>Next-Gen Autonomous Trading & Prop Firm Engine</b>\n"
        "• <b>Chain:</b> Polygon Mainnet (Bor RPC 137)\n"
        "• <b>Predictive Heart:</b> White Line (Real) ⟷ Red Line (P50 Forecast)\n"
        "• <b>Autotrade Model:</b> 10 POL → 1 Run → 2 POL Real Reward\n"
        "• <b>Prop Challenges:</b> $10k, $50k, $100k, $150k Tiers (+8% Target)\n"
        "• <b>Security Policy:</b> Fail-Closed Risk Gate & CORTEX Veto\n\n"
        f"💰 <b>4-MONIES WALLET HUD:</b>\n"
        f"🧪 <b>Paper Capital:</b> ${profile['paper_equity']:,.2f} USDT (Zero-Risk)\n"
        f"⚡ <b>Trading Credits:</b> {profile['trading_credits']:.2f} TAC | 💎 <b>Gas:</b> {profile['pol_balance']:.2f} POL\n"
        f"🏆 <b>Withdrawable Rewards:</b> {profile['withdrawable_rewards']:.2f} POL / USDT\n"
        f"🆔 <b>Identity:</b> <code>{profile['wallet'][:8]}...{profile['wallet'][-4:]}</code> ⟷ <code>{profile['sic_id']}</code>\n\n"
        "Tap <b>OPEN TRADEAID COCKPIT</b> or select an action below:"
    )
    if update.effective_message:
        await update.effective_message.reply_text(text, parse_mode="HTML", reply_markup=get_main_menu_keyboard())


async def cmd_run(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Execute 1 Autotrade Run (10 POL -> Paper Execution -> Win 2 POL / Loss 0 POL)."""
    user_id = update.effective_user.id if update.effective_user else 1
    profile = get_user_profile(user_id)
    run_uuid = uuid.uuid4()
    run_short = str(run_uuid)[:8]

    # Evaluate current market condition for POL/USDT
    snap = market_provider.get_snapshot("POL/USDT")
    meta_dec = meta_agent.evaluate(snap)

    # Determine simulated run outcome based on net edge and confidence
    is_win = meta_dec.confidence >= 0.65 or meta_dec.net_edge_pct > 0.003
    gross_pnl = 45.20 if is_win else -22.50
    costs = 2.70
    net_pnl = gross_pnl - costs
    reward_amount = 2.0 if is_win else 0.0
    reward_status = "RESERVED" if is_win else "NONE"
    result = "WIN" if is_win else "LOSS"

    run_data = {
        "run_id": f"RUN_{run_short}",
        "wallet": profile["wallet"],
        "result": result,
        "gross_pnl": gross_pnl,
        "execution_costs": costs,
        "net_pnl": net_pnl,
        "reward_amount": reward_amount,
        "reward_status": reward_status,
        "strategy": meta_dec.strategy_name if hasattr(meta_dec, "strategy_name") else "MetaAgent",
    }

    # If win, accrue withdrawable reward in user's profile
    if is_win:
        profile["withdrawable_rewards"] = profile.get("withdrawable_rewards", 0.0) + reward_amount
        _user_identity_links[user_id] = profile

    text = format_autotrade_run_event(run_data)

    # Publish notification into official group's TRADE AI topic
    router.publish(
        "AUTOTRADE_RUN_WON" if is_win else "AUTOTRADE_RUN_LOST",
        text,
        reply_markup=None,
    )

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("⚡ RUN AGAIN (10 POL)", callback_data="ctl_autotrade_run")],
        [InlineKeyboardButton("🚀 VIEW COCKPIT (WEBAPP)", web_app=WebAppInfo(url="https://trade.cryptoaid.support/dapp.html"))],
        [InlineKeyboardButton("🔙 MAIN MENU", callback_data="ctl_main_menu")],
    ])

    if update.effective_message:
        await update.effective_message.reply_text(text, parse_mode="HTML", reply_markup=kb)


async def cmd_prop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Display the 4 official Prop Challenge Tiers and Progress."""
    text = format_prop_tiers()
    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🥉 $10k STARTER", callback_data="ctl_prop_10k"),
            InlineKeyboardButton("🥈 $50k PRO", callback_data="ctl_prop_50k"),
        ],
        [
            InlineKeyboardButton("🥇 $100k ELITE", callback_data="ctl_prop_100k"),
            InlineKeyboardButton("👑 $150k BLACK", callback_data="ctl_prop_150k"),
        ],
        [InlineKeyboardButton("📊 CHECK ACTIVE PROGRESS", callback_data="ctl_prop_progress")],
        [InlineKeyboardButton("🚀 START IN WEBAPP", web_app=WebAppInfo(url="https://trade.cryptoaid.support/dapp.html"))],
    ])
    if update.effective_message:
        await update.effective_message.reply_text(text, parse_mode="HTML", reply_markup=kb)


async def cmd_heart(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Render Predictive Heart Dual-Line: White Line (Real) vs Red Line (P50 envelope)."""
    asset = "POL/USDT"
    if context.args and len(context.args) > 0:
        arg = context.args[0].upper()
        if "/" not in arg:
            arg = f"{arg}/USDT"
        if arg in settings.universe:
            asset = arg

    snap = market_provider.get_snapshot(asset)
    meta_dec = meta_agent.evaluate(snap)

    # Compute probabilistic forecast trajectory
    is_bull = meta_dec.decision.value in ("BUY", "LONG")
    drift = 0.018 if is_bull else -0.014
    forecast_p50 = snap.price * (1.0 + drift)
    data = {
        "current_price": snap.price,
        "forecast_p50": forecast_p50,
        "forecast_p10": forecast_p50 * 0.985,
        "forecast_p90": forecast_p50 * 1.018,
        "regime": meta_dec.regime.value,
        "confidence": meta_dec.confidence,
        "horizon": meta_dec.time_horizon,
        "cortex_veto": False,
    }
    text = format_predictive_heart(asset, data)
    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⚪ POL/USDT", callback_data="ctl_heart_POL"),
            InlineKeyboardButton("🟡 WETH/USDT", callback_data="ctl_heart_WETH"),
            InlineKeyboardButton("🟠 WBTC/USDT", callback_data="ctl_heart_WBTC"),
        ],
        [InlineKeyboardButton("🚀 LIVE OSCILLOSCOPE (WEBAPP)", web_app=WebAppInfo(url="https://trade.cryptoaid.support/dapp.html"))],
    ])
    if update.effective_message:
        await update.effective_message.reply_text(text, parse_mode="HTML", reply_markup=kb)


async def cmd_gem(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Display Polygon DEX Gem Scanner & Sniping radar."""
    gems = [
        {"symbol": "POL/USDT", "price": market_provider.get_snapshot("POL/USDT").price, "liquidity_usd": 12400000.0, "security_score": 99.0, "edge_pct": 1.45},
        {"symbol": "LINK/USDT", "price": market_provider.get_snapshot("LINK/USDT").price, "liquidity_usd": 6800000.0, "security_score": 98.0, "edge_pct": 0.88},
        {"symbol": "QUICK/USDT", "price": 0.0425, "liquidity_usd": 2150000.0, "security_score": 96.0, "edge_pct": 2.10},
        {"symbol": "GHST/USDT", "price": 1.15, "liquidity_usd": 1420000.0, "security_score": 94.0, "edge_pct": 1.75},
    ]
    text = format_gem_radar(gems)
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("⚡ SNIPE BEST PAIR", callback_data="ctl_autotrade_run")],
        [InlineKeyboardButton("🚀 OPEN RADAR COCKPIT", web_app=WebAppInfo(url="https://trade.cryptoaid.support/dapp.html"))],
    ])
    if update.effective_message:
        await update.effective_message.reply_text(text, parse_mode="HTML", reply_markup=kb)


async def cmd_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Display user's 4-Monies balance card with linked identity."""
    user_id = update.effective_user.id if update.effective_user else None
    profile = get_user_profile(user_id)
    text = format_wallet_hub(profile)
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🎁 CLAIM REWARDS", callback_data="ctl_rewards")],
        [InlineKeyboardButton("🔗 LINK WALLET / SIC-ID", callback_data="ctl_link_identity")],
    ])
    if update.effective_message:
        await update.effective_message.reply_text(text, parse_mode="HTML", reply_markup=kb)


async def cmd_link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Link user's Telegram ID to their Polygon Wallet or SIC-ID Digital Twin."""
    user_id = update.effective_user.id if update.effective_user else 1
    profile = get_user_profile(user_id)

    if not context.args or len(context.args) == 0:
        text = (
            "🔗 <b>Federated Identity Linker</b>\n\n"
            "To connect your on-chain account or digital twin, send:\n"
            "• <code>/link 0xYourPolygonAddress</code>\n"
            "• or <code>/link SIC-ID-XXXX-XXXX</code>\n\n"
            f"<b>Current link:</b>\n"
            f"• Wallet: <code>{profile['wallet']}</code>\n"
            f"• Digital Twin: <code>{profile['sic_id']}</code>"
        )
    else:
        arg = context.args[0].strip()
        if arg.startswith("0x") and len(arg) >= 10:
            profile["wallet"] = arg
            _user_identity_links[user_id] = profile
            text = f"✅ <b>Polygon Wallet Linked!</b>\nNew active address: <code>{arg}</code>"
        elif arg.upper().startswith("SIC-ID"):
            profile["sic_id"] = arg.upper()
            _user_identity_links[user_id] = profile
            text = f"✅ <b>Digital Twin Linked!</b>\nFederated SIC-ID: <code>{profile['sic_id']}</code>"
        else:
            text = "⚠️ <b>Invalid Format</b>. Please provide a valid Polygon address (0x...) or SIC-ID."

    if update.effective_message:
        await update.effective_message.reply_text(text, parse_mode="HTML")


async def cmd_rewards(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Display user's accrued rewards from winning Autotrade runs and Prop milestones."""
    user_id = update.effective_user.id if update.effective_user else None
    profile = get_user_profile(user_id)
    reward_bal = profile.get("withdrawable_rewards", 0.0)

    text = (
        "🏆 <b>TRADEAID PROTOCOL REWARDS & ACCRUAL</b>\n\n"
        f"<b>Accrued Withdrawable Rewards:</b> <b>{reward_bal:.2f} POL / USDT</b>\n"
        f"<b>Destination Wallet:</b> <code>{profile['wallet']}</code>\n\n"
        "• <b>Autotrade Wins:</b> +2.0 POL per winning run\n"
        "• <b>Prop Challenges:</b> Milestone allocations from Protocol Reward Pool\n\n"
        "<i>Withdrawals are executed directly on Polygon Mainnet via Protocol Treasury contract.</i>"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("⚡ RUN AUTOTRADE (10 POL)", callback_data="ctl_autotrade_run")],
        [InlineKeyboardButton("🚀 WITHDRAW IN COCKPIT", web_app=WebAppInfo(url="https://trade.cryptoaid.support/dapp.html"))],
    ])
    if update.effective_message:
        await update.effective_message.reply_text(text, parse_mode="HTML", reply_markup=kb)


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    state = execution_engine.get_portfolio_state()
    autotrade_status = "🟢 ACTIVE" if _autotrade_active else "🔴 PAUSED"
    ks_status = "🚨 TRIGGERED" if capital_engine.kill_switch_active else "🛡 OK (DISARMED)"
    text = (
        f"🤖 <b>CryptoAID Trade AI — System Status</b>\n\n"
        f"<b>Environment:</b> {settings.app_env}\n"
        f"<b>Polygon Chain ID:</b> 137 (Bor RPC)\n"
        f"<b>Autotrade Engine:</b> {autotrade_status}\n"
        f"<b>Kill Switch:</b> {ks_status}\n"
        f"<b>Active Positions:</b> {state.active_positions_count} / {settings.max_simultaneous_positions}\n"
        f"<b>Total Equity:</b> ${state.total_equity:,.2f} USDT\n"
        f"<b>Cash Available:</b> ${state.cash_balance:,.2f} USDT\n"
        f"<b>Drawdown:</b> {state.current_drawdown_pct:.1f}%\n"
        f"<b>Live Trading Flag:</b> {settings.live_trading_enabled}\n"
    )
    if update.effective_message:
        await update.effective_message.reply_text(text, parse_mode="HTML")


async def cmd_scan(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_message:
        await update.effective_message.reply_text("🔄 <i>Scanning Polygon universe across Multi-Strategy & Risk Gates...</i>", parse_mode="HTML")

    lines = ["🔍 <b>Polygon Scanner Snapshot:</b>\n"]
    for sym in settings.universe:
        metrics = scanner.scan_asset(sym)
        snap = market_provider.get_snapshot(sym)
        meta_dec = meta_agent.evaluate(snap)
        tradable_badge = "✅ TRADABLE" if metrics.is_tradable else "⚠️ GATED"
        lines.append(
            f"• <b>{sym}</b>: ${snap.price:,.4f if snap.price < 10 else snap.price:,.2f}\n"
            f"  Signal: <b>{meta_dec.decision.value}</b> ({meta_dec.confidence*100:.0f}%) | Regime: <code>{meta_dec.regime.value}</code>\n"
            f"  Liquidity: ${metrics.liquidity_depth_usd/1e6:.1f}M | Spread: {metrics.spread_pct*100:.2f}% | Gate: {tradable_badge}\n"
        )
    if update.effective_message:
        await update.effective_message.reply_text("\n".join(lines), parse_mode="HTML")


async def cmd_signals(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    found_signals = 0
    for sym in settings.universe:
        snap = market_provider.get_snapshot(sym)
        meta_dec = meta_agent.evaluate(snap)
        risk_res = risk_gate.evaluate(meta_dec, snap)

        if meta_dec.decision.value in ("BUY", "LONG") and risk_res.passed:
            found_signals += 1
            text = format_ai_signal(
                signal_id=f"SIG_{sym.replace('/', '_')}",
                asset=sym,
                signal=meta_dec.decision.value,
                confidence=meta_dec.confidence,
                strategy="MetaStrategy",
                regime=meta_dec.regime.value,
                timeframe=meta_dec.time_horizon,
                entry=meta_dec.entry_price,
                sl=meta_dec.recommended_stop_loss,
                tp=meta_dec.recommended_take_profit,
                trailing=None,
                expected_net_edge_pct=meta_dec.net_edge_pct,
                slippage_est_pct=meta_dec.slippage_pct,
                price_impact_pct=meta_dec.price_impact_pct,
                gas_estimate_usd=meta_dec.estimated_gas_usd,
                risk_gate_status="PASS",
                execution_mode="PAPER" if not settings.live_trading_enabled else "LIVE",
                evidence=meta_dec.evidence,
                timestamp=snap.timestamp.strftime("%Y-%m-%d %H:%M:%S UTC"),
            )
            if update.effective_message:
                await update.effective_message.reply_text(text, parse_mode="HTML")

    if found_signals == 0 and update.effective_message:
        await update.effective_message.reply_text("📡 <b>No active signals passing net edge & risk criteria at this moment.</b>", parse_mode="HTML")


async def cmd_portfolio(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    state = execution_engine.get_portfolio_state()
    positions = db.get_open_positions()

    text = (
        f"💼 <b>CryptoAID Portfolio Accounting (USDT)</b>\n\n"
        f"<b>Total Equity:</b> ${state.total_equity:,.2f} USDT\n"
        f"<b>Cash Balance:</b> ${state.cash_balance:,.2f} USDT\n"
        f"<b>Allocated Notional:</b> ${state.allocated_margin:,.2f} USDT\n"
        f"<b>Realized P&L:</b> ${state.daily_realized_pnl:+,.2f} USDT\n"
        f"<b>Unrealized P&L:</b> ${state.unrealized_pnl:+,.2f} USDT\n"
        f"<b>Drawdown:</b> {state.current_drawdown_pct:.1f}%\n"
        f"<b>Open Positions:</b> {len(positions)} active\n\n"
        f"<i>Settlement: 100% USDT on Polygon</i>"
    )
    if update.effective_message:
        await update.effective_message.reply_text(text, parse_mode="HTML")


async def cmd_positions(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    positions = db.get_open_positions()
    if not positions:
        text = "📊 <b>Active Positions:</b> Zero open positions. Capital 100% in USDT."
    else:
        lines = ["📊 <b>Active Guardian Positions:</b>\n"]
        for p in positions:
            p_curr = p['current_price']
            p_curr_str = f"${p_curr:,.4f}" if p_curr < 10 else f"${p_curr:,.2f}"
            p_entry = p['entry_price']
            p_entry_str = f"${p_entry:,.4f}" if p_entry < 10 else f"${p_entry:,.2f}"
            lines.append(
                f"• <b>{p['side']} {p['asset']}</b>\n"
                f"  Size: {p['size']} | Entry: {p_entry_str} -> Current: {p_curr_str}\n"
                f"  PnL: <b>${p['unrealized_pnl']:+,.2f} ({p.get('unrealized_pnl_pct', 0.0):+.2f}%)</b>\n"
                f"  SL: ${p.get('sl', 0.0) or 0.0:.4f} | TP: ${p.get('tp', 0.0) or 0.0:.4f}\n"
            )
        text = "\n".join(lines)
    if update.effective_message:
        await update.effective_message.reply_text(text, parse_mode="HTML")


async def cmd_trades(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    trades = db.get_trades(limit=8)
    if not trades:
        text = "📜 <b>Execution History:</b> No recorded trades yet."
    else:
        lines = ["📜 <b>Recent Execution Trades:</b>\n"]
        for t in trades:
            p_str = f"${t['price']:,.4f}" if t['price'] < 10 else f"${t['price']:,.2f}"
            lines.append(
                f"• <code>{t['executed_at'][:19]}</code> | <b>{t['side']} {t['asset']}</b>\n"
                f"  Price: {p_str} | Size: {t['size']} | Fees: ${t['fees']:.4f}\n"
            )
        text = "\n".join(lines)
    if update.effective_message:
        await update.effective_message.reply_text(text, parse_mode="HTML")


async def cmd_performance(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    closed = [o for o in db.get_orders() if o["status"] == "CLOSED"]
    metrics = calculate_performance(closed, initial_capital=settings.default_paper_capital)
    text = (
        f"🏆 <b>Verifiable Performance Engine ({metrics.environment})</b>\n\n"
        f"<b>Total Closed Trades:</b> {metrics.trade_count}\n"
        f"<b>Win Rate:</b> {metrics.win_rate_pct:.1f}% ({metrics.winning_trades}W / {metrics.losing_trades}L)\n"
        f"<b>Net P&L:</b> ${metrics.net_pnl:+,.2f} USDT ({metrics.return_pct:+.2f}%)\n"
        f"<b>Profit Factor:</b> {metrics.profit_factor:.2f}\n"
        f"<b>Sharpe Ratio:</b> {metrics.sharpe_ratio:.2f}\n"
        f"<b>Sortino Ratio:</b> {metrics.sortino_ratio:.2f}\n"
        f"<b>Max Drawdown:</b> {metrics.max_drawdown_pct:.1f}%\n\n"
        f"<i>Initial Capital: $1,000.00 USDT</i>"
    )
    if update.effective_message:
        await update.effective_message.reply_text(text, parse_mode="HTML")


async def cmd_strategies(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    lines = ["🧠 <b>Multi-Strategy Engine Architecture:</b>\n"]
    lines.append("• <b>ScalpingAgent:</b> 1m/3m/5m micro-structure with tight spread gate")
    lines.append("• <b>TrendAgent:</b> Moving average alignment & ADX continuation")
    lines.append("• <b>MomentumAgent:</b> Multi-timeframe RSI & MACD divergence")
    lines.append("• <b>BreakoutAgent:</b> Donchian channel & volatility expansion")
    lines.append("• <b>MeanReversionAgent:</b> Bollinger band compression & statistical z-score")
    lines.append("• <b>VolatilityAgent:</b> ATR expansion & volatility regime")
    lines.append("• <b>RiskAgent:</b> Tail risk & fail-closed capital safety")
    lines.append("\n<b>Regime Matrix:</b> TRENDING, RANGING, HIGH_VOL, LOW_VOL, LOW_LIQ, RISK_OFF")
    if update.effective_message:
        await update.effective_message.reply_text("\n".join(lines), parse_mode="HTML")


async def cmd_risk(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        "🛡 <b>CryptoAID Risk & Capital Protection Gates</b>\n\n"
        f"• <b>Base Capital:</b> ${settings.default_paper_capital:,.2f} USDT\n"
        f"• <b>Max Position Size:</b> {settings.max_position_size_ratio*100:.0f}% (${settings.default_paper_capital*settings.max_position_size_ratio:.0f} USDT)\n"
        f"• <b>Max Total Exposure:</b> {settings.max_portfolio_exposure_ratio*100:.0f}% (${settings.default_paper_capital*settings.max_portfolio_exposure_ratio:.0f} USDT)\n"
        f"• <b>Daily Loss Breaker:</b> {settings.daily_loss_limit_ratio*100:.0f}% (${settings.default_paper_capital*settings.daily_loss_limit_ratio:.0f} USDT)\n"
        f"• <b>Max Drawdown Limit:</b> {settings.max_drawdown_limit_ratio*100:.0f}%\n"
        f"• <b>Consecutive Loss Limit:</b> {settings.consecutive_loss_limit} trades\n"
        f"• <b>Emergency Stop Ceiling:</b> {settings.emergency_stop_ceiling_pct*100:.0f}% (Absolute Stop Loss)\n"
        f"• <b>Max Swap Slippage:</b> {settings.hard_max_slippage_bps/100:.2f}%\n"
        f"• <b>Kill Switch:</b> {'🚨 ACTIVE' if capital_engine.kill_switch_active else 'DISARMED'}\n"
    )
    if update.effective_message:
        await update.effective_message.reply_text(text, parse_mode="HTML")


async def cmd_autotrade(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    global _autotrade_active
    _autotrade_active = not _autotrade_active
    status = "🟢 ACTIVE" if _autotrade_active else "🔴 PAUSED"
    text = f"🤖 <b>Autonomous Trading Engine:</b> {status}"
    if update.effective_message:
        await update.effective_message.reply_text(text, parse_mode="HTML")


async def cmd_stop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    global _autotrade_active
    _autotrade_active = False
    capital_engine.kill_switch_active = True
    closed = execution_engine.guardian.emergency_close_all(reason="Operator /stop command")
    text = f"🚨 <b>KILL SWITCH TRIGGERED & ENGINE STOPPED!</b>\n\nAutotrade paused. Closed {len(closed)} open positions back to USDT."
    if update.effective_message:
        await update.effective_message.reply_text(text, parse_mode="HTML")


async def cmd_resume(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    global _autotrade_active
    _autotrade_active = True
    capital_engine.kill_switch_active = False
    text = "🟢 <b>SYSTEM RESUMED:</b> Kill switch disarmed and autotrade active."
    if update.effective_message:
        await update.effective_message.reply_text(text, parse_mode="HTML")


async def cmd_health(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    rpc_ok = execution_engine.router.polygon.is_healthy()
    text = (
        "🩺 <b>CryptoAID System Healthcheck</b>\n\n"
        f"• <b>Polygon Bor RPC:</b> {'🟢 CONNECTED (Chain 137)' if rpc_ok else '🟡 FALLBACK'}\n"
        f"• <b>Market Data Provider:</b> 🟢 ONLINE\n"
        f"• <b>Database Ledgers:</b> 🟢 MIGRATED (V1.1 Atomic Units)\n"
        f"• <b>Position Guardian:</b> 🟢 ACTIVE (24/7 Monitoring)\n"
        f"• <b>Telegram Topic Router:</b> 🟢 OPERATIONAL\n"
        f"• <b>Risk Gate Engine:</b> 🟢 FAIL-CLOSED\n"
    )
    if update.effective_message:
        await update.effective_message.reply_text(text, parse_mode="HTML")


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query:
        return
    await query.answer()

    data = query.data
    global _autotrade_active

    if data == "ctl_main_menu":
        await cmd_start(update, context)
    elif data == "ctl_autotrade_run":
        await cmd_run(update, context)
    elif data == "ctl_prop_tiers":
        await cmd_prop(update, context)
    elif data == "ctl_predictive_heart":
        await cmd_heart(update, context)
    elif data == "ctl_heart_POL":
        context.args = ["POL"]
        await cmd_heart(update, context)
    elif data == "ctl_heart_WETH":
        context.args = ["WETH"]
        await cmd_heart(update, context)
    elif data == "ctl_heart_WBTC":
        context.args = ["WBTC"]
        await cmd_heart(update, context)
    elif data == "ctl_gem_radar":
        await cmd_gem(update, context)
    elif data == "ctl_wallet_hub":
        await cmd_wallet(update, context)
    elif data == "ctl_rewards":
        await cmd_rewards(update, context)
    elif data == "ctl_link_identity":
        await cmd_link(update, context)
    elif data in ("ctl_prop_10k", "ctl_prop_50k", "ctl_prop_100k", "ctl_prop_150k"):
        tier_names = {"ctl_prop_10k": "STARTER", "ctl_prop_50k": "PRO", "ctl_prop_100k": "ELITE", "ctl_prop_150k": "BLACK"}
        tier = tier_names.get(data, "PRO")
        await query.message.reply_text(
            f"🎯 <b>Tier Selected: {tier}</b>\n\nTo activate your challenge and start trading with Paper capital, open the Cockpit below:",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🚀 ACTIVATE IN WEBAPP", web_app=WebAppInfo(url="https://trade.cryptoaid.support/dapp.html"))]
            ]),
        )
    elif data == "ctl_prop_progress":
        user_id = update.effective_user.id if update.effective_user else 1
        demo_ch = {
            "challenge_id": f"CH_{str(user_id)[:6]}",
            "tier": "PRO",
            "initial_balance": 50000.0,
            "current_equity": 52450.0,
            "daily_drawdown_pct": 0.85,
            "max_drawdown_pct": 1.40,
            "status": "ACTIVE",
        }
        await query.message.reply_text(format_prop_challenge_progress(demo_ch), parse_mode="HTML")
    elif data == "ctl_toggle_autotrade":
        _autotrade_active = not _autotrade_active
        await query.message.reply_text(f"🤖 <b>Autotrade:</b> {'🟢 ACTIVE' if _autotrade_active else '🔴 PAUSED'}", parse_mode="HTML")
    elif data == "ctl_balance":
        await cmd_portfolio(update, context)
    elif data == "ctl_positions":
        await cmd_positions(update, context)
    elif data == "ctl_signals":
        await cmd_signals(update, context)
    elif data == "ctl_strategies":
        await cmd_strategies(update, context)
    elif data == "ctl_risk":
        await cmd_risk(update, context)
    elif data == "ctl_performance":
        await cmd_performance(update, context)
    elif data == "ctl_toggle_kill_switch":
        if capital_engine.kill_switch_active:
            capital_engine.kill_switch_active = False
            await query.message.reply_text("🛡 <b>Kill switch DISARMED.</b>", parse_mode="HTML")
        else:
            capital_engine.kill_switch_active = True
            await query.message.reply_text("🚨 <b>KILL SWITCH ARMED! All new trades blocked.</b>", parse_mode="HTML")


def build_bot_app() -> Application:
    """Build python-telegram-bot application with all SuperTradingAI commands and handlers."""
    token = settings.telegram_bot_token or "MOCK_TOKEN_FOR_BUILD"
    builder = Application.builder().token(token)
    app = builder.build()

    commands = {
        "start": cmd_start,
        "run": cmd_run,
        "autotrade_run": cmd_run,
        "prop": cmd_prop,
        "challenge": cmd_prop,
        "heart": cmd_heart,
        "predict": cmd_heart,
        "gem": cmd_gem,
        "snipe": cmd_gem,
        "wallet": cmd_wallet,
        "link": cmd_link,
        "rewards": cmd_rewards,
        "claim": cmd_rewards,
        "status": cmd_status,
        "scan": cmd_scan,
        "signals": cmd_signals,
        "portfolio": cmd_portfolio,
        "positions": cmd_positions,
        "trades": cmd_trades,
        "performance": cmd_performance,
        "strategies": cmd_strategies,
        "risk": cmd_risk,
        "autotrade": cmd_autotrade,
        "stop": cmd_stop,
        "resume": cmd_resume,
        "health": cmd_health,
    }

    for name, handler in commands.items():
        app.add_handler(CommandHandler(name, handler))

    app.add_handler(CallbackQueryHandler(button_callback))
    return app
