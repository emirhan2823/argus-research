"""ARGUS v6 — Regime Validation Layer.

Takes the declared regime from the existing classifier and validates it using
three independent scoring dimensions. Can override the declared regime when
scores strongly disagree, and introduces a TRANSITION regime for ambiguous states.

Hysteresis:
    min_hold = 4 candles  — a new regime must persist at least 4 bars
    cooldown = 4 candles  — after a transition, ignore further changes for 4 bars
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


# ── Data contracts ──────────────────────────────────────────────────

@dataclass(frozen=True)
class RegimeValidation:
    """Result of regime validation for a single candle."""

    regime_declared: str        # Original from classifier
    trend_score: float          # 0-1 — ADX quality + EMA slopes
    volatility_score: float     # 0-1 — ATR percentile
    structure_score: float      # 0-1 — HH/HL market structure
    final_regime: str           # TRENDING | RANGING | VOLATILE | TRANSITION | CRISIS
    override_applied: bool      # True if final != declared
    scores_detail: dict         # Breakdown of sub-scores


# ── Validator ───────────────────────────────────────────────────────

@dataclass
class RegimeValidator:
    """Validates declared regime using multi-dimensional scoring.

    Parameters
    ----------
    min_hold : int
        Minimum candles a regime must persist before allowing change.
    cooldown : int
        After a transition, ignore further regime changes for this many bars.
    trend_override_threshold : float
        If trend_score >= this when declared RANGING, override to TRENDING.
    range_override_threshold : float
        If trend_score < this when declared TRENDING, override to RANGING.
    transition_band : tuple[float, float]
        When scores are in this range with conflicting signals, emit TRANSITION.
    """

    min_hold: int = 4
    cooldown: int = 4
    trend_override_threshold: float = 0.65
    range_override_threshold: float = 0.35
    transition_band: tuple[float, float] = (0.35, 0.65)

    # Internal state per symbol
    _adx_buffers: dict[str, list[float]] = field(default_factory=dict, repr=False)
    _current_regime: dict[str, str] = field(default_factory=dict, repr=False)
    _regime_age: dict[str, int] = field(default_factory=dict, repr=False)
    _cooldown_remaining: dict[str, int] = field(default_factory=dict, repr=False)

    def validate(
        self,
        *,
        symbol: str,
        declared_regime: str,
        adx_14: float,
        ema_21_vs_55: float,
        price_vs_ma200: float,
        lr_slope_20: float,
        atr_pctl: float,
        hurst_exponent: float,
        swing_highs: Optional[list[float]] = None,
        swing_lows: Optional[list[float]] = None,
    ) -> RegimeValidation:
        """Validate the declared regime and return a (possibly overridden) result."""

        # ── Update ADX buffer ──
        buf = self._adx_buffers.setdefault(symbol, [])
        buf.append(adx_14)
        if len(buf) > 10:
            buf[:] = buf[-10:]

        # ── Score dimensions ──
        trend_score, trend_detail = self._compute_trend_score(
            adx_14=adx_14,
            adx_buffer=buf,
            ema_21_vs_55=ema_21_vs_55,
            price_vs_ma200=price_vs_ma200,
            lr_slope_20=lr_slope_20,
        )

        volatility_score = self._compute_volatility_score(atr_pctl)

        structure_score, struct_detail = self._compute_structure_score(
            swing_highs=swing_highs,
            swing_lows=swing_lows,
        )

        # ── Determine proposed regime ──
        proposed = self._propose_regime(
            declared_regime=declared_regime,
            trend_score=trend_score,
            volatility_score=volatility_score,
            structure_score=structure_score,
            hurst_exponent=hurst_exponent,
        )

        # ── Apply hysteresis + cooldown ──
        final = self._apply_hysteresis(symbol, proposed, declared_regime)

        scores_detail = {
            **trend_detail,
            **struct_detail,
            "atr_pctl": round(atr_pctl, 4),
            "hurst": round(hurst_exponent, 4),
        }

        return RegimeValidation(
            regime_declared=declared_regime,
            trend_score=round(trend_score, 4),
            volatility_score=round(volatility_score, 4),
            structure_score=round(structure_score, 4),
            final_regime=final,
            override_applied=(final != declared_regime),
            scores_detail=scores_detail,
        )

    # ── Scoring helpers ─────────────────────────────────────────────

    def _compute_trend_score(
        self,
        *,
        adx_14: float,
        adx_buffer: list[float],
        ema_21_vs_55: float,
        price_vs_ma200: float,
        lr_slope_20: float,
    ) -> tuple[float, dict]:
        """Compute trend score [0, 1] from 4 sub-components."""

        # Sub-score 1: ADX level (weight 0.30)
        # ADX > 25 → strong, 20-25 borderline, < 20 weak
        if adx_14 >= 30:
            adx_level = 1.0
        elif adx_14 >= 25:
            adx_level = 0.75
        elif adx_14 >= 20:
            adx_level = 0.50
        elif adx_14 >= 15:
            adx_level = 0.25
        else:
            adx_level = 0.0

        # Sub-score 2: ADX slope rising over last 5 bars (weight 0.20)
        adx_slope = 0.0
        if len(adx_buffer) >= 5:
            recent5 = adx_buffer[-5:]
            rising_count = sum(
                1 for i in range(1, len(recent5)) if recent5[i] > recent5[i - 1]
            )
            adx_slope = rising_count / 4.0  # 0 to 1

        # Sub-score 3: EMA21 slope via lr_slope_20 (weight 0.20)
        # Positive slope = potential trend
        ema_slope = min(1.0, max(0.0, 0.5 + lr_slope_20 * 50.0))

        # Sub-score 4: EMA21/55 aligned with MA200 (weight 0.30)
        # Both same sign = trend alignment
        if ema_21_vs_55 > 0 and price_vs_ma200 > 0:
            alignment = 1.0
        elif ema_21_vs_55 < 0 and price_vs_ma200 < 0:
            alignment = 1.0  # Downtrend alignment
        elif ema_21_vs_55 == 0.0 and price_vs_ma200 == 0.0:
            alignment = 0.0
        else:
            alignment = 0.2  # Conflicting signals

        # Weighted average
        trend_score = (
            adx_level * 0.30
            + adx_slope * 0.20
            + ema_slope * 0.20
            + alignment * 0.30
        )

        detail = {
            "adx_level_sub": round(adx_level, 3),
            "adx_slope_sub": round(adx_slope, 3),
            "ema_slope_sub": round(ema_slope, 3),
            "alignment_sub": round(alignment, 3),
        }
        return min(1.0, max(0.0, trend_score)), detail

    @staticmethod
    def _compute_volatility_score(atr_pctl: float) -> float:
        """Map ATR percentile to [0, 1] volatility score."""
        return min(1.0, max(0.0, atr_pctl))

    @staticmethod
    def _compute_structure_score(
        *,
        swing_highs: Optional[list[float]] = None,
        swing_lows: Optional[list[float]] = None,
    ) -> tuple[float, dict]:
        """Score market structure from swing levels.

        HH/HL pattern (uptrend): score → 1.0
        LL/LH pattern (downtrend): score → 1.0 (trend is trend)
        Mixed: score → 0.0-0.5
        """
        if not swing_highs or len(swing_highs) < 2:
            return 0.5, {"struct_reason": "insufficient_data"}

        if not swing_lows or len(swing_lows) < 2:
            return 0.5, {"struct_reason": "insufficient_lows"}

        # Check last few swing highs for HH
        highs = swing_highs[-3:] if len(swing_highs) >= 3 else swing_highs[-2:]
        lows = swing_lows[-3:] if len(swing_lows) >= 3 else swing_lows[-2:]

        hh_count = sum(1 for i in range(1, len(highs)) if highs[i] > highs[i - 1])
        hl_count = sum(1 for i in range(1, len(lows)) if lows[i] > lows[i - 1])
        ll_count = sum(1 for i in range(1, len(lows)) if lows[i] < lows[i - 1])
        lh_count = sum(1 for i in range(1, len(highs)) if highs[i] < highs[i - 1])

        total_checks = max(len(highs) - 1, 1) + max(len(lows) - 1, 1)

        # Uptrend: HH + HL
        uptrend_score = (hh_count + hl_count) / total_checks if total_checks > 0 else 0.0
        # Downtrend: LL + LH
        downtrend_score = (ll_count + lh_count) / total_checks if total_checks > 0 else 0.0

        # Trend structure = max of up or down trend
        structure = max(uptrend_score, downtrend_score)

        detail = {
            "hh": hh_count,
            "hl": hl_count,
            "ll": ll_count,
            "lh": lh_count,
            "struct_up": round(uptrend_score, 3),
            "struct_down": round(downtrend_score, 3),
        }
        return min(1.0, max(0.0, structure)), detail

    def _propose_regime(
        self,
        *,
        declared_regime: str,
        trend_score: float,
        volatility_score: float,
        structure_score: float,
        hurst_exponent: float,
    ) -> str:
        """Propose a final regime, possibly overriding declared."""

        # CRISIS is never overridden
        if declared_regime == "CRISIS":
            return "CRISIS"

        # High volatility with low trend = VOLATILE
        if volatility_score > 0.80 and trend_score < 0.40:
            return "VOLATILE"

        # Strong trend evidence overrides RANGING
        if declared_regime == "RANGING" and trend_score >= self.trend_override_threshold:
            if structure_score >= 0.5:
                return "TRENDING"
            # Moderate structure + strong trend → TRANSITION
            return "TRANSITION"

        # Weak trend evidence overrides TRENDING
        if declared_regime == "TRENDING" and trend_score < self.range_override_threshold:
            if hurst_exponent < 0.45:
                return "RANGING"
            return "TRANSITION"

        # Ambiguous zone → TRANSITION
        low, high = self.transition_band
        if (
            declared_regime in ("TRENDING", "RANGING")
            and low < trend_score < high
            and structure_score < 0.4
        ):
            return "TRANSITION"

        return declared_regime

    def _apply_hysteresis(self, symbol: str, proposed: str, declared: str) -> str:
        """Apply min_hold and cooldown to prevent regime flip-flopping."""

        current = self._current_regime.get(symbol, declared)
        age = self._regime_age.get(symbol, 0)
        cd = self._cooldown_remaining.get(symbol, 0)

        # Cooldown active → keep current regime
        if cd > 0:
            self._cooldown_remaining[symbol] = cd - 1
            self._regime_age[symbol] = age + 1
            return current

        # Same regime → increment age
        if proposed == current:
            self._regime_age[symbol] = age + 1
            return current

        # Different regime → must meet min_hold
        if age < self.min_hold:
            # Too young to change, keep current
            self._regime_age[symbol] = age + 1
            return current

        # Transition accepted
        self._current_regime[symbol] = proposed
        self._regime_age[symbol] = 0
        self._cooldown_remaining[symbol] = self.cooldown
        return proposed

    def get_adx_rising(self, symbol: str, bars: int = 3) -> bool:
        """Check if ADX has been rising for `bars` consecutive bars."""
        buf = self._adx_buffers.get(symbol, [])
        if len(buf) < bars + 1:
            return False
        recent = buf[-(bars + 1):]
        return all(recent[i + 1] > recent[i] for i in range(bars))
