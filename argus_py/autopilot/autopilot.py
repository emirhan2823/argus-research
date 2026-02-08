from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from .config import AutoPilotConfig


class AutoPilotMode(Enum):
    CORSE = "CORSE"
    PULSE = "PULSE"


@dataclass
class TradePosition:
    symbol: str
    entry_price: float
    quantity: float
    mode: AutoPilotMode
    entry_time: float
    high_water_mark: float
    engine: str


@dataclass
class AutoPilotSignal:
    action: str
    quantity: float
    reason: str
    stop_loss: Optional[float]
    take_profit: Optional[float]
    trim_percentage: Optional[float]


class AutoPilotEngine:
    """Handles position entry and exit logic."""

    def __init__(self, config: AutoPilotConfig = None):
        self.config = config or AutoPilotConfig()

    def evaluate(
        self,
        symbol: str,
        current_price: float,
        council_score: float,
        council_action: str,
        existing_position: Optional[TradePosition],
        portfolio_equity: float,
        cash_available: float,
    ) -> AutoPilotSignal:
        if existing_position:
            return self._manage_existing(symbol, current_price, council_score, existing_position)
        return self._evaluate_entry(
            symbol,
            current_price,
            council_score,
            council_action,
            portfolio_equity,
            cash_available,
        )

    def _manage_existing(
        self,
        symbol: str,
        price: float,
        score: float,
        pos: TradePosition,
    ) -> AutoPilotSignal:
        pnl_pct = ((price - pos.entry_price) / pos.entry_price) * 100.0

        cfg = self.config
        if pos.mode == AutoPilotMode.CORSE:
            stop_pct = cfg.corse_stop_pct
            trim_pct = cfg.corse_trim_threshold_pct
            trail_activate = cfg.corse_trailing_activation_pct
            trail_distance = cfg.corse_trailing_distance_pct
        else:
            stop_pct = cfg.pulse_stop_pct
            trim_pct = cfg.pulse_trim_threshold_pct
            trail_activate = cfg.pulse_trailing_activation_pct
            trail_distance = cfg.pulse_trailing_distance_pct

        # 1. HARD STOP
        if pnl_pct < -stop_pct:
            return AutoPilotSignal("SELL", pos.quantity, f"Stop Loss ({pnl_pct:.1f}%)", None, None, None)

        # 2. TRIM PROFITS
        if pnl_pct > trim_pct:
            trim_qty = pos.quantity * 0.3
            return AutoPilotSignal("TRIM", trim_qty, f"Profit Taking ({pnl_pct:.1f}%)", None, None, 0.3)

        # 3. TRAILING STOP
        hwm = pos.high_water_mark if pos.high_water_mark > 0 else price
        drawdown_from_high = ((hwm - price) / hwm) * 100.0 if hwm > 0 else 0.0
        if pnl_pct > trail_activate and drawdown_from_high > trail_distance:
            return AutoPilotSignal(
                "SELL",
                pos.quantity,
                f"Trailing Stop (DD: {drawdown_from_high:.1f}%)",
                None,
                None,
                None,
            )

        # 4. THESIS BROKEN
        score_threshold = 55.0 if pos.mode == AutoPilotMode.CORSE else 50.0
        if score < score_threshold and pnl_pct < 0:
            return AutoPilotSignal("SELL", pos.quantity, f"Thesis Broken (Score: {score:.0f})", None, None, None)

        return AutoPilotSignal("HOLD", 0.0, "Position OK", None, None, None)

    def _evaluate_entry(
        self,
        symbol: str,
        price: float,
        score: float,
        action: str,
        equity: float,
        cash: float,
    ) -> AutoPilotSignal:
        if score < self.config.min_score_for_entry:
            return AutoPilotSignal("HOLD", 0.0, f"Score too low ({score:.0f})", None, None, None)

        if action not in ["AGGRESSIVE_BUY", "ACCUMULATE"]:
            return AutoPilotSignal("HOLD", 0.0, f"No buy signal ({action})", None, None, None)

        risk_amount = equity * (self.config.max_risk_per_trade_pct / 100.0)
        assumed_stop_pct = self.config.pulse_stop_pct
        position_value = risk_amount / (assumed_stop_pct / 100.0)

        # Cap by cash and exposure settings.
        max_cash_value = cash * 0.95
        exposure_cap = equity * self.config.max_equity_exposure
        position_value = min(position_value, max_cash_value, exposure_cap)

        quantity = position_value / price if price > 0 else 0.0

        if quantity <= 0:
            return AutoPilotSignal("HOLD", 0.0, "Insufficient cash", None, None, None)

        stop_loss = price * (1.0 - assumed_stop_pct / 100.0)
        take_profit = price * 1.15

        return AutoPilotSignal(
            "BUY",
            quantity,
            f"Entry Signal (Score: {score:.0f})",
            stop_loss,
            take_profit,
            None,
        )

    def update_high_water_mark(self, position: TradePosition, current_price: float) -> TradePosition:
        if current_price > position.high_water_mark:
            position.high_water_mark = current_price
        return position
