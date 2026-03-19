"""LightGBM trainer with fallback linear-probability backend."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Protocol

import numpy as np
from numpy.typing import NDArray


def _sigmoid(x: NDArray[np.float64]) -> NDArray[np.float64]:
    return 1.0 / (1.0 + np.exp(-x))


class _ModelProtocol(Protocol):
    def fit(self, X: NDArray[np.float64], y: NDArray[np.int_]) -> None:
        ...

    def predict_proba(self, X: NDArray[np.float64]) -> NDArray[np.float64]:
        ...


@dataclass
class LGBMTrainer:
    random_state: int = 42

    def __post_init__(self) -> None:
        self.backend = "linear_fallback"
        self.model: _ModelProtocol | None = None
        self.coef_: Optional[NDArray[np.float64]] = None
        self.intercept_: float = 0.0
        try:
            import lightgbm as lgb

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

    def fit(self, X: NDArray[np.float64], y: NDArray[np.int_] | NDArray[np.float64]) -> None:
        y_arr = np.asarray(y, dtype=int)
        X_arr = np.asarray(X, dtype=float)
        if self.model is not None:
            self.model.fit(X_arr, y_arr)
            return

        # Fallback: class-mean linear separator.
        pos = X_arr[y_arr == 1]
        neg = X_arr[y_arr == 0]
        if len(pos) == 0 or len(neg) == 0:
            self.coef_ = np.zeros(X_arr.shape[1], dtype=float)
            self.intercept_ = 0.0
            return
        self.coef_ = np.mean(pos, axis=0) - np.mean(neg, axis=0)
        self.intercept_ = -0.5 * float(np.dot(self.coef_, np.mean(pos, axis=0) + np.mean(neg, axis=0)))

    def predict_proba(self, X: NDArray[np.float64]) -> NDArray[np.float64]:
        X_arr = np.asarray(X, dtype=float)
        if self.model is not None:
            proba = self.model.predict_proba(X_arr)
            return np.asarray(proba[:, 1], dtype=float)

        coef = self.coef_ if self.coef_ is not None else np.zeros(X_arr.shape[1], dtype=float)
        logits = X_arr @ coef + self.intercept_
        return _sigmoid(logits)

    def predict_direction(self, X: NDArray[np.float64]) -> NDArray[np.int_]:
        probs = self.predict_proba(X)
        return np.where(probs >= 0.5, 1, -1).astype(int)
