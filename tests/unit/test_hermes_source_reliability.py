from __future__ import annotations

from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from argus_py.ops.hermes_source_reliability import HermesSourceReliability


def test_source_reliability_adjusts_score_and_persists(tmp_path) -> None:
    path = tmp_path / "hermes_source_reliability.json"
    engine = HermesSourceReliability(
        path,
        prior_reliability=0.5,
        prior_weight=2,
        min_multiplier=0.8,
        max_multiplier=1.2,
    )

    base = engine.adjust_score("rss_main", 40.0)
    assert base.adjusted_score == 40.0
    assert base.reliability == 0.5

    engine.record_outcome("rss_main", predicted_score=80.0, realized_return_bps=20.0)
    engine.record_outcome("rss_main", predicted_score=70.0, realized_return_bps=12.0)
    engine.record_outcome("rss_main", predicted_score=90.0, realized_return_bps=-15.0)

    reloaded = HermesSourceReliability(path, prior_reliability=0.5, prior_weight=2)
    stats = reloaded.summary(top_n=3)["sources"]
    assert len(stats) == 1
    row = stats[0]
    assert row["source"] == "rss_main"
    assert row["total"] == 3
    assert row["hits"] == 2
    assert row["misses"] == 1
    assert 0.5 < row["reliability"] < 1.0

    boosted = reloaded.adjust_score("rss_main", 40.0)
    assert boosted.adjusted_score > 40.0


def test_source_reliability_ignores_weak_or_neutral_outcomes(tmp_path) -> None:
    path = tmp_path / "hermes_source_reliability.json"
    engine = HermesSourceReliability(path)

    engine.record_outcome("rss_alt", predicted_score=5.0, realized_return_bps=100.0)  # prediction below threshold
    engine.record_outcome("rss_alt", predicted_score=50.0, realized_return_bps=1.0)  # realized below threshold

    stats = engine.summary()["sources"]
    assert stats == []
    assert engine.reliability("rss_alt") == 0.5

