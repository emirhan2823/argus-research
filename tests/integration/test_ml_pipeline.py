from __future__ import annotations

import numpy as np
import pandas as pd

from src.backtest.ml_data.labeler import triple_barrier_label
from src.ml.chronos.forecaster import ChronosForecaster
from src.ml.training.lgbm_trainer import LGBMTrainer
from src.ml.training.meta_label import meta_label_filter


def test_ml_pipeline_end_to_end() -> None:
    rng = np.random.default_rng(99)
    close = pd.Series(100 + np.cumsum(rng.normal(0, 1, 400)))
    labels_raw = triple_barrier_label(
        close,
        take_profit_pct=0.01,
        stop_loss_pct=0.01,
        horizon=8,
    )
    y = (labels_raw > 0).astype(int).values

    # Simple feature matrix from lagged returns
    rets = close.pct_change().fillna(0.0)
    X = np.column_stack(
        [
            rets.shift(1).fillna(0.0).values,
            rets.shift(2).fillna(0.0).values,
            rets.rolling(5).mean().fillna(0.0).values,
            rets.rolling(10).std().fillna(0.0).values,
        ]
    )

    trainer = LGBMTrainer()
    trainer.fit(X, y)
    prob = trainer.predict_proba(X[-20:])
    direction = trainer.predict_direction(X[-20:])
    filtered = meta_label_filter(direction_pred=direction, meta_prob=prob, threshold=0.55)
    assert filtered.shape == (20,)

    chronos = ChronosForecaster()
    fc = chronos.forecast(close.tail(200).tolist(), horizon=1)
    assert "median" in fc and "confidence_width" in fc
