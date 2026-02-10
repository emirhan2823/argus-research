"""LightGBM trainer with fallback linear-probability backend."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np


def _sigmoid(x: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-x))


@dataclass
class LGBMTrainer:
    random_state: int = 42

    def __post_init__(self) -> None:
        self.backend = "linear_fallback"
        self.model = None
        self.coef_: Optional[np.ndarray] = None
        self.intercept_: float = 0.0
        try:
            import lightgbm as lgb  # type: ignore

            self.model = lgb.LGBMClassifier(
                n_estimators=100,
                learning_rate=0.05,
                max_depth=5,
                random_state=self.random_state,
            )
            self.backend = "lightgbm"
        except Exception:
            self.model = None
            self.backend = "linear_fallback"

    def fit(self, X: np.ndarray, y: np.ndarray) -> None:
        y = np.asarray(y).astype(int)
        X = np.asarray(X, dtype=float)
        if self.model is not None:
            self.model.fit(X, y)
            return

        # Fallback: class-mean linear separator.
        pos = X[y == 1]
        neg = X[y == 0]
        if len(pos) == 0 or len(neg) == 0:
            self.coef_ = np.zeros(X.shape[1], dtype=float)
            self.intercept_ = 0.0
            return
        self.coef_ = np.mean(pos, axis=0) - np.mean(neg, axis=0)
        self.intercept_ = -0.5 * float(np.dot(self.coef_, np.mean(pos, axis=0) + np.mean(neg, axis=0)))

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        X = np.asarray(X, dtype=float)
        if self.model is not None:
            return self.model.predict_proba(X)[:, 1]

        coef = self.coef_ if self.coef_ is not None else np.zeros(X.shape[1], dtype=float)
        logits = X @ coef + self.intercept_
        return _sigmoid(logits)

    def predict_direction(self, X: np.ndarray) -> np.ndarray:
        probs = self.predict_proba(X)
        return np.where(probs >= 0.5, 1, -1)
