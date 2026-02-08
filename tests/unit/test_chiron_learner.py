from pathlib import Path
import sys

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from argus_py.models.chiron.learner import ChironLearner, TradeOutcome


def test_outcome_recording_works(tmp_path):
    learner = ChironLearner(state_path=tmp_path / "state.json")
    learner.add_outcome(
        TradeOutcome(
            timestamp=1,
            symbol="BTCUSDT",
            regime="TREND",
            engine_scores={"orion": 70},
            verdict="GO",
            pnl=10.0,
            hold_duration=1.0,
        )
    )
    assert len(learner.outcomes) == 1


def test_weight_optimization_produces_valid_weights(tmp_path):
    learner = ChironLearner(state_path=tmp_path / "state.json")

    for i in range(40):
        pnl = 1.0 if i % 2 == 0 else -0.5
        learner.add_outcome(
            TradeOutcome(
                timestamp=i,
                symbol="BTCUSDT",
                regime="TREND",
                engine_scores={
                    "orion": 80 - i * 0.1,
                    "aether": 50,
                    "hermes": 50,
                    "phoenix": 50 + i * 0.05,
                    "aegean": 45,
                },
                verdict="GO",
                pnl=pnl,
                hold_duration=1.0,
            )
        )

    w = learner.optimize_weights("TREND", min_samples=30)
    assert w is not None
    assert abs(sum(w.values()) - 1.0) < 1e-9
    assert all(0.0 <= v <= 1.0 for v in w.values())


def test_correlation_optimization_reasonable(tmp_path):
    learner = ChironLearner(state_path=tmp_path / "state.json")

    # Strong positive correlation for orion score vs pnl.
    X = np.array([
        [10, 50, 50, 50, 50],
        [20, 50, 50, 50, 50],
        [30, 50, 50, 50, 50],
        [40, 50, 50, 50, 50],
        [50, 50, 50, 50, 50],
    ], dtype=float)
    y = np.array([1, 2, 3, 4, 5], dtype=float)

    w = learner._optimize_correlation(X, y, ["orion", "aether", "hermes", "phoenix", "aegean"])
    top = max(w, key=lambda k: w[k])
    assert top == "orion"


def test_state_persistence_roundtrip(tmp_path):
    state = tmp_path / "learn_state.json"
    learner = ChironLearner(state_path=state)

    for i in range(35):
        learner.add_outcome(
            TradeOutcome(
                timestamp=i,
                symbol="BTCUSDT",
                regime="CHOP",
                engine_scores={"orion": 50, "aether": 55, "hermes": 40, "phoenix": 60, "aegean": 50},
                verdict="GO",
                pnl=0.2,
                hold_duration=1.0,
            )
        )

    learner.optimize_weights("CHOP", min_samples=30)
    learner.save_state()

    loaded = ChironLearner(state_path=state)
    assert "CHOP" in loaded.records
    assert loaded.records["CHOP"].sample_count == 35


def test_csv_loading_works(tmp_path):
    trades = tmp_path / "trades.csv"
    decisions = tmp_path / "decisions.csv"

    trades.write_text(
        "ts_iso,symbol,side,price,qty,pnl,event\n"
        "2026-02-07T00:00:00,BTCUSDT,BUY,50000,0.01,12.0,CLOSE\n"
        "2026-02-07T00:01:00,BTCUSDT,BUY,50010,0.01,-5.0,CLOSE\n",
        encoding="utf-8",
    )
    decisions.write_text(
        "ts_iso,bar_ts_iso,symbol,regime,mode,decision,direction,score,exp_move,adx,reasons\n"
        "2026-02-07T00:00:00,2026-02-07T00:00:00,BTCUSDT,TREND,ATTACK,GO,BUY,70,60,30,\n"
        "2026-02-07T00:01:00,2026-02-07T00:01:00,BTCUSDT,CHOP,DEFENSE,GO,BUY,65,40,20,\n",
        encoding="utf-8",
    )

    learner = ChironLearner(state_path=tmp_path / "state.json")
    count = learner.load_outcomes_from_csv(trades, decisions)
    assert count == 2
    assert len(learner.outcomes) == 2
