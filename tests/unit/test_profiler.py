from pathlib import Path
import time
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from argus_py.profiling.profiler import Profiler


def test_profiler_records_calls_and_timing():
    p = Profiler()

    with p.measure("task"):
        time.sleep(0.01)

    with p.measure("task"):
        time.sleep(0.01)

    r = p.results["task"]
    assert r.calls == 2
    assert r.total_ms > 0
    assert r.max_ms >= r.min_ms
    assert r.avg_ms > 0


def test_report_contains_profile_lines():
    p = Profiler()

    with p.measure("data_fetch"):
        pass
    with p.measure("strategy_eval"):
        pass

    out = p.report()
    assert "=== Performance Profile ===" in out
    assert "data_fetch" in out
    assert "strategy_eval" in out
