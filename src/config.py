"""Configuration module for CryptoAID Trade AI."""
from __future__ import annotations

import os
from pathlib import Path
from pydantic import BaseModel, Field
from dotenv import load_dotenv

# Load local env if present
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)


class Settings(BaseModel):
    # App & Runtime
    app_name: str = "CryptoAID Trade AI"
    app_version: str = "1.0.0"
    app_env: str = Field(default_factory=lambda: os.getenv("APP_ENV", "production"))
    
    # CRITICAL SECURITY RULE: Live trading strictly false by default (fail-closed)
    live_trading_enabled: bool = Field(default_factory=lambda: os.getenv("LIVE_TRADING_ENABLED", "false").lower() in ("true", "1"))
    
    # Polygon Network & Web3
    polygon_chain_id: int = 137
    polygon_rpc_url: str = Field(default_factory=lambda: os.getenv("POLYGON_RPC", "https://polygon-bor-rpc.publicnode.com"))
    polygon_backup_rpc_urls: list[str] = [
        "https://polygon-rpc.com",
        "https://rpc.ankr.com/polygon",
        "https://1rpc.io/matic",
    ]
    
    # Dedicated Trading Wallet Signer (Server-side only, NEVER log or expose)
    trading_wallet_address: str | None = Field(default_factory=lambda: os.getenv("TRADING_WALLET_ADDRESS"))
    trading_wallet_private_key: str | None = Field(default_factory=lambda: os.getenv("TRADING_WALLET_PRIVATE_KEY"))
    
    # Database
    db_path: Path = DATA_DIR / "trade_ai.db"
    
    # Market Universe: USDT Accounting with Polygon Top Liquid Candidates
    base_quote: str = "USDT"
    universe: list[str] = ["POL/USDT", "WETH/USDT", "WBTC/USDT", "LINK/USDT"]
    
    # Polygon Contract Addresses (Mainnet)
    token_addresses: dict[str, str] = {
        "USDT": "0xc2132D05D31c914a87C6611C10748AEb04B58e8F",
        "POL": "0x0000000000000000000000000000000000001010",
        "WPOL": "0x0d500B1d8E8eF31E21C99d1Db9A6444d3ADf1270",
        "WETH": "0x7ceB23fD6bC0adD59E62ac25578270cFf1b9f619",
        "WBTC": "0x1BFD67037B42Cf73acF2047067bd4F2C47D9BfD6",
        "LINK": "0x53E0bca35eC356BD5ddDFebbD1Fc0fD03FaBad39",
    }
    
    token_decimals: dict[str, int] = {
        "USDT": 6,
        "POL": 18,
        "WPOL": 18,
        "WETH": 18,
        "WBTC": 8,
        "LINK": 18,
    }
    
    # DEX Routers on Polygon
    uniswap_v3_router: str = "0xE592427A0AEce92De3Edee1F18E0157C05861564"
    uniswap_v3_quoter: str = "0x61fFE014bA17989E743c5F6cB21bF9697530B21e"
    quickswap_router: str = "0xa5E0829CaCEd8fFDD4De3c43696c57F7D7A678ff"
    
    # Capital & Execution Model (Starting capital ~1,000 USDT)
    default_paper_capital: float = 1_000.0
    max_position_size_ratio: float = 0.10       # Max 10% capital ($100 on $1,000) per trade
    max_portfolio_exposure_ratio: float = 0.50  # Max 50% capital ($500 on $1,000) active exposure
    max_simultaneous_positions: int = 4         # Maximum concurrent active positions
    max_leverage: float = 1.0                   # Spot DEX execution only (no leverage)
    
    # Slippage & Execution Quality (P0)
    dynamic_slippage_bps: float = 20.0          # 0.20% dynamic base slippage tolerance
    hard_max_slippage_bps: float = 100.0        # 1.00% absolute hard maximum swap slippage ceiling
    emergency_stop_ceiling_pct: float = 0.05    # 5.0% Emergency Stop Loss ceiling (NOT swap slippage)
    max_price_impact_pct: float = 0.008         # 0.80% maximum price impact allowed
    min_net_edge_pct: float = 0.004             # 0.40% minimum net edge required to trade
    quote_validity_seconds: int = 15            # Reject quotes older than 15 seconds
    
    # Realistic DEX Fees & Gas Modeling
    dex_fee_bps: float = 30.0                   # 0.30% standard DEX pool fee (e.g. Uniswap 0.30% or 0.05%)
    simulated_fee_bps: float = 30.0             # 0.30% simulated trading fee in bps
    simulated_slippage_bps: float = 15.0        # 0.15% realistic DEX execution slippage
    polygon_base_gas_units: int = 180_000       # Typical ERC-20 DEX swap gas units on Polygon
    
    # Risk & Capital Protection
    daily_loss_limit_ratio: float = 0.03        # 3.0% daily loss circuit breaker ($30 on $1,000)
    weekly_loss_limit_ratio: float = 0.06       # 6.0% weekly loss limit ($60 on $1,000)
    max_drawdown_limit_ratio: float = 0.10      # 10.0% max drawdown limit ($100 on $1,000)
    consecutive_loss_limit: int = 3             # Pause after 3 consecutive losses
    default_stop_loss_pct: float = 0.015        # 1.5% dynamic ATR/volatility stop loss
    default_take_profit_pct: float = 0.035      # 3.5% take profit
    trailing_stop_activation_pct: float = 0.018 # Activate trailing after +1.8% gain
    trailing_distance_pct: float = 0.010        # 1.0% trailing distance
    break_even_activation_pct: float = 0.012    # Move SL to break-even after +1.2% gain
    kill_switch_active: bool = False
    
    # Strategy & MetaAgent
    min_confidence_threshold: float = 0.65      # Minimum confidence for directional trade
    autotrade_enabled: bool = True              # Autonomous multi-strategy paper trading daemon
    
    # Telegram Integration
    telegram_bot_token: str | None = Field(default_factory=lambda: os.getenv("TELEGRAM_BOT_TOKEN"))
    telegram_group: str = Field(default_factory=lambda: os.getenv("TELEGRAM_GROUP", "@cryptoAIDsupporter"))
    telegram_channel: str = Field(default_factory=lambda: os.getenv("TELEGRAM_CHANNEL", "@cryptoaidsup"))
    
    # Telegram Topics (CryptoAID Official Structure)
    topic_trade_ai: int | None = Field(default_factory=lambda: int(os.getenv("TOPIC_TRADE_AI_ID")) if os.getenv("TOPIC_TRADE_AI_ID") else None)
    topic_ai_signals: int | None = Field(default_factory=lambda: int(os.getenv("TOPIC_AI_SIGNALS_ID")) if os.getenv("TOPIC_AI_SIGNALS_ID") else None)
    topic_security_scam: int | None = Field(default_factory=lambda: int(os.getenv("TOPIC_SECURITY_SCAM_ID")) if os.getenv("TOPIC_SECURITY_SCAM_ID") else None)
    topic_cryptoaid_lab: int | None = Field(default_factory=lambda: int(os.getenv("TOPIC_CRYPTOAID_LAB_ID")) if os.getenv("TOPIC_CRYPTOAID_LAB_ID") else None)
    
    # AI Gateway / LLM (Advisory explanation only, never invent prices, never send secrets)
    groq_api_key: str | None = Field(default_factory=lambda: os.getenv("GROQ_API_KEY"))
    openai_api_key: str | None = Field(default_factory=lambda: os.getenv("OPENAI_API_KEY"))
    gemini_api_key: str | None = Field(default_factory=lambda: os.getenv("GEMINI_API_KEY"))


settings = Settings()
