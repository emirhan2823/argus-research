from __future__ import annotations

from pathlib import Path
import sys

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from argus_py.learning.chiron import ChironLearningEngine, LearningSample


def test_chiron_learning_prioritizes_predictive_engine() -> None:
    rng = np.random.default_rng(7)
    engine = ChironLearningEngine(engine_names=["orion", "aegean"], drawdown_penalty=0.2)

    latent = rng.normal(0.0, 1.0, size=180)
    pnl = latent + rng.normal(0.0, 0.1, size=180)
    orion_sig = latent * 85.0
    aegean_sig = -latent * 85.0

    for i in range(180):
        engine.add_sample(
            LearningSample(
                regime="TREND",
                pnl=float(pnl[i]),
                engine_signals={"orion": float(orion_sig[i]), "aegean": float(aegean_sig[i])},
            )
        )

    result = engine.optimize_regime("TREND", min_samples=80)
    assert result is not None
    assert result.weights["orion"] > result.weights["aegean"]
    assert result.sharpe > 0.0


def test_chiron_learning_persistence_roundtrip(tmp_path) -> None:
    path = tmp_path / "chiron_learning.json"

    engine = ChironLearningEngine(engine_names=["orion", "phoenix"])
    for i in range(90):
        x = 1.0 if i % 2 == 0 else -1.0
        engine.add_sample(
            LearningSample(
                regime="CHOP",
                pnl=0.8 * x,
                engine_signals={"orion": 80.0 * x, "phoenix": 20.0 * x},
            )
        )
    res = engine.optimize_regime("CHOP", min_samples=40)
    assert res is not None

    engine.save(path)
    loaded = ChironLearningEngine.load(path)
    loaded_weights = loaded.get_weights("CHOP")
    assert loaded_weights is not None
    assert abs(sum(loaded_weights.values()) - 1.0) < 1e-9
