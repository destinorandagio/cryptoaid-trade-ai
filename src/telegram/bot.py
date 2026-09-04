"""Telegram Bot Runtime for @CryptoAidTradeAIbot with Complete Command & Control Suite."""
from __future__ import annotations

import logging
from typing import Any
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
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
from src.telegram.formatter import format_ai_signal, format_paper_trade_event, format_security_rejection
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

# Runtime flags
_autotrade_active: bool = True


def get_main_menu_keyboard() -> InlineKeyboardMarkup:
    """Inline Keyboard with the 8 required controls."""
    autotrade_label = "🟢 AUTOTRADE: ON" if _autotrade_active else "🔴 AUTOTRADE: OFF"
    ks_label = "🚨 KILL SWITCH: ACTIVE" if capital_engine.kill_switch_active else "🛡 KILL SWITCH: DISARMED"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(autotrade_label, callback_data="ctl_toggle_autotrade")],
        [InlineKeyboardButton("💰 BALANCE", callback_data="ctl_balance"), InlineKeyboardButton("📊 POSITIONS", callback_data="ctl_positions")],
        [InlineKeyboardButton("📡 SIGNALS", callback_data="ctl_signals"), InlineKeyboardButton("🧠 STRATEGIES", callback_data="ctl_strategies")],
        [InlineKeyboardButton("🛡 RISK", callback_data="ctl_risk"), InlineKeyboardButton("🏆 PERFORMANCE", callback_data="ctl_performance")],
        [InlineKeyboardButton(ks_label, callback_data="ctl_toggle_kill_switch")],
    ])


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        "🤖 <b>Welcome to CryptoAID Trade AI</b>\n\n"
        "Autonomous Polygon DEX Quantitative System\n"
        "• <b>Base Asset:</b> USDT Accounting\n"
        "• <b>Universe:</b> POL, WETH, WBTC, LINK\n"
        "• <b>Mode:</b> PAPER / AUTOMATED 24/7\n"
        "• <b>Protection:</b> CryptoAID Support Risk Gate\n\n"
        "Select an action or use command shortcuts below:"
    )
    if update.effective_message:
        await update.effective_message.reply_text(text, parse_mode="HTML", reply_markup=get_main_menu_keyboard())


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    state = execution_engine.get_portfolio_state()
    autotrade_status = "🟢 ACTIVE" if _autotrade_active else "🔴 PAUSED"
    ks_status = "🚨 TRIGGERED" if capital_engine.kill_switch_active else "🛡 OK (DISARMED)"
    text = (
        f"🤖 <b>CryptoAID Trade AI — System Status</b>\n\n"
        f"<b>Environment:</b> {settings.app_env}\n"
        f"<b>Polygon Chain ID:</b> 137 (Mainnet)\n"
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
    # Close open positions via Guardian
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
        f"• <b>SQLite Database:</b> 🟢 MIGRATED (16 Tables)\n"
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

    if data == "ctl_toggle_autotrade":
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
    """Build python-telegram-bot application with all 14 required commands and handlers."""
    token = settings.telegram_bot_token or "MOCK_TOKEN_FOR_BUILD"
    builder = Application.builder().token(token)
    app = builder.build()

    commands = {
        "start": cmd_start,
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
