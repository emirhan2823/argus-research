"""POSEIDON engine: Mean Reversion Consortium.

Multi-indicator mean-reversion engine that aggregates weighted signals from
multiple oscillators and deviation metrics. Each indicator independently votes
long/short, votes are weighted, and the aggregate score determines signal
grade (STRONG / NORMAL / WEAK) and confidence.

Indicator set (FeatureVector-based, no candle history needed):
  1. Bollinger %B           (weight 2.0)
  2. RSI(14)                (weight 1.5)
  3. CCI(20)                (weight 1.5)
  4. Williams %R(14)        (weight 1.0)
  5. VWAP Deviation         (weight 2.0)
  6. CMF(20)                (weight 1.0)

Candle-history indicators (computed internally):
  7. Wave Trend Oscillator   (weight 2.0)
  8. HARSI (Heikin Ashi RSI)  (weight 2.5)
  9. Entropy Adaptive SuperTrend (weight 2.0)

Total max weight: 11.0 (FeatureVector) + 6.5 (candle-history) = 17.5

Signal grades:
  STRONG (>=70%): conf base 0.80 — high conviction mean-reversion
  NORMAL (>=45%): conf base 0.65 — standard mean-reversion
  WEAK   (>=30%): conf base 0.52 — low conviction, reduced leverage
  <30%:           no signal

Stop-loss: ATR x 2.0 (wide for liquidation wick protection, DRM adjusts leverage)
Time-decay: max_hold_bars = 12 (3 hours on 15m TF) — close if no reversion
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional

from src.core.constants import (
    ENGINE_POSEIDON,
    REGIME_CRISIS,
    REGIME_RANGING,
    REGIME_TRENDING,
    REGIME_VOLATILE,
)
from src.core.types import EngineSignal, FeatureVector, RegimeState
from src.engines.poseidon.aggregator import MasterSignal, compute_master_signal
from src.engines.poseidon.consortium import (
    ConsortiumResult,
    IndicatorVote,
    compute_consortium_score,
)
from src.engines.poseidon.profiles import (
    ALL_CONSORTIUMS,
    IndicatorProfile,
    build_default_profiles,
)


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, float(value)))


def _ema(series: list[float], period: int) -> list[float]:
    """Exponential moving average over a list."""
    if not series or period < 1:
        return []
    alpha = 2.0 / (period + 1)
    result = [series[0]]
    for i in range(1, len(series)):
        result.append(alpha * series[i] + (1 - alpha) * result[-1])
    return result


def _sma(series: list[float], period: int) -> float:
    """Simple moving average of the last `period` values."""
    if len(series) < period:
        return series[-1] if series else 0.0
    return sum(series[-period:]) / period


def _rsi_series(closes: list[float], period: int) -> list[float]:
    """Compute zero-median RSI series (RSI - 50) using Wilder smoothing."""
    if len(closes) < period + 1:
        return []

    deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
    gains = [max(0, d) for d in deltas]
    losses = [max(0, -d) for d in deltas]

    # Wilder smoothing for first `period` values
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    result: list[float] = []
    for i in range(period, len(deltas)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        if avg_loss == 0:
            rsi = 50.0  # Avoid div by zero, neutral
        else:
            rs = avg_gain / avg_loss
            rsi = 100.0 - (100.0 / (1.0 + rs))
        result.append(rsi - 50.0)  # Zero-median

    return result


def _atr_series(
    highs: list[float], lows: list[float], closes: list[float], period: int
) -> list[float]:
    """Compute ATR series using Wilder smoothing."""
    n = min(len(highs), len(lows), len(closes))
    if n < period + 1:
        return []

    tr_list: list[float] = []
    for i in range(1, n):
        tr = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1]),
        )
        tr_list.append(tr)

    if len(tr_list) < period:
        return []

    atr = sum(tr_list[:period]) / period
    result = [atr]
    for i in range(period, len(tr_list)):
        atr = (atr * (period - 1) + tr_list[i]) / period
        result.append(atr)

    return result


# ── Indicator vote types ──────────────────────────────────────────

_LONG = "long"
_SHORT = "short"


@dataclass
class _IndicatorVote:
    """A single indicator's vote with weight."""
    name: str
    bias: Optional[str]  # "long", "short", or None
    weight: float
    strength: float  # 0.0-1.0, how extreme the reading is


# ── POSEIDON Engine ───────────────────────────────────────────────


@dataclass
class PoseidonEngine:
    """Mean Reversion Consortium engine."""

    # Gate thresholds
    min_confidence: float = 0.50
    max_hold_bars: int = 12  # Time-decay exit (15m TF: 12 bars = 3 hours)

    # ATR stop multiplier (wide for spike protection)
    atr_stop_mult: float = 2.0

    # Bollinger %B thresholds
    bb_long_threshold: float = 0.15
    bb_short_threshold: float = 0.85

    # RSI thresholds
    rsi_oversold: float = 30.0
    rsi_overbought: float = 70.0

    # CCI thresholds
    cci_oversold: float = -150.0
    cci_overbought: float = 150.0

    # Williams %R thresholds
    willr_oversold: float = -85.0
    willr_overbought: float = -15.0

    # VWAP deviation thresholds (%)
    vwap_long_threshold: float = -0.02
    vwap_short_threshold: float = 0.02

    # CMF thresholds
    cmf_long_threshold: float = -0.15
    cmf_short_threshold: float = 0.15

    # Wave Trend parameters
    wt_n1: int = 10
    wt_n2: int = 21
    wt_ob: float = 53.0
    wt_os: float = -53.0

    # HARSI parameters (Heikin Ashi RSI Oscillator)
    harsi_length: int = 14
    harsi_smoothing: int = 1
    harsi_ob: float = 20.0       # Overbought zone
    harsi_ob_extreme: float = 30.0  # Extreme overbought
    harsi_os: float = -20.0      # Oversold zone
    harsi_os_extreme: float = -30.0  # Extreme oversold

    # Entropy-Based Adaptive SuperTrend parameters
    entropy_period: int = 20
    entropy_smooth: int = 10
    entropy_bins: int = 10
    entropy_atr_period: int = 10
    entropy_atr_base: float = 2.0
    entropy_atr_max: float = 5.0
    entropy_filter_weight: float = 0.5

    # Grade thresholds
    strong_threshold: float = 0.70
    normal_threshold: float = 0.45
    weak_threshold: float = 0.30

    # Consortium alpha coefficient (internal-external correlation)
    consortium_alpha: float = 0.3

    # Internal state: candle history for Wave Trend
    _candle_history: dict[str, tuple[list[float], list[float], list[float]]] = field(
        default_factory=dict, repr=False
    )

    # Indicator profiles (lazy-initialized)
    _profiles: dict[str, IndicatorProfile] = field(default_factory=dict, repr=False)

    def feed_candles(
        self,
        *,
        symbol: str,
        highs: list[float],
        lows: list[float],
        closes: list[float],
    ) -> None:
        """Feed OHLC candle history for Wave Trend calculation."""
        max_len = 200  # Enough for WT EMA convergence
        self._candle_history[symbol] = (
            highs[-max_len:],
            lows[-max_len:],
            closes[-max_len:],
        )

    def _ensure_profiles(self) -> dict[str, IndicatorProfile]:
        """Lazy-init indicator profiles."""
        if not self._profiles:
            self._profiles = build_default_profiles()
        return self._profiles

    def _detect_macro_direction(self, features: FeatureVector) -> str:
        """Detect macro market direction from price structure.

        Returns "bear", "bull", or "neutral".
        Uses price_vs_ma200 and ema_21_vs_55 as primary signals.
        """
        price_vs_ma200 = getattr(features, "price_vs_ma200", 0.0) or 0.0
        ema_cross = getattr(features, "ema_21_vs_55", 0.0) or 0.0
        adx = getattr(features, "adx_14", 0.0) or 0.0

        bear_score = 0
        bull_score = 0

        # Price below MA200 = bearish structure
        if price_vs_ma200 < -0.03:
            bear_score += 2
        elif price_vs_ma200 < 0.0:
            bear_score += 1
        elif price_vs_ma200 > 0.03:
            bull_score += 2
        elif price_vs_ma200 > 0.0:
            bull_score += 1

        # EMA21 below EMA55 = bearish momentum
        if ema_cross < -0.01:
            bear_score += 2
        elif ema_cross < 0.0:
            bear_score += 1
        elif ema_cross > 0.01:
            bull_score += 2
        elif ema_cross > 0.0:
            bull_score += 1

        # Strong ADX amplifies the directional signal
        if adx > 30:
            if bear_score > bull_score:
                bear_score += 1
            elif bull_score > bear_score:
                bull_score += 1

        if bear_score >= 3:
            return "bear"
        if bull_score >= 3:
            return "bull"
        return "neutral"

    def generate_signal(
        self,
        *,
        regime: RegimeState,
        features: FeatureVector,
    ) -> Optional[EngineSignal]:
        """Generate mean-reversion signal from indicator consortium."""
        if regime.regime == REGIME_CRISIS:
            return None

        # Collect raw votes from all indicators
        raw_votes = self._collect_votes(features)

        # Build feature dict for condition evaluation
        profiles = self._ensure_profiles()
        feat_dict = self._features_to_dict(features)

        # Map raw votes to consortium IndicatorVotes
        consortium_votes: dict[str, list[IndicatorVote]] = {c: [] for c in ALL_CONSORTIUMS}
        for rv in raw_votes:
            profile = profiles.get(rv.name)
            if profile is None:
                continue
            consortium_votes[profile.consortium].append(
                IndicatorVote(profile=profile, bias=rv.bias, strength=rv.strength)
            )

        # Compute each consortium's internal score
        consortium_results: dict[str, ConsortiumResult] = {}
        for c_name in ALL_CONSORTIUMS:
            votes = consortium_votes.get(c_name, [])
            if votes:
                consortium_results[c_name] = compute_consortium_score(
                    c_name, votes, feat_dict, regime.regime,
                )

        # Master aggregation with agreement/disagreement
        master = compute_master_signal(
            consortium_results, regime.regime, alpha=self.consortium_alpha,
        )

        bias = master.bias
        if bias is None:
            return None

        # Grade based on master confidence
        score = master.confidence
        if score >= self.strong_threshold:
            grade = "STRONG"
            conf_base = 0.80
        elif score >= self.normal_threshold:
            grade = "NORMAL"
            conf_base = 0.65
        elif score >= self.weak_threshold:
            grade = "WEAK"
            conf_base = 0.52
        else:
            return None  # Below minimum threshold

        # Build confidence from master signal
        conf = conf_base

        # Agreement bonus from consortium system
        conf += master.agreement_bonus * 0.10

        # Volume confirmation bonus
        if features.volume_ratio >= 1.3:
            conf += 0.03

        # Regime alignment bonus
        if regime.regime == REGIME_RANGING:
            conf += 0.05  # MR is ideal in ranging
        elif regime.regime == REGIME_VOLATILE:
            conf += 0.02  # Can work but riskier

        # Disagreement penalty
        conf *= (1.0 - master.disagreement_penalty * 0.5)

        # Scale by regime confidence (moderate: never reduce below 85%)
        conf *= _clamp(regime.confidence, 0.85, 1.10)
        conf = _clamp(conf, 0.0, 1.0)

        if conf < self.min_confidence:
            return None

        # Stop-loss: ATR x 2.0 (wide for spike protection)
        approx_price = features.atr_14 / features.atr_14_pct if features.atr_14_pct > 0 else 1.0
        stop = _clamp(
            (features.atr_14 * self.atr_stop_mult) / approx_price,
            0.002,
            0.08,
        )

        # Expected return: mean distance target
        # For MR, the target is the mean — estimate from indicator extremity
        expected_return = _clamp(stop * 2.0, stop * 1.5, 0.10)

        sub_strategy = f"mr_consortium_{grade.lower()}"

        return EngineSignal(
            engine=ENGINE_POSEIDON,
            sub_strategy=sub_strategy,
            asset_class=features.asset_class,
            symbol=features.symbol,
            bias=bias,
            confidence=round(conf, 4),
            stop_distance=round(stop, 6),
            expected_return=round(expected_return, 6),
            atr=features.atr_14,
        )

    def _features_to_dict(self, features: FeatureVector) -> dict[str, float]:
        """Convert FeatureVector to dict for condition evaluation."""
        d: dict[str, float] = {}
        for attr in (
            "adx_14", "rsi_14", "cci_20", "willr_14", "cmf_20",
            "bb_pct_b", "bb_width", "volume_ratio", "vwap_dev_pct",
            "atr_14", "atr_14_pct", "hurst_exponent", "roc_10",
        ):
            val = getattr(features, attr, None)
            if val is not None:
                d[attr] = float(val)
        # Candle count from internal history
        history = self._candle_history.get(features.symbol)
        d["candle_count"] = float(len(history[2])) if history else 0.0
        # LR R² (not always available)
        lr_r2 = getattr(features, "lr_r_squared", None)
        if lr_r2 is not None:
            d["lr_r_squared"] = float(lr_r2)
        return d

    def _collect_votes(self, features: FeatureVector) -> list[_IndicatorVote]:
        """Collect votes from all indicators."""
        votes: list[_IndicatorVote] = []

        # 1. Bollinger %B (weight 2.0)
        votes.append(self._vote_bb(features))

        # 2. RSI(14) (weight 1.5)
        votes.append(self._vote_rsi(features))

        # 3. CCI(20) (weight 1.5)
        votes.append(self._vote_cci(features))

        # 4. Williams %R(14) (weight 1.0)
        votes.append(self._vote_willr(features))

        # 5. VWAP Deviation (weight 2.0)
        votes.append(self._vote_vwap(features))

        # 6. CMF(20) (weight 1.0)
        votes.append(self._vote_cmf(features))

        # 7. Wave Trend (weight 2.0) — needs candle history
        wt_vote = self._vote_wave_trend(features)
        if wt_vote is not None:
            votes.append(wt_vote)

        # 8. HARSI (weight 2.5) — needs candle history
        harsi_vote = self._vote_harsi(features)
        if harsi_vote is not None:
            votes.append(harsi_vote)

        # 9. Entropy Adaptive SuperTrend (weight 2.0) — needs candle history
        est_vote = self._vote_entropy_supertrend(features)
        if est_vote is not None:
            votes.append(est_vote)

        return votes

    # ── Individual indicator voters ───────────────────────────────

    def _vote_bb(self, f: FeatureVector) -> _IndicatorVote:
        """Bollinger %B: <0.15 = long, >0.85 = short."""
        bb = f.bb_pct_b
        if bb <= self.bb_long_threshold:
            strength = _clamp((self.bb_long_threshold - bb) / self.bb_long_threshold, 0, 1)
            return _IndicatorVote("bb_pct_b", _LONG, 2.0, strength)
        elif bb >= self.bb_short_threshold:
            strength = _clamp((bb - self.bb_short_threshold) / (1 - self.bb_short_threshold), 0, 1)
            return _IndicatorVote("bb_pct_b", _SHORT, 2.0, strength)
        return _IndicatorVote("bb_pct_b", None, 2.0, 0.0)

    def _vote_rsi(self, f: FeatureVector) -> _IndicatorVote:
        """RSI(14): <30 = long, >70 = short."""
        rsi = f.rsi_14
        if rsi <= self.rsi_oversold:
            strength = _clamp((self.rsi_oversold - rsi) / self.rsi_oversold, 0, 1)
            return _IndicatorVote("rsi_14", _LONG, 1.5, strength)
        elif rsi >= self.rsi_overbought:
            strength = _clamp((rsi - self.rsi_overbought) / (100 - self.rsi_overbought), 0, 1)
            return _IndicatorVote("rsi_14", _SHORT, 1.5, strength)
        return _IndicatorVote("rsi_14", None, 1.5, 0.0)

    def _vote_cci(self, f: FeatureVector) -> _IndicatorVote:
        """CCI(20): <-150 = long, >150 = short."""
        cci = f.cci_20
        if cci <= self.cci_oversold:
            strength = _clamp((self.cci_oversold - cci) / abs(self.cci_oversold), 0, 1)
            return _IndicatorVote("cci_20", _LONG, 1.5, strength)
        elif cci >= self.cci_overbought:
            strength = _clamp((cci - self.cci_overbought) / self.cci_overbought, 0, 1)
            return _IndicatorVote("cci_20", _SHORT, 1.5, strength)
        return _IndicatorVote("cci_20", None, 1.5, 0.0)

    def _vote_willr(self, f: FeatureVector) -> _IndicatorVote:
        """Williams %R(14): <-85 = long, >-15 = short."""
        willr = f.willr_14
        if willr <= self.willr_oversold:
            strength = _clamp((self.willr_oversold - willr) / abs(self.willr_oversold), 0, 1)
            return _IndicatorVote("willr_14", _LONG, 1.0, strength)
        elif willr >= self.willr_overbought:
            strength = _clamp((willr - self.willr_overbought) / abs(self.willr_overbought), 0, 1)
            return _IndicatorVote("willr_14", _SHORT, 1.0, strength)
        return _IndicatorVote("willr_14", None, 1.0, 0.0)

    def _vote_vwap(self, f: FeatureVector) -> _IndicatorVote:
        """VWAP Deviation: <-2% = long, >2% = short."""
        vwap = f.vwap_dev_pct
        if vwap <= self.vwap_long_threshold:
            strength = _clamp(abs(vwap) / 0.05, 0, 1)  # 5% dev = max strength
            return _IndicatorVote("vwap_dev", _LONG, 2.0, strength)
        elif vwap >= self.vwap_short_threshold:
            strength = _clamp(vwap / 0.05, 0, 1)
            return _IndicatorVote("vwap_dev", _SHORT, 2.0, strength)
        return _IndicatorVote("vwap_dev", None, 2.0, 0.0)

    def _vote_cmf(self, f: FeatureVector) -> _IndicatorVote:
        """CMF(20): <-0.15 = long (bearish exhaustion), >0.15 = short (bullish exhaustion)."""
        cmf = f.cmf_20
        if cmf <= self.cmf_long_threshold:
            # Negative CMF = selling pressure — potential long reversal
            strength = _clamp(abs(cmf) / 0.30, 0, 1)
            return _IndicatorVote("cmf_20", _LONG, 1.0, strength)
        elif cmf >= self.cmf_short_threshold:
            # Positive CMF = buying pressure — potential short reversal
            strength = _clamp(cmf / 0.30, 0, 1)
            return _IndicatorVote("cmf_20", _SHORT, 1.0, strength)
        return _IndicatorVote("cmf_20", None, 1.0, 0.0)

    def _vote_wave_trend(self, f: FeatureVector) -> Optional[_IndicatorVote]:
        """Wave Trend Oscillator from candle history."""
        history = self._candle_history.get(f.symbol)
        if history is None:
            return None

        highs, lows, closes = history
        if len(closes) < 50:
            return None

        # Compute HLC3
        min_len = min(len(highs), len(lows), len(closes))
        hlc3 = [
            (highs[i] + lows[i] + closes[i]) / 3.0
            for i in range(min_len)
        ]

        # ESA = EMA(hlc3, n1)
        esa = _ema(hlc3, self.wt_n1)
        if len(esa) < 2:
            return None

        # D = EMA(abs(hlc3 - esa), n1)
        d_series = [abs(hlc3[i] - esa[i]) for i in range(len(hlc3))]
        d = _ema(d_series, self.wt_n1)
        if len(d) < 2 or d[-1] == 0:
            return None

        # CI = (hlc3 - esa) / (0.015 * d)
        ci = [
            (hlc3[i] - esa[i]) / (0.015 * d[i]) if d[i] != 0 else 0.0
            for i in range(len(hlc3))
        ]

        # WT1 = EMA(CI, n2)
        wt1_series = _ema(ci, self.wt_n2)
        if len(wt1_series) < 5:
            return None

        # WT2 = SMA(WT1, 4)
        wt1 = wt1_series[-1]
        wt1_prev = wt1_series[-2]
        wt2 = _sma(wt1_series, 4)
        wt2_prev = _sma(wt1_series[:-1], 4)

        # Oversold cross up → long
        if wt1 <= self.wt_os and wt1 > wt2 and wt1_prev <= wt2_prev:
            strength = _clamp(abs(wt1) / 80.0, 0, 1)
            return _IndicatorVote("wave_trend", _LONG, 2.0, strength)
        # Just oversold (no cross yet) — weaker signal
        elif wt1 <= self.wt_os:
            strength = _clamp(abs(wt1) / 80.0, 0, 1) * 0.6
            return _IndicatorVote("wave_trend", _LONG, 2.0, strength)

        # Overbought cross down → short
        if wt1 >= self.wt_ob and wt1 < wt2 and wt1_prev >= wt2_prev:
            strength = _clamp(wt1 / 80.0, 0, 1)
            return _IndicatorVote("wave_trend", _SHORT, 2.0, strength)
        # Just overbought (no cross yet)
        elif wt1 >= self.wt_ob:
            strength = _clamp(wt1 / 80.0, 0, 1) * 0.6
            return _IndicatorVote("wave_trend", _SHORT, 2.0, strength)

        return _IndicatorVote("wave_trend", None, 2.0, 0.0)

    def _vote_harsi(self, f: FeatureVector) -> Optional[_IndicatorVote]:
        """HARSI (Heikin Ashi RSI Oscillator) from candle history.

        Translates JayRogers' Pine Script:
        1. Compute zero-median RSI (RSI - 50) for close, high, low
        2. Build Heikin Ashi OHLC from RSI values
        3. HA Close = (open_rsi + high_rsi + low_rsi + close_rsi) / 4
        4. HA Open = smoothed prior close
        5. Signal: HA close in OB/OS zones
        """
        history = self._candle_history.get(f.symbol)
        if history is None:
            return None

        highs, lows, closes = history
        n = len(closes)
        if n < self.harsi_length + 10:
            return None

        # Compute RSI for close, high, low series (zero-median: RSI - 50)
        close_rsi = _rsi_series(closes, self.harsi_length)
        high_rsi_raw = _rsi_series(highs, self.harsi_length)
        low_rsi_raw = _rsi_series(lows, self.harsi_length)

        if not close_rsi or not high_rsi_raw or not low_rsi_raw:
            return None

        min_len = min(len(close_rsi), len(high_rsi_raw), len(low_rsi_raw))
        if min_len < 3:
            return None

        # Ensure high is max, low is min (Pine: max/min of high_rsi, low_rsi)
        high_rsi = [max(high_rsi_raw[i], low_rsi_raw[i]) for i in range(min_len)]
        low_rsi = [min(high_rsi_raw[i], low_rsi_raw[i]) for i in range(min_len)]

        # Build HA candles
        ha_open = [0.0] * min_len
        ha_close = [0.0] * min_len

        # First bar: HA open = (open_rsi + close_rsi) / 2
        open_rsi_0 = close_rsi[0]  # approximate open as prior close
        ha_open[0] = (open_rsi_0 + close_rsi[0]) / 2.0
        ha_close[0] = (ha_open[0] + high_rsi[0] + low_rsi[0] + close_rsi[0]) / 4.0

        smoothing = max(1, self.harsi_smoothing)
        for i in range(1, min_len):
            # HA Open with smoothing: (open[prev] * smoothing + close[prev]) / (smoothing + 1)
            ha_open[i] = (ha_open[i - 1] * smoothing + ha_close[i - 1]) / (smoothing + 1)
            ha_close[i] = (ha_open[i] + high_rsi[i] + low_rsi[i] + close_rsi[i]) / 4.0

        # Current HARSI values
        harsi_c = ha_close[-1]
        harsi_o = ha_open[-1]

        # Candle direction: bullish (close > open) or bearish
        bullish = harsi_c > harsi_o

        # Mean-reversion signals from OB/OS zones
        if harsi_c <= self.harsi_os:
            # Oversold — long signal
            extreme = harsi_c <= self.harsi_os_extreme
            strength = _clamp(abs(harsi_c) / 40.0, 0.3, 1.0)
            if extreme:
                strength = min(1.0, strength * 1.3)
            # Bullish candle in OS = reversal confirmation
            if bullish:
                strength = min(1.0, strength * 1.2)
            return _IndicatorVote("harsi", _LONG, 2.5, strength)

        elif harsi_c >= self.harsi_ob:
            # Overbought — short signal
            extreme = harsi_c >= self.harsi_ob_extreme
            strength = _clamp(harsi_c / 40.0, 0.3, 1.0)
            if extreme:
                strength = min(1.0, strength * 1.3)
            # Bearish candle in OB = reversal confirmation
            if not bullish:
                strength = min(1.0, strength * 1.2)
            return _IndicatorVote("harsi", _SHORT, 2.5, strength)

        return _IndicatorVote("harsi", None, 2.5, 0.0)

    def _vote_entropy_supertrend(self, f: FeatureVector) -> Optional[_IndicatorVote]:
        """Entropy-Based Adaptive SuperTrend from candle history.

        Translates BullVisionCapital's Pine Script:
        1. Calculate Shannon entropy of price distribution
        2. Adaptive ATR multiplier based on entropy
        3. SuperTrend with dynamic bands
        4. Direction change = signal
        """
        history = self._candle_history.get(f.symbol)
        if history is None:
            return None

        highs, lows, closes = history
        n = len(closes)
        if n < max(self.entropy_period, self.entropy_atr_period) + 20:
            return None

        # Step 1: Calculate entropy
        entropy = self._calc_entropy(closes)
        if entropy is None:
            return None

        # Step 2: Adaptive ATR multiplier
        # High entropy (chaotic) → higher multiplier (less sensitive)
        # Low entropy (ordered) → lower multiplier (more sensitive)
        entropy_score = _clamp(1.0 - entropy, 0.0, 1.0)
        dynamic_mult = self.entropy_atr_base + (
            self.entropy_atr_max - self.entropy_atr_base
        ) * (1.0 - entropy_score)

        # Step 3: Compute ATR
        atr_vals = _atr_series(highs, lows, closes, self.entropy_atr_period)
        if not atr_vals or len(atr_vals) < 3:
            return None

        # Step 4: SuperTrend calculation
        # up = hl2 - mult * atr, down = hl2 + mult * atr
        min_len = min(len(highs), len(lows), len(closes), len(atr_vals))
        offset = len(closes) - min_len

        trend = 1  # 1 = bullish, -1 = bearish
        prev_up = 0.0
        prev_down = float("inf")
        curr_trend = 1
        prev_trend = 1

        for i in range(max(0, min_len - 30), min_len):
            idx = offset + i
            hl2 = (highs[idx] + lows[idx]) / 2.0
            atr_val = atr_vals[i] if i < len(atr_vals) else atr_vals[-1]

            up = hl2 - dynamic_mult * atr_val
            down = hl2 + dynamic_mult * atr_val

            # Ratchet: up can only go higher, down can only go lower
            if closes[idx] > prev_up:
                up = max(up, prev_up) if prev_up != 0 else up
            if closes[idx] < prev_down:
                down = min(down, prev_down) if prev_down != float("inf") else down

            prev_trend = curr_trend
            if closes[idx] > prev_down:
                curr_trend = 1
            elif closes[idx] < prev_up:
                curr_trend = -1

            prev_up = up
            prev_down = down

        # Signal: direction change
        direction_changed = curr_trend != prev_trend

        if direction_changed:
            if curr_trend == 1:
                # Bullish reversal
                strength = _clamp(entropy_score * 1.5, 0.4, 1.0)
                return _IndicatorVote("entropy_st", _LONG, 2.0, strength)
            else:
                # Bearish reversal
                strength = _clamp(entropy_score * 1.5, 0.4, 1.0)
                return _IndicatorVote("entropy_st", _SHORT, 2.0, strength)

        # No direction change — use current trend as weak directional bias
        # This acts as trend confirmation rather than reversal signal
        return _IndicatorVote("entropy_st", None, 2.0, 0.0)

    def _calc_entropy(self, closes: list[float]) -> Optional[float]:
        """Calculate normalized Shannon entropy of price distribution."""
        n = min(len(closes), self.entropy_period)
        if n < 10:
            return None

        recent = closes[-n:]
        min_p = min(recent)
        max_p = max(recent)
        price_range = max_p - min_p

        if price_range <= 0:
            return 0.0

        bins = [0] * self.entropy_bins
        for p in recent:
            idx = int((p - min_p) / price_range * (self.entropy_bins - 1))
            idx = max(0, min(self.entropy_bins - 1, idx))
            bins[idx] += 1

        entropy = 0.0
        for count in bins:
            if count > 0:
                prob = count / n
                entropy -= prob * math.log(prob)

        # Normalize to [0, 1]
        max_entropy = math.log(self.entropy_bins)
        return entropy / max_entropy if max_entropy > 0 else 0.0
