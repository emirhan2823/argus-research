from __future__ import annotations

import numpy as np

from src.ml.training.lgbm_trainer import LGBMTrainer
from src.ml.training.meta_label import meta_label_filter


def test_lgbm_trainer_fit_predict() -> None:
    rng = np.random.default_rng(0)
    X = rng.normal(size=(200, 8))
    y = (X[:, 0] + X[:, 1] > 0).astype(int)
    trainer = LGBMTrainer()
    trainer.fit(X, y)
    probs = trainer.predict_proba(X[:10])
    dirs = trainer.predict_direction(X[:10])
    assert probs.shape == (10,)
    assert dirs.shape == (10,)
    assert set(np.unique(dirs)).issubset({-1, 1})


def test_meta_label_filter() -> None:
    direction = np.array([1, -1, 1, -1])
    meta_prob = np.array([0.8, 0.2, 0.6, 0.4])
    out = meta_label_filter(direction_pred=direction, meta_prob=meta_prob, threshold=0.55)
    assert np.array_equal(out, np.array([1, 0, 1, 0]))
