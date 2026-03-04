"""Stateful Backtest Engine v5 — Engine-Aware Trade Simulator.

Converts advisory signals into simulated trades with full position
lifecycle management: open, SL/TP hit detection on candle wicks,
breakeven lock, engine-conditional trailing stops, time stops,
and professional tear sheet with engine breakdown.

Design:
    VirtualAccount — equity, margin, trade history
    SimulatedPosition — one open trade with engine/regime metadata
    BacktestSimulator — orchestrator: on_signal + on_candle + tear_sheet
"""

from __future__ import annotations

import logging
import statistics
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

_LOG = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────
# Engine-Aware Constants
# ─────────────────────────────────────────────────────────────────────

# Engines that get trailing stop applied
TRAILING_ENGINES = frozenset({"POSEIDON", "TITAN"})

# Per-engine max candle age before time_stop (15m candles)
ENGINE_MAX_AGE: dict[str, int] = {
    "HYDRA": 6,
    "AEGEAN": 8,
    "NAUTILUS": 12,
    "POSEIDON": 24,
}
DEFAULT_MAX_AGE = 16  # fallback for unknown engines

# ─────────────────────────────────────────────────────────────────────
# Data Contracts
# ─────────────────────────────────────────────────────────────────────


@dataclass
class ClosedTrade:
    """Record of a completed simulated trade."""

    trade_id: str
    symbol: str
    side: str  # "long" | "short"
    engine: str  # v5: which engine opened this trade
    regime: str  # v5: regime at entry
    entry_price: float
    exit_price: float
    size_usd: float
    leverage: float
    pnl_usd: float
    pnl_pct: float
    opened_at: datetime
    closed_at: datetime
    exit_reason: str  # "sl" | "tp" | "trailing" | "be_stop" | "time_stop"
    duration_candles: int = 0  # v5: how many candles the position was open


@dataclass
class SimulatedPosition:
    """One active simulated trade with engine metadata."""

    trade_id: str
    symbol: str
    side: str  # "long" | "short"
    engine: str  # v5: which engine opened this trade
    regime: str  # v5: regime at entry
    entry_price: float
    size_usd: float  # notional
    leverage: float
    sl_price: float
    tp_price: float
    current_sl: float  # may ratchet via trailing/BE
    opened_at: datetime
    adx: float = 0.0  # v5: ADX at entry
    atr_pctl: float = 0.0  # v5: ATR percentile at entry
    candle_age: int = 0  # v5: candles since open
    be_locked: bool = False  # breakeven lock engaged?

    # ── SL/TP hit detection on candle wicks ──

    def check_exit(
        self, *, high: float, low: float, close: float,
    ) -> Literal["sl", "tp"] | None:
        """Check if SL or TP is hit by this candle's wick.

        Conservative rule: if BOTH hit on the same candle, SL wins.
        """
        sl_hit = False
        tp_hit = False

        if self.side == "long":
            sl_hit = low <= self.current_sl
            tp_hit = high >= self.tp_price
        else:  # short
            sl_hit = high >= self.current_sl
            tp_hit = low <= self.tp_price

        # Conservative: SL wins if both hit
        if sl_hit:
            return "sl"
        if tp_hit:
            return "tp"
        return None

    def exit_price_for(self, reason: str) -> float:
        """Return the fill price for the given exit reason."""
        if reason == "sl":
            return self.current_sl
        if reason == "tp":
            return self.tp_price
        # time_stop / be_stop → use current_sl (conservative)
        return self.current_sl

    def compute_pnl(self, exit_price: float) -> tuple[float, float]:
        """Compute PnL in USD and as percentage of margin.

        Returns:
            (pnl_usd, pnl_pct_of_margin)
        """
        if self.side == "long":
            price_change_pct = (exit_price - self.entry_price) / self.entry_price
        else:
            price_change_pct = (self.entry_price - exit_price) / self.entry_price

        pnl_usd = self.size_usd * price_change_pct
        margin = self.size_usd / self.leverage if self.leverage > 0 else self.size_usd
        pnl_pct = pnl_usd / margin if margin > 0 else 0.0
        return pnl_usd, pnl_pct

    # ── Breakeven Lock ──

    def try_breakeven_lock(
        self,
        *,
        current_price: float,
        atr_pct: float,
        trigger_multiple: float = 1.0,
        fee_pct: float = 0.001,
    ) -> bool:
        """Snap SL to break-even + fees if price moved Nx ATR in our favor.

        Returns True if lock was engaged (or already engaged).
        """
        if self.be_locked:
            return True

        atr_distance = self.entry_price * atr_pct * trigger_multiple

        if self.side == "long":
            if current_price >= self.entry_price + atr_distance:
                be_price = self.entry_price * (1 + 2 * fee_pct)
                if be_price > self.current_sl:
                    self.current_sl = be_price
                    self.be_locked = True
                    return True
        else:  # short
            if current_price <= self.entry_price - atr_distance:
                be_price = self.entry_price * (1 - 2 * fee_pct)
                if be_price < self.current_sl:
                    self.current_sl = be_price
                    self.be_locked = True
                    return True
        return False

    # ── Trailing Stop (simplified DRM ratchet) ──

    def try_trailing_stop(
        self,
        *,
        current_price: float,
        trail_pct: float = 0.01,
    ) -> bool:
        """Ratchet stop-loss to lock in profits. Never regresses.

        Returns True if SL was tightened.
        """
        if self.side == "long":
            new_sl = current_price * (1 - trail_pct)
            if new_sl > self.current_sl:
                self.current_sl = new_sl
                return True
        else:  # short
            new_sl = current_price * (1 + trail_pct)
            if new_sl < self.current_sl:
                self.current_sl = new_sl
                return True
        return False

    def try_trailing_stop_atr(
        self,
        *,
        current_price: float,
        atr_pct: float,
        atr_mult: float = 2.5,
    ) -> bool:
        """ATR-based trailing stop. Distance = entry_price * atr_pct * atr_mult.

        Returns True if SL was tightened.
        """
        trail_dist = self.entry_price * atr_pct * atr_mult
        if trail_dist <= 0:
            return False
        if self.side == "long":
            new_sl = current_price - trail_dist
            if new_sl > self.current_sl:
                self.current_sl = new_sl
                return True
        else:
            new_sl = current_price + trail_dist
            if new_sl < self.current_sl:
                self.current_sl = new_sl
                return True
        return False


# ─────────────────────────────────────────────────────────────────────
# Virtual Account
# ─────────────────────────────────────────────────────────────────────


@dataclass
class VirtualAccount:
    """Simulated trading account with margin tracking."""

    initial_balance: float = 10_000.0
    balance: float = 0.0  # available cash (not locked in margin)
    total_equity: float = 0.0  # balance + unrealized PnL
    locked_margin: float = 0.0
    peak_equity: float = 0.0
    equity_curve: list[tuple[datetime, float]] = field(default_factory=list)
    closed_trades: list[ClosedTrade] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.balance == 0.0:
            self.balance = self.initial_balance
        if self.total_equity == 0.0:
            self.total_equity = self.initial_balance
        if self.peak_equity == 0.0:
            self.peak_equity = self.initial_balance

    def lock_margin(self, amount: float) -> bool:
        """Reserve margin for a new position. Returns False if insufficient."""
        if amount > self.balance:
            return False
        self.balance -= amount
        self.locked_margin += amount
        return True

    def release_margin(self, amount: float, pnl: float) -> None:
        """Release margin and apply PnL when position closes."""
        self.locked_margin -= min(amount, self.locked_margin)
        self.balance += amount + pnl
        self.total_equity = self.balance + self.locked_margin
        self.peak_equity = max(self.peak_equity, self.total_equity)

    def snapshot(self, timestamp: datetime) -> None:
        """Record equity at this point in time."""
        self.total_equity = self.balance + self.locked_margin
        self.peak_equity = max(self.peak_equity, self.total_equity)
        self.equity_curve.append((timestamp, self.total_equity))

    @property
    def current_drawdown_pct(self) -> float:
        """Current drawdown from peak as a negative percentage."""
        if self.peak_equity <= 0:
            return 0.0
        return (self.total_equity / self.peak_equity) - 1.0


# ─────────────────────────────────────────────────────────────────────
# Backtest Simulator (orchestrator)
# ─────────────────────────────────────────────────────────────────────


@dataclass
class BacktestSimulator:
    """Stateful backtest engine v5 — engine-aware trade simulation.

    Usage:
        sim = BacktestSimulator(initial_balance=10_000)

        for cycle in range(max_cycles):
            sim.on_signal(output_dict, timestamp)
            sim.on_candle(high=h, low=l, close=c, atr_pct=a,
                          atr_pctl=p, timestamp=ts)

        results = sim.tear_sheet()
    """

    initial_balance: float = 10_000.0
    default_fee_pct: float = 0.001  # 0.1% per side (BingX)
    be_trigger_atr_multiple: float = 1.5
    trail_pct: float = 0.01  # 1.0% trailing distance
    max_concurrent_positions: int = 3
    account: VirtualAccount = field(default=None)  # type: ignore[assignment]
    positions: dict[str, SimulatedPosition] = field(default_factory=dict)
    _trade_counter: int = 0

    def __post_init__(self) -> None:
        if self.account is None:
            self.account = VirtualAccount(initial_balance=self.initial_balance)

    # ── Signal Intake ──

    def on_signal(self, output: dict[str, Any], timestamp: datetime) -> str | None:
        """Process one pipeline output. Opens a position if it's an advisory signal.

        v5: Reads engine, regime, adx from output and stores in position.

        Returns:
            trade_id if a position was opened, None otherwise.
        """
        status = str(output.get("status", "")).lower()
        reason = str(output.get("reason", ""))
        action = str(output.get("action", "")).lower()

        # Only accept advisory signals that passed all gates
        if status != "executed" or "advisory" not in reason:
            return None
        if action not in ("long", "short"):
            return None

        # Respect max concurrent positions
        if len(self.positions) >= self.max_concurrent_positions:
            return None

        # Don't double-enter the same symbol in the same direction
        for pos in self.positions.values():
            if pos.symbol == output.get("symbol") and pos.side == action:
                return None

        symbol = str(output.get("symbol", "UNKNOWN"))
        entry_price = float(output.get("suggested_entry_price") or 0)
        if entry_price <= 0:
            return None

        leverage = max(1.0, float(output.get("leverage", 1.0)))
        position_size_pct = float(output.get("position_size_pct", 0.0))
        sl_pct = float(output.get("stop_loss_pct", 0.0))
        tp_pct = float(output.get("take_profit_pct", 0.0))

        if sl_pct <= 0 or tp_pct <= 0 or position_size_pct <= 0:
            return None

        # v5: Extract engine + snapshot metadata
        engine = str(output.get("engine", "UNKNOWN"))
        gate_results = output.get("gate_results") or {}
        features_snap = gate_results.get("features_snapshot") or {}
        regime = str(features_snap.get("regime", "UNKNOWN"))
        adx = float(features_snap.get("adx_14", 0.0))

        # v6: Read orchestrator risk overrides
        v6_orch = output.get("v6_orchestrator") or {}
        v6_rr_mult = float(v6_orch.get("rr_mult", 1.0))
        v6_size_mult = float(v6_orch.get("size_mult", 1.0))
        v6_verified_trend = bool(v6_orch.get("verified_trend", False))
        v6_regime = str(output.get("v6_regime") or regime)

        # v6: Apply size multiplier
        position_size_pct = position_size_pct * v6_size_mult

        # v6: Apply RR multiplier to TP
        tp_pct = tp_pct * v6_rr_mult

        # Calculate notional and margin
        notional = self.account.total_equity * position_size_pct * leverage
        margin = notional / leverage

        if not self.account.lock_margin(margin):
            _LOG.debug("Insufficient margin for %s %s (need %.2f)", symbol, action, margin)
            return None

        # Calculate SL/TP prices
        if action == "long":
            sl_price = entry_price * (1 - sl_pct)
            tp_price = entry_price * (1 + tp_pct)
        else:
            sl_price = entry_price * (1 + sl_pct)
            tp_price = entry_price * (1 - tp_pct)

        self._trade_counter += 1
        trade_id = f"bt-{self._trade_counter:04d}"

        # TITAN v2: single position with multi-tier TP (handled by exit_policy)
        # No longer splits into 2 positions — tiers manage partial closes.
        if engine == "TITAN":
            from src.backtest.exit_policy import get_engine_exit_config as _get_exit_cfg
            _titan_cfg = _get_exit_cfg("TITAN")
            r_dist = abs(entry_price - sl_price)
            # Set TP very far — exit managed by trailing + tiers, not fixed TP
            if action == "long":
                tp_price = entry_price + r_dist * 20.0
            else:
                tp_price = entry_price - r_dist * 20.0

            pos = SimulatedPosition(
                trade_id=trade_id,
                symbol=symbol, side=action, engine=engine,
                regime=v6_regime, entry_price=entry_price,
                size_usd=notional, leverage=leverage,
                sl_price=sl_price, tp_price=tp_price, current_sl=sl_price,
                opened_at=timestamp, adx=adx, atr_pctl=0.0, candle_age=0,
            )
            pos._v6_verified_trend = v6_verified_trend  # type: ignore[attr-defined]
            pos._titan_runner = False  # type: ignore[attr-defined]
            pos._titan_tiers_filled = 0  # type: ignore[attr-defined]
            pos._titan_runner_active = False  # type: ignore[attr-defined]
            self.positions[trade_id] = pos

            _LOG.info(
                "[BT] OPEN %s TITAN %s %s @ %.2f | SL=%.2f TP=trail | size=$%.0f lev=%.1fx | regime=%s",
                trade_id, action.upper(), symbol, entry_price,
                sl_price, notional, leverage, v6_regime,
            )
            return trade_id

        pos = SimulatedPosition(
            trade_id=trade_id,
            symbol=symbol,
            side=action,
            engine=engine,
            regime=v6_regime,
            entry_price=entry_price,
            size_usd=notional,
            leverage=leverage,
            sl_price=sl_price,
            tp_price=tp_price,
            current_sl=sl_price,
            opened_at=timestamp,
            adx=adx,
            atr_pctl=0.0,
            candle_age=0,
        )
        pos._v6_verified_trend = v6_verified_trend  # type: ignore[attr-defined]
        self.positions[trade_id] = pos

        _LOG.info(
            "[BT] OPEN %s %s %s %s @ %.2f | SL=%.2f TP=%.2f | size=$%.0f lev=%.1fx | regime=%s adx=%.1f | v6: rr=%.1fx sz=%.1fx vt=%s",
            trade_id, engine, action.upper(), symbol, entry_price,
            sl_price, tp_price, notional, leverage, v6_regime, adx,
            v6_rr_mult, v6_size_mult, v6_verified_trend,
        )
        return trade_id

    # ── Candle Evaluation ──

    def on_candle(
        self,
        *,
        high: float,
        low: float,
        close: float,
        atr_pct: float = 0.0,
        atr_pctl: float = 0.0,
        timestamp: datetime,
    ) -> list[ClosedTrade]:
        """Evaluate all open positions against this candle.

        v5 steps:
            1. Increment candle_age for all positions
            2. Apply breakeven lock (if ATR condition met)
            3. Apply trailing stop (trend engines only)
            4. Check SL/TP hit on candle wicks
            5. Check time_stop (engine-specific max age)
            6. Close any hit positions

        Returns list of trades closed this candle.
        """
        closed: list[ClosedTrade] = []
        to_remove: list[str] = []

        for trade_id, pos in self.positions.items():
            # 1. Increment candle age
            pos.candle_age += 1

            # 2. Breakeven lock
            if not pos.be_locked:
                if pos.engine == "TITAN":
                    # TITAN: BE lock after TP1 (handled in step 2.5 below)
                    pass
                elif atr_pct > 0:
                    locked = pos.try_breakeven_lock(
                        current_price=close,
                        atr_pct=atr_pct,
                        trigger_multiple=self.be_trigger_atr_multiple,
                        fee_pct=self.default_fee_pct,
                    )
                    if locked:
                        _LOG.debug("[BT] BE lock engaged: %s SL -> %.2f", trade_id, pos.current_sl)

            # 2.5 TITAN multi-tier TP check
            if pos.engine == "TITAN" and atr_pct > 0:
                from src.backtest.exit_policy import get_engine_exit_config as _get_exit_cfg
                _titan_cfg = _get_exit_cfg("TITAN")
                _tiers_filled = getattr(pos, '_titan_tiers_filled', 0)
                _runner_active = getattr(pos, '_titan_runner_active', False)
                r_dist = abs(pos.entry_price - pos.sl_price)

                if r_dist > 0 and _tiers_filled < len(_titan_cfg.partial_tp_tiers):
                    tier_r, tier_frac = _titan_cfg.partial_tp_tiers[_tiers_filled]
                    tp_target = r_dist * tier_r
                    if pos.side == "long":
                        hit = close >= pos.entry_price + tp_target
                    else:
                        hit = close <= pos.entry_price - tp_target
                    if hit:
                        _tiers_filled += 1
                        pos._titan_tiers_filled = _tiers_filled  # type: ignore[attr-defined]
                        # Reduce position size
                        pos.size_usd *= (1.0 - tier_frac)
                        _LOG.debug(
                            "[BT] TITAN TP%d at %.1fR: %s size -> $%.0f",
                            _tiers_filled, tier_r, trade_id, pos.size_usd,
                        )
                        # After TP1: move SL to BE + fees
                        if _tiers_filled == 1 and _titan_cfg.be_after_tp1:
                            buffer = _titan_cfg.be_after_tp1_buffer_pct
                            if pos.side == "long":
                                be_price = pos.entry_price * (1 + buffer)
                                if be_price > pos.current_sl:
                                    pos.current_sl = be_price
                                    pos.be_locked = True
                            else:
                                be_price = pos.entry_price * (1 - buffer)
                                if be_price < pos.current_sl:
                                    pos.current_sl = be_price
                                    pos.be_locked = True
                        # If all tiers filled → runner mode
                        if _tiers_filled >= len(_titan_cfg.partial_tp_tiers):
                            pos._titan_runner_active = True  # type: ignore[attr-defined]

            # 3. Trailing stop — v6: trend engines + verified trend engines
            _v6_vt = getattr(pos, '_v6_verified_trend', False)
            _runner_active = getattr(pos, '_titan_runner_active', False)
            _trail_ok = pos.engine in TRAILING_ENGINES or (pos.engine == "TITAN" and _v6_vt)
            if _trail_ok:
                if pos.engine == "TITAN" and atr_pct > 0:
                    from src.backtest.exit_policy import get_engine_exit_config as _get_exit_cfg2
                    _titan_cfg2 = _get_exit_cfg2("TITAN")
                    if _runner_active:
                        # Runner: tighter ATR trailing
                        pos.try_trailing_stop_atr(
                            current_price=close, atr_pct=atr_pct,
                            atr_mult=_titan_cfg2.runner_trail_atr_mult,
                        )
                    else:
                        # Pre-runner: wider ATR trailing
                        pos.try_trailing_stop_atr(
                            current_price=close, atr_pct=atr_pct,
                            atr_mult=_titan_cfg2.trail_atr_mult or 2.5,
                        )
                elif pos.engine != "TITAN":
                    pos.try_trailing_stop(current_price=close, trail_pct=self.trail_pct)

            # 4. Check SL/TP hit
            exit_reason = pos.check_exit(high=high, low=low, close=close)

            # 5. Time stop — v5: per-engine max candle age (TITAN: unlimited hold)
            if exit_reason is None and pos.engine != "TITAN":
                max_age = ENGINE_MAX_AGE.get(pos.engine, DEFAULT_MAX_AGE)
                if pos.candle_age >= max_age:
                    exit_reason = "time_stop"

            if exit_reason is not None:
                # Determine fill price
                if exit_reason == "time_stop":
                    exit_price = close  # market exit at close
                else:
                    exit_price = pos.exit_price_for(exit_reason)

                pnl_usd, pnl_pct = pos.compute_pnl(exit_price)
                margin = pos.size_usd / pos.leverage if pos.leverage > 0 else pos.size_usd

                # Determine detailed exit reason
                detailed_reason = exit_reason
                if exit_reason == "sl" and pos.be_locked:
                    detailed_reason = "be_stop"

                trade = ClosedTrade(
                    trade_id=trade_id,
                    symbol=pos.symbol,
                    side=pos.side,
                    engine=pos.engine,
                    regime=pos.regime,
                    entry_price=pos.entry_price,
                    exit_price=exit_price,
                    size_usd=pos.size_usd,
                    leverage=pos.leverage,
                    pnl_usd=pnl_usd,
                    pnl_pct=pnl_pct,
                    opened_at=pos.opened_at,
                    closed_at=timestamp,
                    exit_reason=detailed_reason,
                    duration_candles=pos.candle_age,
                )
                self.account.release_margin(margin, pnl_usd)
                self.account.closed_trades.append(trade)
                closed.append(trade)
                to_remove.append(trade_id)

                _LOG.info(
                    "[BT] CLOSE %s %s %s %s @ %.2f -> %.2f | PnL=$%.2f (%.2f%%) | reason=%s | age=%d",
                    trade_id, pos.engine, pos.side.upper(), pos.symbol,
                    pos.entry_price, exit_price, pnl_usd, pnl_pct * 100,
                    detailed_reason, pos.candle_age,
                )

        for tid in to_remove:
            del self.positions[tid]

        # Snapshot equity
        self.account.snapshot(timestamp)

        return closed

    # ── Tear Sheet ──

    def tear_sheet(self) -> dict[str, Any]:
        """Generate a professional tear sheet with engine breakdown.

        Returns dict with global metrics + per-engine breakdown.
        """
        trades = self.account.closed_trades
        if not trades:
            return {
                "total_pnl_usd": 0.0,
                "total_pnl_pct": 0.0,
                "win_rate": 0.0,
                "max_drawdown_pct": 0.0,
                "total_trades": 0,
                "profit_factor": 0.0,
                "exit_reasons": {},
                "initial_balance": getattr(self, "initial_balance", 10000.0),
                "final_equity": self.account.total_equity,
                "open_positions": len(self.positions),
                "engine_breakdown": {},
            }

        # ── Global stats ──
        total_pnl = sum(t.pnl_usd for t in trades)
        wins = [t for t in trades if t.pnl_usd > 0]
        losses = [t for t in trades if t.pnl_usd <= 0]
        win_rate = len(wins) / len(trades) if trades else 0.0

        avg_win = sum(t.pnl_usd for t in wins) / len(wins) if wins else 0.0
        avg_loss = sum(t.pnl_usd for t in losses) / len(losses) if losses else 0.0

        gross_profit = sum(t.pnl_usd for t in wins)
        gross_loss = abs(sum(t.pnl_usd for t in losses))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")

        # Max drawdown from equity curve
        max_dd = 0.0
        peak = self.initial_balance
        for _, equity in self.account.equity_curve:
            peak = max(peak, equity)
            dd = (equity / peak) - 1.0 if peak > 0 else 0.0
            max_dd = min(max_dd, dd)

        # Best/worst trades
        best = max(trades, key=lambda t: t.pnl_usd)
        worst = min(trades, key=lambda t: t.pnl_usd)

        # Exit reason breakdown
        exit_reasons: dict[str, int] = {}
        for t in trades:
            exit_reasons[t.exit_reason] = exit_reasons.get(t.exit_reason, 0) + 1

        # Approximate Sharpe (trade-based)
        pnl_series = [t.pnl_usd for t in trades]
        if len(pnl_series) >= 2:
            mean_pnl = statistics.mean(pnl_series)
            std_pnl = statistics.stdev(pnl_series)
            sharpe = (mean_pnl / std_pnl) * (252 ** 0.5) if std_pnl > 0 else 0.0
        else:
            sharpe = 0.0

        # ── v5: Engine Breakdown ──
        engine_breakdown = self._compute_engine_breakdown(trades)

        return {
            "total_pnl_usd": round(total_pnl, 2),
            "total_pnl_pct": round(total_pnl / self.initial_balance * 100, 2),
            "win_rate": round(win_rate * 100, 1),
            "max_drawdown_pct": round(max_dd * 100, 2),
            "total_trades": len(trades),
            "wins": len(wins),
            "losses": len(losses),
            "avg_win_usd": round(avg_win, 2),
            "avg_loss_usd": round(avg_loss, 2),
            "profit_factor": round(profit_factor, 2),
            "sharpe_approx": round(sharpe, 2),
            "best_trade_usd": round(best.pnl_usd, 2),
            "worst_trade_usd": round(worst.pnl_usd, 2),
            "exit_reasons": exit_reasons,
            "final_equity": round(self.account.total_equity, 2),
            "open_positions": len(self.positions),
            "initial_balance": self.initial_balance,
            "engine_breakdown": engine_breakdown,
            "regime_breakdown": self._compute_regime_breakdown(trades),
            "engine_regime_matrix": self._compute_engine_regime_matrix(trades),
        }

    @staticmethod
    def _compute_engine_breakdown(trades: list[ClosedTrade]) -> dict[str, dict[str, Any]]:
        """Compute per-engine metrics: PF, win rate, avg win/loss, exit reasons."""
        by_engine: dict[str, list[ClosedTrade]] = {}
        for t in trades:
            by_engine.setdefault(t.engine, []).append(t)

        breakdown: dict[str, dict[str, Any]] = {}
        for engine, engine_trades in sorted(by_engine.items()):
            e_wins = [t for t in engine_trades if t.pnl_usd > 0]
            e_losses = [t for t in engine_trades if t.pnl_usd <= 0]
            e_gross_profit = sum(t.pnl_usd for t in e_wins)
            e_gross_loss = abs(sum(t.pnl_usd for t in e_losses))
            e_pf = e_gross_profit / e_gross_loss if e_gross_loss > 0 else float("inf")

            e_exit: dict[str, int] = {}
            for t in engine_trades:
                e_exit[t.exit_reason] = e_exit.get(t.exit_reason, 0) + 1

            e_durations = [t.duration_candles for t in engine_trades]

            breakdown[engine] = {
                "trades": len(engine_trades),
                "wins": len(e_wins),
                "losses": len(e_losses),
                "win_rate": round(len(e_wins) / len(engine_trades) * 100, 1) if engine_trades else 0.0,
                "gross_profit": round(e_gross_profit, 2),
                "gross_loss": round(e_gross_loss, 2),
                "profit_factor": round(e_pf, 2),
                "avg_win": round(sum(t.pnl_usd for t in e_wins) / len(e_wins), 2) if e_wins else 0.0,
                "avg_loss": round(sum(t.pnl_usd for t in e_losses) / len(e_losses), 2) if e_losses else 0.0,
                "avg_duration_candles": round(sum(e_durations) / len(e_durations), 1) if e_durations else 0.0,
                "exit_reasons": e_exit,
            }
        return breakdown

    def print_tear_sheet(self) -> None:
        """Print a formatted tear sheet with engine breakdown to stdout."""
        ts = self.tear_sheet()
        border = "=" * 60
        print(f"\n{border}")
        print("  ARGUS v2.5 — STATEFUL BACKTEST TEAR SHEET (v5)")
        print(border)
        print(f"  Initial Balance:     ${ts['initial_balance']:>10,.2f}")
        print(f"  Final Equity:        ${ts['final_equity']:>10,.2f}")
        print(f"  Total PnL:           ${ts['total_pnl_usd']:>10,.2f}  ({ts['total_pnl_pct']:+.2f}%)")
        print(f"  Max Drawdown:         {ts['max_drawdown_pct']:>10.2f}%")
        print(f"  {'-' * 58}")
        print(f"  Total Trades:         {ts['total_trades']:>10d}")
        print(f"  Wins / Losses:        {ts.get('wins', 0):>4d} / {ts.get('losses', 0):<4d}")
        print(f"  Win Rate:             {ts['win_rate']:>10.1f}%")
        print(f"  Profit Factor:        {ts.get('profit_factor', 0):>10.2f}")
        print(f"  Sharpe (approx):      {ts.get('sharpe_approx', 0):>10.2f}")
        print(f"  {'-' * 58}")
        print(f"  Avg Win:             ${ts.get('avg_win_usd', 0):>10,.2f}")
        print(f"  Avg Loss:            ${ts.get('avg_loss_usd', 0):>10,.2f}")
        print(f"  Best Trade:          ${ts.get('best_trade_usd', 0):>10,.2f}")
        print(f"  Worst Trade:         ${ts.get('worst_trade_usd', 0):>10,.2f}")
        print(f"  {'-' * 58}")
        print(f"  Exit Reasons:")
        for reason, count in sorted(ts.get("exit_reasons", {}).items()):
            print(f"    {reason:<20s} {count:>5d}")
        if ts["open_positions"] > 0:
            print(f"  Open Positions:       {ts['open_positions']:>10d} (still active)")

        # v5: Engine Breakdown
        eb = ts.get("engine_breakdown", {})
        if eb:
            print(f"\n  {'-' * 58}")
            print(f"  ENGINE BREAKDOWN:")
            print(f"  {'Engine':<12s} {'Trades':>6s} {'WR%':>6s} {'PF':>6s} {'AvgW':>8s} {'AvgL':>8s} {'AvgAge':>6s}")
            print(f"  {'-' * 58}")
            for eng, m in sorted(eb.items()):
                print(
                    f"  {eng:<12s} {m['trades']:>6d} {m['win_rate']:>5.1f}% "
                    f"{m['profit_factor']:>5.2f} ${m['avg_win']:>7.2f} ${m['avg_loss']:>7.2f} "
                    f"{m['avg_duration_candles']:>5.1f}"
                )
                for reason, count in sorted(m.get("exit_reasons", {}).items()):
                    print(f"    - {reason}: {count}")

        # v6: Regime Breakdown
        rb = ts.get("regime_breakdown", {})
        if rb:
            print(f"\n  {'-' * 58}")
            print(f"  REGIME BREAKDOWN:")
            print(f"  {'Regime':<12s} {'Trades':>6s} {'WR%':>6s} {'PF':>6s} {'AvgW':>8s} {'AvgL':>8s}")
            print(f"  {'-' * 58}")
            for reg, m in sorted(rb.items()):
                print(
                    f"  {reg:<12s} {m['trades']:>6d} {m['win_rate']:>5.1f}% "
                    f"{m['profit_factor']:>5.2f} ${m['avg_win']:>7.2f} ${m['avg_loss']:>7.2f}"
                )

        # v6: Engine x Regime Matrix
        erm = ts.get("engine_regime_matrix", {})
        if erm:
            print(f"\n  {'-' * 58}")
            print(f"  ENGINE x REGIME MATRIX (PF):")
            regimes = sorted(set(r for eng_data in erm.values() for r in eng_data))
            header = f"  {'Engine':<12s}" + "".join(f" {r:<10s}" for r in regimes)
            print(header)
            print(f"  {'-' * 58}")
            for eng, reg_data in sorted(erm.items()):
                row = f"  {eng:<12s}"
                for r in regimes:
                    if r in reg_data:
                        row += f" {reg_data[r]['pf']:>9.2f}"
                    else:
                        row += f" {'---':>9s}"
                print(row)

        print(border)
        print()

    @staticmethod
    def _compute_regime_breakdown(trades: list[ClosedTrade]) -> dict[str, dict[str, Any]]:
        """Compute per-regime metrics: PF, win rate, avg win/loss."""
        by_regime: dict[str, list[ClosedTrade]] = {}
        for t in trades:
            by_regime.setdefault(t.regime, []).append(t)

        breakdown: dict[str, dict[str, Any]] = {}
        for regime, regime_trades in sorted(by_regime.items()):
            r_wins = [t for t in regime_trades if t.pnl_usd > 0]
            r_losses = [t for t in regime_trades if t.pnl_usd <= 0]
            r_gross_profit = sum(t.pnl_usd for t in r_wins)
            r_gross_loss = abs(sum(t.pnl_usd for t in r_losses))
            r_pf = r_gross_profit / r_gross_loss if r_gross_loss > 0 else float("inf")

            breakdown[regime] = {
                "trades": len(regime_trades),
                "wins": len(r_wins),
                "losses": len(r_losses),
                "win_rate": round(len(r_wins) / len(regime_trades) * 100, 1) if regime_trades else 0.0,
                "gross_profit": round(r_gross_profit, 2),
                "gross_loss": round(r_gross_loss, 2),
                "profit_factor": round(r_pf, 2),
                "avg_win": round(sum(t.pnl_usd for t in r_wins) / len(r_wins), 2) if r_wins else 0.0,
                "avg_loss": round(sum(t.pnl_usd for t in r_losses) / len(r_losses), 2) if r_losses else 0.0,
                "total_pnl": round(sum(t.pnl_usd for t in regime_trades), 2),
            }
        return breakdown

    @staticmethod
    def _compute_engine_regime_matrix(trades: list[ClosedTrade]) -> dict[str, dict[str, dict[str, Any]]]:
        """Compute Engine x Regime cross-matrix with PF and trade count."""
        by_combo: dict[tuple[str, str], list[ClosedTrade]] = {}
        for t in trades:
            key = (t.engine, t.regime)
            by_combo.setdefault(key, []).append(t)

        matrix: dict[str, dict[str, dict[str, Any]]] = {}
        for (engine, regime), combo_trades in sorted(by_combo.items()):
            c_wins = [t for t in combo_trades if t.pnl_usd > 0]
            c_losses = [t for t in combo_trades if t.pnl_usd <= 0]
            c_gp = sum(t.pnl_usd for t in c_wins)
            c_gl = abs(sum(t.pnl_usd for t in c_losses))
            c_pf = c_gp / c_gl if c_gl > 0 else float("inf")

            matrix.setdefault(engine, {})[regime] = {
                "trades": len(combo_trades),
                "pf": round(c_pf, 2),
                "win_rate": round(len(c_wins) / len(combo_trades) * 100, 1) if combo_trades else 0.0,
                "pnl": round(sum(t.pnl_usd for t in combo_trades), 2),
            }
        return matrix
