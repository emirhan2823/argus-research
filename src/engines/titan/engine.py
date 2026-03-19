"""TITAN v2: Dual-setup institutional trend engine.

Two setup types:
  REVERSAL:     Exhaustion → Structure Shift → Volume → Pullback entry
  CONTINUATION: Trend Confirm → HH/HL continuation → Volume → Pullback entry

Both long and short supported equally. Short wins tie-break only.

Active in TRENDING regime. Call feed_candles() each cycle before generate_signal().
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from src.core.constants import ENGINE_TITAN, REGIME_TRENDING
from src.core.types import EngineSignal, FeatureVector, RegimeState
from src.features.market_structure import detect_swing_levels


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _compute_adx_series(
    highs: list[float], lows: list[float], closes: list[float], length: int = 14,
) -> list[float]:
    """Compute ADX values from raw OHLC using Wilder smoothing."""
    n = len(closes)
    if n < length + 1:
        return []

    h = np.array(highs, dtype=float)
    l = np.array(lows, dtype=float)
    c = np.array(closes, dtype=float)

    up_move = np.diff(h)
    down_move = -np.diff(l)

    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)

    tr = np.maximum(
        h[1:] - l[1:],
        np.maximum(np.abs(h[1:] - c[:-1]), np.abs(l[1:] - c[:-1])),
    )

    alpha = 1.0 / length
    atr_vals = np.zeros(len(tr))
    plus_di_smooth = np.zeros(len(tr))
    minus_di_smooth = np.zeros(len(tr))

    atr_vals[0] = tr[0]
    plus_di_smooth[0] = plus_dm[0]
    minus_di_smooth[0] = minus_dm[0]

    for i in range(1, len(tr)):
        atr_vals[i] = atr_vals[i - 1] * (1 - alpha) + tr[i] * alpha
        plus_di_smooth[i] = plus_di_smooth[i - 1] * (1 - alpha) + plus_dm[i] * alpha
        minus_di_smooth[i] = minus_di_smooth[i - 1] * (1 - alpha) + minus_dm[i] * alpha

    atr_safe = np.where(atr_vals > 0, atr_vals, 1e-10)
    plus_di = 100.0 * plus_di_smooth / atr_safe
    minus_di = 100.0 * minus_di_smooth / atr_safe
    di_sum = plus_di + minus_di
    di_sum_safe = np.where(di_sum > 0, di_sum, 1e-10)
    dx = 100.0 * np.abs(plus_di - minus_di) / di_sum_safe

    adx = np.zeros(len(dx))
    adx[0] = dx[0]
    for i in range(1, len(dx)):
        adx[i] = adx[i - 1] * (1 - alpha) + dx[i] * alpha

    return adx.tolist()


def _rsi_series(closes: list[float], length: int = 14) -> list[float]:
    """Compute Wilder RSI from close prices."""
    n = len(closes)
    if n < length + 1:
        return []

    c = np.array(closes, dtype=float)
    deltas = np.diff(c)
    gains = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)

    alpha = 1.0 / length
    avg_gain = np.zeros(len(deltas))
    avg_loss = np.zeros(len(deltas))

    avg_gain[0] = gains[0]
    avg_loss[0] = losses[0]

    for i in range(1, len(deltas)):
        avg_gain[i] = avg_gain[i - 1] * (1 - alpha) + gains[i] * alpha
        avg_loss[i] = avg_loss[i - 1] * (1 - alpha) + losses[i] * alpha

    rs = avg_gain / np.where(avg_loss > 0, avg_loss, 1e-10)
    rsi = 100.0 - 100.0 / (1.0 + rs)
    return rsi.tolist()


def _ema(values: list[float], length: int) -> list[float]:
    """Simple EMA computation."""
    if not values:
        return []
    alpha = 2.0 / (length + 1)
    result = [values[0]]
    for v in values[1:]:
        result.append(result[-1] * (1 - alpha) + v * alpha)
    return result


def _bb_pct_b(closes: list[float], length: int = 20, mult: float = 2.0) -> float:
    """Compute Bollinger Band %B for the last bar."""
    if len(closes) < length:
        return 0.5
    window = closes[-length:]
    sma = sum(window) / length
    std = (sum((x - sma) ** 2 for x in window) / length) ** 0.5
    if std < 1e-10:
        return 0.5
    upper = sma + mult * std
    lower = sma - mult * std
    band_width = upper - lower
    if band_width < 1e-10:
        return 0.5
    return (closes[-1] - lower) / band_width


@dataclass
class TitanEngine:
    """TITAN v2: Dual-setup institutional trend engine.

    Two setup types:
      REVERSAL:     Exhaustion -> Structure Shift -> Volume -> Pullback entry
      CONTINUATION: Trend Confirm -> HH/HL continuation -> Volume -> Pullback entry

    Both long and short supported equally. Short wins tie-break only.
    """

    # --- REVERSAL setup: exhaustion detection ---
    rsi_exhaustion_high: float = 70.0
    rsi_exhaustion_low: float = 30.0
    exhaustion_lookback: int = 20
    bb_proximity_pct: float = 0.95
    atr_expansion_pctl: float = 0.65

    # --- CONTINUATION setup: trend confirmation ---
    min_adx: float = 35.0  # YAML single source of truth (config/engines.yaml)
    adx_rising_bars: int = 1  # YAML single source of truth
    min_atr_pctl: float = 0.55
    min_volume_expansion: float = 0.8  # YAML single source of truth

    # --- Shared ---
    swing_window: int = 5
    breakdown_volume_mult: float = 1.5
    pullback_atr_tolerance: float = 1.2  # YAML single source of truth

    # --- Risk ---
    target_rr: float = 3.0
    atr_trail_mult: float = 2.5
    min_confidence: float = 0.55
    max_stop_pct: float = 0.05

    # Internal state (candle history per symbol)
    _candle_history: dict[str, tuple[list[float], list[float], list[float]]] = field(
        default_factory=dict, repr=False,
    )

    # Diagnostic counters (no behavior change, just observability)
    _diag: dict[str, int] = field(default_factory=lambda: {
        "cont_long_calls": 0, "cont_short_calls": 0,
        "cont_long_fail_adx": 0, "cont_long_fail_adx_rising": 0,
        "cont_long_fail_ema": 0, "cont_long_fail_ma200": 0,
        "cont_long_fail_structure": 0, "cont_long_fail_atr_pctl": 0,
        "cont_long_fail_volume": 0, "cont_long_pass": 0,
        "cont_short_fail_adx": 0, "cont_short_fail_adx_rising": 0,
        "cont_short_fail_ema": 0, "cont_short_fail_ma200": 0,
        "cont_short_fail_structure": 0, "cont_short_fail_atr_pctl": 0,
        "cont_short_fail_volume": 0, "cont_short_pass": 0,
        "pullback_fail": 0, "pullback_pass": 0,
        "regime_reject": 0, "history_reject": 0,
        "signal_produced": 0,
    }, repr=False)

    def feed_candles(
        self,
        *,
        symbol: str,
        highs: list[float],
        lows: list[float],
        closes: list[float],
    ) -> None:
        """Update candle history for a symbol. Call before generate_signal()."""
        max_len = 500
        self._candle_history[symbol] = (
            highs[-max_len:],
            lows[-max_len:],
            closes[-max_len:],
        )

    def generate_signal(
        self,
        *,
        regime: RegimeState,
        features: FeatureVector,
        trend_score: float = 0.0,
    ) -> Optional[EngineSignal]:
        """Generate trend signal using dual-setup architecture.

        Tries REVERSAL (both directions) then CONTINUATION (both directions).
        Picks highest confidence. Short wins tie-break only.
        """
        if regime.regime != REGIME_TRENDING:
            self._diag["regime_reject"] += 1
            return None

        history = self._candle_history.get(features.symbol)
        if history is None or len(history[0]) < 50:
            self._diag["history_reject"] += 1
            return None

        highs, lows, closes = history

        candidates: list[EngineSignal] = []

        # --- REVERSAL setups (require exhaustion) ---
        rev_short = self._try_reversal(features, highs, lows, closes, bias="short")
        if rev_short is not None:
            candidates.append(rev_short)

        rev_long = self._try_reversal(features, highs, lows, closes, bias="long")
        if rev_long is not None:
            candidates.append(rev_long)

        # --- CONTINUATION setups (no exhaustion) ---
        cont_short = self._try_continuation(features, highs, lows, closes, bias="short")
        if cont_short is not None:
            candidates.append(cont_short)

        cont_long = self._try_continuation(features, highs, lows, closes, bias="long")
        if cont_long is not None:
            candidates.append(cont_long)

        if not candidates:
            return None

        # Sort by confidence DESC; short wins tie-break
        candidates.sort(key=lambda s: (s.confidence, 1 if s.bias == "short" else 0), reverse=True)

        best = candidates[0]
        if best.confidence < self.min_confidence:
            return None

        # Attach leverage hint if trend_score provided
        if trend_score > 0:
            best = self._apply_leverage_hint(best, trend_score)

        self._diag["signal_produced"] += 1
        return best

    # ------------------------------------------------------------------
    # REVERSAL setup: Exhaustion → Structure Shift → Volume → Pullback
    # ------------------------------------------------------------------

    def _try_reversal(
        self,
        features: FeatureVector,
        highs: list[float],
        lows: list[float],
        closes: list[float],
        bias: str,
    ) -> Optional[EngineSignal]:
        """Attempt a REVERSAL setup in the given direction."""
        # Stage 1: Exhaustion detection
        if bias == "short":
            if not self._detect_exhaustion_top(closes):
                return None
        else:
            if not self._detect_exhaustion_bottom(closes):
                return None

        # Stage 2: Structure shift
        if bias == "short":
            structure_ok, strength = self._detect_structure_shift_bearish(
                features, highs, lows, closes,
            )
        else:
            structure_ok, strength = self._detect_structure_shift_bullish(
                features, highs, lows, closes,
            )
        if not structure_ok:
            return None

        # Stage 3: Volume confirmation
        if features.volume_ratio < self.breakdown_volume_mult:
            return None

        # Stage 4: Pullback entry
        if not self._check_pullback_entry(features, highs, lows, closes, bias):
            return None

        # Compute exhaustion strength for confidence
        rsi_vals = _rsi_series(closes, 14)
        exhaustion_strength = 0.0
        if rsi_vals:
            if bias == "short":
                peak = max(rsi_vals[-self.exhaustion_lookback:]) if len(rsi_vals) >= self.exhaustion_lookback else max(rsi_vals)
                exhaustion_strength = _clamp((peak - self.rsi_exhaustion_high) / 30.0, 0.0, 1.0)
            else:
                trough = min(rsi_vals[-self.exhaustion_lookback:]) if len(rsi_vals) >= self.exhaustion_lookback else min(rsi_vals)
                exhaustion_strength = _clamp((self.rsi_exhaustion_low - trough) / 30.0, 0.0, 1.0)

        volume_bonus = _clamp((features.volume_ratio - 1.0) / 2.0, 0.0, 1.0)

        conf = _clamp(
            0.62
            + (features.adx_14 / 100.0) * 0.12
            + strength * 0.10
            + volume_bonus * 0.08
            + exhaustion_strength * 0.08,
            0.0,
            1.0,
        )

        stop = self._structural_stop(highs, lows, closes, bias, features)

        return EngineSignal(
            engine=ENGINE_TITAN,
            sub_strategy=f"reversal_{bias}",
            asset_class=features.asset_class,
            symbol=features.symbol,
            bias=bias,
            confidence=conf,
            stop_distance=stop,
            expected_return=stop * self.target_rr,
            atr=features.atr_14,
        )

    def _detect_exhaustion_top(self, closes: list[float]) -> bool:
        """Detect exhaustion at top: RSI>70 + BB%B>0.95 in recent bars."""
        rsi_vals = _rsi_series(closes, 14)
        if not rsi_vals:
            return False

        lookback = min(self.exhaustion_lookback, len(rsi_vals))
        recent_rsi = rsi_vals[-lookback:]

        rsi_extreme = any(v >= self.rsi_exhaustion_high for v in recent_rsi)
        if not rsi_extreme:
            return False

        bb_b = _bb_pct_b(closes)
        # BB%B check: either currently extreme or was extreme recently
        # We check current BB%B as proxy
        bb_extreme = bb_b >= self.bb_proximity_pct
        if not bb_extreme:
            # Also check if BB%B was extreme in recent history (within lookback)
            # Use a sliding BB%B check over last few bars
            for offset in range(1, min(5, len(closes))):
                bb_check = _bb_pct_b(closes[:-offset] if offset > 0 else closes)
                if bb_check >= self.bb_proximity_pct:
                    bb_extreme = True
                    break

        return bb_extreme

    def _detect_exhaustion_bottom(self, closes: list[float]) -> bool:
        """Detect exhaustion at bottom: RSI<30 + BB%B<0.05 in recent bars."""
        rsi_vals = _rsi_series(closes, 14)
        if not rsi_vals:
            return False

        lookback = min(self.exhaustion_lookback, len(rsi_vals))
        recent_rsi = rsi_vals[-lookback:]

        rsi_extreme = any(v <= self.rsi_exhaustion_low for v in recent_rsi)
        if not rsi_extreme:
            return False

        bb_b = _bb_pct_b(closes)
        bb_low_threshold = 1.0 - self.bb_proximity_pct  # 0.05
        bb_extreme = bb_b <= bb_low_threshold

        if not bb_extreme:
            for offset in range(1, min(5, len(closes))):
                bb_check = _bb_pct_b(closes[:-offset] if offset > 0 else closes)
                if bb_check <= bb_low_threshold:
                    bb_extreme = True
                    break

        return bb_extreme

    def _detect_structure_shift_bearish(
        self,
        features: FeatureVector,
        highs: list[float],
        lows: list[float],
        closes: list[float],
    ) -> tuple[bool, float]:
        """Detect bearish structure shift: HH->LH + swing low break + EMA21<EMA55.

        Returns (passed, structure_strength 0-1).
        """
        if features.ema_21_vs_55 >= 0:
            return False, 0.0

        levels = detect_swing_levels(highs=highs, lows=lows, window=self.swing_window)
        swing_highs = sorted(
            [lv for lv in levels if lv.level_type == "resistance"],
            key=lambda lv: lv.bar_index,
        )
        swing_lows = sorted(
            [lv for lv in levels if lv.level_type == "support"],
            key=lambda lv: lv.bar_index,
        )

        if len(swing_highs) < 2 or len(swing_lows) < 1:
            return False, 0.0

        # LH: most recent high < previous high
        lh = swing_highs[-1].price < swing_highs[-2].price
        if not lh:
            return False, 0.0

        # Swing low break: current close below most recent swing low
        recent_low = swing_lows[-1]
        low_break = closes[-1] < recent_low.price

        if not low_break:
            return False, 0.0

        # Count consecutive bearish structure (LL/LH)
        strength = self._count_bearish_structure(swing_highs, swing_lows)
        norm_strength = _clamp(strength / 4.0, 0.0, 1.0)

        return True, norm_strength

    def _detect_structure_shift_bullish(
        self,
        features: FeatureVector,
        highs: list[float],
        lows: list[float],
        closes: list[float],
    ) -> tuple[bool, float]:
        """Detect bullish structure shift: LL->HL + swing high break + EMA21>EMA55."""
        if features.ema_21_vs_55 <= 0:
            return False, 0.0

        levels = detect_swing_levels(highs=highs, lows=lows, window=self.swing_window)
        swing_highs = sorted(
            [lv for lv in levels if lv.level_type == "resistance"],
            key=lambda lv: lv.bar_index,
        )
        swing_lows = sorted(
            [lv for lv in levels if lv.level_type == "support"],
            key=lambda lv: lv.bar_index,
        )

        if len(swing_lows) < 2 or len(swing_highs) < 1:
            return False, 0.0

        # HL: most recent low > previous low
        hl = swing_lows[-1].price > swing_lows[-2].price
        if not hl:
            return False, 0.0

        # Swing high break: current close above most recent swing high
        recent_high = swing_highs[-1]
        high_break = closes[-1] > recent_high.price

        if not high_break:
            return False, 0.0

        strength = self._count_bullish_structure(swing_highs, swing_lows)
        norm_strength = _clamp(strength / 4.0, 0.0, 1.0)

        return True, norm_strength

    # ------------------------------------------------------------------
    # CONTINUATION setup: Trend Confirm → HH/HL → Volume → Pullback
    # ------------------------------------------------------------------

    def _try_continuation(
        self,
        features: FeatureVector,
        highs: list[float],
        lows: list[float],
        closes: list[float],
        bias: str,
    ) -> Optional[EngineSignal]:
        """Attempt a CONTINUATION setup. No exhaustion required."""
        # Trend confirmation
        if bias == "short":
            confirm_ok, strength = self._check_trend_confirmation_short(
                features, highs, lows, closes,
            )
        else:
            confirm_ok, strength = self._check_trend_confirmation_long(
                features, highs, lows, closes,
            )
        if not confirm_ok:
            return None

        # Pullback entry
        if not self._check_pullback_entry(features, highs, lows, closes, bias):
            self._diag["pullback_fail"] += 1
            return None

        self._diag["pullback_pass"] += 1
        volume_bonus = _clamp((features.volume_ratio - 1.0) / 2.0, 0.0, 1.0)
        atr_pctl = features.atr_pctl if features.atr_pctl is not None else 0.0
        atr_bonus = _clamp(atr_pctl, 0.0, 1.0)

        conf = _clamp(
            0.58
            + (features.adx_14 / 100.0) * 0.15
            + strength * 0.12
            + volume_bonus * 0.10
            + atr_bonus * 0.05,
            0.0,
            1.0,
        )

        stop = self._structural_stop(highs, lows, closes, bias, features)

        return EngineSignal(
            engine=ENGINE_TITAN,
            sub_strategy=f"continuation_{bias}",
            asset_class=features.asset_class,
            symbol=features.symbol,
            bias=bias,
            confidence=conf,
            stop_distance=stop,
            expected_return=stop * self.target_rr,
            atr=features.atr_14,
        )

    def _check_trend_confirmation_long(
        self,
        features: FeatureVector,
        highs: list[float],
        lows: list[float],
        closes: list[float],
    ) -> tuple[bool, float]:
        """6-condition trend confirmation for long CONTINUATION.

        Returns (passed, structure_strength 0-1).
        """
        self._diag["cont_long_calls"] += 1

        # 1) ADX > min_adx
        if features.adx_14 < self.min_adx:
            self._diag["cont_long_fail_adx"] += 1
            return False, 0.0

        # 2) ADX rising
        if not self._check_adx_rising(highs, lows, closes):
            self._diag["cont_long_fail_adx_rising"] += 1
            return False, 0.0

        # 3) EMA21 > EMA55
        if features.ema_21_vs_55 <= 0:
            self._diag["cont_long_fail_ema"] += 1
            return False, 0.0

        # 4) Price > MA200
        if features.price_vs_ma200 <= 0:
            self._diag["cont_long_fail_ma200"] += 1
            return False, 0.0

        # 5) HH/HL structure
        levels = detect_swing_levels(highs=highs, lows=lows, window=self.swing_window)
        swing_highs = sorted(
            [lv for lv in levels if lv.level_type == "resistance"],
            key=lambda lv: lv.bar_index,
        )
        swing_lows = sorted(
            [lv for lv in levels if lv.level_type == "support"],
            key=lambda lv: lv.bar_index,
        )

        if len(swing_highs) < 2 or len(swing_lows) < 2:
            self._diag["cont_long_fail_structure"] += 1
            return False, 0.0

        hh = swing_highs[-1].price > swing_highs[-2].price
        hl = swing_lows[-1].price > swing_lows[-2].price
        if not (hh and hl):
            self._diag["cont_long_fail_structure"] += 1
            return False, 0.0

        # 6) ATR percentile
        atr_pctl = features.atr_pctl if features.atr_pctl is not None else 0.0
        if atr_pctl < self.min_atr_pctl:
            self._diag["cont_long_fail_atr_pctl"] += 1
            return False, 0.0

        # 7) Volume expansion
        if features.volume_ratio < self.min_volume_expansion:
            self._diag["cont_long_fail_volume"] += 1
            return False, 0.0

        self._diag["cont_long_pass"] += 1
        strength = self._count_bullish_structure(swing_highs, swing_lows)
        norm_strength = _clamp(strength / 4.0, 0.0, 1.0)

        return True, norm_strength

    def _check_trend_confirmation_short(
        self,
        features: FeatureVector,
        highs: list[float],
        lows: list[float],
        closes: list[float],
    ) -> tuple[bool, float]:
        """6-condition trend confirmation for short CONTINUATION."""
        self._diag["cont_short_calls"] += 1

        if features.adx_14 < self.min_adx:
            self._diag["cont_short_fail_adx"] += 1
            return False, 0.0

        if not self._check_adx_rising(highs, lows, closes):
            self._diag["cont_short_fail_adx_rising"] += 1
            return False, 0.0

        if features.ema_21_vs_55 >= 0:
            self._diag["cont_short_fail_ema"] += 1
            return False, 0.0

        if features.price_vs_ma200 >= 0:
            self._diag["cont_short_fail_ma200"] += 1
            return False, 0.0

        levels = detect_swing_levels(highs=highs, lows=lows, window=self.swing_window)
        swing_highs = sorted(
            [lv for lv in levels if lv.level_type == "resistance"],
            key=lambda lv: lv.bar_index,
        )
        swing_lows = sorted(
            [lv for lv in levels if lv.level_type == "support"],
            key=lambda lv: lv.bar_index,
        )

        if len(swing_highs) < 2 or len(swing_lows) < 2:
            self._diag["cont_short_fail_structure"] += 1
            return False, 0.0

        ll = swing_lows[-1].price < swing_lows[-2].price
        lh = swing_highs[-1].price < swing_highs[-2].price
        if not (ll and lh):
            self._diag["cont_short_fail_structure"] += 1
            return False, 0.0

        atr_pctl = features.atr_pctl if features.atr_pctl is not None else 0.0
        if atr_pctl < self.min_atr_pctl:
            self._diag["cont_short_fail_atr_pctl"] += 1
            return False, 0.0

        if features.volume_ratio < self.min_volume_expansion:
            self._diag["cont_short_fail_volume"] += 1
            return False, 0.0

        self._diag["cont_short_pass"] += 1
        strength = self._count_bearish_structure(swing_highs, swing_lows)
        norm_strength = _clamp(strength / 4.0, 0.0, 1.0)

        return True, norm_strength

    # ------------------------------------------------------------------
    # Shared helpers
    # ------------------------------------------------------------------

    def _check_pullback_entry(
        self,
        features: FeatureVector,
        highs: list[float],
        lows: list[float],
        closes: list[float],
        bias: str,
    ) -> bool:
        """Check if price is pulling back to EMA21 zone with rejection candle."""
        if len(closes) < 2:
            return False

        current_close = closes[-1]
        current_high = highs[-1]
        current_low = lows[-1]

        atr = features.atr_14
        if atr <= 0:
            return False

        tolerance = self.pullback_atr_tolerance * atr

        if bias == "long":
            # Pullback: candle dips near EMA21 zone, close in upper half (rejection)
            rejection = current_close > (current_low + current_high) / 2
            pullback_near = (current_close - current_low) <= tolerance
            return rejection and pullback_near
        else:
            # Short: candle wicks up near EMA21 zone, close in lower half
            rejection = current_close < (current_low + current_high) / 2
            pullback_near = (current_high - current_close) <= tolerance
            return rejection and pullback_near

    def _check_adx_rising(
        self,
        highs: list[float],
        lows: list[float],
        closes: list[float],
    ) -> bool:
        """Check if ADX has risen for the required consecutive bars."""
        if len(closes) < 30:
            return False

        adx_values = _compute_adx_series(highs, lows, closes, length=14)
        needed = self.adx_rising_bars + 1
        if len(adx_values) < needed:
            return False

        tail = adx_values[-needed:]
        return all(tail[i + 1] > tail[i] for i in range(len(tail) - 1))

    def _structural_stop(
        self,
        highs: list[float],
        lows: list[float],
        closes: list[float],
        bias: str,
        features: FeatureVector,
    ) -> float:
        """Compute structural stop-loss distance.

        Short: stop above last lower high.
        Long: stop below last higher low.
        Clamped at max_stop_pct.
        """
        levels = detect_swing_levels(highs=highs, lows=lows, window=self.swing_window)
        current_close = closes[-1]
        if current_close <= 0:
            return self.max_stop_pct

        if bias == "short":
            # Stop above last lower high (resistance)
            swing_highs = sorted(
                [lv for lv in levels if lv.level_type == "resistance"],
                key=lambda lv: lv.bar_index,
            )
            if swing_highs:
                stop_price = swing_highs[-1].price
                stop_dist = (stop_price - current_close) / current_close
                if stop_dist > 0:
                    return _clamp(stop_dist, 0.001, self.max_stop_pct)
        else:
            # Stop below last higher low (support)
            swing_lows = sorted(
                [lv for lv in levels if lv.level_type == "support"],
                key=lambda lv: lv.bar_index,
            )
            if swing_lows:
                stop_price = swing_lows[-1].price
                stop_dist = (current_close - stop_price) / current_close
                if stop_dist > 0:
                    return _clamp(stop_dist, 0.001, self.max_stop_pct)

        # Fallback: ATR-based stop
        approx_price = max(features.atr_14 / max(features.atr_14_pct, 1e-6), 1.0)
        return _clamp((features.atr_14 * self.atr_trail_mult) / approx_price, 0.001, self.max_stop_pct)

    def _count_bullish_structure(
        self,
        swing_highs: list,
        swing_lows: list,
    ) -> int:
        """Count consecutive HH/HL pairs from the most recent swings."""
        count = 0
        # Walk backwards through swing highs
        for i in range(len(swing_highs) - 1, 0, -1):
            if swing_highs[i].price > swing_highs[i - 1].price:
                count += 1
            else:
                break
        # Walk backwards through swing lows
        for i in range(len(swing_lows) - 1, 0, -1):
            if swing_lows[i].price > swing_lows[i - 1].price:
                count += 1
            else:
                break
        return count

    def _count_bearish_structure(
        self,
        swing_highs: list,
        swing_lows: list,
    ) -> int:
        """Count consecutive LL/LH pairs from the most recent swings."""
        count = 0
        for i in range(len(swing_lows) - 1, 0, -1):
            if swing_lows[i].price < swing_lows[i - 1].price:
                count += 1
            else:
                break
        for i in range(len(swing_highs) - 1, 0, -1):
            if swing_highs[i].price < swing_highs[i - 1].price:
                count += 1
            else:
                break
        return count

    @staticmethod
    def _suggest_leverage_cap(trend_score: float) -> float:
        """Suggest leverage cap based on SONAR trend score."""
        if trend_score >= 70:
            return 15.0
        elif trend_score >= 50:
            return 10.0
        elif trend_score >= 30:
            return 5.0
        return 3.0

    def _apply_leverage_hint(self, signal: EngineSignal, trend_score: float) -> EngineSignal:
        """Return signal unchanged — leverage hint is advisory only.

        The leverage cap is consumed by the pipeline/sizer, not embedded in the signal.
        We return the signal as-is since EngineSignal has no leverage field.
        """
        # Leverage hint is used externally via _suggest_leverage_cap()
        return signal


def _stop_distance(features: FeatureVector, *, atr_mult: float) -> float:
    """ATR-based stop distance (legacy helper, kept for compatibility)."""
    approx_price = max(features.atr_14 / max(features.atr_14_pct, 1e-6), 1.0)
    return _clamp((features.atr_14 * atr_mult) / approx_price, 0.001, 0.10)
