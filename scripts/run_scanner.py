"""CLI Market Scanner for CryptoAID Trade AI."""
from __future__ import annotations

import sys
from pathlib import Path

# Bootstrap project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.agents.meta_agent import MetaAgent
from src.config import settings
from src.data.provider import CompositeMarketDataProvider
from src.risk.cryptoaid_gate import CryptoAidRiskGate


def main() -> None:
    print("=" * 65)
    print("  CRYPTOAID TRADE AI — MULTI-AGENT MARKET SCANNER")
    print("=" * 65)
    mkt = CompositeMarketDataProvider()
    meta = MetaAgent()
    gate = CryptoAidRiskGate()

    for symbol in settings.universe:
        snap = mkt.get_snapshot(symbol)
        dec = meta.evaluate(snap)
        risk = gate.evaluate(dec, snap)

        print(f"\n[ASSET] {symbol}")
        print(f"  Price: ${snap.price:,.2f} | 24h Vol: ${snap.volume_24h:,.0f} | 24h Chg: {snap.change_24h_pct:+.2f}%")
        print(f"  Meta Decision: {dec.decision.value} (Confidence: {dec.confidence*100:.1f}%)")
        print(f"  Stop Loss: {dec.recommended_stop_loss} | Take Profit: {dec.recommended_take_profit}")
        print(f"  CryptoAID Risk Gate: {risk.final_decision} (Score: {risk.composite_risk_score})")
        if risk.rejection_reasons:
            print(f"  Rejection reasons: {', '.join(risk.rejection_reasons)}")
        print("  Key Evidence:")
        for ev in dec.evidence:
            print(f"    • {ev}")

    print("\n" + "=" * 65)
    print("  Scan complete. Status: VERIFIED PAPER TRADING")
    print("=" * 65)


if __name__ == "__main__":
    main()
