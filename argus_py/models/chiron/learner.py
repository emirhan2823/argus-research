from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import csv
import json
import numpy as np


@dataclass
class TradeOutcome:
    timestamp: int
    symbol: str
    regime: str
    engine_scores: Dict[str, float]
    verdict: str
    pnl: float
    hold_duration: float


@dataclass
class LearningRecord:
    regime: str
    weights: Dict[str, float]
    sample_count: int
    avg_pnl: float
    win_rate: float
    sharpe: float
    last_updated: str


class ChironLearner:
    """
    ML-based weight optimizer for Council voting.

    Uses historical trade outcomes to optimize engine weights per regime.
    """

    def __init__(self, state_path: Optional[Path] = None):
        self.state_path = Path(state_path) if state_path else None
        self.records: Dict[str, LearningRecord] = {}
        self.outcomes: List[TradeOutcome] = []

        if self.state_path and self.state_path.exists():
            self.load_state()

    def add_outcome(self, outcome: TradeOutcome) -> None:
        self.outcomes.append(outcome)

    def optimize_weights(self, regime: str, min_samples: int = 30) -> Optional[Dict[str, float]]:
        regime_outcomes = [o for o in self.outcomes if o.regime == regime]

        if len(regime_outcomes) < min_samples:
            return None

        engines = ["orion", "aether", "hermes", "phoenix", "aegean"]
        X = np.array([[o.engine_scores.get(e, 50.0) for e in engines] for o in regime_outcomes], dtype=float)
        y = np.array([o.pnl for o in regime_outcomes], dtype=float)

        best_weights = self._optimize_correlation(X, y, engines)

        win_rate = float(np.mean(y > 0)) if len(y) else 0.0
        avg_pnl = float(np.mean(y)) if len(y) else 0.0
        sharpe = float(np.mean(y) / np.std(y)) if np.std(y) > 0 else 0.0

        self.records[regime] = LearningRecord(
            regime=regime,
            weights=best_weights,
            sample_count=len(regime_outcomes),
            avg_pnl=avg_pnl,
            win_rate=win_rate,
            sharpe=sharpe,
            last_updated=datetime.now().isoformat(),
        )

        return best_weights

    def _optimize_correlation(self, X: np.ndarray, y: np.ndarray, engines: List[str]) -> Dict[str, float]:
        weights: Dict[str, float] = {}

        for i, engine in enumerate(engines):
            scores = X[:, i]

            if np.std(scores) > 0 and np.std(y) > 0:
                corr = float(np.corrcoef(scores, y)[0, 1])
                if np.isnan(corr):
                    corr = 0.0
            else:
                corr = 0.0

            weights[engine] = max(0.1, min(0.4, 0.25 + corr * 0.15))

        total = float(sum(weights.values()))
        if total <= 0:
            return {k: 1.0 / len(weights) for k in weights}

        return {k: v / total for k, v in weights.items()}

    def get_optimal_weights(self, regime: str) -> Optional[Dict[str, float]]:
        if regime in self.records:
            return dict(self.records[regime].weights)
        return None

    def load_outcomes_from_csv(self, trades_csv: Path, decisions_csv: Path) -> int:
        decisions: Dict[str, dict] = {}

        if Path(decisions_csv).exists():
            with Path(decisions_csv).open("r", newline="", encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    key = row.get("bar_ts_iso") or row.get("bar_ts") or row.get("ts_iso") or ""
                    symbol = row.get("symbol", "")
                    decisions[f"{key}|{symbol}"] = row

        count = 0
        if not Path(trades_csv).exists():
            return 0

        with Path(trades_csv).open("r", newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                event = (row.get("event") or "").upper()
                if event not in {"CLOSE", "REJECTED"}:
                    continue

                symbol = row.get("symbol", "")
                pnl = float(row.get("pnl", 0.0) or 0.0)

                # Build soft join key by timestamp columns where available.
                key_time = row.get("bar_ts_iso") or row.get("ts_iso") or row.get("timestamp") or ""
                drow = decisions.get(f"{key_time}|{symbol}")

                regime = "TREND"
                scores = {}
                verdict = "GO"
                if drow:
                    regime = drow.get("regime", "TREND") or "TREND"
                    verdict = drow.get("decision", "GO") or "GO"
                    scores = {
                        "orion": float(drow.get("adx", 50) or 50),
                        "aether": 50.0,
                        "hermes": 50.0,
                        "phoenix": float(drow.get("exp_move", 50) or 50),
                        "aegean": float(drow.get("score", 50) or 50),
                    }

                ts_raw = row.get("timestamp") or row.get("ts") or 0
                try:
                    timestamp = int(float(ts_raw))
                except Exception:
                    timestamp = 0

                self.outcomes.append(
                    TradeOutcome(
                        timestamp=timestamp,
                        symbol=symbol,
                        regime=regime,
                        engine_scores=scores,
                        verdict=verdict,
                        pnl=pnl,
                        hold_duration=0.0,
                    )
                )
                count += 1

        return count

    def save_state(self) -> None:
        if not self.state_path:
            return

        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        state = {
            "records": {
                k: {
                    "regime": v.regime,
                    "weights": v.weights,
                    "sample_count": v.sample_count,
                    "avg_pnl": v.avg_pnl,
                    "win_rate": v.win_rate,
                    "sharpe": v.sharpe,
                    "last_updated": v.last_updated,
                }
                for k, v in self.records.items()
            },
            "outcomes_count": len(self.outcomes),
        }

        self.state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")

    def load_state(self) -> None:
        if not self.state_path or not self.state_path.exists():
            return

        state = json.loads(self.state_path.read_text(encoding="utf-8"))

        for k, v in state.get("records", {}).items():
            self.records[k] = LearningRecord(**v)
