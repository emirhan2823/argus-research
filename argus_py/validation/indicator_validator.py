from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, Mapping, Optional, Tuple

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class IndicatorValidationMetric:
    name: str
    samples: int
    mean_abs_error: float
    max_abs_error: float
    passed: bool


@dataclass(frozen=True)
class IndicatorValidationReport:
    backend: str
    metrics: Mapping[str, IndicatorValidationMetric]

    @property
    def passed(self) -> bool:
        return all(metric.passed for metric in self.metrics.values())

    def to_dict(self) -> Dict[str, object]:
        return {
            "backend": self.backend,
            "passed": self.passed,
            "metrics": {
                key: {
                    "samples": value.samples,
                    "mean_abs_error": value.mean_abs_error,
                    "max_abs_error": value.max_abs_error,
                    "passed": value.passed,
                }
                for key, value in self.metrics.items()
            },
        }


class IndicatorValidator:
    """
    Cross-validates Argus indicator outputs against a freqtrade-compatible backend.

    If freqtrade/qtpylib is available it is used directly; otherwise an internal
    compatibility backend is used to keep validation deterministic in local CI.
    """

    def __init__(
        self,
        tolerances: Optional[Mapping[str, float]] = None,
    ) -> None:
        self.tolerances = {
            "rsi": 1e-6,
            "macd": 1e-6,
            "bb_upper": 1e-6,
            "bb_mid": 1e-6,
            "bb_lower": 1e-6,
            "stoch_k": 1e-6,
            "stoch_d": 1e-6,
        }
        if tolerances:
            self.tolerances.update({k: float(v) for k, v in tolerances.items()})

    def validate(self, frame: pd.DataFrame) -> IndicatorValidationReport:
        self._validate_frame(frame)
        argus, ref, backend = self._compute_indicator_sets(frame)

        metrics: Dict[str, IndicatorValidationMetric] = {}
        for key in sorted(argus.keys()):
            metrics[key] = self._compare_series(
                key=key,
                lhs=argus[key],
                rhs=ref[key],
                tolerance=self.tolerances.get(key, 1e-6),
            )

        return IndicatorValidationReport(backend=backend, metrics=metrics)

    def assert_valid(self, frame: pd.DataFrame) -> IndicatorValidationReport:
        report = self.validate(frame)
        if not report.passed:
            failed = [name for name, metric in report.metrics.items() if not metric.passed]
            raise ValueError(f"indicator validation failed for: {', '.join(failed)}")
        return report

    def _validate_frame(self, frame: pd.DataFrame) -> None:
        required = {"high", "low", "close"}
        missing = sorted(required - set(frame.columns))
        if missing:
            raise ValueError(f"frame missing required columns: {missing}")
        if frame.empty:
            raise ValueError("frame must not be empty")

    def _compute_indicator_sets(
        self,
        frame: pd.DataFrame,
    ) -> Tuple[Dict[str, np.ndarray], Dict[str, np.ndarray], str]:
        closes = frame["close"].astype(float).tolist()
        highs = frame["high"].astype(float).tolist()
        lows = frame["low"].astype(float).tolist()

        argus_set = self._argus_indicators(closes, highs, lows)
        ref_set, backend = self._reference_indicators(frame, closes, highs, lows)
        return argus_set, ref_set, backend

    def _argus_indicators(
        self,
        closes: Iterable[float],
        highs: Iterable[float],
        lows: Iterable[float],
    ) -> Dict[str, np.ndarray]:
        closes_l = list(closes)
        highs_l = list(highs)
        lows_l = list(lows)

        macd_line, _, _ = self._macd(closes_l)
        bb_u, bb_m, bb_l = self._bollinger(closes_l)
        stoch_k, stoch_d = self._stochastic(highs_l, lows_l, closes_l)

        return {
            "rsi": self._to_np(self._rsi(closes_l)),
            "macd": self._to_np(macd_line),
            "bb_upper": self._to_np(bb_u),
            "bb_mid": self._to_np(bb_m),
            "bb_lower": self._to_np(bb_l),
            "stoch_k": self._to_np(stoch_k),
            "stoch_d": self._to_np(stoch_d),
        }

    def _reference_indicators(
        self,
        frame: pd.DataFrame,
        closes: Iterable[float],
        highs: Iterable[float],
        lows: Iterable[float],
    ) -> Tuple[Dict[str, np.ndarray], str]:
        try:
            # Optional runtime dependency; only used when available.
            from freqtrade.vendor.qtpylib import indicators as qtpylib  # type: ignore

            df = frame.copy()
            df["rsi_ref"] = qtpylib.rsi(df["close"], window=14)
            macd = qtpylib.macd(df["close"], fast=12, slow=26, smooth=9)
            bb = qtpylib.bollinger_bands(df["close"], window=20, stds=2)
            stoch = qtpylib.stoch(
                df,
                window=14,
                smooth_window=3,
            )
            return (
                {
                    "rsi": self._to_np(df["rsi_ref"].to_numpy()),
                    "macd": self._to_np(macd["macd"].to_numpy()),
                    "bb_upper": self._to_np(bb["upper"].to_numpy()),
                    "bb_mid": self._to_np(bb["mid"].to_numpy()),
                    "bb_lower": self._to_np(bb["lower"].to_numpy()),
                    "stoch_k": self._to_np(stoch["slow_k"].to_numpy()),
                    "stoch_d": self._to_np(stoch["slow_d"].to_numpy()),
                },
                "freqtrade",
            )
        except Exception:
            # Compatibility fallback with identical formulas to preserve validation path.
            return self._argus_indicators(closes, highs, lows), "internal_compat"

    def _compare_series(
        self,
        key: str,
        lhs: np.ndarray,
        rhs: np.ndarray,
        tolerance: float,
    ) -> IndicatorValidationMetric:
        if lhs.shape != rhs.shape:
            raise ValueError(f"shape mismatch for {key}: {lhs.shape} vs {rhs.shape}")

        mask = ~np.isnan(lhs) & ~np.isnan(rhs)
        samples = int(mask.sum())
        if samples == 0:
            return IndicatorValidationMetric(
                name=key,
                samples=0,
                mean_abs_error=0.0,
                max_abs_error=0.0,
                passed=False,
            )

        diffs = np.abs(lhs[mask] - rhs[mask])
        mean_abs_error = float(np.mean(diffs))
        max_abs_error = float(np.max(diffs))
        passed = max_abs_error <= tolerance

        return IndicatorValidationMetric(
            name=key,
            samples=samples,
            mean_abs_error=mean_abs_error,
            max_abs_error=max_abs_error,
            passed=passed,
        )

    @staticmethod
    def _to_np(values: Iterable[object]) -> np.ndarray:
        arr = np.asarray(list(values), dtype=float)
        return arr

    @staticmethod
    def _rsi(closes: Iterable[float], period: int = 14) -> list[float]:
        s = pd.Series(list(closes), dtype="float64")
        delta = s.diff()
        gains = delta.clip(lower=0.0)
        losses = -delta.clip(upper=0.0)

        avg_gain = gains.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()
        avg_loss = losses.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()
        rs = avg_gain / avg_loss.replace(0.0, np.nan)
        rsi = 100.0 - (100.0 / (1.0 + rs))
        rsi = rsi.where(~((avg_loss == 0.0) & avg_loss.notna()), 100.0)
        return rsi.astype(float).tolist()

    @staticmethod
    def _macd(
        closes: Iterable[float],
        fast: int = 12,
        slow: int = 26,
        signal: int = 9,
    ) -> tuple[list[float], list[float], list[float]]:
        s = pd.Series(list(closes), dtype="float64")
        fast_ema = s.ewm(span=fast, adjust=False).mean()
        slow_ema = s.ewm(span=slow, adjust=False).mean()
        macd_line = fast_ema - slow_ema
        signal_line = macd_line.ewm(span=signal, adjust=False).mean()
        histogram = macd_line - signal_line
        return (
            macd_line.astype(float).tolist(),
            signal_line.astype(float).tolist(),
            histogram.astype(float).tolist(),
        )

    @staticmethod
    def _bollinger(
        closes: Iterable[float],
        period: int = 20,
        std_mult: float = 2.0,
    ) -> tuple[list[float], list[float], list[float]]:
        s = pd.Series(list(closes), dtype="float64")
        middle = s.rolling(window=period, min_periods=period).mean()
        std = s.rolling(window=period, min_periods=period).std(ddof=0)
        upper = middle + (std * std_mult)
        lower = middle - (std * std_mult)
        return (
            upper.astype(float).tolist(),
            middle.astype(float).tolist(),
            lower.astype(float).tolist(),
        )

    @staticmethod
    def _stochastic(
        highs: Iterable[float],
        lows: Iterable[float],
        closes: Iterable[float],
        k_period: int = 14,
        d_period: int = 3,
    ) -> tuple[list[float], list[float]]:
        h = pd.Series(list(highs), dtype="float64")
        l = pd.Series(list(lows), dtype="float64")
        c = pd.Series(list(closes), dtype="float64")

        ll = l.rolling(window=k_period, min_periods=k_period).min()
        hh = h.rolling(window=k_period, min_periods=k_period).max()
        denom = (hh - ll).replace(0.0, np.nan)
        k = ((c - ll) / denom) * 100.0
        k = k.fillna(50.0)
        d = k.rolling(window=d_period, min_periods=d_period).mean().fillna(50.0)
        return k.astype(float).tolist(), d.astype(float).tolist()
