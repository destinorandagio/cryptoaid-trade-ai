"""
Challenge Risk Agent — Top-Tier Institutional Prop Firm Risk Rules (Option A)
Enforces Consistency Rule, News Trading Filter, Weekend Sizing Reduction,
Drawdown Gates, and 80% Real Payout Calculations.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional, List, Tuple
import numpy as np
import pandas as pd

logger = logging.getLogger("trade_ai.challenge_risk_agent")


# ============================================================
# CONFIGURAZIONE E COSTANTI TIERS
# ============================================================

class TradeDirection(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"
    BUY = "BUY"
    SELL = "SELL"


class CortexHealth(str, Enum):
    GREEN = "GREEN"      # Normale (DD basso, operatività piena)
    YELLOW = "YELLOW"    # DD crescente (Modalità difensiva, size ridotta)
    ORANGE = "ORANGE"    # Vicino al limite (Capital preservation, solo trade ad alto RR)
    RED = "RED"          # Niente nuove posizioni (Freeze totale entrate)
    BREACH = "BREACH"    # Challenge fallita per violazione Daily DD o Total DD


class RiskDecision(str, Enum):
    PASS = "PASS"                      # Approvato a size piena
    REDUCE = "REDUCE"                  # Approvato con size ridotta dai vincoli di rischio
    REDUCE_SIZE = "REDUCE_SIZE"        # Alias canonico V2 per size ridotta
    REJECT = "REJECT"                  # Rifiutato (Headroom esaurito, violazione, o CORTEX RED)
    EXIT = "EXIT"                      # Richiesta di chiusura posizione
    CLOSE_EXISTING = "CLOSE_EXISTING"  # Richiesta di chiusura posizione esistente a rischio
    CLOSE_ALL = "CLOSE_ALL"            # Chiusura immediata di tutte le posizioni (Breach prevention)


@dataclass
class TradeIntent:
    intent_id: str
    target_asset: str
    direction: TradeDirection | str
    target_price: float
    timeframe: str = "15m"
    strategy_name: str = "PredictiveHeart"
    prediction_confidence: float = 0.80
    strategy_confidence: float = 0.85
    market_regime: str = "TRENDING_BULL"
    volatility_14d: float = 0.02
    atr_14: float | None = None
    estimated_slippage_pct: float = 0.0005
    estimated_price_impact_pct: float = 0.0005
    estimated_gas_usd: float = 0.05
    current_portfolio_exposure: dict[str, float] = field(default_factory=dict)
    challenge_id: str | None = None
    volume_24h_usd: float = 5_000_000.0
    book_depth_usd: float = 200_000.0
    contract_verified: bool = True
    is_honeypot: bool = False
    token_tax_pct: float = 0.0


@dataclass
class TradeAuthorization:
    intent_id: str
    decision: RiskDecision
    authorized: bool
    position_size_units: float
    nominal_value_usdt: float
    authorized_leverage: int
    stop_loss_price: float
    take_profit_price: float
    trailing_stop_price: float
    max_hold_hours: int
    risk_budget_usd: float
    cortex_health: CortexHealth
    rejection_reason: str | None = None
    audit_trail: dict[str, Any] = field(default_factory=dict)


@dataclass
class TierConfig:
    name: str
    nominal_capital: float
    max_daily_dd_pct: float  # Es. 0.05 per 5%
    max_total_dd_pct: float  # Es. 0.10 per 10%
    phase1_target_pct: float # Es. 0.08 per 8%
    min_trading_days: int


TIER_STARTER = TierConfig(
    name="STARTER",
    nominal_capital=10000.0,
    max_daily_dd_pct=0.05,
    max_total_dd_pct=0.10,
    phase1_target_pct=0.08,
    min_trading_days=5,
)

TIER_PRO = TierConfig(
    name="PRO",
    nominal_capital=50000.0,
    max_daily_dd_pct=0.05,
    max_total_dd_pct=0.10,
    phase1_target_pct=0.08,
    min_trading_days=5,
)

TIER_ELITE = TierConfig(
    name="ELITE",
    nominal_capital=100000.0,
    max_daily_dd_pct=0.05,
    max_total_dd_pct=0.10,
    phase1_target_pct=0.08,
    min_trading_days=5,
)

TIER_BLACK = TierConfig(
    name="BLACK",
    nominal_capital=150000.0,
    max_daily_dd_pct=0.05,
    max_total_dd_pct=0.10,
    phase1_target_pct=0.08,
    min_trading_days=5,
)


# ============================================================
# 1. CHALLENGE STATE MANAGER (CON MARK-TO-MARKET CONTINUO)
# ============================================================

class ChallengeState:
    """
    Mantiene lo stato finanziario in tempo reale della challenge.
    Monitora continuamente l'equity intraday (incluso unrealized P&L),
    la Distance to Ruin e la CORTEX Challenge Health.
    """
    def __init__(self, tier_config: TierConfig):
        self.config = tier_config
        self.starting_balance = tier_config.nominal_capital
        self.cash_balance = tier_config.nominal_capital
        self.unrealized_pnl = 0.0
        self.current_equity = tier_config.nominal_capital

        # Tracking Drawdown
        self.high_water_mark = tier_config.nominal_capital
        self.daily_start_equity = tier_config.nominal_capital # Reset a mezzanotte UTC

        # Storico per analisi
        self.daily_snapshots: list[float] = []

    def update_equity(self, new_equity: float):
        """Aggiorna l'equity totale (chiusura trade o snapshot)."""
        self.current_equity = new_equity
        self.cash_balance = new_equity
        self.unrealized_pnl = 0.0
        if new_equity > self.high_water_mark:
            self.high_water_mark = new_equity

    def update_mark_to_market(self, unrealized_pnl: float, cash_balance: float | None = None):
        """
        Aggiornamento continuo intraday con Mark-to-Market delle posizioni aperte.
        Non aspetta mezzanotte per rilevare breach di Daily DD o Total DD!
        """
        if cash_balance is not None:
            self.cash_balance = cash_balance
        self.unrealized_pnl = unrealized_pnl
        self.current_equity = self.cash_balance + self.unrealized_pnl
        if self.current_equity > self.high_water_mark:
            self.high_water_mark = self.current_equity

    def reset_daily_tracking(self):
        """Da chiamare ogni giorno a 00:00 UTC"""
        self.daily_start_equity = self.current_equity
        self.daily_snapshots.append(self.current_equity)

    @property
    def total_dd_usd(self) -> float:
        return max(0.0, self.high_water_mark - self.current_equity)

    @property
    def total_dd_pct(self) -> float:
        return self.total_dd_usd / self.starting_balance if self.starting_balance > 0 else 0.0

    @property
    def daily_dd_usd(self) -> float:
        loss = self.daily_start_equity - self.current_equity
        return max(0.0, loss)

    @property
    def daily_dd_pct(self) -> float:
        return self.daily_dd_usd / self.daily_start_equity if self.daily_start_equity > 0 else 0.0

    @property
    def target_equity_usd(self) -> float:
        return self.starting_balance * (1.0 + self.config.phase1_target_pct)

    @property
    def distance_to_target_usd(self) -> float:
        return max(0.0, self.target_equity_usd - self.current_equity)

    @property
    def distance_to_target_pct(self) -> float:
        return self.distance_to_target_usd / self.starting_balance if self.starting_balance > 0 else 0.0

    @property
    def daily_dd_limit_usd(self) -> float:
        return self.daily_start_equity * self.config.max_daily_dd_pct

    @property
    def total_dd_limit_usd(self) -> float:
        return self.starting_balance * self.config.max_total_dd_pct

    @property
    def daily_headroom_usd(self) -> float:
        return max(0.0, self.daily_dd_limit_usd - self.daily_dd_usd)

    @property
    def total_headroom_usd(self) -> float:
        return max(0.0, self.total_dd_limit_usd - self.total_dd_usd)

    @property
    def distance_to_ruin_usd(self) -> float:
        """La capacità residua prima del fallimento (minimo tra daily e total headroom)."""
        return min(self.daily_headroom_usd, self.total_headroom_usd)

    @property
    def cortex_health(self) -> CortexHealth:
        """
        State Machine CORTEX Health (Parametrica sui limiti configurati del Tier):
        GREEN -> YELLOW -> ORANGE -> RED -> BREACH
        Soglie proporzionali:
        - RED: >= 90% del Drawdown limite consumato (es. 4.5% su 5%)
        - ORANGE: >= 70% del Drawdown limite consumato (es. 3.5% su 5%)
        - YELLOW: >= 40% del Drawdown limite consumato (es. 2.0% su 5%)
        - GREEN: < 40% del Drawdown limite consumato
        """
        if self.check_violations() is not None:
            return CortexHealth.BREACH

        daily_limit = self.config.max_daily_dd_pct if self.config.max_daily_dd_pct > 0 else 0.05
        total_limit = self.config.max_total_dd_pct if self.config.max_total_dd_pct > 0 else 0.10

        daily_ratio = self.daily_dd_pct / daily_limit
        total_ratio = self.total_dd_pct / total_limit
        worst_ratio = max(daily_ratio, total_ratio)

        if worst_ratio >= 1.0:
            return CortexHealth.BREACH
        if worst_ratio >= 0.90:
            return CortexHealth.RED
        if worst_ratio >= 0.70:
            return CortexHealth.ORANGE
        if worst_ratio >= 0.40:
            return CortexHealth.YELLOW
        return CortexHealth.GREEN

    @property
    def available_risk_budget_usd(self) -> float:
        """
        Available Risk Budget = remaining DD capacity × safety factor.
        In DEFENSIVE / CAPITAL PRESERVATION, il budget viene tagliato drasticamente.
        """
        health = self.cortex_health
        if health == CortexHealth.GREEN:
            safety_factor = 0.40  # Max 40% del headroom
        elif health == CortexHealth.YELLOW:
            safety_factor = 0.25  # Max 25% del headroom
        elif health == CortexHealth.ORANGE:
            safety_factor = 0.10  # Max 10% del headroom
        else:
            safety_factor = 0.0   # RED o BREACH: nessun nuovo trade!

        return round(self.distance_to_ruin_usd * safety_factor, 2)

    def check_violations(self) -> str | None:
        if self.total_dd_pct >= self.config.max_total_dd_pct:
            return "TOTAL_DD_EXCEEDED"
        if self.daily_dd_pct >= self.config.max_daily_dd_pct:
            return "DAILY_DD_EXCEEDED"
        return None



# ============================================================
# 2. RISK METRICS ENGINE
# ============================================================

class RiskMetrics:
    """
    Calcola ATR, Correlazioni e Volatilità per il sizing.
    """
    @staticmethod
    def calculate_atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> float:
        """Calcola l'Average True Range"""
        tr1 = high - low
        tr2 = (high - close.shift()).abs()
        tr3 = (low - close.shift()).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        res = tr.rolling(window=period).mean().iloc[-1]
        return float(res) if pd.notna(res) else float(tr.mean())

    @staticmethod
    def calculate_correlation(asset_returns: pd.Series, portfolio_returns: pd.Series) -> float:
        """Calcola correlazione rolling a 30 periodi"""
        if len(asset_returns) < 10 or len(portfolio_returns) < 10:
            return 0.0
        corr = asset_returns.tail(30).corr(portfolio_returns.tail(30))
        return float(corr) if pd.notna(corr) else 0.0

    @staticmethod
    def calculate_rolling_correlation_matrix(
        price_series_dict: dict[str, pd.Series | list[float]],
        window: int = 30,
    ) -> pd.DataFrame:
        """
        Calcola la vera Rolling Correlation Matrix sui rendimenti percentuali.
        Sostituisce qualsiasi stima artificiale o statica.
        """
        if not price_series_dict:
            return pd.DataFrame()

        clean_dict = {}
        for k, v in price_series_dict.items():
            if isinstance(v, pd.Series):
                clean_dict[k] = v.values
            elif isinstance(v, (list, np.ndarray)):
                clean_dict[k] = np.array(v, dtype=float)

        min_len = min(len(arr) for arr in clean_dict.values()) if clean_dict else 0
        if min_len < 3:
            cols = list(clean_dict.keys())
            return pd.DataFrame(np.eye(len(cols)), index=cols, columns=cols)

        df_prices = pd.DataFrame({k: v[-min_len:] for k, v in clean_dict.items()})
        returns = df_prices.pct_change().dropna()
        if len(returns) < 2:
            cols = list(clean_dict.keys())
            return pd.DataFrame(np.eye(len(cols)), index=cols, columns=cols)

        tail_returns = returns.tail(min(len(returns), window))
        corr_matrix = tail_returns.corr()
        return corr_matrix.fillna(0.0)

    @classmethod
    def get_pairwise_correlation(
        cls,
        asset_a: str,
        asset_b: str,
        market_series_dict: dict[str, Any] | None = None,
        regime: str = "TRENDING_BULL",
    ) -> float:
        """
        Restituisce la reale correlazione storica rolling tra due asset.
        Se mancano serie storiche complete, usa un prior bayesiano dipendente dal regime di mercato
        invece di una costante statica hardcoded (es. 0.8).
        """
        a_clean = asset_a.split("/")[0].upper()
        b_clean = asset_b.split("/")[0].upper()
        if a_clean == b_clean:
            return 1.0

        if market_series_dict and a_clean in market_series_dict and b_clean in market_series_dict:
            series_a = market_series_dict[a_clean]
            series_b = market_series_dict[b_clean]
            if isinstance(series_a, pd.DataFrame) and 'close' in series_a:
                series_a = series_a['close']
            if isinstance(series_b, pd.DataFrame) and 'close' in series_b:
                series_b = series_b['close']
            returns_a = pd.Series(series_a).pct_change().dropna()
            returns_b = pd.Series(series_b).pct_change().dropna()
            if len(returns_a) >= 10 and len(returns_b) >= 10:
                corr = returns_a.tail(30).corr(returns_b.tail(30))
                if pd.notna(corr):
                    return float(corr)

        # Dynamic Prior per Regime di Mercato (non costante fissa)
        regime_upper = regime.upper()
        if "HIGH_VOLATILITY" in regime_upper:
            return 0.70  # Nelle espansioni di volatilità le correlazioni crypto convergono
        elif "TRENDING" in regime_upper:
            return 0.55  # Durante trend forte c'è moderata correlazione di beta
        elif "RANGING" in regime_upper:
            return 0.35  # Durante lateralità le correlazioni cross-asset si disaccoppiano
        return 0.50


@dataclass
class MacroEvent:
    name: str
    timestamp_utc: float
    window_minutes: int = 5  # 5 min before and after


@dataclass
class PositionSizingResult:
    can_execute: bool
    rejection_reason: str | None
    quantity: float
    nominal_value_usdt: float
    effective_leverage: float
    risk_usdt: float
    risk_pct_balance: float
    entry_price: float
    stop_loss_price: float
    take_profit_price: float
    sl_distance_usdt: float
    tp_distance_usdt: float
    risk_reward_ratio: float
    daily_dd_budget_remaining_usdt: float


@dataclass
class ChallengeRiskDecision:
    can_trade: bool
    position_size_multiplier: float  # 1.0 standard, 0.5 on weekends
    veto_reason: str | None
    current_total_dd_pct: float
    current_daily_dd_pct: float
    is_consistency_satisfied: bool
    highest_day_profit_ratio: float  # Must be <= 0.30 (30%)
    status: str  # ACTIVE, PASSED, FAILED
    tac_credits_awarded: float
    withdrawable_payout_usdt: float  # 80% of verified profits


class ChallengeRiskAgent:
    """
    Decide SE entrare e QUANTO comprare/vendere basandosi sui vincoli Prop.
    """

    TARGET_PROFIT_PCT = 8.0          # +8% target
    MAX_TOTAL_DD_PCT = 10.0          # -10% max total drawdown
    MAX_DAILY_DD_PCT = 5.0           # -5% max daily drawdown
    MIN_TRADING_DAYS = 5             # Minimum 5 days
    MAX_SINGLE_DAY_PROFIT_RATIO = 0.30  # Consistency Rule: max 30% on a single day
    PAYOUT_SHARE_PCT = 0.80          # 80% profit share to user

    # Known high-impact macro events calendar (CPI, FOMC, NFP)
    SCHEDULED_EVENTS: list[MacroEvent] = [
        MacroEvent(name="US CPI Release", timestamp_utc=1788547200.0, window_minutes=5),
        MacroEvent(name="FOMC Rate Decision", timestamp_utc=1788633600.0, window_minutes=10),
    ]

    def __init__(
        self,
        tier_or_state: ChallengeState | TierConfig | None = None,
        tier_fee_usdt: float = 100.0,
        virtual_capital: float = 100000.0,
    ):
        if isinstance(tier_or_state, ChallengeState):
            self.state = tier_or_state
            self.virtual_capital = tier_or_state.starting_balance
            self.tier_fee_usdt = tier_fee_usdt
        elif isinstance(tier_or_state, TierConfig):
            self.state = ChallengeState(tier_or_state)
            self.virtual_capital = tier_or_state.nominal_capital
            self.tier_fee_usdt = tier_fee_usdt
        else:
            self.tier_fee_usdt = tier_fee_usdt
            self.virtual_capital = virtual_capital
            cfg = TierConfig(
                name="CUSTOM",
                nominal_capital=virtual_capital,
                max_daily_dd_pct=0.05,
                max_total_dd_pct=0.10,
                phase1_target_pct=0.08,
                min_trading_days=5,
            )
            self.state = ChallengeState(cfg)

        self.metrics = RiskMetrics()
        self.risk_per_trade_pct = 0.005 # 0.5% risk per trade
        self.atr_multiplier_sl = 2.0    # Stop Loss distance = 2 * ATR
        self.max_correlation_threshold = 0.7

    def evaluate_trade(
        self,
        signal_direction: TradeDirection | str,
        entry_price: float,
        asset_historical_data: pd.DataFrame, # Deve contenere 'high', 'low', 'close'
        current_portfolio_exposure: dict[str, float] | None = None,
        target_asset_id: str = "BTC",
    ) -> dict[str, Any]:
        """
        Restituisce un dizionario con decisione, size e motivazione basata su ATR e vincoli Prop.
        """
        if current_portfolio_exposure is None:
            current_portfolio_exposure = {}

        dir_enum = signal_direction if isinstance(signal_direction, TradeDirection) else TradeDirection(str(signal_direction).upper())

        # 1. CHECK VIOLATIONS (Hard Stop)
        violation = self.state.check_violations()
        if violation:
            return {"action": "VETO", "reason": f"Challenge Violation: {violation}"}

        # 2. CHECK DAILY HEADROOM (Safety Buffer dinamico: 80% del limite)
        daily_limit_usd = self.state.daily_start_equity * self.state.config.max_daily_dd_pct
        daily_headroom = daily_limit_usd - self.state.daily_dd_usd

        # Se abbiamo già perso l'80% o più del limite giornaliero (es. >=4% su 5%), blocchiamo nuove entrate
        if self.state.daily_dd_pct >= (self.state.config.max_daily_dd_pct * 0.80):
            return {"action": "VETO", "reason": "Daily DD approaching limit"}

        # 3. CALCULATE VOLATILITY & STOP LOSS
        atr = self.metrics.calculate_atr(
            asset_historical_data['high'],
            asset_historical_data['low'],
            asset_historical_data['close'],
        )

        sl_distance_price = atr * self.atr_multiplier_sl
        if sl_distance_price <= 0:
            return {"action": "VETO", "reason": "Invalid ATR Data"}

        # 4. CALCULATE POSITION SIZE
        risk_amount_usd = self.state.current_equity * self.risk_per_trade_pct

        # La size non deve mai consumare più del 50% dell'headroom giornaliero residuo
        max_risk_by_headroom = daily_headroom * 0.5
        effective_risk_cap = min(risk_amount_usd, max_risk_by_headroom)

        position_size_units = effective_risk_cap / sl_distance_price

        # Controllo minimo di liquidità/size
        if position_size_units * entry_price < 100: # Min trade size $100
            return {"action": "VETO", "reason": "Position size too small"}

        # 5. CHECK CORRELATION (Exposure Cap)
        total_correlated_exposure = 0.0
        for asset_id, exposure in current_portfolio_exposure.items():
            corr_factor = 0.8 if asset_id != target_asset_id else 1.0
            total_correlated_exposure += (exposure * corr_factor)

        new_exposure = position_size_units * entry_price
        if (total_correlated_exposure + new_exposure) > (self.state.current_equity * 0.20):
            return {"action": "VETO", "reason": "Max Correlated Exposure Exceeded"}

        # 6. APPROVAL
        stop_loss_price = entry_price - sl_distance_price if dir_enum == TradeDirection.LONG else entry_price + sl_distance_price
        take_profit_price = entry_price + (sl_distance_price * 1.5) if dir_enum == TradeDirection.LONG else entry_price - (sl_distance_price * 1.5)

        return {
            "action": "APPROVED",
            "size_units": round(position_size_units, 4),
            "stop_loss": round(stop_loss_price, 2),
            "take_profit": round(take_profit_price, 2),
            "risk_usd": round(effective_risk_cap, 2),
            "atr_used": round(atr, 2),
        }

    def get_dynamic_risk_parameters(
        self,
        strategy_name: str = "MOMENTUM",
        regime: str = "TRENDING_BULL",
        volatility_14d: float = 0.02,
        experience_matrix_reliability: float = 0.75,
    ) -> dict[str, float]:
        """
        Calcola i parametri di rischio in modo completamente parametrico basandosi su:
        TIER × STRATEGY × REGIME × VOLATILITY × LIQUIDITY × DRAWDOWN STATE × EXPERIENCE MATRIX
        Nessun valore è una costante universale fissa.
        """
        # 1. Base Risk per trade da Tier Nominal Capital
        cap = self.state.starting_balance
        if cap >= 150000.0:
            base_risk_pct = 0.0075
        elif cap >= 50000.0:
            base_risk_pct = 0.0075
        else:
            base_risk_pct = 0.0050

        # 2. Strategy Multiplier & ATR Multipliers
        strat_upper = strategy_name.upper()
        if "SCALP" in strat_upper:
            strat_mult = 0.60
            atr_mult_sl = 1.3
            target_rr = 1.5
        elif "MOMENTUM" in strat_upper:
            strat_mult = 1.00
            atr_mult_sl = 1.8
            target_rr = 2.0
        elif "TREND" in strat_upper:
            strat_mult = 1.20
            atr_mult_sl = 2.5
            target_rr = 2.5
        elif "MEAN_REVERSION" in strat_upper:
            strat_mult = 0.75
            atr_mult_sl = 1.5
            target_rr = 1.6
        elif "BREAKOUT" in strat_upper:
            strat_mult = 0.90
            atr_mult_sl = 1.7
            target_rr = 2.2
        else:
            strat_mult = 0.80
            atr_mult_sl = 1.8
            target_rr = 2.0

        # 3. Regime Multiplier
        reg_upper = regime.upper()
        if "HIGH_VOLATILITY" in reg_upper:
            reg_mult = 0.50
            atr_mult_sl *= 1.25  # Allarga lo stop per evitare whip da rumore
        elif "TRENDING" in reg_upper:
            reg_mult = 1.00
        elif "RANGING_LOW_VOL" in reg_upper:
            reg_mult = 0.85
            atr_mult_sl *= 0.90
        elif "RANGING" in reg_upper:
            reg_mult = 0.75
        else:
            reg_mult = 0.70

        # 4. Volatility Multiplier
        vol_mult = 1.0 / (1.0 + max(0.0, (volatility_14d - 0.02) * 12.0))

        # 5. Drawdown State Multiplier (CORTEX State Machine)
        health = self.state.cortex_health
        if health == CortexHealth.GREEN:
            dd_mult = 1.00
            max_exp_pct = 0.25
        elif health == CortexHealth.YELLOW:
            dd_mult = 0.70
            max_exp_pct = 0.15
        elif health == CortexHealth.ORANGE:
            dd_mult = 0.35
            max_exp_pct = 0.08
        else:
            dd_mult = 0.00
            max_exp_pct = 0.00

        # 6. Experience Matrix Reliability Scaling
        exp_mult = max(0.60, min(1.25, experience_matrix_reliability / 0.70))

        final_risk_per_trade_pct = base_risk_pct * strat_mult * reg_mult * vol_mult * dd_mult * exp_mult
        min_trade_notional = max(25.0, cap * 0.001)

        return {
            "risk_per_trade_pct": final_risk_per_trade_pct,
            "atr_multiplier_sl": round(atr_mult_sl, 2),
            "target_risk_reward": round(target_rr, 2),
            "max_correlated_exposure_pct": max_exp_pct,
            "min_trade_notional_usd": min_trade_notional,
        }

    def evaluate_execution_gates(
        self,
        intent: TradeIntent,
        trial_nominal_usd: float,
        available_budget_usd: float,
    ) -> tuple[bool, RiskDecision, str | None, float]:
        """
        Valuta gli 8 Execution Gates istituzionali prima di autorizzare qualsiasi trade:
        1. LIQUIDITY GATE
        2. SLIPPAGE GATE
        3. PRICE IMPACT GATE
        4. GAS / COST GATE
        5. PREDICTION CONFIDENCE GATE
        6. STRATEGY CONFIDENCE GATE
        7. REGIME COMPATIBILITY GATE
        8. CORTEX TOKEN / CONTRACT RISK GATE
        """
        health = self.state.cortex_health
        size_mult = 1.0

        # Gate 8: CORTEX TOKEN / CONTRACT RISK GATE
        if not getattr(intent, "contract_verified", True):
            return False, RiskDecision.REJECT, "CONTRACT_RISK_GATE: Token contract unverified", 0.0
        if getattr(intent, "is_honeypot", False):
            return False, RiskDecision.REJECT, "CONTRACT_RISK_GATE: Honeypot / Transfer tax exploit detected", 0.0
        if getattr(intent, "token_tax_pct", 0.0) > 0.01:
            return False, RiskDecision.REJECT, f"CONTRACT_RISK_GATE: Token tax ({intent.token_tax_pct:.1%}) exceeds 1.0% limit", 0.0

        # Gate 1: LIQUIDITY GATE
        vol_24h = getattr(intent, "volume_24h_usd", 5_000_000.0)
        book_depth = getattr(intent, "book_depth_usd", 200_000.0)
        if trial_nominal_usd > (vol_24h * 0.05):
            return False, RiskDecision.REJECT, f"LIQUIDITY_GATE: Order size (${trial_nominal_usd:,.2f}) exceeds 5% of 24h volume (${vol_24h:,.2f})", 0.0
        if trial_nominal_usd > (book_depth * 0.50):
            size_mult *= 0.60  # Riduci la size per evitare di svuotare il book

        # Gate 2: SLIPPAGE GATE
        slip = intent.estimated_slippage_pct
        if slip > 0.0040:  # > 0.40%
            return False, RiskDecision.REJECT, f"SLIPPAGE_GATE: Estimated slippage ({slip:.2%}) exceeds 0.40% tolerance", 0.0
        elif slip > 0.0015:  # > 0.15%
            size_mult *= max(0.50, 1.0 - (slip * 50.0))

        # Gate 3: PRICE IMPACT GATE
        impact = intent.estimated_price_impact_pct
        if impact > 0.0030:  # > 0.30%
            return False, RiskDecision.REJECT, f"PRICE_IMPACT_GATE: Estimated price impact ({impact:.2%}) exceeds 0.30% tolerance", 0.0
        elif impact > 0.0010:
            size_mult *= max(0.60, 1.0 - (impact * 60.0))

        # Gate 4: GAS / COST GATE
        gas = intent.estimated_gas_usd
        if available_budget_usd > 0 and (gas / available_budget_usd) > 0.25:
            return False, RiskDecision.REJECT, f"GAS_COST_GATE: Execution costs (${gas:.2f}) consume > 25% of trade risk budget (${available_budget_usd:.2f})", 0.0

        # Gate 5: PREDICTION CONFIDENCE GATE
        min_pred_conf = 0.75 if health == CortexHealth.ORANGE else 0.60
        if intent.prediction_confidence < min_pred_conf:
            return False, RiskDecision.REJECT, f"PREDICTION_CONFIDENCE_GATE: Confidence ({intent.prediction_confidence:.2f}) below threshold ({min_pred_conf:.2f}) for state {health.value}", 0.0

        # Gate 6: STRATEGY CONFIDENCE GATE
        min_strat_conf = 0.70 if health in (CortexHealth.YELLOW, CortexHealth.ORANGE) else 0.60
        if intent.strategy_confidence < min_strat_conf:
            return False, RiskDecision.REJECT, f"STRATEGY_CONFIDENCE_GATE: Strategy confidence ({intent.strategy_confidence:.2f}) below threshold ({min_strat_conf:.2f})", 0.0

        # Gate 7: REGIME COMPATIBILITY GATE
        strat_up = intent.strategy_name.upper()
        reg_up = intent.market_regime.upper()
        if "MEAN_REVERSION" in strat_up and ("HIGH_VOLATILITY" in reg_up or "RUNAWAY" in reg_up):
            return False, RiskDecision.REJECT, f"REGIME_COMPATIBILITY_GATE: Mean reversion incompatible with volatile runaway regime ({reg_up})", 0.0
        if "TREND" in strat_up and "RANGING_LOW_VOL" in reg_up:
            size_mult *= 0.50

        decision = RiskDecision.REDUCE_SIZE if size_mult < 0.95 else RiskDecision.PASS
        return True, decision, None, size_mult

    def evaluate_portfolio_close_triggers(
        self,
        open_positions: list[dict[str, Any]],
        current_market_regime: str = "TRENDING_BULL",
    ) -> list[dict[str, Any]]:
        """
        Valuta la necessità di intervenire d'emergenza sulle posizioni aperte:
        - CLOSE_ALL: Se scatta BREACH o Daily DD critico.
        - CLOSE_EXISTING: Se un asset specifico subisce shift di regime avverso o perdita non tollerabile in CORTEX RED.
        """
        triggers = []
        health = self.state.cortex_health

        if health == CortexHealth.BREACH:
            for pos in open_positions:
                triggers.append({
                    "position_id": pos.get("id"),
                    "asset": pos.get("asset"),
                    "decision": RiskDecision.CLOSE_ALL,
                    "reason": "CORTEX BREACH: Emergency liquidation to protect remaining capital",
                })
            return triggers

        if health == CortexHealth.RED:
            for pos in open_positions:
                unrealized_pnl = float(pos.get("unrealized_pnl", 0.0))
                if unrealized_pnl < 0:
                    triggers.append({
                        "position_id": pos.get("id"),
                        "asset": pos.get("asset"),
                        "decision": RiskDecision.CLOSE_EXISTING,
                        "reason": f"CORTEX RED LOCK: Unrealized loss (${abs(unrealized_pnl):.2f}) closed to prevent breach",
                    })

        return triggers

    def authorize_trade_intent(
        self,
        intent: TradeIntent,
        asset_historical_data: pd.DataFrame | None = None,
        market_series_dict: dict[str, Any] | None = None,
    ) -> TradeAuthorization:
        """
        CORTEX Challenge Risk Engine V2 — Full Institutional Risk Evaluation
        Input: Equity · Daily P&L · Total DD · Distance to Target · Distance to Breach · Volatility ·
               ATR · Liquidity · Prediction Confidence · Strategy Confidence · Regime · Correlation ·
               Slippage · Price Impact · Gas · Token Security
        Output: PASS · REDUCE_SIZE · REJECT · CLOSE_EXISTING · CLOSE_ALL
                + POSITION SIZE · STOP · TP · TRAILING · MAX HOLD · RISK BUDGET · LEVERAGE
        """
        health = self.state.cortex_health
        audit_trail: dict[str, Any] = {
            "intent_id": intent.intent_id,
            "target_asset": intent.target_asset,
            "cortex_health": health.value,
            "current_equity": self.state.current_equity,
            "daily_dd_pct": round(self.state.daily_dd_pct * 100, 2),
            "total_dd_pct": round(self.state.total_dd_pct * 100, 2),
            "distance_to_ruin_usd": self.state.distance_to_ruin_usd,
            "distance_to_target_usd": self.state.distance_to_target_usd,
        }

        # 1. HARD STOPS / BREACH & CAPITAL PRESERVATION CHECKS
        if health == CortexHealth.BREACH:
            reason = f"Challenge Violation: {self.state.check_violations()}"
            return TradeAuthorization(
                intent_id=intent.intent_id,
                decision=RiskDecision.REJECT,
                authorized=False,
                position_size_units=0.0,
                nominal_value_usdt=0.0,
                authorized_leverage=1,
                stop_loss_price=0.0,
                take_profit_price=0.0,
                trailing_stop_price=0.0,
                max_hold_hours=0,
                risk_budget_usd=0.0,
                cortex_health=health,
                rejection_reason=reason,
                audit_trail=audit_trail,
            )

        if health == CortexHealth.RED:
            reason = "CORTEX RED: Capital preservation lock active (Daily DD >= 4.5% or Total DD >= 9.0%). No new trades."
            return TradeAuthorization(
                intent_id=intent.intent_id,
                decision=RiskDecision.REJECT,
                authorized=False,
                position_size_units=0.0,
                nominal_value_usdt=0.0,
                authorized_leverage=1,
                stop_loss_price=0.0,
                take_profit_price=0.0,
                trailing_stop_price=0.0,
                max_hold_hours=0,
                risk_budget_usd=0.0,
                cortex_health=health,
                rejection_reason=reason,
                audit_trail=audit_trail,
            )

        # 2. NEWS BLACKOUT WINDOW
        is_news, news_reason = self.is_news_window_active()
        if is_news:
            return TradeAuthorization(
                intent_id=intent.intent_id,
                decision=RiskDecision.REJECT,
                authorized=False,
                position_size_units=0.0,
                nominal_value_usdt=0.0,
                authorized_leverage=1,
                stop_loss_price=0.0,
                take_profit_price=0.0,
                trailing_stop_price=0.0,
                max_hold_hours=0,
                risk_budget_usd=0.0,
                cortex_health=health,
                rejection_reason=news_reason,
                audit_trail=audit_trail,
            )

        # 3. DYNAMIC PARAMETERS & RISK BUDGET
        dyn_params = self.get_dynamic_risk_parameters(
            strategy_name=intent.strategy_name,
            regime=intent.market_regime,
            volatility_14d=intent.volatility_14d,
        )
        available_risk_budget = self.state.available_risk_budget_usd
        if available_risk_budget <= 0.0:
            return TradeAuthorization(
                intent_id=intent.intent_id,
                decision=RiskDecision.REJECT,
                authorized=False,
                position_size_units=0.0,
                nominal_value_usdt=0.0,
                authorized_leverage=1,
                stop_loss_price=0.0,
                take_profit_price=0.0,
                trailing_stop_price=0.0,
                max_hold_hours=0,
                risk_budget_usd=0.0,
                cortex_health=health,
                rejection_reason="Available Risk Budget is $0.00 (Distance to Ruin exhausted)",
                audit_trail=audit_trail,
            )

        # 4. EFFECTIVE STOP LOSS DISTANCE (Determines Position Size, NOT vice-versa!)
        if asset_historical_data is not None and len(asset_historical_data) >= 14:
            atr = self.metrics.calculate_atr(
                asset_historical_data["high"],
                asset_historical_data["low"],
                asset_historical_data["close"],
            )
        elif intent.atr_14 and intent.atr_14 > 0:
            atr = intent.atr_14
        else:
            atr = intent.target_price * max(0.01, intent.volatility_14d)

        # Dynamic timeframe & strategy stop adjustment
        tf_mult = 1.2 if intent.timeframe in ("1m", "5m") else (1.8 if intent.timeframe in ("15m", "30m") else 2.5)
        stop_distance_price = max(atr * tf_mult, intent.target_price * 0.004)

        # Hard emergency ceiling: stop loss cannot exceed 5% of entry price
        emergency_ceiling = intent.target_price * 0.05
        stop_distance_price = min(stop_distance_price, emergency_ceiling)

        # 5. BASE SIZING FROM DYNAMIC RISK BUDGET & STOP DISTANCE
        max_risk_for_trade = min(self.state.current_equity * dyn_params["risk_per_trade_pct"], available_risk_budget)
        base_units = max_risk_for_trade / stop_distance_price
        nominal_trial = base_units * intent.target_price

        # 6. EXECUTION RISK GATES EVALUATION
        gates_ok, gate_decision, gate_reason, gate_multiplier = self.evaluate_execution_gates(
            intent=intent,
            trial_nominal_usd=nominal_trial,
            available_budget_usd=available_risk_budget,
        )
        if not gates_ok:
            return TradeAuthorization(
                intent_id=intent.intent_id,
                decision=RiskDecision.REJECT,
                authorized=False,
                position_size_units=0.0,
                nominal_value_usdt=0.0,
                authorized_leverage=1,
                stop_loss_price=0.0,
                take_profit_price=0.0,
                trailing_stop_price=0.0,
                max_hold_hours=0,
                risk_budget_usd=0.0,
                cortex_health=health,
                rejection_reason=gate_reason,
                audit_trail=audit_trail,
            )

        # 7. MULTIPLIER REDUCTION HIERARCHY
        volatility_factor = 1.0 / (1.0 + max(0.0, (intent.volatility_14d - 0.02) * 10.0))
        liquidity_factor = max(0.40, 1.0 - (intent.estimated_slippage_pct + intent.estimated_price_impact_pct) * 15.0)

        # Confidence cannot override Drawdown
        composite_conf = (intent.prediction_confidence * 0.5) + (intent.strategy_confidence * 0.5)
        confidence_factor = max(0.60, min(1.0, composite_conf))

        # Drawdown Factor by CORTEX Health
        if health == CortexHealth.GREEN:
            drawdown_factor = 1.0
        elif health == CortexHealth.YELLOW:
            drawdown_factor = 0.70  # Defensive
        elif health == CortexHealth.ORANGE:
            drawdown_factor = 0.35  # Capital preservation
        else:
            drawdown_factor = 0.0

        # Execution Quality Factor
        execution_quality_factor = max(0.30, 1.0 - (intent.estimated_gas_usd / (max_risk_for_trade + 1e-6)))

        # 8. CORRELATION FACTOR (Rolling Correlation Matrix)
        total_correlated_exposure = 0.0
        for asset_id, exposure in intent.current_portfolio_exposure.items():
            corr_factor = self.metrics.get_pairwise_correlation(
                asset_a=asset_id,
                asset_b=intent.target_asset,
                market_series_dict=market_series_dict,
                regime=intent.market_regime,
            )
            total_correlated_exposure += (exposure * max(0.10, corr_factor))

        max_allowed_correlated = self.state.current_equity * dyn_params["max_correlated_exposure_pct"]
        if (total_correlated_exposure + nominal_trial) > max_allowed_correlated:
            remaining_corr_capacity = max(0.0, max_allowed_correlated - total_correlated_exposure)
            if remaining_corr_capacity < 50.0:
                correlation_factor = 0.0
            else:
                correlation_factor = min(1.0, remaining_corr_capacity / nominal_trial)
        else:
            correlation_factor = 1.0

        if correlation_factor <= 0.0:
            return TradeAuthorization(
                intent_id=intent.intent_id,
                decision=RiskDecision.REJECT,
                authorized=False,
                position_size_units=0.0,
                nominal_value_usdt=0.0,
                authorized_leverage=1,
                stop_loss_price=0.0,
                take_profit_price=0.0,
                trailing_stop_price=0.0,
                max_hold_hours=0,
                risk_budget_usd=0.0,
                cortex_health=health,
                rejection_reason=f"Max Correlated Exposure Exceeded ({dyn_params['max_correlated_exposure_pct'] * 100:.0f}% Cap)",
                audit_trail=audit_trail,
            )

        # Combine all multipliers (including execution gate scaling)
        total_scaling_factor = (
            volatility_factor
            * liquidity_factor
            * confidence_factor
            * correlation_factor
            * drawdown_factor
            * execution_quality_factor
            * gate_multiplier
        )

        final_units = base_units * total_scaling_factor
        final_nominal_usd = final_units * intent.target_price

        # 9. DYNAMIC MINIMUM NOTIONAL CHECK
        min_notional = dyn_params["min_trade_notional_usd"]
        if final_nominal_usd < min_notional:
            return TradeAuthorization(
                intent_id=intent.intent_id,
                decision=RiskDecision.REJECT,
                authorized=False,
                position_size_units=0.0,
                nominal_value_usdt=0.0,
                authorized_leverage=1,
                stop_loss_price=0.0,
                take_profit_price=0.0,
                trailing_stop_price=0.0,
                max_hold_hours=0,
                risk_budget_usd=0.0,
                cortex_health=health,
                rejection_reason=f"Position size too small (${final_nominal_usd:.2f} < Min ${min_notional:.2f})",
                audit_trail=audit_trail,
            )

        # 10. AUTHORIZED LEVERAGE (Strict institutional cap at 3x)
        raw_leverage = max(1, int(round(final_nominal_usd / self.state.current_equity)))
        authorized_leverage = min(raw_leverage, 3)

        # 11. STOP LOSS, TAKE PROFIT, TRAILING & MAX HOLD
        dir_str = str(intent.direction.value if isinstance(intent.direction, TradeDirection) else intent.direction).upper()
        is_long = dir_str in ("LONG", "BUY")
        target_rr = dyn_params["target_risk_reward"]

        if is_long:
            stop_loss_price = intent.target_price - stop_distance_price
            take_profit_price = intent.target_price + (stop_distance_price * target_rr)
            trailing_stop_price = intent.target_price - (stop_distance_price * 0.8)
        else:
            stop_loss_price = intent.target_price + stop_distance_price
            take_profit_price = intent.target_price - (stop_distance_price * target_rr)
            trailing_stop_price = intent.target_price + (stop_distance_price * 0.8)

        tf_hours_map = {"1m": 2, "5m": 4, "15m": 12, "1h": 24, "4h": 72, "1d": 168}
        max_hold_hours = tf_hours_map.get(intent.timeframe.lower(), 24)

        decision = RiskDecision.REDUCE_SIZE if (total_scaling_factor < 0.85 or gate_decision == RiskDecision.REDUCE_SIZE) else RiskDecision.PASS

        audit_trail.update({
            "volatility_factor": round(volatility_factor, 3),
            "liquidity_factor": round(liquidity_factor, 3),
            "confidence_factor": round(confidence_factor, 3),
            "correlation_factor": round(correlation_factor, 3),
            "drawdown_factor": round(drawdown_factor, 3),
            "execution_quality_factor": round(execution_quality_factor, 3),
            "gate_multiplier": round(gate_multiplier, 3),
            "total_scaling_factor": round(total_scaling_factor, 3),
            "effective_risk_budget_usd": round(max_risk_for_trade, 2),
            "target_rr_used": target_rr,
        })

        return TradeAuthorization(
            intent_id=intent.intent_id,
            decision=decision,
            authorized=True,
            position_size_units=round(final_units, 4),
            nominal_value_usdt=round(final_nominal_usd, 2),
            authorized_leverage=authorized_leverage,
            stop_loss_price=round(stop_loss_price, 2),
            take_profit_price=round(take_profit_price, 2),
            trailing_stop_price=round(trailing_stop_price, 2),
            max_hold_hours=max_hold_hours,
            risk_budget_usd=round(max_risk_for_trade * total_scaling_factor, 2),
            cortex_health=health,
            rejection_reason=None,
        )



    def is_news_window_active(self, current_timestamp: float | None = None) -> tuple[bool, str | None]:
        """Checks if current time is within +-5 min of a major macro event."""
        now = current_timestamp if current_timestamp is not None else datetime.now(timezone.utc).timestamp()
        for ev in self.SCHEDULED_EVENTS:
            diff_minutes = abs(now - ev.timestamp_utc) / 60.0
            if diff_minutes <= ev.window_minutes:
                return True, f"NEWS FILTER ACTIVE: {ev.name} (+/- {ev.window_minutes}m window)"
        return False, None

    def is_weekend(self, dt: datetime | None = None) -> bool:
        """Checks if current time is weekend (Saturday=5, Sunday=6)."""
        check_dt = dt if dt is not None else datetime.now(timezone.utc)
        return check_dt.weekday() in [5, 6]

    def check_consistency(self, daily_profits_usdt: list[float], total_target_profit_usdt: float) -> tuple[bool, float]:
        """
        Consistency Rule: No single day can represent > 30% of total target profit.
        Prevents lucky single-trade gambling spikes.
        """
        if not daily_profits_usdt or total_target_profit_usdt <= 0:
            return True, 0.0

        max_day = max(daily_profits_usdt)
        if max_day <= 0:
            return True, 0.0

        ratio = max_day / total_target_profit_usdt
        is_consistent = ratio <= self.MAX_SINGLE_DAY_PROFIT_RATIO
        return is_consistent, round(ratio, 4)

    def evaluate_challenge(
        self,
        current_equity: float,
        peak_equity: float,
        daily_loss_pct: float,
        trading_days_count: int,
        daily_profits_usdt: list[float],
        cortex_violations: int = 0,
        current_timestamp: float | None = None,
    ) -> ChallengeRiskDecision:
        """
        Full evaluation of the challenge state, enforcing all 4 rules:
        1. Drawdown Gates (-10% Total, -5% Daily)
        2. Consistency Rule (max 30% per day)
        3. News Filter (5m buffer)
        4. Weekend Sizing (50% reduction)
        """
        initial = self.virtual_capital
        target_profit_usdt = initial * (self.TARGET_PROFIT_PCT / 100.0)

        # Drawdowns
        total_dd = ((peak_equity - current_equity) / peak_equity) * 100.0 if peak_equity > 0 else 0.0
        profit_usdt = current_equity - initial
        profit_pct = (profit_usdt / initial) * 100.0 if initial > 0 else 0.0

        # Check breach conditions
        total_dd_breached = total_dd >= self.MAX_TOTAL_DD_PCT
        daily_dd_breached = daily_loss_pct >= self.MAX_DAILY_DD_PCT
        cortex_breached = cortex_violations > 0

        # Consistency check
        is_consistent, highest_day_ratio = self.check_consistency(daily_profits_usdt, target_profit_usdt)

        # News & Weekend sizing
        is_news, news_reason = self.is_news_window_active(current_timestamp)
        now_dt = datetime.fromtimestamp(current_timestamp, tz=timezone.utc) if current_timestamp else datetime.now(timezone.utc)
        is_wknd = self.is_weekend(now_dt)
        size_multiplier = 0.50 if is_wknd else 1.0

        # Failure logic (Drawdowns or Risk Gate Breaches)
        if total_dd_breached or daily_dd_breached or cortex_breached:
            veto = "DRAWDOWN OR CORTEX BREACH"
            if total_dd_breached:
                veto = f"MAX TOTAL DRAWDOWN BREACHED: -{total_dd:.2f}% (Limit -{self.MAX_TOTAL_DD_PCT:.1f}%)"
            elif daily_dd_breached:
                veto = f"MAX DAILY DRAWDOWN BREACHED: -{daily_loss_pct:.2f}% (Limit -{self.MAX_DAILY_DD_PCT:.1f}%)"
            elif cortex_breached:
                veto = f"CORTEX VIOLATIONS DETECTED: {cortex_violations} (Zero Tolerance)"

            # Second Chance: fee converted to TAC credits
            return ChallengeRiskDecision(
                can_trade=False,
                position_size_multiplier=0.0,
                veto_reason=veto,
                current_total_dd_pct=round(total_dd, 2),
                current_daily_dd_pct=round(daily_loss_pct, 2),
                is_consistency_satisfied=is_consistent,
                highest_day_profit_ratio=highest_day_ratio,
                status="FAILED",
                tac_credits_awarded=self.tier_fee_usdt,
                withdrawable_payout_usdt=0.0,
            )

        # Passing logic: profit >= +8%, days >= 5, consistency satisfied
        if profit_pct >= self.TARGET_PROFIT_PCT and trading_days_count >= self.MIN_TRADING_DAYS and is_consistent:
            # Payout: 80% of verified net profit
            user_payout = profit_usdt * self.PAYOUT_SHARE_PCT
            return ChallengeRiskDecision(
                can_trade=False,
                position_size_multiplier=0.0,
                veto_reason=None,
                current_total_dd_pct=round(total_dd, 2),
                current_daily_dd_pct=round(daily_loss_pct, 2),
                is_consistency_satisfied=True,
                highest_day_profit_ratio=highest_day_ratio,
                status="PASSED",
                tac_credits_awarded=0.0,
                withdrawable_payout_usdt=round(user_payout, 2),
            )

        # Active trade execution filters (News veto, weekend dampener)
        if is_news:
            return ChallengeRiskDecision(
                can_trade=False,
                position_size_multiplier=0.0,
                veto_reason=news_reason,
                current_total_dd_pct=round(total_dd, 2),
                current_daily_dd_pct=round(daily_loss_pct, 2),
                is_consistency_satisfied=is_consistent,
                highest_day_profit_ratio=highest_day_ratio,
                status="ACTIVE",
                tac_credits_awarded=0.0,
                withdrawable_payout_usdt=0.0,
            )

        veto_note = "WEEKEND SIZING DAMPENER (50% Sizing)" if is_wknd else None

        return ChallengeRiskDecision(
            can_trade=True,
            position_size_multiplier=size_multiplier,
            veto_reason=veto_note,
            current_total_dd_pct=round(total_dd, 2),
            current_daily_dd_pct=round(daily_loss_pct, 2),
            is_consistency_satisfied=is_consistent,
            highest_day_profit_ratio=highest_day_ratio,
            status="ACTIVE",
            tac_credits_awarded=0.0,
            withdrawable_payout_usdt=0.0,
        )

    def calculate_position_size(
        self,
        current_balance: float,
        start_of_day_balance: float,
        entry_price: float,
        direction: str,  # 'LONG' or 'SHORT'
        atr_14: float,
        risk_per_trade_target_pct: float = 0.75,  # Standard 0.75% risk per trade
        atr_multiplier: float = 1.8,
        min_risk_reward_ratio: float = 2.0,
        max_leverage: float = 10.0,
        current_timestamp: float | None = None,
    ) -> PositionSizingResult:
        """
        Calculates exact position size and dynamic SL/TP levels engineered to strictly
        prevent breaching the 5.0% Daily Drawdown and 10.0% Total Drawdown limits.
        """
        # 1. Check macro news blackout
        is_news, news_reason = self.is_news_window_active(current_timestamp)
        if is_news:
            return PositionSizingResult(
                can_execute=False,
                rejection_reason=news_reason,
                quantity=0.0,
                nominal_value_usdt=0.0,
                effective_leverage=0.0,
                risk_usdt=0.0,
                risk_pct_balance=0.0,
                entry_price=entry_price,
                stop_loss_price=0.0,
                take_profit_price=0.0,
                sl_distance_usdt=0.0,
                tp_distance_usdt=0.0,
                risk_reward_ratio=0.0,
                daily_dd_budget_remaining_usdt=0.0,
            )

        if current_balance <= 0 or entry_price <= 0:
            return PositionSizingResult(
                can_execute=False,
                rejection_reason="INVALID_PRICE_OR_BALANCE",
                quantity=0.0,
                nominal_value_usdt=0.0,
                effective_leverage=0.0,
                risk_usdt=0.0,
                risk_pct_balance=0.0,
                entry_price=entry_price,
                stop_loss_price=0.0,
                take_profit_price=0.0,
                sl_distance_usdt=0.0,
                tp_distance_usdt=0.0,
                risk_reward_ratio=0.0,
                daily_dd_budget_remaining_usdt=0.0,
            )

        # 2. Drawdown headroom computation
        max_daily_loss_usdt = start_of_day_balance * (self.MAX_DAILY_DD_PCT / 100.0)
        current_day_loss_usdt = max(0.0, start_of_day_balance - current_balance)
        daily_budget_remaining_usdt = max(0.0, max_daily_loss_usdt - current_day_loss_usdt)

        if daily_budget_remaining_usdt <= 0.0:
            return PositionSizingResult(
                can_execute=False,
                rejection_reason=f"DAILY_DRAWDOWN_BUDGET_EXHAUSTED (Loss: ${current_day_loss_usdt:.2f} >= Limit: ${max_daily_loss_usdt:.2f})",
                quantity=0.0,
                nominal_value_usdt=0.0,
                effective_leverage=0.0,
                risk_usdt=0.0,
                risk_pct_balance=0.0,
                entry_price=entry_price,
                stop_loss_price=0.0,
                take_profit_price=0.0,
                sl_distance_usdt=0.0,
                tp_distance_usdt=0.0,
                risk_reward_ratio=0.0,
                daily_dd_budget_remaining_usdt=0.0,
            )

        # 3. Base single-trade risk dollar allocation
        # Maximum 0.75% of current equity, and never more than 1/3 of the remaining daily DD buffer
        standard_trade_risk_usdt = current_balance * (risk_per_trade_target_pct / 100.0)
        buffer_trade_risk_usdt = daily_budget_remaining_usdt / 3.0
        allowed_risk_usdt = min(standard_trade_risk_usdt, buffer_trade_risk_usdt)

        # 4. Volatility dampeners
        # Weekend sizing: reduce risk budget by 50%
        now_dt = datetime.fromtimestamp(current_timestamp, tz=timezone.utc) if current_timestamp else datetime.now(timezone.utc)
        if self.is_weekend(now_dt):
            allowed_risk_usdt *= 0.50

        # Drawdown danger zone dampener (if daily loss > 3.0%)
        current_daily_dd_pct = (current_day_loss_usdt / start_of_day_balance) * 100.0 if start_of_day_balance > 0 else 0.0
        if current_daily_dd_pct >= 3.0:
            allowed_risk_usdt *= 0.50  # Cut size by half in yellow caution zone

        # 5. Dynamic Stop Loss distance (ATR-based with 0.8% floor)
        min_sl_distance = entry_price * 0.008  # 0.8% minimum distance to avoid market noise
        sl_distance = max(atr_14 * atr_multiplier, min_sl_distance)
        tp_distance = sl_distance * min_risk_reward_ratio

        direction_upper = direction.upper()
        if direction_upper == "LONG":
            sl_price = max(0.00000001, entry_price - sl_distance)
            tp_price = entry_price + tp_distance
        else:
            sl_price = entry_price + sl_distance
            tp_price = max(0.00000001, entry_price - tp_distance)

        # 6. Sizing math: Quantity = Allowed Risk / SL Distance
        quantity = allowed_risk_usdt / sl_distance
        nominal_val = quantity * entry_price
        effective_leverage = nominal_val / current_balance

        # 7. Leverage clamp (e.g. 10x max)
        if effective_leverage > max_leverage:
            nominal_val = current_balance * max_leverage
            quantity = nominal_val / entry_price
            allowed_risk_usdt = quantity * sl_distance
            effective_leverage = max_leverage

        # 8. Consistency Rule Cap on Take Profit
        # Single trade profit should never exceed 30% of total target profit in one swing
        total_target_profit_usdt = self.virtual_capital * (self.TARGET_PROFIT_PCT / 100.0)
        max_allowed_single_trade_tp_usdt = total_target_profit_usdt * self.MAX_SINGLE_DAY_PROFIT_RATIO
        potential_profit_usdt = quantity * tp_distance

        if potential_profit_usdt > max_allowed_single_trade_tp_usdt and potential_profit_usdt > 0:
            scale_down = max_allowed_single_trade_tp_usdt / potential_profit_usdt
            quantity *= scale_down
            nominal_val = quantity * entry_price
            allowed_risk_usdt = quantity * sl_distance
            effective_leverage = nominal_val / current_balance

        actual_risk_pct = (allowed_risk_usdt / current_balance) * 100.0 if current_balance > 0 else 0.0

        return PositionSizingResult(
            can_execute=True,
            rejection_reason=None,
            quantity=round(quantity, 8),
            nominal_value_usdt=round(nominal_val, 2),
            effective_leverage=round(effective_leverage, 2),
            risk_usdt=round(allowed_risk_usdt, 2),
            risk_pct_balance=round(actual_risk_pct, 3),
            entry_price=round(entry_price, 4),
            stop_loss_price=round(sl_price, 4),
            take_profit_price=round(tp_price, 4),
            sl_distance_usdt=round(sl_distance, 4),
            tp_distance_usdt=round(tp_distance, 4),
            risk_reward_ratio=round(tp_distance / sl_distance, 2) if sl_distance > 0 else 0.0,
            daily_dd_budget_remaining_usdt=round(daily_budget_remaining_usdt, 2),
        )

    # -------------------------------------------------------------------------
    # SPEC V1 MATHEMATICAL ENGINE (Dynamic Volatility Targeting & Survival)
    # -------------------------------------------------------------------------

    def calculate_spec_v1_sizing(
        self,
        equity_current: float,
        equity_start_of_day: float,
        atr_14: float,
        mode: str = "scalping",
        max_risk_per_trade_pct: float = 0.005,  # 0.5% Golden Rule
        daily_dd_limit_pct: float = 0.05,        # 5.0% Daily Limit
    ) -> dict[str, Any]:
        """
        Implements the exact Spec V1 Dynamic Volatility Targeting formula:
        Step A: daily_headroom = (Equity_StartOfDay * Daily_DD_Limit) - (Equity_StartOfDay - Equity_Current)
        Step B: stop_loss_distance = ATR_14 * Multiplier_SL (1.5 for Scalping, 2.5 for Swing)
        Step C: effective_risk_cap = min(Equity_Current * max_risk_pct, daily_headroom * 0.5)
        """
        # Step A: Daily Headroom
        max_daily_dd_dollars = equity_start_of_day * daily_dd_limit_pct
        current_loss_today = max(0.0, equity_start_of_day - equity_current)
        daily_headroom = max(0.0, max_daily_dd_dollars - current_loss_today)

        if daily_headroom <= 0.0:
            return {
                "can_trade": False,
                "reason": "DAILY_HEADROOM_EXHAUSTED",
                "position_size_units": 0.0,
                "effective_risk_cap": 0.0,
                "daily_headroom": 0.0,
                "stop_loss_distance": 0.0,
            }

        # Step B: Stop Loss Distance (ATR Based)
        multiplier_sl = 1.5 if mode.lower() == "scalping" else 2.5
        stop_loss_distance = atr_14 * multiplier_sl

        if stop_loss_distance <= 0:
            return {
                "can_trade": False,
                "reason": "INVALID_ATR_DISTANCE",
                "position_size_units": 0.0,
                "effective_risk_cap": 0.0,
                "daily_headroom": daily_headroom,
                "stop_loss_distance": 0.0,
            }

        # Step C: Size with Fixed Fractional Risk adjusted by Headroom
        risk_amount_usdt = equity_current * max_risk_per_trade_pct
        effective_risk_cap = min(risk_amount_usdt, daily_headroom * 0.5)
        position_size_units = effective_risk_cap / stop_loss_distance

        return {
            "can_trade": True,
            "reason": None,
            "daily_headroom": round(daily_headroom, 2),
            "multiplier_sl": multiplier_sl,
            "stop_loss_distance": round(stop_loss_distance, 4),
            "risk_amount_usdt": round(risk_amount_usdt, 2),
            "effective_risk_cap": round(effective_risk_cap, 2),
            "position_size_units": round(position_size_units, 6),
            "risk_params_used": {
                "atr_value": atr_14,
                "sl_multiplier": multiplier_sl,
                "risk_pct": max_risk_per_trade_pct * 100.0,
                "daily_headroom": round(daily_headroom, 2),
                "correlation_adjustment": 1.0,
            },
        }

    def calculate_chandelier_exit(
        self,
        highest_high_since_entry: float,
        lowest_low_since_entry: float,
        atr_14: float,
        direction: str = "LONG",
        multiplier: float = 3.0,
    ) -> float:
        """
        Chandelier Exit:
        LONG:  Trailing_SL = Highest_High_since_Entry - (3 * ATR_14)
        SHORT: Trailing_SL = Lowest_Low_since_Entry + (3 * ATR_14)
        """
        if direction.upper() == "LONG":
            return max(0.00000001, highest_high_since_entry - (multiplier * atr_14))
        else:
            return lowest_low_since_entry + (multiplier * atr_14)

    def evaluate_correlation_cap(
        self,
        target_asset: str,
        target_nominal_value: float,
        open_positions: list[dict[str, Any]],
        correlation_threshold: float = 0.70,
        max_exposure_cap_pct: float = 0.20,  # Hard Cap: max 20% correlated exposure
    ) -> tuple[bool, str | None, float]:
        """
        Enforces Section 4 Correlation & Exposure Hard Cap:
        If correlation > 0.7 with open positions, total correlated exposure must not exceed 20% nominal capital.
        """
        max_allowed_correlated_usdt = self.virtual_capital * max_exposure_cap_pct
        correlated_exposure = target_nominal_value

        # High correlation clusters (e.g. BTC, ETH, SOL, POL crypto beta)
        crypto_majors = {"BTC", "ETH", "SOL", "POL", "WBTC", "WETH"}
        target_base = target_asset.split("/")[0].upper()

        for pos in open_positions:
            pos_asset = pos.get("asset", "").split("/")[0].upper()
            pos_nominal = float(pos.get("size", 0.0)) * float(pos.get("current_price", pos.get("entry_price", 1.0)))

            # If both are in the major beta cluster, assume Pearson correlation > 0.70
            if (target_base in crypto_majors and pos_asset in crypto_majors) or target_base == pos_asset:
                correlated_exposure += pos_nominal

        if correlated_exposure > max_allowed_correlated_usdt:
            return (
                False,
                f"CORRELATED_EXPOSURE_CAP_EXCEEDED: ${correlated_exposure:,.2f} > Max 20% (${max_allowed_correlated_usdt:,.2f})",
                correlated_exposure,
            )

        return True, None, correlated_exposure

    def evaluate_circuit_breakers(
        self,
        daily_dd_pct: float,
        total_dd_pct: float,
        consecutive_losses: int,
        signal_confidence: float = 0.80,
        reward_risk_ratio: float = 2.0,
        current_timestamp: float | None = None,
    ) -> dict[str, Any]:
        """
        Enforces Section 5 Circuit Breakers:
        - Daily DD > 3.5%: Reduce size by 50%
        - Daily DD > 4.5%: Freeze new entries
        - Total DD > 8%: Survival Mode (Only R:R > 3:1 and Confidence > 0.9)
        - 3 Consecutive Losses: 4-hour pause
        - News blackout: +/- 5 min
        """
        is_news, news_reason = self.is_news_window_active(current_timestamp)
        if is_news:
            return {"action": "FREEZE", "allowed": False, "reason": news_reason, "size_multiplier": 0.0}

        if daily_dd_pct >= 4.5:
            return {"action": "FREEZE", "allowed": False, "reason": f"DAILY_DD_CRITICAL ({daily_dd_pct:.2f}% >= 4.5%)", "size_multiplier": 0.0}

        if consecutive_losses >= 3:
            return {"action": "PAUSE_4H", "allowed": False, "reason": "3_CONSECUTIVE_LOSSES_PAUSE_4H", "size_multiplier": 0.0}

        if total_dd_pct >= 8.0:
            if signal_confidence < 0.90 or reward_risk_ratio < 3.0:
                return {
                    "action": "SURVIVAL_MODE_RESTRICTION",
                    "allowed": False,
                    "reason": f"SURVIVAL_MODE (Total DD {total_dd_pct:.2f}% >= 8.0% requires R:R > 3.0 & Confidence > 0.90)",
                    "size_multiplier": 0.0,
                }

        size_multiplier = 0.50 if daily_dd_pct >= 3.5 else 1.0
        return {
            "action": "REDUCE_SIZE_50" if daily_dd_pct >= 3.5 else "NORMAL",
            "allowed": True,
            "reason": "DAILY_DD_YELLOW_ZONE (Size reduced 50%)" if daily_dd_pct >= 3.5 else None,
            "size_multiplier": size_multiplier,
        }


# Canonical V2 Architecture Alias
CortexChallengeRiskEngine = ChallengeRiskAgent


# ============================================================
# ESEMPIO DI UTILIZZO (TEST UNITARIO / SIMULAZIONE DIRETTA)
# ============================================================

if __name__ == "__main__":
    # Setup Iniziale
    agent_state = ChallengeState(TIER_PRO)
    risk_agent = ChallengeRiskAgent(agent_state)

    # Simulazione Dati Mercato (BTC)
    dates = pd.date_range(end=pd.Timestamp.now(), periods=20)
    mock_data = pd.DataFrame({
        "high": [65000 + np.random.rand() * 1000 for _ in range(20)],
        "low": [64000 + np.random.rand() * 1000 for _ in range(20)],
        "close": [64500 + np.random.rand() * 1000 for _ in range(20)],
    })

    # Simulazione Segnale AI
    print("--- TRADE EVALUATION ---")
    decision = risk_agent.evaluate_trade(
        signal_direction=TradeDirection.LONG,
        entry_price=65000.0,
        asset_historical_data=mock_data,
        current_portfolio_exposure={},  # Portfolio vuoto
        target_asset_id="BTC",
    )

    print(decision)

    # Simulazione Aggiornamento Equity dopo perdita
    print("\n--- SIMULATING LOSS ---")
    agent_state.update_equity(49500)  # Perdita di 500$
    print(f"Daily DD: {agent_state.daily_dd_pct:.2%}")

    # Secondo trade con equity ridotta
    decision_2 = risk_agent.evaluate_trade(
        signal_direction=TradeDirection.SHORT,
        entry_price=64800.0,
        asset_historical_data=mock_data,
        current_portfolio_exposure={"BTC": 5000},  # Abbiamo già esposizione
        target_asset_id="ETH",
    )
    print(decision_2)


