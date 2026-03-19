from __future__ import annotations

import json
from argparse import Namespace
from pathlib import Path
import sys

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from Scripts.paper_daemon import DEFAULT_CONFIG, PaperDaemon


def _cfg(tmp_path: Path, asset_class: str):
    cfg = DEFAULT_CONFIG.copy()
    run_dir = tmp_path / f"run_{asset_class}"
    cfg["run_dir"] = run_dir
    cfg["daemon_id"] = f"TEST_{asset_class.upper()}"
    cfg["run_id"] = f"itest_{asset_class}"
    cfg["mode"] = "v2"
    cfg["asset_class"] = asset_class
    cfg["venue_id"] = "auto"
    cfg["strategy"] = "council"
    cfg["interval"] = "1m"
    cfg["args"] = Namespace(symbol=cfg["symbol"], min_adx=cfg["min_adx"])
    return cfg


@pytest.mark.parametrize(
    ("asset_class", "expected_venue"),
    [
        ("stock", "stock_sim_paper"),
        ("defi", "defi_sim_paper"),
    ],
)
def test_sprint_b_v2_multi_asset_tags_are_emitted(tmp_path, asset_class: str, expected_venue: str):
    daemon = PaperDaemon(_cfg(tmp_path, asset_class))

    bars = daemon.fetch_klines(limit=340)
    assert len(bars) >= 100
    daemon.history_bars = bars[:-1]
    daemon.process_bar(bars[-1])
    daemon.update_heartbeat(last_bar=bars[-1])

    run_dir = Path(daemon.cfg["run_dir"])
    metrics = json.loads((run_dir / "metrics.json").read_text(encoding="utf-8"))
    assert metrics.get("mode") == "v2"
    assert metrics.get("asset_class") == asset_class
    assert metrics.get("venue_id") == expected_venue

    # decision jsonl should carry structured asset tags
    decision_lines = (run_dir / "decisions.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert decision_lines
    decision = json.loads(decision_lines[-1])
    assert decision.get("asset_class") == asset_class
    assert decision.get("venue_id") == expected_venue

    rejects_path = run_dir / "rejects.jsonl"
    if rejects_path.exists():
        reject_lines = rejects_path.read_text(encoding="utf-8").strip().splitlines()
        if reject_lines:
            reject = json.loads(reject_lines[-1])
            assert reject.get("asset_class") == asset_class
            assert reject.get("venue_id") == expected_venue


def test_sprint_b_backend_failure_does_not_crash_fetch(tmp_path):
    daemon = PaperDaemon(_cfg(tmp_path, "stock"))
    assert daemon.asset_router is not None
    daemon.asset_router.allow_fallback = False
    daemon.asset_router._adapters["stock"].fetch_klines = lambda _req: (_ for _ in ()).throw(RuntimeError("forced_fail"))  # type: ignore[attr-defined]

    bars = daemon.fetch_klines(limit=5)
    assert bars == []
    assert daemon.asset_router.route.error is not None
