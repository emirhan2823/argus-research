"""Confluence Filter — multi-factor independent confirmation for trade signals.

Requires N out of M independent factors to agree before a trade passes.
Each factor checks a different dimension of market evidence (trend, volume,
momentum, volatility, orderbook, statistics) to ensure genuine signal
diversification rather than redundant checks.

Integration point: Step 6.8 (after precision filter, before trade quality).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from src.core.constants import (
    ENGINE_AEGEAN,
    ENGINE_HYDRA,
    ENGINE_NAUTILUS,
    ENGINE_PHOENIX,
    ENGINE_POSEIDON,
    ENGINE_TITAN,
)

_MEAN_REVERSION_ENGINES = (ENGINE_NAUTILUS, ENGINE_HYDRA, ENGINE_PHOENIX, ENGINE_AEGEAN, ENGINE_POSEIDON)


@dataclass(frozen=True)
class ConfluenceConfig:
    """Configuration for the confluence filter."""

    min_factors_required: int = 4        # N: minimum factors that must pass
    min_confluence_score: float = 0.60   # Weighted score floor
    counter_trend_penalty: float = 0.15  # Extra score penalty for counter-trend


@dataclass(frozen=True)
class FactorResult:
    """Result of a single confluence factor check."""

    name: str
    passed: bool
    score: float   # 0.0-1.0
    weight: float
    detail: str


@dataclass(frozen=True)
class ConfluenceResult:
    """Result of the full confluence evaluation."""

    passed: bool
    score: float                          # 0.0-1.0 weighted confluence score
    factors_passed: int
    factors_total: int
    factor_details: dict[str, FactorResult]
    reason: str


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


# ── Factor 1: Multi-Timeframe Alignment (weight 0.25) ──────────────


def _check_mtf_alignment(
    *,
    bias: str,
    ema_21_vs_55: float,
    price_vs_ma200: float,
    supertrend_dir: int,
    lr_slope_20: float,
) -> FactorResult:
    """Check if multiple timeframe proxies agree with signal direction.

    For long: EMA21>EMA55, price>MA200, supertrend=+1, lr_slope>0.
    For short: inverse.
    """
    if bias == "long":
        votes = [
            ema_21_vs_55 > 0,
            price_vs_ma200 > 0,
            supertrend_dir == 1,
            lr_slope_20 > 0,
        ]
    else:
        votes = [
            ema_21_vs_55 < 0,
            price_vs_ma200 < 0,
            supertrend_dir == -1,
            lr_slope_20 < 0,
        ]

    score = sum(1 for v in votes if v) / len(votes)
    passed = score >= 0.60  # At least 3 of 4
    return FactorResult(
        name="mtf_alignment",
        passed=passed,
        score=round(score, 4),
        weight=0.25,
        detail=f"mtf {sum(votes)}/4 agree bias={bias}",
    )


# ── Factor 1b: Distance-from-Mean (for mean-reversion engines) ──────


def _check_distance_from_mean(
    *,
    bias: str,
    bb_pct_b: float,
    rsi_14: float,
    cci_20: float,
    vwap_dev_pct: float,
) -> FactorResult:
    """Check if price is sufficiently extended from mean for mean-reversion.

    Replaces MTF alignment for NAUTILUS/HYDRA/PHOENIX/AEGEAN where trend
    alignment would structurally penalize counter-trend entries.

    Long: price below mean (BB low, RSI low, CCI<0, below VWAP)
    Short: price above mean (BB high, RSI high, CCI>0, above VWAP)
    """
    if bias == "long":
        votes = [
            bb_pct_b <= 0.35,
            rsi_14 <= 45.0,
            cci_20 < 0,
            vwap_dev_pct < 0,
        ]
    else:
        votes = [
            bb_pct_b >= 0.65,
            rsi_14 >= 55.0,
            cci_20 > 0,
            vwap_dev_pct > 0,
        ]

    score = sum(1 for v in votes if v) / len(votes)
    passed = score >= 0.50
    return FactorResult(
        name="mtf_alignment",  # Same name for transparent downstream compatibility
        passed=passed,
        score=round(score, 4),
        weight=0.25,
        detail=f"distance_from_mean {sum(votes)}/4 agree bias={bias} bb={bb_pct_b:.3f}",
    )


# ── Factor 2: Volume Profile Confirmation (weight 0.20) ────────────


def _check_volume_confirmation(
    *,
    bias: str,
    volume_ratio: float,
    volume_delta: float,
    obv_slope_10: float,
    cmf_20: float,
) -> FactorResult:
    """Check if volume supports the signal direction."""
    votes = []

    # Above-average volume
    votes.append(volume_ratio >= 1.0)

    # Volume delta agrees with direction
    if bias == "long":
        votes.append(volume_delta > 0)
        votes.append(obv_slope_10 > 0)
        votes.append(cmf_20 > 0)
    else:
        votes.append(volume_delta < 0)
        votes.append(obv_slope_10 < 0)
        votes.append(cmf_20 < 0)

    score = sum(1 for v in votes if v) / len(votes)
    passed = score >= 0.50  # At least 2 of 4
    return FactorResult(
        name="volume_confirmation",
        passed=passed,
        score=round(score, 4),
        weight=0.20,
        detail=f"vol {sum(votes)}/4 agree vol_ratio={volume_ratio:.2f}",
    )


# ── Factor 3: Momentum Alignment (weight 0.20) ─────────────────────


def _check_momentum_alignment(
    *,
    bias: str,
    rsi_14: float,
    cci_20: float,
    willr_14: float,
    roc_10: float,
    engine: str = "",
) -> FactorResult:
    """Check if momentum indicators agree with signal direction.

    For trend engines:
      Long: RSI 40-70, CCI>0, WillR>-50, ROC>0.
      Short: RSI 30-60, CCI<0, WillR<-50, ROC<0.

    For MR engines: extreme readings ARE the setup — oversold momentum
    confirms a long MR entry, overbought confirms a short MR entry.
    """
    if engine in _MEAN_REVERSION_ENGINES:
        # MR logic: extreme readings = good momentum for reversal
        if bias == "long":
            votes = [
                rsi_14 <= 40,       # oversold = MR long setup
                cci_20 < -50,       # extreme negative = reversal opportunity
                willr_14 < -60,     # deeply oversold
                roc_10 < -0.005,    # negative momentum = exhaustion
            ]
        else:
            votes = [
                rsi_14 >= 60,       # overbought = MR short setup
                cci_20 > 50,        # extreme positive = reversal opportunity
                willr_14 > -40,     # overbought zone
                roc_10 > 0.005,     # positive momentum = exhaustion
            ]
    elif bias == "long":
        votes = [
            40 <= rsi_14 <= 70,   # Not overbought, not deeply oversold
            cci_20 > 0,
            willr_14 > -50,
            roc_10 > 0,
        ]
    else:
        votes = [
            30 <= rsi_14 <= 60,   # Not oversold, not deeply overbought
            cci_20 < 0,
            willr_14 < -50,
            roc_10 < 0,
        ]

    score = sum(1 for v in votes if v) / len(votes)
    passed = score >= 0.50  # At least 2 of 4
    return FactorResult(
        name="momentum_alignment",
        passed=passed,
        score=round(score, 4),
        weight=0.20,
        detail=f"mom {sum(votes)}/4 agree rsi={rsi_14:.1f} roc={roc_10:.4f}",
    )


# ── Factor 4: Volatility Regime Suitability (weight 0.15) ──────────


def _check_volatility_suitability(
    *,
    engine: str,
    atr_ratio_5_20: float,
    bb_width: float,
    realized_vol_20d: float,
) -> FactorResult:
    """Check if current volatility matches engine's preferred environment.

    TITAN (trend): moderate volatility (atr_ratio 0.8-2.0).
    NAUTILUS (mean-rev): low volatility (atr_ratio < 1.5).
    HYDRA (scalp): tight ranges (low bb_width, low atr_ratio).
    PHOENIX (carry): wide tolerance.
    """
    if engine == ENGINE_TITAN:
        # Trend-following needs some volatility but not too much
        if 0.8 <= atr_ratio_5_20 <= 2.0:
            atr_score = 1.0
        elif 0.6 <= atr_ratio_5_20 <= 2.5:
            atr_score = 0.60
        else:
            atr_score = 0.25

        vol_score = 1.0 if realized_vol_20d <= 0.06 else (0.50 if realized_vol_20d <= 0.10 else 0.20)
        score = atr_score * 0.60 + vol_score * 0.40

    elif engine == ENGINE_NAUTILUS:
        # Mean reversion needs calm conditions
        if atr_ratio_5_20 <= 1.2:
            atr_score = 1.0
        elif atr_ratio_5_20 <= 1.5:
            atr_score = 0.65
        else:
            atr_score = 0.25

        vol_score = 1.0 if realized_vol_20d <= 0.04 else (0.55 if realized_vol_20d <= 0.07 else 0.20)
        score = atr_score * 0.50 + vol_score * 0.50

    elif engine == ENGINE_HYDRA:
        # Scalping needs very tight conditions
        if atr_ratio_5_20 <= 1.0:
            atr_score = 1.0
        elif atr_ratio_5_20 <= 1.3:
            atr_score = 0.60
        else:
            atr_score = 0.15

        bb_score = 1.0 if bb_width <= 0.03 else (0.60 if bb_width <= 0.05 else 0.20)
        score = atr_score * 0.50 + bb_score * 0.50

    elif engine == ENGINE_PHOENIX:
        # Carry trades are volatility-tolerant
        score = 0.70 if atr_ratio_5_20 <= 2.5 else 0.40

    else:
        # Default: moderate tolerance
        score = 0.60 if atr_ratio_5_20 <= 2.0 else 0.35

    score = _clamp(score, 0.0, 1.0)
    passed = score >= 0.50
    return FactorResult(
        name="volatility_suitability",
        passed=passed,
        score=round(score, 4),
        weight=0.15,
        detail=f"vol_suit engine={engine} atr_ratio={atr_ratio_5_20:.2f} bb_w={bb_width:.4f}",
    )


# ── Factor 5: Orderbook/Microstructure Pressure (weight 0.10) ──────


def _check_orderbook_pressure(
    *,
    bias: str,
    orderbook_imbalance: Optional[float],
    trade_flow_imbalance: Optional[float],
    spread_pct: float,
) -> FactorResult:
    """Check if orderbook microstructure supports the signal.

    When crypto-specific fields are None, returns neutral score (0.50).
    """
    if orderbook_imbalance is None and trade_flow_imbalance is None:
        return FactorResult(
            name="orderbook_pressure",
            passed=True,
            score=0.50,
            weight=0.10,
            detail="orderbook_data_unavailable neutral=0.50",
        )

    scores = []

    # OBI alignment
    if orderbook_imbalance is not None:
        if bias == "long":
            obi_s = _clamp(0.5 + orderbook_imbalance * 1.5, 0.0, 1.0)
        else:
            obi_s = _clamp(0.5 - orderbook_imbalance * 1.5, 0.0, 1.0)
        scores.append(obi_s)

    # Trade flow alignment
    if trade_flow_imbalance is not None:
        if bias == "long":
            tfi_s = _clamp(0.5 + trade_flow_imbalance * 1.5, 0.0, 1.0)
        else:
            tfi_s = _clamp(0.5 - trade_flow_imbalance * 1.5, 0.0, 1.0)
        scores.append(tfi_s)

    # Spread not excessive
    spread_s = 1.0 if spread_pct <= 0.0005 else (0.70 if spread_pct <= 0.001 else (0.40 if spread_pct <= 0.003 else 0.15))
    scores.append(spread_s)

    score = sum(scores) / len(scores) if scores else 0.50
    score = _clamp(score, 0.0, 1.0)
    passed = score >= 0.40
    return FactorResult(
        name="orderbook_pressure",
        passed=passed,
        score=round(score, 4),
        weight=0.10,
        detail=f"ob_pressure bias={bias} obi={orderbook_imbalance} spread={spread_pct:.5f}",
    )


# ── Factor 6: Statistical Edge (weight 0.10) ───────────────────────


def _check_statistical_edge(
    *,
    engine: str,
    hurst_exponent: float,
    return_autocorr_20: float,
    entropy_50: float,
) -> FactorResult:
    """Check if statistical properties favor the engine's strategy type.

    TITAN: Hurst > 0.55 (trending) + positive autocorrelation.
    NAUTILUS/HYDRA: Hurst < 0.45 (mean-reverting) + negative autocorrelation.
    Low entropy favors both (more predictable).
    """
    scores = []

    if engine == ENGINE_TITAN:
        # Trending series
        if hurst_exponent >= 0.60:
            scores.append(1.0)
        elif hurst_exponent >= 0.55:
            scores.append(0.75)
        elif hurst_exponent >= 0.50:
            scores.append(0.45)
        else:
            scores.append(0.20)

        # Positive autocorrelation = momentum
        if return_autocorr_20 > 0.10:
            scores.append(1.0)
        elif return_autocorr_20 > 0:
            scores.append(0.65)
        else:
            scores.append(0.30)

    elif engine in (ENGINE_NAUTILUS, ENGINE_HYDRA):
        # Mean-reverting series
        if hurst_exponent <= 0.35:
            scores.append(1.0)
        elif hurst_exponent <= 0.42:
            scores.append(0.75)
        elif hurst_exponent <= 0.50:
            scores.append(0.45)
        else:
            scores.append(0.20)

        # Negative autocorrelation = mean reversion
        if return_autocorr_20 < -0.10:
            scores.append(1.0)
        elif return_autocorr_20 < 0:
            scores.append(0.65)
        else:
            scores.append(0.30)

    else:
        # Other engines: neutral
        scores.append(0.55)
        scores.append(0.55)

    # Low entropy = more predictable = better for all
    if entropy_50 <= 0.40:
        scores.append(1.0)
    elif entropy_50 <= 0.60:
        scores.append(0.70)
    elif entropy_50 <= 0.80:
        scores.append(0.45)
    else:
        scores.append(0.20)

    score = sum(scores) / len(scores) if scores else 0.50
    score = _clamp(score, 0.0, 1.0)
    passed = score >= 0.40
    return FactorResult(
        name="statistical_edge",
        passed=passed,
        score=round(score, 4),
        weight=0.10,
        detail=f"stat_edge engine={engine} hurst={hurst_exponent:.3f} autocorr={return_autocorr_20:.3f}",
    )


# ── Main Entry Point ───────────────────────────────────────────────


def evaluate_confluence(
    *,
    bias: str,
    engine: str,
    # Multi-timeframe
    ema_21_vs_55: float,
    price_vs_ma200: float,
    supertrend_dir: int,
    lr_slope_20: float,
    # Volume
    volume_ratio: float,
    volume_delta: float,
    obv_slope_10: float,
    cmf_20: float,
    # Momentum
    rsi_14: float,
    cci_20: float,
    willr_14: float,
    roc_10: float,
    # Volatility
    atr_ratio_5_20: float,
    bb_width: float,
    realized_vol_20d: float,
    # Orderbook (optional for non-crypto)
    orderbook_imbalance: Optional[float] = None,
    trade_flow_imbalance: Optional[float] = None,
    spread_pct: float = 0.001,
    # Statistical
    hurst_exponent: float = 0.50,
    return_autocorr_20: float = 0.0,
    entropy_50: float = 0.50,
    # Mean-reversion factor inputs
    bb_pct_b: float = 0.50,
    vwap_dev_pct: float = 0.0,
    # Config
    config: Optional[ConfluenceConfig] = None,
) -> ConfluenceResult:
    """Evaluate N-of-M independent confluence factors.

    A trade passes only if:
    1. factors_passed >= config.min_factors_required (default 4 of 6)
    2. weighted_score >= config.min_confluence_score (default 0.60)
    """
    if config is None:
        config = ConfluenceConfig()

    factors: dict[str, FactorResult] = {}

    # Factor 1: MTF alignment (trend engines) or distance-from-mean (mean-reversion)
    if engine in _MEAN_REVERSION_ENGINES:
        f1 = _check_distance_from_mean(
            bias=bias,
            bb_pct_b=bb_pct_b,
            rsi_14=rsi_14,
            cci_20=cci_20,
            vwap_dev_pct=vwap_dev_pct,
        )
    else:
        f1 = _check_mtf_alignment(
            bias=bias,
            ema_21_vs_55=ema_21_vs_55,
            price_vs_ma200=price_vs_ma200,
            supertrend_dir=supertrend_dir,
            lr_slope_20=lr_slope_20,
        )
    factors[f1.name] = f1

    # Factor 2: Volume confirmation
    f2 = _check_volume_confirmation(
        bias=bias,
        volume_ratio=volume_ratio,
        volume_delta=volume_delta,
        obv_slope_10=obv_slope_10,
        cmf_20=cmf_20,
    )
    factors[f2.name] = f2

    # Factor 3: Momentum alignment
    f3 = _check_momentum_alignment(
        bias=bias,
        rsi_14=rsi_14,
        cci_20=cci_20,
        willr_14=willr_14,
        roc_10=roc_10,
        engine=engine,
    )
    factors[f3.name] = f3

    # Factor 4: Volatility suitability
    f4 = _check_volatility_suitability(
        engine=engine,
        atr_ratio_5_20=atr_ratio_5_20,
        bb_width=bb_width,
        realized_vol_20d=realized_vol_20d,
    )
    factors[f4.name] = f4

    # Factor 5: Orderbook pressure
    f5 = _check_orderbook_pressure(
        bias=bias,
        orderbook_imbalance=orderbook_imbalance,
        trade_flow_imbalance=trade_flow_imbalance,
        spread_pct=spread_pct,
    )
    factors[f5.name] = f5

    # Factor 6: Statistical edge
    f6 = _check_statistical_edge(
        engine=engine,
        hurst_exponent=hurst_exponent,
        return_autocorr_20=return_autocorr_20,
        entropy_50=entropy_50,
    )
    factors[f6.name] = f6

    # Count passed factors
    factors_passed = sum(1 for f in factors.values() if f.passed)
    factors_total = len(factors)

    # Compute weighted score
    total_weight = sum(f.weight for f in factors.values())
    weighted_score = sum(f.score * f.weight for f in factors.values()) / max(total_weight, 1e-9)
    weighted_score = _clamp(weighted_score, 0.0, 1.0)

    # Pass logic
    enough_factors = factors_passed >= config.min_factors_required
    enough_score = weighted_score >= config.min_confluence_score
    passed = enough_factors and enough_score

    if passed:
        reason = f"confluence_pass {factors_passed}/{factors_total} score={weighted_score:.3f}"
    elif not enough_factors:
        reason = f"confluence_fail_factors {factors_passed}/{config.min_factors_required} required"
    else:
        reason = f"confluence_fail_score {weighted_score:.3f}<{config.min_confluence_score}"

    return ConfluenceResult(
        passed=passed,
        score=round(weighted_score, 4),
        factors_passed=factors_passed,
        factors_total=factors_total,
        factor_details=factors,
        reason=reason,
    )
