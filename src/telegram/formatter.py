"""Telegram message formatting conforming to CryptoAID specifications."""
from __future__ import annotations

from typing import Any


def format_ai_signal(
    signal_id: str,
    asset: str,
    signal: str,
    confidence: float,
    strategy: str = "MetaAgent",
    regime: str = "RANGING",
    timeframe: str = "15m-1H",
    entry: float = 0.0,
    sl: float | None = None,
    tp: float | None = None,
    trailing: float | None = None,
    expected_net_edge_pct: float = 0.004,
    slippage_est_pct: float = 0.0015,
    price_impact_pct: float = 0.0008,
    gas_estimate_usd: float = 0.015,
    risk_gate_status: str = "PASS",
    execution_mode: str = "PAPER",
    evidence: list[str] | None = None,
    timestamp: str = "",
    risk_pct: float | None = None,
    **kwargs: Any,
) -> str:
    """Format standardized signal announcement for Telegram AI SIGNALS topic."""
    evidence_lines = "\n".join(f"• {e}" for e in (evidence or [])[:3])
    sl_str = f"${sl:,.4f}" if sl and sl < 10 else (f"${sl:,.2f}" if sl else "N/A")
    tp_str = f"${tp:,.4f}" if tp and tp < 10 else (f"${tp:,.2f}" if tp else "N/A")
    trailing_str = f"${trailing:,.4f}" if trailing and trailing < 10 else (f"${trailing:,.2f}" if trailing else "Dynamic")
    entry_str = f"${entry:,.4f}" if entry < 10 else f"${entry:,.2f}"
    conf_pct = confidence * 100.0
    conf_str = f"{int(conf_pct)}%" if conf_pct.is_integer() else f"{conf_pct:.1f}%"

    return f"""📡 <b>CRYPTOAID TRADE AI — SIGNAL DISPATCH</b>

<b>SIGNAL_ID:</b> <code>{signal_id}</code>
<b>ASSET:</b> <code>{asset}</code> (Polygon)
<b>SIGNAL:</b> <b>{signal}</b>
<b>CONFIDENCE:</b> <b>{conf_str}</b>
<b>STRATEGY:</b> <code>{strategy}</code>
<b>REGIME:</b> <code>{regime}</code>
<b>TIMEFRAME:</b> {timeframe}

<b>ENTRY:</b> {entry_str}
<b>STOP:</b> {sl_str} (Dynamic Ceiling: 5%)
<b>TARGET:</b> {tp_str}
<b>TRAILING:</b> {trailing_str}

<b>EXPECTED NET EDGE:</b> <b>{expected_net_edge_pct * 100:+.3f}%</b>
<b>SLIPPAGE EST:</b> {slippage_est_pct * 100:.2f}% (Hard Max: 1.0%)
<b>PRICE IMPACT:</b> {price_impact_pct * 100:.3f}%
<b>GAS ESTIMATE:</b> ${gas_estimate_usd:.4f} (Polygon)
<b>CRYPTOAID RISK:</b> 🛡 <b>{risk_gate_status}</b>
<b>EXECUTION MODE:</b> 🧪 <b>{execution_mode}</b>

<b>EVIDENCE:</b>
{evidence_lines}

<i>Timestamp: {timestamp}</i>
"""


def format_paper_trade_event(order: dict[str, Any]) -> str:
    """Format paper order execution or close notification for TRADE AI topic."""
    status = order.get("status", "OPEN")
    side = order.get("side", "BUY")
    asset = order.get("asset", "")
    entry = order.get("entry", 0.0)
    size = order.get("size", 0.0)
    pnl = order.get("pnl", 0.0)
    pnl_pct = order.get("pnl_percent", 0.0)
    fees = order.get("fees", 0.0)
    reason = order.get("reason", "")
    entry_str = f"${entry:,.4f}" if entry < 10 else f"${entry:,.2f}"

    if status == "FILLED":
        return f"""🤖 <b>TRADE AI — EXECUTION EVENT</b>

<b>STATUS:</b> 💼 <b>POSITION OPENED</b>
<b>ASSET:</b> <code>{asset}</code>
<b>SIDE:</b> {side}
<b>SIZE:</b> {size}
<b>ENTRY:</b> {entry_str}
<b>FEES & GAS:</b> ${fees:.4f} USDT
<b>STRATEGY:</b> {order.get('strategy', 'MetaAgent')}
<b>EXECUTION ROUTE:</b> Polygon DEX (Uniswap V3 / QuickSwap)

<i>Runtime: AUTOMATED 24/7 PAPER ENGINE</i>
"""
    elif status == "CLOSED":
        emoji = "🟢" if pnl >= 0 else "🔴"
        exit_p = order.get('exit_price', 0.0)
        exit_str = f"${exit_p:,.4f}" if exit_p < 10 else f"${exit_p:,.2f}"
        return f"""{emoji} <b>TRADE AI — SETTLEMENT EVENT</b>

<b>STATUS:</b> 🏁 <b>POSITION CLOSED -> USDT SETTLED</b>
<b>ASSET:</b> <code>{asset}</code>
<b>SIDE:</b> {side}
<b>EXIT PRICE:</b> {exit_str}
<b>NET P&L:</b> <b>{pnl:+.2f} USDT ({pnl_pct:+.2f}%)</b>
<b>SETTLEMENT:</b> 100% USDT
<b>REASON:</b> {reason}

<i>Guardian state verified and persisted to DB.</i>
"""
    return f"Order {order.get('order_id')}: {status}"


def format_security_rejection(asset: str, reasons: list[str]) -> str:
    """Format risk gate rejection message for SECURITY & SCAM topic."""
    reasons_str = "\n".join(f"• {r}" for r in reasons)
    return f"""🚨 <b>CRYPTOAID RISK GATE — REJECTION ALERT</b>

<b>ASSET:</b> <code>{asset}</code>
<b>DECISION:</b> ❌ <b>TRADE REJECTED</b> (Strict Fail-Closed Security Policy)

<b>FAIL-CLOSED AUDIT FINDINGS:</b>
{reasons_str}

<i>Protected by CryptoAID Digital Twin, Smart Contract Security & Anti-Scam Intelligence.</i>
"""
