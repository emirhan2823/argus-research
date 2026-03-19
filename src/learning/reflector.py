"""ARGUS v2.5 — Reflector: Post-Trade Reflection & Shadow Simulation Engine.

Every completed trade is decomposed into a MarketSnapshot, subjected to
counterfactual "shadow simulations", and distilled into a CorrectionVector
that feeds Darwin (genome mutation) and Chiron (weight adjustment).

Architecture
============
TradeRecord  -->  Reflector.reflect()
                    |
                    +-- build MarketSnapshot (regime, sentiment, oracle, indicators)
                    +-- classify outcome (win / loss / scratch)
                    |
                    [if loss or under-performance]
                    +-- run N shadow simulations (SL width, entry timing, veto respect)
                    +-- identify dominant failure mode
                    +-- emit CorrectionVector
                    |
                    +-- persist ReflectionRecord to SQLite
                    +-- publish REFLECTION_COMPLETE event
"""

from __future__ import annotations

import json
import logging
import math
import sqlite3
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional, Sequence

import numpy as np

LOGGER = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data contracts
# ---------------------------------------------------------------------------


class FailureMode(str, Enum):
    """Taxonomy of trade failure root causes."""

    SL_TOO_TIGHT = "sl_too_tight"
    SL_TOO_WIDE = "sl_too_wide"
    ENTRY_TIMING = "entry_timing"
    HERMES_VETO_IGNORED = "hermes_veto_ignored"
    REGIME_MISMATCH = "regime_mismatch"
    ADX_THRESHOLD_WRONG = "adx_threshold_wrong"
    CONFIDENCE_INFLATED = "confidence_inflated"
    ORACLE_DIVERGENCE = "oracle_divergence"
    SIZING_ERROR = "sizing_error"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class MarketSnapshot:
    """Full market context at time of trade entry."""

    regime: str
    regime_confidence: float
    regime_stability: float
    hermes_sentiment: float  # -100 to +100
    hermes_urgency: str
    hermes_action: str  # NONE | BLOCK_ENTRY | etc.
    chronos_forecast: Optional[float]  # predicted 1h return
    chronos_confidence_width: Optional[float]
    adx_14: float
    rsi_14: float
    bb_pct_b: float
    atr_14_pct: float
    volume_ratio: float
    ema_21_vs_55: float
    hurst_exponent: float
    funding_rate: Optional[float]
    engine: str
    sub_strategy: str
    confidence: float
    stop_distance: float
    expected_return: float


@dataclass(frozen=True)
class ShadowResult:
    """Result of a single counterfactual simulation."""

    hypothesis: str  # Human-readable description
    adjusted_param: str  # Which parameter was changed
    original_value: float
    shadow_value: float
    shadow_pnl: float  # Simulated PnL under the counterfactual
    improvement_pct: float  # How much better (positive) or worse (negative)


@dataclass(frozen=True)
class CorrectionVector:
    """Actionable adjustment signal for Darwin/Chiron."""

    failure_mode: FailureMode
    severity: float  # 0.0 to 1.0 — how confident we are in this diagnosis
    # Genome-level adjustments for Darwin
    genome_deltas: dict[str, float]  # e.g. {"adx_threshold": -2.0, "sl_atr_mult": +0.3}
    # Weight-level adjustments for Chiron
    chiron_weight_nudge: dict[str, float]  # e.g. {"HERMES": +0.05, "TITAN": -0.03}
    # The shadow simulation that produced this correction
    shadow_evidence: list[ShadowResult]
    # Metadata
    trade_id: str
    symbol: str
    asset_class: str
    regime: str
    timestamp: str


@dataclass(frozen=True)
class ReflectionRecord:
    """Complete post-mortem record for a single trade."""

    reflection_id: str
    trade_id: str
    symbol: str
    asset_class: str
    outcome: str  # "win" | "loss" | "scratch"
    pnl_pct: float
    snapshot: MarketSnapshot
    shadows: list[ShadowResult]
    correction: Optional[CorrectionVector]
    architectural_regret: float  # Best shadow PnL minus actual PnL
    timestamp: str


# ---------------------------------------------------------------------------
# Shadow Simulator — counterfactual analysis
# ---------------------------------------------------------------------------


class ShadowSimulator:
    """Runs counterfactual 'what-if' analyses on completed trades.

    Each shadow test perturbs exactly ONE parameter and re-evaluates
    the hypothetical PnL using the recorded price path. This isolates
    the marginal contribution of each decision variable.
    """

    # SL width perturbation range (multipliers of original)
    SL_PERTURBATIONS = (0.5, 0.75, 1.25, 1.5, 2.0)
    # Entry delay offsets (in candles)
    ENTRY_DELAYS = (1, 2, 3)

    def run_sl_shadow(
        self,
        *,
        original_sl: float,
        entry_price: float,
        exit_price: float,
        side: str,
        high_low_path: Sequence[tuple[float, float]],
        atr: float,
    ) -> list[ShadowResult]:
        """Test whether tighter or wider SL would have improved outcome."""
        results: list[ShadowResult] = []
        is_long = side == "long"

        for mult in self.SL_PERTURBATIONS:
            shadow_sl = original_sl * mult
            shadow_sl_price = (
                entry_price * (1.0 - shadow_sl) if is_long else entry_price * (1.0 + shadow_sl)
            )

            # Walk through the candle path to see if shadow SL would have been hit
            stopped_out = False
            stop_price_hit = 0.0
            for high, low in high_low_path:
                if is_long and low <= shadow_sl_price:
                    stopped_out = True
                    stop_price_hit = shadow_sl_price
                    break
                elif not is_long and high >= shadow_sl_price:
                    stopped_out = True
                    stop_price_hit = shadow_sl_price
                    break

            if stopped_out:
                shadow_exit = stop_price_hit
            else:
                shadow_exit = exit_price

            if is_long:
                shadow_pnl = (shadow_exit - entry_price) / entry_price
                actual_pnl = (exit_price - entry_price) / entry_price
            else:
                shadow_pnl = (entry_price - shadow_exit) / entry_price
                actual_pnl = (entry_price - exit_price) / entry_price

            improvement = shadow_pnl - actual_pnl

            results.append(
                ShadowResult(
                    hypothesis=f"SL at {mult:.0%} of original ({shadow_sl:.4f} vs {original_sl:.4f})",
                    adjusted_param="stop_distance",
                    original_value=original_sl,
                    shadow_value=shadow_sl,
                    shadow_pnl=shadow_pnl,
                    improvement_pct=improvement,
                )
            )

        return results

    def run_entry_delay_shadow(
        self,
        *,
        entry_price: float,
        exit_price: float,
        side: str,
        ohlc_after_entry: Sequence[tuple[float, float, float, float]],
    ) -> list[ShadowResult]:
        """Test whether entering N candles later would have been better."""
        results: list[ShadowResult] = []
        is_long = side == "long"

        for delay in self.ENTRY_DELAYS:
            if delay >= len(ohlc_after_entry):
                break

            shadow_entry = ohlc_after_entry[delay][3]  # close of the delayed candle

            if is_long:
                shadow_pnl = (exit_price - shadow_entry) / shadow_entry
                actual_pnl = (exit_price - entry_price) / entry_price
            else:
                shadow_pnl = (shadow_entry - exit_price) / shadow_entry
                actual_pnl = (entry_price - exit_price) / entry_price

            improvement = shadow_pnl - actual_pnl

            results.append(
                ShadowResult(
                    hypothesis=f"Entry delayed by {delay} candle(s) (price {shadow_entry:.4f} vs {entry_price:.4f})",
                    adjusted_param="entry_timing",
                    original_value=entry_price,
                    shadow_value=shadow_entry,
                    shadow_pnl=shadow_pnl,
                    improvement_pct=improvement,
                )
            )

        return results

    def run_hermes_veto_shadow(
        self,
        *,
        hermes_sentiment: float,
        hermes_urgency: str,
        hermes_action: str,
        side: str,
        pnl_pct: float,
    ) -> Optional[ShadowResult]:
        """Check if respecting a Hermes veto would have avoided this loss."""
        # Only relevant if Hermes was signaling caution but was overridden
        should_have_blocked = (
            (hermes_action == "BLOCK_ENTRY")
            or (hermes_urgency in ("HIGH", "CRITICAL") and hermes_sentiment < -30)
            or (side == "long" and hermes_sentiment < -50)
            or (side == "short" and hermes_sentiment > 50)
        )

        if not should_have_blocked:
            return None

        return ShadowResult(
            hypothesis=f"Hermes veto respected (sentiment={hermes_sentiment:.1f}, urgency={hermes_urgency})",
            adjusted_param="hermes_veto",
            original_value=0.0,  # veto ignored
            shadow_value=1.0,  # veto respected
            shadow_pnl=0.0,  # no trade = no loss
            improvement_pct=-pnl_pct,  # improvement = avoiding the loss
        )

    def run_adx_threshold_shadow(
        self,
        *,
        adx_14: float,
        regime: str,
        engine: str,
        pnl_pct: float,
    ) -> Optional[ShadowResult]:
        """Check if ADX threshold gating would have filtered this trade."""
        # Titan requires ADX >= 25 for trending. If ADX was borderline and we lost,
        # a stricter threshold would have saved us.
        if engine != "TITAN" or regime != "TRENDING":
            return None

        if adx_14 >= 30.0:
            return None  # ADX was strong, not the problem

        # Borderline ADX (25-30) and we lost — stricter threshold helps
        return ShadowResult(
            hypothesis=f"Stricter ADX threshold (30 vs 25, actual ADX={adx_14:.1f})",
            adjusted_param="adx_threshold",
            original_value=25.0,
            shadow_value=30.0,
            shadow_pnl=0.0,  # trade would not have been taken
            improvement_pct=-pnl_pct,
        )


# ---------------------------------------------------------------------------
# Failure Diagnoser
# ---------------------------------------------------------------------------


class FailureDiagnoser:
    """Analyzes shadow results to identify the dominant failure mode."""

    def diagnose(
        self,
        *,
        shadows: list[ShadowResult],
        snapshot: MarketSnapshot,
        pnl_pct: float,
    ) -> tuple[FailureMode, float, dict[str, float], dict[str, float]]:
        """Returns (failure_mode, severity, genome_deltas, chiron_nudges)."""

        if not shadows:
            return FailureMode.UNKNOWN, 0.0, {}, {}

        # Sort shadows by improvement — the best counterfactual reveals the cause
        best = max(shadows, key=lambda s: s.improvement_pct)

        genome_deltas: dict[str, float] = {}
        chiron_nudges: dict[str, float] = {}
        severity = min(1.0, abs(best.improvement_pct) / 0.05)  # Normalize to 5% scale

        if best.adjusted_param == "stop_distance":
            if best.shadow_value > best.original_value:
                mode = FailureMode.SL_TOO_TIGHT
                # Nudge SL multiplier wider
                delta = (best.shadow_value - best.original_value) / max(best.original_value, 1e-9)
                genome_deltas["sl_atr_mult"] = min(delta, 0.5)  # Cap adjustment
            else:
                mode = FailureMode.SL_TOO_WIDE
                delta = (best.original_value - best.shadow_value) / max(best.original_value, 1e-9)
                genome_deltas["sl_atr_mult"] = -min(delta, 0.3)
        elif best.adjusted_param == "entry_timing":
            mode = FailureMode.ENTRY_TIMING
            # Nudge confidence threshold up (require more confirmation)
            genome_deltas["confidence_threshold"] = 0.02
        elif best.adjusted_param == "hermes_veto":
            mode = FailureMode.HERMES_VETO_IGNORED
            # Increase Hermes weight in council
            chiron_nudges["HERMES"] = 0.05
            # Decrease the offending engine's weight
            chiron_nudges[snapshot.engine] = -0.03
        elif best.adjusted_param == "adx_threshold":
            mode = FailureMode.ADX_THRESHOLD_WRONG
            genome_deltas["adx_threshold"] = 2.0  # Make it stricter
        else:
            mode = FailureMode.UNKNOWN

        # Additional heuristic checks
        if snapshot.confidence > 0.85 and pnl_pct < -0.02:
            # Overconfident trade that lost big
            if mode == FailureMode.UNKNOWN:
                mode = FailureMode.CONFIDENCE_INFLATED
            genome_deltas["confidence_decay"] = 0.05
            severity = max(severity, 0.7)

        if (
            snapshot.chronos_forecast is not None
            and snapshot.engine in ("TITAN", "NAUTILUS")
        ):
            # Check if oracle was pointing opposite direction
            oracle_dir = 1.0 if snapshot.chronos_forecast > 0 else -1.0
            trade_dir = 1.0 if snapshot.engine == "TITAN" else -1.0  # simplified
            if oracle_dir != trade_dir and pnl_pct < -0.01:
                if mode == FailureMode.UNKNOWN:
                    mode = FailureMode.ORACLE_DIVERGENCE
                chiron_nudges["CHRONOS"] = 0.04

        if snapshot.regime == "TRENDING" and snapshot.hurst_exponent < 0.45:
            if mode == FailureMode.UNKNOWN:
                mode = FailureMode.REGIME_MISMATCH
            chiron_nudges["REGIME"] = 0.03
            severity = max(severity, 0.6)

        return mode, severity, genome_deltas, chiron_nudges


# ---------------------------------------------------------------------------
# Reflector — Main orchestrator
# ---------------------------------------------------------------------------


class Reflector:
    """Post-trade reflection engine.

    For every completed trade:
    1. Captures a MarketSnapshot from the trade's feature vector
    2. Classifies outcome (win/loss/scratch)
    3. For losses: runs shadow simulations to find root cause
    4. Emits a CorrectionVector to adjust Darwin genomes and Chiron weights
    5. Persists the full ReflectionRecord
    6. Tracks failure mode frequencies for Darwin's micro-evolution trigger

    The Reflector is the entry point for the recursive learning loop:
        Execution -> Reflection -> Correction -> Better Execution
    """

    # Minimum loss to trigger full shadow analysis
    LOSS_THRESHOLD = -0.002  # -0.2%
    # Underperformance threshold (actual vs expected)
    UNDERPERFORMANCE_RATIO = 0.3  # Got <30% of expected return

    def __init__(
        self,
        *,
        db_path: str = "runs/argus_reflections.db",
        failure_lookback: int = 20,
        micro_evolution_threshold: int = 5,
    ) -> None:
        self._db_path = db_path
        self._simulator = ShadowSimulator()
        self._diagnoser = FailureDiagnoser()
        self._failure_lookback = failure_lookback
        self._micro_evolution_threshold = micro_evolution_threshold

        # Rolling failure mode counter (for triggering micro-evolution)
        self._recent_failures: list[tuple[str, FailureMode]] = []  # (trade_id, mode)

        self._init_db()

    def _init_db(self) -> None:
        """Create reflections table if not exists."""
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self._db_path)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS reflections (
                reflection_id TEXT PRIMARY KEY,
                trade_id TEXT NOT NULL,
                symbol TEXT NOT NULL,
                asset_class TEXT NOT NULL,
                outcome TEXT NOT NULL,
                pnl_pct REAL NOT NULL,
                failure_mode TEXT,
                severity REAL,
                architectural_regret REAL NOT NULL,
                snapshot_json TEXT NOT NULL,
                shadows_json TEXT NOT NULL,
                correction_json TEXT,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_reflections_symbol
            ON reflections(symbol, created_at)
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_reflections_failure
            ON reflections(failure_mode, created_at)
            """
        )
        conn.commit()
        conn.close()

    def build_snapshot(
        self,
        *,
        features: dict[str, Any],
        regime: str,
        regime_confidence: float,
        regime_stability: float,
        engine: str,
        sub_strategy: str,
        confidence: float,
        stop_distance: float,
        expected_return: float,
    ) -> MarketSnapshot:
        """Construct a MarketSnapshot from a feature dict and trade metadata."""
        return MarketSnapshot(
            regime=regime,
            regime_confidence=regime_confidence,
            regime_stability=regime_stability,
            hermes_sentiment=float(features.get("hermes_sentiment_score", 0.0) or 0.0),
            hermes_urgency=str(features.get("hermes_urgency", "LOW") or "LOW"),
            hermes_action=str(features.get("hermes_action", "NONE") or "NONE"),
            chronos_forecast=features.get("chronos_forecast_1h"),
            chronos_confidence_width=features.get("chronos_confidence_width"),
            adx_14=float(features.get("adx_14", 0.0) or 0.0),
            rsi_14=float(features.get("rsi_14", 50.0) or 50.0),
            bb_pct_b=float(features.get("bb_pct_b", 0.5) or 0.5),
            atr_14_pct=float(features.get("atr_14_pct", 0.02) or 0.02),
            volume_ratio=float(features.get("volume_ratio", 1.0) or 1.0),
            ema_21_vs_55=float(features.get("ema_21_vs_55", 0.0) or 0.0),
            hurst_exponent=float(features.get("hurst_exponent", 0.5) or 0.5),
            funding_rate=features.get("funding_rate"),
            engine=engine,
            sub_strategy=sub_strategy,
            confidence=confidence,
            stop_distance=stop_distance,
            expected_return=expected_return,
        )

    def reflect(
        self,
        *,
        trade_id: str,
        symbol: str,
        asset_class: str,
        side: str,
        entry_price: float,
        exit_price: float,
        pnl_pct: float,
        stop_distance: float,
        expected_return: float,
        snapshot: MarketSnapshot,
        high_low_path: Sequence[tuple[float, float]] = (),
        ohlc_after_entry: Sequence[tuple[float, float, float, float]] = (),
    ) -> ReflectionRecord:
        """Run full post-mortem analysis on a completed trade.

        Parameters
        ----------
        trade_id : Unique trade identifier
        symbol : Trading pair / ticker
        asset_class : crypto | us_equity | commodity | index | bist
        side : "long" | "short"
        entry_price, exit_price : Fill prices
        pnl_pct : Net PnL as fraction (e.g., -0.02 for -2%)
        stop_distance : Original SL distance as fraction
        expected_return : Expected return at entry
        snapshot : MarketSnapshot at time of entry
        high_low_path : Sequence of (high, low) candles during trade lifetime
        ohlc_after_entry : OHLC candles starting from entry (for entry timing shadow)
        """
        # 1. Classify outcome
        outcome = self._classify_outcome(pnl_pct, expected_return)

        # 2. Run shadow simulations (only for losses/underperformance)
        shadows: list[ShadowResult] = []
        correction: Optional[CorrectionVector] = None

        needs_analysis = (
            outcome == "loss"
            or (outcome == "scratch" and pnl_pct < 0)
            or (outcome == "win" and pnl_pct < expected_return * self.UNDERPERFORMANCE_RATIO)
        )

        if needs_analysis:
            shadows = self._run_all_shadows(
                side=side,
                entry_price=entry_price,
                exit_price=exit_price,
                pnl_pct=pnl_pct,
                stop_distance=stop_distance,
                snapshot=snapshot,
                high_low_path=high_low_path,
                ohlc_after_entry=ohlc_after_entry,
            )

            # 3. Diagnose failure
            mode, severity, genome_deltas, chiron_nudges = self._diagnoser.diagnose(
                shadows=shadows,
                snapshot=snapshot,
                pnl_pct=pnl_pct,
            )

            correction = CorrectionVector(
                failure_mode=mode,
                severity=severity,
                genome_deltas=genome_deltas,
                chiron_weight_nudge=chiron_nudges,
                shadow_evidence=shadows,
                trade_id=trade_id,
                symbol=symbol,
                asset_class=asset_class,
                regime=snapshot.regime,
                timestamp=datetime.now(timezone.utc).isoformat(),
            )

            # Track failure mode for micro-evolution trigger
            self._recent_failures.append((trade_id, mode))
            if len(self._recent_failures) > self._failure_lookback:
                self._recent_failures = self._recent_failures[-self._failure_lookback :]

        # 4. Compute architectural regret
        if shadows:
            best_shadow_pnl = max(s.shadow_pnl for s in shadows)
            architectural_regret = max(0.0, best_shadow_pnl - pnl_pct)
        else:
            architectural_regret = 0.0

        # 5. Build record
        now = datetime.now(timezone.utc).isoformat()
        record = ReflectionRecord(
            reflection_id=str(uuid.uuid4()),
            trade_id=trade_id,
            symbol=symbol,
            asset_class=asset_class,
            outcome=outcome,
            pnl_pct=pnl_pct,
            snapshot=snapshot,
            shadows=shadows,
            correction=correction,
            architectural_regret=architectural_regret,
            timestamp=now,
        )

        # 6. Persist
        self._persist(record)

        LOGGER.info(
            "Reflection complete: trade=%s outcome=%s pnl=%.4f regret=%.4f mode=%s",
            trade_id,
            outcome,
            pnl_pct,
            architectural_regret,
            correction.failure_mode.value if correction else "n/a",
        )

        return record

    def should_trigger_micro_evolution(self, failure_mode: FailureMode) -> bool:
        """Check if a specific failure mode has occurred enough times recently
        to warrant a Darwin micro-evolution cycle.

        Returns True if the same failure mode appeared >= micro_evolution_threshold
        times in the last `failure_lookback` trades.
        """
        count = sum(1 for _, m in self._recent_failures if m == failure_mode)
        if count >= self._micro_evolution_threshold:
            LOGGER.warning(
                "Micro-evolution triggered: failure_mode=%s count=%d threshold=%d",
                failure_mode.value,
                count,
                self._micro_evolution_threshold,
            )
            return True
        return False

    def get_failure_distribution(self) -> dict[str, int]:
        """Return frequency count of recent failure modes."""
        dist: dict[str, int] = {}
        for _, mode in self._recent_failures:
            key = mode.value
            dist[key] = dist.get(key, 0) + 1
        return dist

    def get_cumulative_regret(self, last_n: int = 50) -> float:
        """Sum of architectural regret over last N reflections from DB."""
        conn = sqlite3.connect(self._db_path)
        cursor = conn.execute(
            """
            SELECT SUM(architectural_regret)
            FROM (
                SELECT architectural_regret
                FROM reflections
                ORDER BY created_at DESC
                LIMIT ?
            )
            """,
            (last_n,),
        )
        row = cursor.fetchone()
        conn.close()
        return float(row[0]) if row and row[0] is not None else 0.0

    # -------------------------------------------------------------------
    # Private helpers
    # -------------------------------------------------------------------

    def _classify_outcome(self, pnl_pct: float, expected_return: float) -> str:
        if pnl_pct < self.LOSS_THRESHOLD:
            return "loss"
        elif pnl_pct < abs(expected_return) * 0.1:
            return "scratch"
        else:
            return "win"

    def _run_all_shadows(
        self,
        *,
        side: str,
        entry_price: float,
        exit_price: float,
        pnl_pct: float,
        stop_distance: float,
        snapshot: MarketSnapshot,
        high_low_path: Sequence[tuple[float, float]],
        ohlc_after_entry: Sequence[tuple[float, float, float, float]],
    ) -> list[ShadowResult]:
        shadows: list[ShadowResult] = []

        # SL width shadow
        if high_low_path:
            shadows.extend(
                self._simulator.run_sl_shadow(
                    original_sl=stop_distance,
                    entry_price=entry_price,
                    exit_price=exit_price,
                    side=side,
                    high_low_path=high_low_path,
                    atr=snapshot.atr_14_pct,
                )
            )

        # Entry timing shadow
        if ohlc_after_entry:
            shadows.extend(
                self._simulator.run_entry_delay_shadow(
                    entry_price=entry_price,
                    exit_price=exit_price,
                    side=side,
                    ohlc_after_entry=ohlc_after_entry,
                )
            )

        # Hermes veto shadow
        hermes_shadow = self._simulator.run_hermes_veto_shadow(
            hermes_sentiment=snapshot.hermes_sentiment,
            hermes_urgency=snapshot.hermes_urgency,
            hermes_action=snapshot.hermes_action,
            side=side,
            pnl_pct=pnl_pct,
        )
        if hermes_shadow is not None:
            shadows.append(hermes_shadow)

        # ADX threshold shadow
        adx_shadow = self._simulator.run_adx_threshold_shadow(
            adx_14=snapshot.adx_14,
            regime=snapshot.regime,
            engine=snapshot.engine,
            pnl_pct=pnl_pct,
        )
        if adx_shadow is not None:
            shadows.append(adx_shadow)

        return shadows

    def _persist(self, record: ReflectionRecord) -> None:
        """Store reflection in SQLite."""
        import dataclasses

        def _to_dict(obj: Any) -> Any:
            if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
                d = {}
                for f in dataclasses.fields(obj):
                    val = getattr(obj, f.name)
                    d[f.name] = _to_dict(val)
                return d
            if isinstance(obj, list):
                return [_to_dict(v) for v in obj]
            if isinstance(obj, dict):
                return {k: _to_dict(v) for k, v in obj.items()}
            if isinstance(obj, Enum):
                return obj.value
            return obj

        conn = sqlite3.connect(self._db_path)
        conn.execute(
            """
            INSERT OR REPLACE INTO reflections
            (reflection_id, trade_id, symbol, asset_class, outcome, pnl_pct,
             failure_mode, severity, architectural_regret,
             snapshot_json, shadows_json, correction_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.reflection_id,
                record.trade_id,
                record.symbol,
                record.asset_class,
                record.outcome,
                record.pnl_pct,
                record.correction.failure_mode.value if record.correction else None,
                record.correction.severity if record.correction else None,
                record.architectural_regret,
                json.dumps(_to_dict(record.snapshot)),
                json.dumps([_to_dict(s) for s in record.shadows]),
                json.dumps(_to_dict(record.correction)) if record.correction else None,
                record.timestamp,
            ),
        )
        conn.commit()
        conn.close()
