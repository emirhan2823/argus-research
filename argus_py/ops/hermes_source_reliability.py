from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple
import json


def _sign(v: float, threshold: float = 0.0) -> int:
    x = float(v)
    if x > threshold:
        return 1
    if x < -threshold:
        return -1
    return 0


@dataclass(frozen=True)
class SourceReliabilitySnapshot:
    source: str
    total: int
    hits: int
    misses: int
    reliability: float
    last_updated_utc: Optional[str]


@dataclass(frozen=True)
class AdjustedHermesScore:
    source: str
    raw_score: float
    adjusted_score: float
    reliability: float
    multiplier: float


class HermesSourceReliability:
    """
    Track source-level predictive reliability and adjust sentiment score weights.

    - reliability in [0..1], Bayesian-smoothed with prior.
    - multiplier in [min_mult..max_mult], centered at 1.0 when reliability == prior.
    """

    def __init__(
        self,
        storage_path: Path,
        *,
        prior_reliability: float = 0.5,
        prior_weight: int = 6,
        min_multiplier: float = 0.75,
        max_multiplier: float = 1.25,
    ) -> None:
        self.storage_path = Path(storage_path)
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self.prior_reliability = max(0.0, min(1.0, float(prior_reliability)))
        self.prior_weight = max(1, int(prior_weight))
        self.min_multiplier = float(min_multiplier)
        self.max_multiplier = float(max_multiplier)
        self._state: Dict[str, Dict[str, object]] = {}
        self._load()

    def adjust_score(self, source: str, raw_score: float) -> AdjustedHermesScore:
        src = str(source or "unknown").strip().lower() or "unknown"
        rel = self.reliability(src)
        centered = (rel - self.prior_reliability)
        multiplier = 1.0 + centered
        multiplier = max(self.min_multiplier, min(self.max_multiplier, multiplier))
        adjusted = float(raw_score) * float(multiplier)
        return AdjustedHermesScore(
            source=src,
            raw_score=float(raw_score),
            adjusted_score=float(max(-100.0, min(100.0, adjusted))),
            reliability=float(rel),
            multiplier=float(multiplier),
        )

    def adjust_many(self, items: Iterable[Tuple[str, float]]) -> List[AdjustedHermesScore]:
        return [self.adjust_score(source=s, raw_score=v) for s, v in items]

    def record_outcome(
        self,
        source: str,
        *,
        predicted_score: float,
        realized_return_bps: float,
        prediction_threshold: float = 8.0,
        realized_threshold: float = 5.0,
    ) -> None:
        src = str(source or "unknown").strip().lower() or "unknown"
        pred = _sign(float(predicted_score), threshold=float(prediction_threshold))
        real = _sign(float(realized_return_bps), threshold=float(realized_threshold))
        if pred == 0 or real == 0:
            return
        row = self._state.setdefault(
            src,
            {
                "total": 0,
                "hits": 0,
                "misses": 0,
                "last_updated_utc": None,
            },
        )
        row["total"] = int(row.get("total", 0)) + 1
        if pred == real:
            row["hits"] = int(row.get("hits", 0)) + 1
        else:
            row["misses"] = int(row.get("misses", 0)) + 1
        row["last_updated_utc"] = datetime.now(timezone.utc).isoformat()
        self._save()

    def reliability(self, source: str) -> float:
        src = str(source or "unknown").strip().lower() or "unknown"
        row = self._state.get(src)
        if row is None:
            return float(self.prior_reliability)
        total = int(row.get("total", 0))
        hits = int(row.get("hits", 0))
        alpha0 = self.prior_reliability * self.prior_weight
        beta0 = (1.0 - self.prior_reliability) * self.prior_weight
        return float((hits + alpha0) / max(1e-9, total + alpha0 + beta0))

    def summary(self, top_n: int = 5) -> Dict[str, object]:
        rows: List[SourceReliabilitySnapshot] = []
        for source, data in self._state.items():
            rows.append(
                SourceReliabilitySnapshot(
                    source=source,
                    total=int(data.get("total", 0)),
                    hits=int(data.get("hits", 0)),
                    misses=int(data.get("misses", 0)),
                    reliability=self.reliability(source),
                    last_updated_utc=data.get("last_updated_utc"),
                )
            )
        rows.sort(key=lambda x: (x.reliability, x.total), reverse=True)
        top = rows[: max(0, int(top_n))]
        bottom = list(reversed(rows[-max(0, int(top_n)) :])) if rows else []
        return {
            "sources": [asdict(x) for x in rows],
            "top": [asdict(x) for x in top],
            "bottom": [asdict(x) for x in bottom],
        }

    def _load(self) -> None:
        if not self.storage_path.exists():
            self._state = {}
            return
        try:
            payload = json.loads(self.storage_path.read_text(encoding="utf-8"))
            state = payload.get("state", {})
            if isinstance(state, dict):
                self._state = state
            else:
                self._state = {}
        except Exception:
            self._state = {}

    def _save(self) -> None:
        payload = {
            "updated_at_utc": datetime.now(timezone.utc).isoformat(),
            "prior_reliability": self.prior_reliability,
            "prior_weight": self.prior_weight,
            "state": self._state,
        }
        self.storage_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")


__all__ = [
    "HermesSourceReliability",
    "AdjustedHermesScore",
    "SourceReliabilitySnapshot",
]
