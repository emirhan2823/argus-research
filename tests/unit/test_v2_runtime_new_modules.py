from __future__ import annotations

from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from argus_py.data.market_state import Bar
from argus_py.runner.v2_runtime import V2RuntimeBridge


class _DummyBroker:
    def __init__(self) -> None:
        self.details = {}

    def execute_strategy(self, **kwargs):  # pragma: no cover - not called in this test
        return False, "disabled"


def _bars(n: int = 80) -> list[Bar]:
    out: list[Bar] = []
    ts0 = 1_700_000_000.0
    price = 100.0
    for i in range(n):
        prev = price
        price = price + 1.8 + ((i % 5) - 2) * 0.01
        out.append(
            Bar(
                timestamp=ts0 + i * 60.0,
                open=prev,
                high=max(prev, price) + 0.2,
                low=min(prev, price) - 0.2,
                close=price,
                volume=1500.0 + i,
            )
        )
    return out


def test_v2_runtime_tracks_hermes_reliability_and_model_promotion(tmp_path) -> None:
    run_dir = tmp_path / "run"
    cfg = {
        "asset_class": "crypto",
        "venue_id": "sim",
        "model_strategy_id": "COUNCIL_BASELINE",
        "model_champion_id": "MODEL_BASE",
        "model_challenger_id": "MODEL_NEW",
        "model_challenger_expectancy_delta": 0.08,
        "model_challenger_sharpe_delta": 0.2,
        "model_challenger_max_dd_delta": -0.2,
    }
    bridge = V2RuntimeBridge(cfg, run_dir, _DummyBroker())

    snapshot = bridge.compute_market_snapshot(_bars(90))
    assert snapshot is not None
    assert snapshot.hermes_score > 8.0

    bridge.observe_trade(
        regime=snapshot.regime_v2,
        engine_signals={"atlas": 20.0, "aether": 10.0, "hermes": 55.0},
        pnl=25.0,
        timestamp=1_700_000_000.0,
    )
    assert (run_dir / "hermes_source_reliability.json").exists()

    bridge.evaluate_lifecycle(
        strategy_id="COUNCIL_BASELINE",
        trades=120,
        expectancy=0.09,
        sharpe=1.25,
        max_dd_pct=3.2,
        error_rate_pct=0.2,
        telemetry_stale_sec=5.0,
        hard_risk_violations=0,
        consecutive_loss_days=0,
    )
    payload = bridge.metrics_payload()

    assert payload["hermes_source"] == "synthetic_keyword"
    assert 0.0 <= float(payload["hermes_source_reliability"]) <= 1.0
    assert payload["model_registry"]["active_model"] == "MODEL_NEW"
    assert payload["model_registry"]["promotion"]["action"] == "PROMOTE_CHALLENGER"
    assert bridge.event_counts.get("ALERT", 0) >= 1
    assert (run_dir / "model_registry.json").exists()
