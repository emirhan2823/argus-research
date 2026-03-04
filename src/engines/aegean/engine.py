"""AEGEAN engine: Exponential RSI + Momentum Linear Regression Channel (MOM-LRC).

Faithfully translates the Aegean Pine Script indicator into a regime-switching
engine. Active across TRENDING, RANGING, and VOLATILE as a secondary engine.

Pine Script logic (translated):
  1. expRsi = exponentially smoothed RSI on HLC3
  2. Channel center = EMA(expRsi, ema_period)[previous bar]
  3. Channel width = linear regression of mean-absolute-% deviation * multiplier
  4. Buy signal: expRsi crosses below lower channel (or < lower * 0.95)
  5. Sell signal: expRsi crosses above upper channel (or > upper * 1.05)

Regime-switching parameters:
  - TRENDING: tight multiplier (1), short RSI (5), momentum continuation added
  - RANGING:  moderate multiplier (2), RSI 5, pure mean-reversion
  - VOLATILE: wide multiplier (3), longer RSI (8), only extreme signals

Multi-Timeframe (MTF) trend filter:
  - 15m signals are confirmed against 1H/4H trend (EMA-200 on HTF closes)
  - Long rejected if HTF price < HTF EMA-200 (bearish macro trend)
  - Short rejected if HTF price > HTF EMA-200 (bullish macro trend)
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional

from src.core.constants import (
    ENGINE_AEGEAN,
    REGIME_CRISIS,
    REGIME_RANGING,
    REGIME_TRENDING,
    REGIME_VOLATILE,
)
from src.core.types import EngineSignal, FeatureVector, RegimeState


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, float(value)))


# ── Regime-specific parameters ──────────────────────────────────────

_CHANNEL_MULT: dict[str, float] = {
    REGIME_TRENDING: 1,
    REGIME_RANGING: 2,
    REGIME_VOLATILE: 3,
}

_RSI_LENGTH: dict[str, int] = {
    REGIME_TRENDING: 5,
    REGIME_RANGING: 5,
    REGIME_VOLATILE: 8,
}

_EMA_PERIOD: dict[str, int] = {
    REGIME_TRENDING: 100,
    REGIME_RANGING: 200,
    REGIME_VOLATILE: 150,
}

_SMOOTH_FACTOR: dict[str, float] = {
    REGIME_TRENDING: 0.15,
    REGIME_RANGING: 0.10,
    REGIME_VOLATILE: 0.08,
}

_LR_BARS: dict[str, int] = {
    REGIME_TRENDING: 5,
    REGIME_RANGING: 5,
    REGIME_VOLATILE: 8,
}

_ATR_STOP_MULT: dict[str, float] = {
    REGIME_TRENDING: 2.2,
    REGIME_RANGING: 1.3,
    REGIME_VOLATILE: 1.8,
}

_RR_RATIO: dict[str, float] = {
    REGIME_TRENDING: 2.5,
    REGIME_RANGING: 1.8,
    REGIME_VOLATILE: 1.6,
}


# ── Helper math ─────────────────────────────────────────────────────


def _rsi(closes: list[float], length: int) -> float | None:
    """Wilder RSI on a price series."""
    if len(closes) < length + 1:
        return None
    recent = closes[-(length + 1):]
    gains = []
    losses = []
    for i in range(1, len(recent)):
        diff = recent[i] - recent[i - 1]
        gains.append(max(diff, 0.0))
        losses.append(max(-diff, 0.0))
    avg_gain = sum(gains) / length
    avg_loss = sum(losses) / length
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - 100.0 / (1.0 + rs)


def _hlc3(highs: list[float], lows: list[float], closes: list[float]) -> list[float]:
    """HLC3 (typical price) series."""
    return [(h + l + c) / 3.0 for h, l, c in zip(highs, lows, closes)]


def _ema_series(values: list[float], period: int) -> list[float]:
    """Full EMA series."""
    if not values or period < 1:
        return []
    alpha = 2.0 / (period + 1)
    result = [values[0]]
    for v in values[1:]:
        result.append(alpha * v + (1.0 - alpha) * result[-1])
    return result


def _linreg_last(values: list[float], length: int) -> float | None:
    """Linear regression value at last bar (offset=0)."""
    if len(values) < length:
        return None
    y = values[-length:]
    n = len(y)
    x_mean = (n - 1) / 2.0
    y_mean = sum(y) / n
    num = sum((i - x_mean) * (y[i] - y_mean) for i in range(n))
    den = sum((i - x_mean) ** 2 for i in range(n))
    if den == 0:
        return y_mean
    slope = num / den
    intercept = y_mean - slope * x_mean
    return intercept + slope * (n - 1)


# ── Engine ──────────────────────────────────────────────────────────


@dataclass
class AegeanEngine:
    """Exponential RSI + MOM-LRC with regime-switching parameters.

    Call ``feed_candles()`` each cycle before ``generate_signal()``.
    """

    min_confidence: float = 0.52
    htf_ema_period: int = 200

    # Per-symbol candle buffers: symbol -> (highs, lows, closes)
    _candle_history: dict[str, tuple[list[float], list[float], list[float]]] = field(
        default_factory=dict, repr=False
    )

    # Previous expRsi per symbol for crossover detection
    _prev_exp_rsi: dict[str, float] = field(default_factory=dict, repr=False)

    # HTF (1H/4H) close buffers per symbol for MTF trend filter
    _htf_closes: dict[str, list[float]] = field(default_factory=dict, repr=False)

    def feed_candles(
        self,
        *,
        symbol: str,
        highs: list[float],
        lows: list[float],
        closes: list[float],
    ) -> None:
        """Update candle history for a symbol (called from main pipeline)."""
        max_len = 500
        self._candle_history[symbol] = (
            highs[-max_len:],
            lows[-max_len:],
            closes[-max_len:],
        )

    def feed_htf_candles(
        self,
        *,
        symbol: str,
        closes: list[float],
    ) -> None:
        """Update higher-timeframe (1H/4H) close data for MTF trend filter.

        Called from main pipeline with 4H closes (or 1H if 4H unavailable).
        Needs at least ``htf_ema_period`` bars for EMA-200 computation.
        """
        max_len = self.htf_ema_period + 50
        self._htf_closes[symbol] = closes[-max_len:]

    def generate_signal(
        self,
        *,
        regime: RegimeState,
        features: FeatureVector,
    ) -> Optional[EngineSignal]:
        if regime.regime == REGIME_CRISIS:
            return None

        history = self._candle_history.get(features.symbol)
        if history is None:
            return self._fallback_signal(regime, features)

        highs, lows, closes = history
        if len(closes) < 50:
            return self._fallback_signal(regime, features)

        # ── Regime-specific parameters ──
        rsi_length = _RSI_LENGTH.get(regime.regime, 5)
        smooth_factor = _SMOOTH_FACTOR.get(regime.regime, 0.10)
        ema_period = _EMA_PERIOD.get(regime.regime, 200)
        channel_mult = _CHANNEL_MULT.get(regime.regime, 2)
        lr_bars = _LR_BARS.get(regime.regime, 5)

        # ── Step 1: RSI on HLC3 ──
        hlc3_series = _hlc3(highs, lows, closes)
        rsi_val = _rsi(hlc3_series, rsi_length)
        if rsi_val is None:
            return None

        # ── Step 2: Exponential smoothing ──
        prev_exp = self._prev_exp_rsi.get(features.symbol, rsi_val)
        exp_rsi = smooth_factor * rsi_val + (1.0 - smooth_factor) * prev_exp
        self._prev_exp_rsi[features.symbol] = exp_rsi

        # ── Step 3: Build expRsi series for EMA + deviation ──
        exp_rsi_series = self._build_exp_rsi_series(
            hlc3_series, rsi_length, smooth_factor,
            min(ema_period + lr_bars + 10, len(hlc3_series)),
        )
        if len(exp_rsi_series) < ema_period:
            return self._fallback_signal(regime, features, exp_rsi)

        # ── Step 4: EMA of expRsi (previous bar value) ──
        ema_vals = _ema_series(exp_rsi_series, ema_period)
        ema_prev = ema_vals[-2] if len(ema_vals) >= 2 else ema_vals[-1]

        # ── Step 5: Mean absolute % deviation from SMA ──
        change_from_mean = self._percent_change_from_mean(exp_rsi_series, ema_period)
        if len(change_from_mean) < lr_bars:
            return self._fallback_signal(regime, features, exp_rsi)

        # ── Step 6: Linear regression of deviation ──
        lr_value = _linreg_last(change_from_mean, lr_bars)
        if lr_value is None or not math.isfinite(lr_value):
            return self._fallback_signal(regime, features, exp_rsi)

        # ── Step 7: Channel bands (Pine Script formula) ──
        upper_band = ema_prev * (1.0 + lr_value * channel_mult / 100.0)
        lower_band = ema_prev * (1.0 - lr_value * channel_mult / 100.0)

        # ── Step 8: Signal detection ──
        bias: str | None = None
        edge: float = 0.0
        band_width = max(abs(upper_band - lower_band), 1.0)

        # Sell: expRsi > upper * 1.05 OR crosses above upper
        if exp_rsi > upper_band * 1.05:
            bias = "short"
            edge = (exp_rsi - upper_band) / band_width
        elif exp_rsi > upper_band and prev_exp <= upper_band:
            bias = "short"
            edge = (exp_rsi - upper_band) / band_width

        # Buy: expRsi < lower * 0.95 OR crosses below lower
        if exp_rsi < lower_band * 0.95:
            bias = "long"
            edge = (lower_band - exp_rsi) / band_width
        elif exp_rsi < lower_band and prev_exp >= lower_band:
            bias = "long"
            edge = (lower_band - exp_rsi) / band_width

        # TRENDING: momentum continuation (relaxed — one confirming indicator sufficient)
        if bias is None and regime.regime == REGIME_TRENDING:
            mid = (upper_band + lower_band) / 2.0
            if exp_rsi > mid and (features.roc_10 > 0 or features.lr_slope_20 > 0):
                bias = "long"
                edge = (exp_rsi - mid) / band_width * 0.7
            elif exp_rsi < mid and (features.roc_10 < 0 or features.lr_slope_20 < 0):
                bias = "short"
                edge = (mid - exp_rsi) / band_width * 0.7

        # RANGING: deep mean-reversion — RSI-confirmed extreme
        if bias is None and regime.regime == REGIME_RANGING:
            if exp_rsi < lower_band * 0.98 and features.rsi_14 < 35:
                bias = "long"
                edge = (lower_band - exp_rsi) / band_width * 0.6
            elif exp_rsi > upper_band * 1.02 and features.rsi_14 > 65:
                bias = "short"
                edge = (exp_rsi - upper_band) / band_width * 0.6

        if bias is None or edge <= 0.0:
            return None

        # ── MTF Trend Gate: reject signals against macro trend ──
        if not self._htf_trend_allows(features.symbol, bias):
            return None

        return self._build_signal(regime, features, bias, edge)

    # ── Internal helpers ────────────────────────────────────────────

    def _htf_trend_allows(self, symbol: str, bias: str) -> bool:
        """MTF trend filter: reject signals against the macro (HTF) trend.

        Uses EMA-200 on higher-timeframe closes (1H or 4H):
          - Long rejected if HTF price < HTF EMA-200 (bearish macro)
          - Short rejected if HTF price > HTF EMA-200 (bullish macro)

        If no HTF data is available, the filter is permissive (returns True)
        to avoid blocking signals when HTF data hasn't been fed yet.
        """
        htf_closes = self._htf_closes.get(symbol)
        if not htf_closes or len(htf_closes) < self.htf_ema_period:
            return True  # No HTF data → permissive (don't block)

        htf_ema = _ema_series(htf_closes, self.htf_ema_period)
        if not htf_ema:
            return True

        current_htf_price = htf_closes[-1]
        current_htf_ema = htf_ema[-1]

        if bias == "long" and current_htf_price < current_htf_ema:
            return False  # HTF bearish → reject long
        if bias == "short" and current_htf_price > current_htf_ema:
            return False  # HTF bullish → reject short
        return True

    def _build_signal(
        self,
        regime: RegimeState,
        features: FeatureVector,
        bias: str,
        edge: float,
        *,
        sub_suffix: str = "",
    ) -> EngineSignal | None:
        conf = 0.56 + _clamp(edge * 0.35, 0.0, 0.30)
        if regime.regime == REGIME_TRENDING and features.adx_14 >= 25:
            conf += 0.05
        elif regime.regime == REGIME_RANGING and features.adx_14 <= 20:
            conf += 0.05
        if features.volume_ratio >= 1.3:
            conf += 0.03
        conf *= _clamp(regime.confidence, 0.70, 1.10)
        conf = _clamp(conf, 0.0, 1.0)
        if conf < self.min_confidence:
            return None

        atr_mult = _ATR_STOP_MULT.get(regime.regime, 1.8)
        approx_price = max(features.atr_14 / max(features.atr_14_pct, 1e-6), 1.0)
        stop = _clamp((features.atr_14 * atr_mult) / approx_price, 0.001, 0.10)
        rr = _RR_RATIO.get(regime.regime, 2.0)

        sub = f"mom_lrc_{regime.regime.lower()}"
        if sub_suffix:
            sub += f"_{sub_suffix}"

        return EngineSignal(
            engine=ENGINE_AEGEAN,
            sub_strategy=sub,
            asset_class=features.asset_class,
            symbol=features.symbol,
            bias=bias,
            confidence=conf,
            stop_distance=stop,
            expected_return=stop * rr,
            atr=features.atr_14,
        )

    def _build_exp_rsi_series(
        self,
        hlc3_series: list[float],
        rsi_length: int,
        smooth_factor: float,
        max_bars: int,
    ) -> list[float]:
        """Build exponentially smoothed RSI series from HLC3 data."""
        n = min(max_bars, len(hlc3_series))
        if n < rsi_length + 2:
            return []

        result: list[float] = []
        exp_val = 0.0
        for i in range(rsi_length + 1, n + 1):
            window = hlc3_series[:i]
            rsi_val = _rsi(window, rsi_length)
            if rsi_val is None:
                continue
            if not result:
                exp_val = rsi_val
            else:
                exp_val = smooth_factor * rsi_val + (1.0 - smooth_factor) * exp_val
            result.append(exp_val)
        return result

    def _percent_change_from_mean(
        self,
        exp_rsi_series: list[float],
        ema_period: int,
    ) -> list[float]:
        """Mean absolute % deviation of expRsi from its SMA.

        Pine: percentChangeFromMean(source, length) =>
            sum(abs((val-mean)/mean*100)) / length
        """
        n = len(exp_rsi_series)
        if n < ema_period:
            return []
        result: list[float] = []
        for i in range(ema_period - 1, n):
            window = exp_rsi_series[i - ema_period + 1: i + 1]
            mean = sum(window) / len(window)
            if abs(mean) < 1e-9:
                result.append(0.0)
                continue
            dev = sum(abs((v - mean) / mean * 100.0) for v in window) / len(window)
            result.append(dev)
        return result

    def _fallback_signal(
        self,
        regime: RegimeState,
        features: FeatureVector,
        exp_rsi: float | None = None,
    ) -> EngineSignal | None:
        """Feature-based fallback when insufficient candle history."""
        if exp_rsi is None:
            # Build a proxy from FeatureVector momentum fields
            willr_norm = _clamp((features.willr_14 + 100.0) / 2.0, 0.0, 100.0)
            cci_norm = _clamp(50.0 + features.cci_20 / 2.0, 0.0, 100.0)
            exp_rsi = features.rsi_14 * 0.60 + willr_norm * 0.25 + cci_norm * 0.15

        channel_mult = _CHANNEL_MULT.get(regime.regime, 2)
        half_width = channel_mult * max(features.atr_14_pct, 0.005) * 100.0
        center = 50.0 + _clamp(features.lr_slope_20 * 200.0, -25.0, 25.0)
        upper = _clamp(center + half_width, 50.0, 95.0)
        lower = _clamp(center - half_width, 5.0, 50.0)

        bias: str | None = None
        edge: float = 0.0

        if regime.regime == REGIME_RANGING:
            if exp_rsi <= lower:
                bias = "long"
                edge = (lower - exp_rsi) / max(half_width, 1.0)
            elif exp_rsi >= upper:
                bias = "short"
                edge = (exp_rsi - upper) / max(half_width, 1.0)
        else:
            mid = (upper + lower) / 2.0
            if exp_rsi > mid and features.roc_10 > 0 and features.lr_slope_20 > 0:
                bias = "long"
                edge = (exp_rsi - mid) / max(half_width, 1.0)
            elif exp_rsi < mid and features.roc_10 < 0 and features.lr_slope_20 < 0:
                bias = "short"
                edge = (mid - exp_rsi) / max(half_width, 1.0)

        if bias is None or edge <= 0.0:
            return None

        # MTF trend gate applies to fallback signals too
        if not self._htf_trend_allows(features.symbol, bias):
            return None

        return self._build_signal(regime, features, bias, edge * 0.8, sub_suffix="fallback")
