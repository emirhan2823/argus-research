"""GEMINI engine: correlation-based pairs trading (B-03, B-04)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from src.core.constants import ENGINE_GEMINI, REGIME_CRISIS
from src.core.types import EngineSignal, FeatureVector, RegimeState
from src.correlation.signals import CorrelationSignalGenerator
from src.correlation.tracker import CorrelationTracker


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


@dataclass
class GeminiEngine:
    """Correlation-based pairs trading engine.

    Satisfies the ``AbstractEngine`` protocol.  For each symbol in
    ``features``, the engine checks whether that symbol belongs to any
    tracked pair in the ``CorrelationTracker`` and, if so, delegates to
    the ``CorrelationSignalGenerator`` for a mean-reversion signal.

    Because the ARGUS pipeline processes one symbol at a time, pair
    signals are mapped to single-leg ``EngineSignal`` instances.
    """

    tracker: CorrelationTracker
    signal_generator: CorrelationSignalGenerator
    max_simultaneous_pairs: int = 3

    # Internal bookkeeping (not constructor args)
    _active_pair_ids: list[str] = field(default_factory=list, init=False, repr=False)

    # ── AbstractEngine protocol ─────────────────────────────────────

    def generate_signal(
        self,
        *,
        regime: RegimeState,
        features: FeatureVector,
    ) -> Optional[EngineSignal]:
        """Generate a single-leg EngineSignal from correlation state.

        Steps
        -----
        1. Check regime — no signals in CRISIS.
        2. Find all pairs that include ``features.symbol``.
        3. For each matching pair, call the signal generator.
        4. Convert the best (highest-confidence) pair signal to an
           ``EngineSignal`` for this symbol's leg.
        """
        if regime.regime == REGIME_CRISIS:
            return None

        symbol = features.symbol
        matching_pairs = self._find_pairs_for_symbol(symbol)

        if not matching_pairs:
            return None

        best_signal: Optional[EngineSignal] = None

        for pair_state in matching_pairs:
            pair_id = pair_state["pair_id"]

            # Extract pair state values
            correlation = float(pair_state.get("correlation", 0.0))
            spread_zscore = float(pair_state.get("spread_zscore", 0.0))
            half_life = pair_state.get("half_life")
            is_cointegrated = bool(pair_state.get("is_cointegrated", False))

            raw_signal = self.signal_generator.generate(
                pair_id=pair_id,
                correlation=correlation,
                spread_zscore=spread_zscore,
                half_life=half_life,
                is_cointegrated=is_cointegrated,
                regime=regime.regime,
            )

            if raw_signal is None:
                continue

            # Determine this symbol's direction in the pair
            is_symbol_a = pair_state["symbol_a"] == symbol
            direction_key = "direction_a" if is_symbol_a else "direction_b"
            direction = raw_signal[direction_key]
            bias = "long" if direction == "LONG" else "short"

            # Confidence: signal confidence * correlation strength
            raw_conf = raw_signal["confidence"]
            corr_strength = min(abs(correlation), 1.0)
            combined_confidence = _clamp(raw_conf * corr_strength, 0.0, 1.0)

            # ATR-based stop distance
            stop_distance = _clamp(
                max(features.atr_14_pct, 0.01) * 1.2,
                0.005,
                0.10,
            )

            engine_signal = EngineSignal(
                engine=ENGINE_GEMINI,
                sub_strategy="corr_mean_reversion",
                asset_class=features.asset_class,
                symbol=symbol,
                bias=bias,
                confidence=round(combined_confidence, 4),
                stop_distance=round(stop_distance, 6),
                expected_return=round(stop_distance * 2.0, 6),
                atr=features.atr_14,
            )

            if best_signal is None or engine_signal.confidence > best_signal.confidence:
                best_signal = engine_signal

        return best_signal

    # ── Internals ───────────────────────────────────────────────────

    def _find_pairs_for_symbol(self, symbol: str) -> list[dict]:
        """Return all tracked pair states that include *symbol*."""
        results: list[dict] = []
        for pair_id, pair in self.tracker._pairs.items():
            if pair["symbol_a"] == symbol or pair["symbol_b"] == symbol:
                results.append(dict(pair))
        return results
