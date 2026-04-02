"""Hybrid Sizing Policy — deterministic leverage and position size for snowball.

Core principle:
    Leverage is the RESULT of quality and context.
    It is NOT the source of edge.

Design:
    Leverage is determined by a multi-factor lookup:
        1. Engine type (Trend vs MR)
        2. Pair class (CORE vs MOVER)
        3. Hybrid regime
        4. Signal confidence score
        5. Portfolio heat
        6. Capital phase (survival / foundation / growth / etc.)

    Interaction rules:
        - Trend Engine on MOVER in EXPANSION → highest leverage allowed
        - MR Engine on CORE in RANGE_MR → conservative leverage
        - Trend Engine on CORE → moderate leverage (cleaner, less leverage needed)
        - Crisis or chop → 0 leverage (no new positions)
        - High heat → always scales down

Snowball phases (from risk.yaml growth_sizer):
    survival      [0, 2000]:     max_leverage 1.0
    foundation    [2000, 10000]: max_leverage 1.5
    growth        [10000, 50000]:max_leverage 2.0
    acceleration  [50000, 200k]: max_leverage 2.5
    compounding   [200k+]:       max_leverage 2.0

    These caps are applied AFTER the base leverage computation.
"""

from __future__ import annotations

from dataclasses import dataclass


# ── Leverage matrix (base values before modifiers) ───────────────────────────
# [engine_type][pair_class][regime] → base_leverage

_LEVERAGE_MATRIX: dict[str, dict[str, dict[str, float]]] = {
    "TREND": {
        "MOVER": {
            "BULLISH_TREND": 8.0,
            "BEARISH_TREND": 7.0,
            "EXPANSION": 10.0,
            "RANGE_MR": 2.0,    # Trend engine in range → very small
            "CHOP": 0.0,
            "CRISIS_DEFENSIVE": 0.0,
            "RANGING": 2.0,
            "VOLATILE": 3.0,
            "TRENDING": 8.0,
            "CRISIS": 0.0,
        },
        "CORE": {
            "BULLISH_TREND": 6.0,
            "BEARISH_TREND": 5.0,
            "EXPANSION": 7.0,
            "RANGE_MR": 1.5,
            "CHOP": 0.0,
            "CRISIS_DEFENSIVE": 0.0,
            "RANGING": 1.5,
            "VOLATILE": 3.0,
            "TRENDING": 6.0,
            "CRISIS": 0.0,
        },
    },
    "MR": {
        "MOVER": {
            "RANGE_MR": 4.0,
            "RANGING": 4.0,
            "VOLATILE": 3.0,
            "BULLISH_TREND": 1.5,
            "BEARISH_TREND": 1.5,
            "EXPANSION": 2.0,
            "CHOP": 0.0,
            "CRISIS_DEFENSIVE": 0.0,
            "TRENDING": 1.5,
            "CRISIS": 0.0,
        },
        "CORE": {
            "RANGE_MR": 5.0,
            "RANGING": 5.0,
            "VOLATILE": 3.5,
            "BULLISH_TREND": 2.0,
            "BEARISH_TREND": 2.0,
            "EXPANSION": 2.5,
            "CHOP": 0.0,
            "CRISIS_DEFENSIVE": 0.0,
            "TRENDING": 2.0,
            "CRISIS": 0.0,
        },
    },
    "HYBRID": {
        "MOVER": {
            "BULLISH_TREND": 5.0, "BEARISH_TREND": 4.0, "RANGE_MR": 3.0,
            "RANGING": 3.0, "VOLATILE": 2.5, "EXPANSION": 4.0,
            "CHOP": 0.0, "CRISIS_DEFENSIVE": 0.0, "TRENDING": 4.0, "CRISIS": 0.0,
        },
        "CORE": {
            "BULLISH_TREND": 4.0, "BEARISH_TREND": 3.5, "RANGE_MR": 3.0,
            "RANGING": 3.0, "VOLATILE": 2.5, "EXPANSION": 3.5,
            "CHOP": 0.0, "CRISIS_DEFENSIVE": 0.0, "TRENDING": 3.5, "CRISIS": 0.0,
        },
    },
}

# ── Capital phase caps ────────────────────────────────────────────────────────

_PHASE_CAPS: list[tuple[float, float, float, float]] = [
    # (equity_min, equity_max, max_leverage, max_risk_pct)
    (0,      2_000,    1.0, 0.015),
    (2_000,  10_000,   1.5, 0.025),
    (10_000, 50_000,   2.0, 0.035),
    (50_000, 200_000,  2.5, 0.045),
    (200_000, 1e12,    2.0, 0.035),
]


def _get_phase_cap(equity: float) -> tuple[float, float]:
    """Return (max_leverage, max_risk_pct) for given equity."""
    for eq_min, eq_max, max_lev, max_risk in _PHASE_CAPS:
        if eq_min <= equity < eq_max:
            return max_lev, max_risk
    return 2.0, 0.035  # fallback


# ── Sizing policy ─────────────────────────────────────────────────────────────


@dataclass
class HybridSizingPolicy:
    """Deterministic leverage and position size policy.

    Call compute_leverage() to get leverage for a signal.
    Call compute_position_pct() to get position size as % of equity.
    """

    # Score tiers: leverage scales with score
    score_high_threshold: float = 0.75   # full leverage at this score
    score_low_threshold: float = 0.50    # minimum score (below → no position)

    # Heat penalty thresholds
    heat_no_penalty: float = 0.04        # heat below this: no penalty
    heat_max_penalty_at: float = 0.10    # heat at this level: 50% leverage reduction

    # Base risk per trade as % of equity
    base_risk_pct: float = 0.020         # 2% default
    min_risk_pct: float = 0.005
    max_risk_pct: float = 0.045

    def compute_leverage(
        self,
        *,
        engine_type: str,        # "TREND", "MR", "HYBRID"
        pair_class: str,         # "CORE", "MOVER"
        regime: str,             # regime label
        signal_score: float,     # 0.0–1.0
        portfolio_heat: float,   # 0.0–1.0
        equity: float = 10_000,  # current account equity
    ) -> float:
        """Return leverage multiplier for the signal.

        Returns 0.0 if signal should not be leveraged (regime mismatch, heat).
        """
        et = engine_type.upper()
        pc = pair_class.upper()
        reg = regime.upper()

        # Lookup base leverage
        engine_matrix = _LEVERAGE_MATRIX.get(et, _LEVERAGE_MATRIX["HYBRID"])
        pair_matrix = engine_matrix.get(pc, engine_matrix.get("CORE", {}))
        base_leverage = float(pair_matrix.get(reg, 2.0))

        if base_leverage <= 0:
            return 0.0

        # Score modifier: scale between 0.6 and 1.0 based on score
        score_clipped = max(self.score_low_threshold, min(1.0, signal_score))
        score_range = max(1.0 - self.score_low_threshold, 0.01)
        score_factor = 0.6 + 0.4 * (score_clipped - self.score_low_threshold) / score_range

        # Heat penalty: linearly reduce leverage as heat increases
        heat_range = max(self.heat_max_penalty_at - self.heat_no_penalty, 0.01)
        heat_excess = max(0.0, portfolio_heat - self.heat_no_penalty)
        heat_factor = max(0.5, 1.0 - 0.5 * heat_excess / heat_range)

        # Phase cap
        phase_max_lev, _ = _get_phase_cap(equity)

        # Final leverage
        leverage = base_leverage * score_factor * heat_factor
        leverage = min(leverage, phase_max_lev)
        leverage = max(1.0, leverage)

        return round(leverage, 1)

    def compute_position_pct(
        self,
        *,
        stop_distance_pct: float,   # SL distance as % of price (e.g. 0.02 = 2%)
        leverage: float,
        signal_score: float,
        portfolio_heat: float,
        equity: float = 10_000,
    ) -> float:
        """Return position size as fraction of equity (e.g. 0.05 = 5%).

        Uses risk-based sizing: position_size = risk_per_trade / stop_distance
        where risk_per_trade is bounded by score and phase caps.
        """
        if stop_distance_pct <= 0 or leverage <= 0:
            return 0.0

        # Phase cap on risk
        _, phase_max_risk = _get_phase_cap(equity)

        # Scale risk by score
        score_clipped = max(self.score_low_threshold, min(1.0, signal_score))
        score_range = max(1.0 - self.score_low_threshold, 0.01)
        score_factor = 0.7 + 0.3 * (score_clipped - self.score_low_threshold) / score_range

        # Heat penalty on risk
        heat_range = max(self.heat_max_penalty_at - self.heat_no_penalty, 0.01)
        heat_excess = max(0.0, portfolio_heat - self.heat_no_penalty)
        heat_factor = max(0.5, 1.0 - 0.5 * heat_excess / heat_range)

        risk_pct = self.base_risk_pct * score_factor * heat_factor
        risk_pct = max(self.min_risk_pct, min(risk_pct, min(self.max_risk_pct, phase_max_risk)))

        # position_size_pct = risk / stop_distance (in equity terms)
        # With leverage: notional = equity * position_size_pct * leverage
        # Risk = notional * stop_distance_pct / leverage = equity * position_size_pct * stop_distance_pct
        position_pct = risk_pct / max(stop_distance_pct, 0.001)
        position_pct = min(position_pct, 0.15)  # global 15% max position

        return round(position_pct, 4)

    def compute_tp_pct(
        self,
        *,
        stop_distance_pct: float,
        engine_type: str,
        regime: str,
        signal_score: float,
    ) -> float:
        """Compute take profit distance based on engine-specific RR.

        Trend engines use wider TP (runner logic).
        MR engines use tighter TP (faster mean-reversion capture).
        """
        et = engine_type.upper()
        reg = regime.upper()

        # Base RR by engine
        if et == "TREND":
            base_rr = 3.0
            if reg in {"EXPANSION", "BULLISH_TREND"} and signal_score >= self.score_high_threshold:
                base_rr = 4.0  # high conviction trend → wider runner TP
        elif et == "MR":
            base_rr = 2.0   # MR: faster capture
            if reg in {"VOLATILE"}:
                base_rr = 1.5  # volatile MR: even faster
        else:
            base_rr = 2.5

        tp_pct = stop_distance_pct * base_rr
        return round(tp_pct, 5)
