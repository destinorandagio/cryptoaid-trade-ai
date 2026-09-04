"""Polygon DEX Execution and Smart Routing Module for CryptoAID Trade AI."""
from src.dex.polygon import PolygonProvider
from src.dex.router import SmartExecutionRouter, RouteQuote
from src.dex.signer import DedicatedWalletSigner

__all__ = [
    "PolygonProvider",
    "SmartExecutionRouter",
    "RouteQuote",
    "DedicatedWalletSigner",
]
