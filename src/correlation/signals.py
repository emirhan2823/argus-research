"""Correlation-based signal generation (B-01, B-02)."""

from __future__ import annotations


class CorrelationSignalGenerator:
    """Generate trading signals from correlation state.

    Produces mean-reversion signals when the spread between a
    cointegrated (or highly-correlated) pair deviates beyond
    configurable z-score thresholds.
    """

    def __init__(
        self,
        entry_zscore: float = 2.0,
        exit_zscore: float = 0.5,
        stop_zscore: float = 3.0,
    ) -> None:
        self.entry_zscore = entry_zscore
        self.exit_zscore = exit_zscore
        self.stop_zscore = stop_zscore

    def generate(
        self,
        *,
        pair_id: str,
        correlation: float,
        spread_zscore: float,
        half_life: float | None,
        is_cointegrated: bool,
        regime: str,
    ) -> dict | None:
        """Generate a mean-reversion signal if conditions are met.

        Rules
        -----
        - No signals in CRISIS regime.
        - Must be cointegrated **or** correlation > 0.70.
        - ``|spread_zscore|`` must exceed ``entry_zscore`` threshold.
        - Positive z-score → SHORT A / LONG B (spread too wide, expect
          convergence).
        - Negative z-score → LONG A / SHORT B.

        Returns
        -------
        dict | None
            Signal dict with keys: ``signal_type``, ``direction_a``,
            ``direction_b``, ``confidence``, ``spread_zscore``,
            ``target_zscore``, ``stop_zscore``, ``reason``.
            ``None`` if no signal conditions are met.
        """
        # Block signals in CRISIS regime
        if regime == "CRISIS":
            return None

        # Must be cointegrated or have high correlation
        if not is_cointegrated and correlation <= 0.70:
            return None

        abs_zscore = abs(spread_zscore)

        # Z-score must exceed entry threshold
        if abs_zscore < self.entry_zscore:
            return None

        # Determine direction
        if spread_zscore > 0:
            # Spread too wide → expect convergence
            direction_a = "SHORT"
            direction_b = "LONG"
            reason = (
                f"Spread z-score {spread_zscore:+.2f} exceeds "
                f"+{self.entry_zscore:.1f}; mean reversion expected"
            )
        else:
            # Spread too narrow → expect divergence back to mean
            direction_a = "LONG"
            direction_b = "SHORT"
            reason = (
                f"Spread z-score {spread_zscore:+.2f} below "
                f"-{self.entry_zscore:.1f}; mean reversion expected"
            )

        # Compute confidence from z-score magnitude and correlation
        # Higher z-score deviation → higher confidence (capped)
        zscore_factor = min(abs_zscore / self.stop_zscore, 1.0)
        corr_factor = min(abs(correlation), 1.0)
        confidence = 0.5 * zscore_factor + 0.5 * corr_factor
        confidence = max(0.0, min(1.0, confidence))

        # Boost confidence when cointegrated
        if is_cointegrated:
            confidence = min(1.0, confidence + 0.10)

        # Boost confidence when half-life is short (fast reversion)
        if half_life is not None and half_life < 20:
            confidence = min(1.0, confidence + 0.05)

        return {
            "signal_type": "MEAN_REVERSION",
            "direction_a": direction_a,
            "direction_b": direction_b,
            "confidence": round(confidence, 4),
            "spread_zscore": spread_zscore,
            "target_zscore": self.exit_zscore if spread_zscore > 0 else -self.exit_zscore,
            "stop_zscore": self.stop_zscore if spread_zscore > 0 else -self.stop_zscore,
            "reason": reason,
        }
