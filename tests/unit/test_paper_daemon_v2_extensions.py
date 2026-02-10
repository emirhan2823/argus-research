from __future__ import annotations

import json
from argparse import Namespace
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from Scripts.paper_daemon import DEFAULT_CONFIG, PaperDaemon
from argus_py.council.defs import ConsensusVerdict
from argus_py.ops.macro_event_guard import MacroEventGuard
from argus_py.portfolio.allocator import PortfolioAllocatorV1
from argus_py.strategy.registry_guard import StrategyRegistryGuard


class _Vote:
    def __init__(self, score: float, metadata: dict[str, float]):
        self.score = score
        self.metadata = metadata


def _cfg(tmp_path: Path) -> dict:
    cfg = DEFAULT_CONFIG.copy()
    cfg["run_dir"] = tmp_path
    cfg["daemon_id"] = "TEST_V2_EXT"
    cfg["run_id"] = "itest_v2_ext"
    cfg["mode"] = "v2"
    cfg["asset_class"] = "stock"
    cfg["venue_id"] = "auto"
    cfg["strategy"] = "council"
    cfg["strategy_registry_file"] = tmp_path / "strategy_registry.json"
    cfg["disabled_strategies_file"] = tmp_path / "disabled_strategies.json"
    cfg["args"] = Namespace(symbol=cfg["symbol"], min_adx=cfg["min_adx"])
    return cfg


def _force_go_wiring(daemon: PaperDaemon) -> None:
    daemon.regime_detector.detect = lambda _history: "TREND"  # type: ignore[assignment]
    if daemon.v2_bridge is not None:
        daemon.v2_bridge.compute_market_snapshot = lambda _history: None  # type: ignore[assignment]
    daemon.aegean.calculate = lambda _history: _Vote(1.0, {"slope": 0.0005})  # type: ignore[assignment]
    daemon.orion.calculate = lambda _history: _Vote(1.0, {"adx": 45.0, "atr": 0.1})  # type: ignore[assignment]
    daemon.council.deliberate = lambda *args, **kwargs: ConsensusVerdict(  # type: ignore[assignment]
        timestamp=0.0,
        decision="GO",
        direction="BUY",
        conviction=70.0,
        regime="TREND",
        rationale="forced_go",
        votes=[],
        metadata={"block_reason": None, "slope": 0.0005, "atr": 0.1},
    )


def test_macro_guard_blocks_entry_in_v2(tmp_path: Path) -> None:
    daemon = PaperDaemon(_cfg(tmp_path))
    _force_go_wiring(daemon)
    bars = daemon.fetch_klines(limit=320)
    assert bars
    daemon.history_bars = bars[:-1]

    event_path = tmp_path / "macro_events.json"
    event_path.write_text(
        json.dumps(
            {
                "events": [
                    {
                        "name": "FOMC",
                        "start_ts": bars[-1].timestamp - 60.0,
                        "end_ts": bars[-1].timestamp + 60.0,
                        "action": "BLOCK_NEW_ENTRY",
                        "asset_classes": ["stock"],
                        "symbols": [daemon.cfg["symbol"]],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    daemon.macro_guard = MacroEventGuard(event_path)
    daemon.process_bar(bars[-1])

    rejects = (tmp_path / "rejects.csv").read_text(encoding="utf-8")
    assert "MACRO_EVENT_BLACKOUT" in rejects
    assert daemon.event_counters["macro_blocks_total"] >= 1


def test_strategy_registry_guard_blocks_entry_in_v2(tmp_path: Path) -> None:
    daemon = PaperDaemon(_cfg(tmp_path))
    _force_go_wiring(daemon)
    bars = daemon.fetch_klines(limit=320)
    assert bars
    daemon.history_bars = bars[:-1]

    reg_path = tmp_path / "strategy_registry.json"
    reg_path.write_text(
        json.dumps({"strategies": {"COUNCIL_BASELINE": {"enabled": False, "disable_reason": "manual_hold"}}}),
        encoding="utf-8",
    )
    daemon.strategy_registry_guard = StrategyRegistryGuard([reg_path])
    daemon.process_bar(bars[-1])

    rejects = (tmp_path / "rejects.csv").read_text(encoding="utf-8")
    assert "STRATEGY_DISABLED" in rejects
    assert daemon.event_counters["strategy_disabled_blocks_total"] >= 1


def test_v2_allocator_block_path(tmp_path: Path) -> None:
    daemon = PaperDaemon(_cfg(tmp_path))
    daemon.allocator = PortfolioAllocatorV1(risk_budget_pct=0.0, max_asset_exposure_pct=35.0, assumed_stop_loss_pct=2.0)
    risk, reason = daemon._apply_v2_risk_sizing(risk_pct=0.01, market_price=100.0)
    assert risk == 0.0
    assert reason is not None
    assert daemon._risk_sizing["allocator_reason"] != "N/A"
