from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence

import json
import logging
import numpy as np

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class LearningSample:
    regime: str
    pnl: float
    engine_signals: Dict[str, float]
    timestamp: Optional[float] = None


@dataclass(frozen=True)
class RegimeOptimizationResult:
    regime: str
    weights: Dict[str, float]
    objective: float
    sharpe: float
    max_drawdown: float
    sample_count: int
    generated_at: str


class ChironLearningEngine:
    """
    Learns regime-specific council weights with Sharpe/DD-aware objective.

    The optimizer runs deterministic coordinate search on simplex weights and
    favors configurations that maximize risk-adjusted returns while penalizing
    drawdown.
    """

    def __init__(
        self,
        engine_names: Optional[Sequence[str]] = None,
        drawdown_penalty: float = 0.8,
    ) -> None:
        self.engine_names = [
            str(x).lower()
            for x in (
                engine_names
                or ["orion", "aegean", "phoenix", "hermes", "aether", "atlas"]
            )
        ]
        self.drawdown_penalty = float(drawdown_penalty)
        self._samples: List[LearningSample] = []
        self._results: Dict[str, RegimeOptimizationResult] = {}

    def add_sample(self, sample: LearningSample) -> None:
        self._samples.append(sample)

    def add_samples(self, samples: Iterable[LearningSample]) -> None:
        for sample in samples:
            self.add_sample(sample)

    def optimize_regime(
        self,
        regime: str,
        min_samples: int = 40,
        step: float = 0.05,
        max_passes: int = 80,
    ) -> Optional[RegimeOptimizationResult]:
        regime_u = str(regime).upper()
        samples = [s for s in self._samples if str(s.regime).upper() == regime_u]
        if len(samples) < min_samples:
            LOGGER.info(
                "Chiron optimize skipped: regime=%s samples=%d < min_samples=%d",
                regime_u,
                len(samples),
                min_samples,
            )
            return None

        X, y = self._build_matrix(samples)
        weights = np.full(len(self.engine_names), 1.0 / len(self.engine_names), dtype=float)
        best_obj, best_sharpe, best_dd = self._objective(X, y, weights)

        improved = True
        passes = 0
        while improved and passes < max_passes:
            improved = False
            passes += 1
            for i in range(len(weights)):
                for j in range(len(weights)):
                    if i == j or weights[j] < step:
                        continue
                    candidate = weights.copy()
                    candidate[i] += step
                    candidate[j] -= step
                    obj, sharpe, max_dd = self._objective(X, y, candidate)
                    if obj > best_obj + 1e-12:
                        weights = candidate
                        best_obj, best_sharpe, best_dd = obj, sharpe, max_dd
                        improved = True

        result = RegimeOptimizationResult(
            regime=regime_u,
            weights=self._normalize_weight_dict(dict(zip(self.engine_names, weights.tolist()))),
            objective=float(best_obj),
            sharpe=float(best_sharpe),
            max_drawdown=float(best_dd),
            sample_count=len(samples),
            generated_at=datetime.now(timezone.utc).isoformat(),
        )
        self._results[regime_u] = result
        return result

    def optimize_all(self, min_samples: int = 40) -> Dict[str, RegimeOptimizationResult]:
        regimes = sorted({str(s.regime).upper() for s in self._samples})
        out: Dict[str, RegimeOptimizationResult] = {}
        for regime in regimes:
            res = self.optimize_regime(regime=regime, min_samples=min_samples)
            if res is not None:
                out[regime] = res
        return out

    def get_weights(self, regime: str) -> Optional[Dict[str, float]]:
        result = self._results.get(str(regime).upper())
        if result is None:
            return None
        return dict(result.weights)

    def save(self, path: Path) -> None:
        payload = {
            "engine_names": self.engine_names,
            "drawdown_penalty": self.drawdown_penalty,
            "results": {
                key: {
                    "regime": value.regime,
                    "weights": value.weights,
                    "objective": value.objective,
                    "sharpe": value.sharpe,
                    "max_drawdown": value.max_drawdown,
                    "sample_count": value.sample_count,
                    "generated_at": value.generated_at,
                }
                for key, value in self._results.items()
            },
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "ChironLearningEngine":
        payload = json.loads(path.read_text(encoding="utf-8"))
        engine = cls(
            engine_names=payload.get("engine_names"),
            drawdown_penalty=float(payload.get("drawdown_penalty", 0.8)),
        )
        for key, raw in (payload.get("results") or {}).items():
            result = RegimeOptimizationResult(
                regime=str(raw["regime"]),
                weights={str(k): float(v) for k, v in dict(raw["weights"]).items()},
                objective=float(raw["objective"]),
                sharpe=float(raw["sharpe"]),
                max_drawdown=float(raw["max_drawdown"]),
                sample_count=int(raw["sample_count"]),
                generated_at=str(raw["generated_at"]),
            )
            engine._results[str(key).upper()] = result
        return engine

    def _build_matrix(self, samples: Sequence[LearningSample]) -> tuple[np.ndarray, np.ndarray]:
        rows: List[List[float]] = []
        pnl: List[float] = []
        for sample in samples:
            row: List[float] = []
            for engine in self.engine_names:
                raw = float(sample.engine_signals.get(engine, 0.0))
                row.append(float(np.clip(raw / 100.0, -1.0, 1.0)))
            rows.append(row)
            pnl.append(float(sample.pnl))

        X = np.asarray(rows, dtype=float)
        y = np.asarray(pnl, dtype=float)
        return X, y

    def _objective(self, X: np.ndarray, y: np.ndarray, weights: np.ndarray) -> tuple[float, float, float]:
        score = X.dot(weights)
        direction = np.sign(score)
        direction[direction == 0.0] = 1.0
        strategy_returns = direction * y

        mean_ret = float(np.mean(strategy_returns))
        std_ret = float(np.std(strategy_returns, ddof=1)) if len(strategy_returns) > 1 else 0.0
        sharpe = (mean_ret / std_ret) if std_ret > 1e-12 else 0.0
        max_dd = self._max_drawdown(strategy_returns)
        objective = sharpe - (self.drawdown_penalty * max_dd)
        return float(objective), float(sharpe), float(max_dd)

    @staticmethod
    def _max_drawdown(returns: np.ndarray) -> float:
        if returns.size == 0:
            return 0.0
        equity = np.cumsum(returns)
        peak = np.maximum.accumulate(equity)
        dd = peak - equity
        return float(np.max(dd)) if dd.size else 0.0

    @staticmethod
    def _normalize_weight_dict(weights: Dict[str, float]) -> Dict[str, float]:
        total = float(sum(max(0.0, float(v)) for v in weights.values()))
        if total <= 1e-12:
            k = len(weights)
            return {name: (1.0 / k if k else 0.0) for name in weights}
        return {name: max(0.0, float(value)) / total for name, value in weights.items()}
