"""Signal Quality Filter — multi-factor confirmation for ARGUS engines.

This filter sits between the engine signal and the MDE gates.
It enriches the raw signal confidence with additional quality checks:

1. Multi-Timeframe Alignment (MTF): Does the higher TF agree with entry direction?
2. Momentum Divergence: Is price making new highs but RSI/momentum declining?
3. Volume Confirmation: Is volume supporting the move?
4. Regime Stability: How long has the current regime been stable?
5. Trend Strength Quality: Is the trend strong enough to trust?

The filter can BOOST confidence (up to +0.15) or PENALIZE it (up to -0.20).
This ensures only the highest quality signals pass through the gates.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class SignalQualityResult:
    """Result of signal quality assessment."""
    original_confidence: float
    adjusted_confidence: float
    quality_score: float  # 0-1, independent quality metric
    adjustments: dict  # breakdown of each factor
    pass_quality: bool  # True if quality meets minimum threshold


MIN_QUALITY_SCORE = 0.55  # Below this, signal is too risky


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def assess_signal_quality(
    *,
    bias: str,
    confidence: float,
    engine: str,
    # Feature values for quality checks
    rsi_14: float,
    adx_14: float,
    bb_pct_b: float,
    volume_ratio: float,
    volume_delta: float,
    ema_21_vs_55: float,
    price_vs_ma200: float,
    roc_10: float,
    willr_14: float,
    cci_20: float,
    hurst_exponent: float,
    aroon_osc: float,
    supertrend_dir: int,
    # Crypto-specific (optional)
    orderbook_imbalance: Optional[float] = None,
    funding_rate: Optional[float] = None,
    long_short_ratio: Optional[float] = None,
    # Regime info
    regime: str = "RANGING",
    candles_in_regime: int = 0,
    regime_confidence: float = 0.5,
) -> SignalQualityResult:
    """Assess signal quality using multiple confirmation factors."""
    adjustments = {}
    quality_factors = []

    # ── Factor 1: Multi-Indicator Alignment ──────────────────────
    # How many momentum indicators agree with the bias?
    alignment_score = _compute_indicator_alignment(
        bias=bias,
        rsi_14=rsi_14,
        willr_14=willr_14,
        cci_20=cci_20,
        roc_10=roc_10,
        aroon_osc=aroon_osc,
        supertrend_dir=supertrend_dir,
    )
    adjustments["indicator_alignment"] = alignment_score
    quality_factors.append(alignment_score)

    # If less than 50% of indicators agree → penalize confidence
    if alignment_score < 0.50:
        conf_adj = -0.10 * (0.50 - alignment_score) / 0.50
    else:
        conf_adj = +0.05 * (alignment_score - 0.50) / 0.50
    adjustments["alignment_conf_adj"] = round(conf_adj, 4)

    # ── Factor 2: Momentum Divergence Detection ──────────────────
    divergence = _detect_divergence(
        bias=bias,
        rsi_14=rsi_14,
        roc_10=roc_10,
        price_vs_ma200=price_vs_ma200,
    )
    adjustments["divergence"] = divergence
    if divergence:
        # Divergence against the signal → big penalty
        conf_adj -= 0.12
        adjustments["divergence_penalty"] = -0.12
        quality_factors.append(0.2)
    else:
        quality_factors.append(0.8)

    # ── Factor 3: Volume Confirmation ────────────────────────────
    vol_quality = _volume_quality(
        bias=bias,
        volume_ratio=volume_ratio,
        volume_delta=volume_delta,
    )
    adjustments["volume_quality"] = round(vol_quality, 4)
    quality_factors.append(vol_quality)

    if vol_quality < 0.40:
        conf_adj -= 0.05
        adjustments["vol_penalty"] = -0.05
    elif vol_quality > 0.70:
        conf_adj += 0.03
        adjustments["vol_bonus"] = 0.03

    # ── Factor 4: Regime Stability ───────────────────────────────
    regime_quality = _regime_stability_quality(
        candles_in_regime=candles_in_regime,
        regime_confidence=regime_confidence,
    )
    adjustments["regime_stability"] = round(regime_quality, 4)
    quality_factors.append(regime_quality)

    if regime_quality < 0.30:
        conf_adj -= 0.08
        adjustments["regime_instability_penalty"] = -0.08

    # ── Factor 5: Orderbook Support (crypto only) ────────────────
    if orderbook_imbalance is not None:
        obi_quality = _orderbook_quality(
            bias=bias,
            orderbook_imbalance=orderbook_imbalance,
        )
        adjustments["orderbook_quality"] = round(obi_quality, 4)
        quality_factors.append(obi_quality)

        if obi_quality > 0.70:
            conf_adj += 0.04
            adjustments["obi_bonus"] = 0.04
        elif obi_quality < 0.30:
            conf_adj -= 0.06
            adjustments["obi_penalty"] = -0.06

    # ── Factor 6: Trend-Bias Alignment ───────────────────────────
    trend_alignment = _trend_alignment_quality(
        bias=bias,
        ema_21_vs_55=ema_21_vs_55,
        price_vs_ma200=price_vs_ma200,
        adx_14=adx_14,
        engine=engine,
    )
    adjustments["trend_alignment"] = round(trend_alignment, 4)
    quality_factors.append(trend_alignment)

    if trend_alignment > 0.70:
        conf_adj += 0.05
    elif trend_alignment < 0.30:
        conf_adj -= 0.07

    # ── Factor 7: Toxic Pattern Detection (backtest-proven) ──────
    toxic_penalty = _toxic_pattern_penalty(
        bias=bias,
        volume_ratio=volume_ratio,
        adx_14=adx_14,
    )
    if toxic_penalty < 0:
        conf_adj += toxic_penalty
        adjustments["toxic_pattern_penalty"] = round(toxic_penalty, 4)
        quality_factors.append(0.15)
    else:
        quality_factors.append(0.70)

    # ── Compute Final Quality Score ──────────────────────────────
    quality_score = sum(quality_factors) / max(len(quality_factors), 1)
    adjusted_confidence = _clamp(confidence + conf_adj, 0.0, 1.0)

    return SignalQualityResult(
        original_confidence=confidence,
        adjusted_confidence=adjusted_confidence,
        quality_score=round(quality_score, 4),
        adjustments=adjustments,
        pass_quality=quality_score >= MIN_QUALITY_SCORE,
    )


def _compute_indicator_alignment(
    *,
    bias: str,
    rsi_14: float,
    willr_14: float,
    cci_20: float,
    roc_10: float,
    aroon_osc: float,
    supertrend_dir: int,
) -> float:
    """Count how many indicators agree with the signal direction."""
    if bias == "long":
        votes = [
            rsi_14 < 50,          # RSI not overbought (room to go up)
            willr_14 < -50,       # Williams %R agrees
            cci_20 < 100,         # CCI not extreme
            roc_10 > -0.01,       # Rate of change not negative
            aroon_osc > -20,      # Aroon not strongly bearish
            supertrend_dir == 1,  # Supertrend long
        ]
    else:  # short
        votes = [
            rsi_14 > 50,          # RSI not oversold
            willr_14 > -50,       # Williams %R agrees
            cci_20 > -100,        # CCI not extreme
            roc_10 < 0.01,        # Rate of change not positive
            aroon_osc < 20,       # Aroon not strongly bullish
            supertrend_dir == -1, # Supertrend short
        ]

    return sum(1 for v in votes if v) / len(votes)


def _detect_divergence(
    *,
    bias: str,
    rsi_14: float,
    roc_10: float,
    price_vs_ma200: float,
) -> bool:
    """Detect bearish/bullish divergence against signal direction.

    Bearish divergence: price making highs but RSI declining.
    Bullish divergence: price making lows but RSI rising.
    """
    if bias == "long":
        # Warning: price is dropping (below MA200) but RSI is high → exhaustion
        if price_vs_ma200 < -0.02 and rsi_14 > 65:
            return True
        # Price momentum positive but RSI overbought → reversal risk
        if roc_10 > 0.03 and rsi_14 > 75:
            return True
    else:
        # Price is rising but RSI is low → exhaustion
        if price_vs_ma200 > 0.02 and rsi_14 < 35:
            return True
        if roc_10 < -0.03 and rsi_14 < 25:
            return True
    return False


def _volume_quality(
    *,
    bias: str,
    volume_ratio: float,
    volume_delta: float,
) -> float:
    """Score volume confirmation (0-1).

    Good signals have:
    - Moderate above-average volume (ratio 1.0-2.0)
    - Volume delta agreeing with direction

    Backtest finding: volume_ratio > 2.0 is toxic for MR engines
    (OOS-confirmed, r=-0.15 Bonferroni-significant).
    Volume spikes signal momentum — bad for mean-reversion entries.
    """
    score = 0.50

    # Volume spike = toxic for MR (backtest-proven)
    if volume_ratio > 2.0:
        score -= 0.30  # Heavy penalty — momentum spike
    elif volume_ratio > 1.5:
        score += 0.10  # Mild positive — was +0.25, reduced
    elif volume_ratio > 1.0:
        score += 0.15
    elif volume_ratio < 0.5:
        score -= 0.20  # Dead market = bad signal

    # Volume delta should agree with bias
    if bias == "long" and volume_delta > 0:
        score += 0.20
    elif bias == "short" and volume_delta < 0:
        score += 0.20
    elif (bias == "long" and volume_delta < -0.5) or (bias == "short" and volume_delta > 0.5):
        score -= 0.15  # Strong disagreement

    return _clamp(score, 0.0, 1.0)


def _regime_stability_quality(
    *,
    candles_in_regime: int,
    regime_confidence: float,
) -> float:
    """Score regime stability (0-1).

    Signals in a freshly transitioned regime are riskier.
    """
    # Regime needs time to establish
    if candles_in_regime < 3:
        time_factor = 0.20  # Very new regime
    elif candles_in_regime < 6:
        time_factor = 0.50
    elif candles_in_regime < 12:
        time_factor = 0.75
    else:
        time_factor = 1.0

    return _clamp((time_factor * 0.6) + (regime_confidence * 0.4), 0.0, 1.0)


def _orderbook_quality(
    *,
    bias: str,
    orderbook_imbalance: float,
) -> float:
    """Score orderbook support (0-1).

    Long signals need buy-side support (positive imbalance).
    Short signals need sell-side pressure (negative imbalance).
    """
    if bias == "long":
        # Positive imbalance = buying pressure
        return _clamp(0.5 + orderbook_imbalance * 2.0, 0.0, 1.0)
    else:
        # Negative imbalance = selling pressure
        return _clamp(0.5 - orderbook_imbalance * 2.0, 0.0, 1.0)


_MR_ENGINES = {"POSEIDON", "NAUTILUS", "HYDRA"}


def _trend_alignment_quality(
    *,
    bias: str,
    ema_21_vs_55: float,
    price_vs_ma200: float,
    adx_14: float,
    engine: str = "",
) -> float:
    """Score how well the signal aligns with the higher-TF trend.

    Trading WITH the trend is higher quality than counter-trend.
    MR engines are exempt — they trade against the trend by design.
    """
    if engine in _MR_ENGINES:
        return 0.50  # Neutral — trend alignment is irrelevant for MR

    score = 0.50

    if bias == "long":
        if ema_21_vs_55 > 0:
            score += 0.20  # Short-term trend agrees
        else:
            score -= 0.15

        if price_vs_ma200 > 0:
            score += 0.15  # Long-term trend agrees
        else:
            score -= 0.10
    else:  # short
        if ema_21_vs_55 < 0:
            score += 0.20
        else:
            score -= 0.15

        if price_vs_ma200 < 0:
            score += 0.15
        else:
            score -= 0.10

    # Strong trend (high ADX) with alignment = very good signal
    if adx_14 > 30:
        score *= 1.15

    return _clamp(score, 0.0, 1.0)


def _toxic_pattern_penalty(
    *,
    bias: str,
    volume_ratio: float,
    adx_14: float,
) -> float:
    """Apply confidence penalty for backtest-proven toxic conditions.

    Wave 1 (OOS-confirmed from luna_crash analysis):
    1. short + volume_ratio > 2.0 -> WR 21.5%, avg -0.83%
    2. ADX < 15 + volume_ratio > 2.0 -> WR 14.3%
    3. short + ADX > 40 + volume > 2.0 -> WR 0%

    Wave 2 (OOS-confirmed from tuned BT analysis):
    4. ADX > 40 + volume 0.5-0.8 -> WR 25% (strong trend + low vol = MR trap)
    5. short + ADX 25-40 -> WR 28.6% (medium trend, MR shorts fail)
    """
    penalty = 0.0

    # Pattern 1: short + extreme volume = disaster
    if bias == "short" and volume_ratio > 2.0:
        penalty -= 0.15

    # Pattern 2: ADX < 15 + extreme volume = trap (no trend, random spike)
    if adx_14 < 15 and volume_ratio > 2.0:
        penalty -= 0.12

    # Pattern 3: short + ADX > 40 + extreme volume = momentum crash
    if bias == "short" and adx_14 > 40 and volume_ratio > 2.0:
        penalty -= 0.10  # Additional on top of Pattern 1

    # Pattern 4: ADX > 40 + low volume = strong trend, MR will revert wrong
    if adx_14 > 40 and volume_ratio < 0.8:
        penalty -= 0.10

    # Pattern 5: short + ADX 25-40 = medium trend, MR short fails
    if bias == "short" and 25 <= adx_14 <= 40:
        penalty -= 0.08

    return penalty
