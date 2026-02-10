from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional
import json


@dataclass(frozen=True)
class ModelMetrics:
    strategy_id: str
    model_id: str
    trades: int
    expectancy: float
    sharpe: float
    max_dd_pct: float
    win_rate: float
    ts_utc: str


@dataclass(frozen=True)
class PromotionDecision:
    action: str
    strategy_id: str
    champion_before: Optional[str]
    champion_after: Optional[str]
    reason: str


class ModelRegistry:
    """
    Champion/Challenger registry with deterministic promotion policy.
    """

    def __init__(
        self,
        path: Path,
        *,
        min_trades_for_promotion: int = 80,
        min_expectancy_edge: float = 0.03,
        min_sharpe_edge: float = 0.10,
        max_dd_guard_pct: float = 8.0,
    ) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.min_trades_for_promotion = int(min_trades_for_promotion)
        self.min_expectancy_edge = float(min_expectancy_edge)
        self.min_sharpe_edge = float(min_sharpe_edge)
        self.max_dd_guard_pct = float(max_dd_guard_pct)
        self._state: Dict[str, object] = {"strategies": {}}
        self._load()

    def ensure_champion(self, strategy_id: str, model_id: str) -> None:
        st = self._strategy_state(strategy_id)
        if st.get("champion") is None:
            st["champion"] = str(model_id)
            self._save()

    def register_challenger(self, strategy_id: str, model_id: str) -> None:
        st = self._strategy_state(strategy_id)
        challengers = st.setdefault("challengers", {})
        if str(model_id) not in challengers:
            challengers[str(model_id)] = {"history": []}
            self._save()

    def record_metrics(self, m: ModelMetrics) -> None:
        st = self._strategy_state(m.strategy_id)
        model_id = str(m.model_id)
        if st.get("champion") == model_id:
            ch_hist = st.setdefault("champion_history", [])
            ch_hist.append(asdict(m))
            st["champion_history"] = ch_hist[-200:]
        else:
            challengers = st.setdefault("challengers", {})
            if model_id not in challengers:
                challengers[model_id] = {"history": []}
            hist = challengers[model_id].setdefault("history", [])
            hist.append(asdict(m))
            challengers[model_id]["history"] = hist[-200:]
            st["challengers"] = challengers
        self._save()

    def evaluate(self, strategy_id: str) -> PromotionDecision:
        st = self._strategy_state(strategy_id)
        champion = st.get("champion")
        champion_metrics = self._latest_champion_metrics(st)
        challenger_best = self._best_challenger_metrics(st)

        if champion is None:
            if challenger_best is None:
                return PromotionDecision("KEEP", strategy_id, None, None, "No champion and no challenger metrics.")
            if challenger_best.trades < self.min_trades_for_promotion:
                return PromotionDecision("KEEP", strategy_id, None, None, "Challenger has insufficient trades.")
            st["champion"] = challenger_best.model_id
            if challenger_best.model_id in st.get("challengers", {}):
                del st["challengers"][challenger_best.model_id]
            self._save()
            return PromotionDecision(
                "PROMOTE_CHALLENGER",
                strategy_id,
                None,
                challenger_best.model_id,
                "No champion existed; challenger promoted.",
            )

        if champion_metrics is None or challenger_best is None:
            return PromotionDecision("KEEP", strategy_id, str(champion), str(champion), "Missing champion/challenger metrics.")

        if challenger_best.trades < self.min_trades_for_promotion:
            return PromotionDecision("KEEP", strategy_id, str(champion), str(champion), "Challenger trades below threshold.")

        if challenger_best.max_dd_pct > self.max_dd_guard_pct:
            return PromotionDecision("KEEP", strategy_id, str(champion), str(champion), "Challenger drawdown too high.")

        exp_ok = challenger_best.expectancy >= (champion_metrics.expectancy + self.min_expectancy_edge)
        sharpe_ok = challenger_best.sharpe >= (champion_metrics.sharpe + self.min_sharpe_edge)
        dd_ok = challenger_best.max_dd_pct <= (champion_metrics.max_dd_pct + 0.50)
        if exp_ok and sharpe_ok and dd_ok:
            prev = str(champion)
            st["champion"] = challenger_best.model_id
            challengers = st.setdefault("challengers", {})
            challengers[prev] = {"history": st.get("champion_history", [])[-120:]}
            if challenger_best.model_id in challengers:
                del challengers[challenger_best.model_id]
            st["challengers"] = challengers
            self._save()
            return PromotionDecision(
                "PROMOTE_CHALLENGER",
                strategy_id,
                prev,
                challenger_best.model_id,
                "Challenger outperformed champion on expectancy/sharpe with controlled DD.",
            )

        return PromotionDecision("KEEP", strategy_id, str(champion), str(champion), "Champion retained.")

    def active_model(self, strategy_id: str) -> Optional[str]:
        st = self._strategy_state(strategy_id)
        champion = st.get("champion")
        return str(champion) if champion else None

    def summary(self) -> Dict[str, object]:
        return dict(self._state)

    def _strategy_state(self, strategy_id: str) -> Dict[str, object]:
        strategies = self._state.setdefault("strategies", {})
        if strategy_id not in strategies:
            strategies[strategy_id] = {
                "champion": None,
                "champion_history": [],
                "challengers": {},
            }
        return strategies[strategy_id]

    @staticmethod
    def _to_metrics(payload: Dict[str, object]) -> ModelMetrics:
        return ModelMetrics(
            strategy_id=str(payload.get("strategy_id")),
            model_id=str(payload.get("model_id")),
            trades=int(payload.get("trades", 0)),
            expectancy=float(payload.get("expectancy", 0.0)),
            sharpe=float(payload.get("sharpe", 0.0)),
            max_dd_pct=float(payload.get("max_dd_pct", 0.0)),
            win_rate=float(payload.get("win_rate", 0.0)),
            ts_utc=str(payload.get("ts_utc", "")),
        )

    def _latest_champion_metrics(self, st: Dict[str, object]) -> Optional[ModelMetrics]:
        hist = st.get("champion_history", [])
        if not hist:
            return None
        return self._to_metrics(hist[-1])

    def _best_challenger_metrics(self, st: Dict[str, object]) -> Optional[ModelMetrics]:
        challengers = st.get("challengers", {})
        best: Optional[ModelMetrics] = None
        for model_id, row in challengers.items():
            hist = row.get("history", [])
            if not hist:
                continue
            m = self._to_metrics(hist[-1])
            if best is None:
                best = m
                continue
            if m.expectancy > best.expectancy:
                best = m
                continue
            if m.expectancy == best.expectancy and m.sharpe > best.sharpe:
                best = m
        return best

    def _load(self) -> None:
        if not self.path.exists():
            self._state = {"strategies": {}}
            return
        try:
            self._state = json.loads(self.path.read_text(encoding="utf-8"))
            if "strategies" not in self._state:
                self._state["strategies"] = {}
        except Exception:
            self._state = {"strategies": {}}

    def _save(self) -> None:
        payload = dict(self._state)
        payload["updated_at_utc"] = datetime.now(timezone.utc).isoformat()
        self.path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")


def metrics_now(
    *,
    strategy_id: str,
    model_id: str,
    trades: int,
    expectancy: float,
    sharpe: float,
    max_dd_pct: float,
    win_rate: float = 0.0,
) -> ModelMetrics:
    return ModelMetrics(
        strategy_id=strategy_id,
        model_id=model_id,
        trades=int(trades),
        expectancy=float(expectancy),
        sharpe=float(sharpe),
        max_dd_pct=float(max_dd_pct),
        win_rate=float(win_rate),
        ts_utc=datetime.now(timezone.utc).isoformat(),
    )


__all__ = [
    "ModelRegistry",
    "ModelMetrics",
    "PromotionDecision",
    "metrics_now",
]
