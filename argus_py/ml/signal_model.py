from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import List, Optional

import numpy as np


@dataclass
class MLFeatures:
    rsi_14: float
    macd_hist: float
    bb_position: float
    atr_pct: float
    volume_ratio: float
    fear_greed: float
    funding_rate: float


@dataclass
class MLPrediction:
    direction: str
    confidence: float
    expected_return: float


class _NumpyMultiClassModel:
    """Lightweight fallback model used when LightGBM is unavailable."""

    def __init__(self, centroids: np.ndarray, priors: np.ndarray):
        self.centroids = centroids.astype(float)
        self.priors = priors.astype(float)

    @classmethod
    def fit(cls, features: np.ndarray, labels: np.ndarray) -> "_NumpyMultiClassModel":
        if features.ndim != 2:
            raise ValueError("features must be 2D")

        n_features = features.shape[1]
        centroids = np.zeros((3, n_features), dtype=float)
        priors = np.zeros(3, dtype=float)

        for klass in (0, 1, 2):
            mask = labels == klass
            priors[klass] = float(mask.mean()) if mask.any() else 0.0
            centroids[klass] = features[mask].mean(axis=0) if mask.any() else features.mean(axis=0)

        priors = np.clip(priors, 1e-6, 1.0)
        priors /= priors.sum()
        return cls(centroids=centroids, priors=priors)

    def predict_proba(self, x: np.ndarray) -> np.ndarray:
        if x.ndim == 1:
            x = x.reshape(1, -1)

        distances = ((x[:, None, :] - self.centroids[None, :, :]) ** 2).mean(axis=2)
        logits = -distances + np.log(self.priors[None, :])

        logits = logits - np.max(logits, axis=1, keepdims=True)
        exp_logits = np.exp(logits)
        probs = exp_logits / np.sum(exp_logits, axis=1, keepdims=True)
        return probs

    def to_dict(self) -> dict:
        return {
            "backend": "numpy",
            "centroids": self.centroids.tolist(),
            "priors": self.priors.tolist(),
        }

    @classmethod
    def from_dict(cls, payload: dict) -> "_NumpyMultiClassModel":
        return cls(
            centroids=np.asarray(payload["centroids"], dtype=float),
            priors=np.asarray(payload["priors"], dtype=float),
        )


class SignalModel:
    def __init__(self, model_path: Optional[Path] = None):
        self.model = None
        self.backend: Optional[str] = None
        if model_path and model_path.exists():
            self.load(model_path)

    def train(self, features: np.ndarray, labels: np.ndarray):
        features = np.asarray(features, dtype=float)
        labels = np.asarray(labels, dtype=int)

        if features.ndim != 2:
            raise ValueError("features must be 2D array")
        if labels.ndim != 1 or labels.shape[0] != features.shape[0]:
            raise ValueError("labels must be 1D with same length as features")

        try:
            import lightgbm as lgb  # type: ignore

            dataset = lgb.Dataset(features, label=labels)
            params = {
                "objective": "multiclass",
                "num_class": 3,
                "metric": "multi_logloss",
                "verbosity": -1,
                "seed": 42,
            }
            self.model = lgb.train(params, dataset, num_boost_round=100)
            self.backend = "lightgbm"
        except Exception:
            self.model = _NumpyMultiClassModel.fit(features, labels)
            self.backend = "numpy"

    def _predict_proba(self, x: np.ndarray) -> np.ndarray:
        if self.model is None:
            return np.array([1.0 / 3.0, 1.0 / 3.0, 1.0 / 3.0], dtype=float)

        if self.backend == "lightgbm":
            probs = np.asarray(self.model.predict(x), dtype=float)
            if probs.ndim == 2:
                probs = probs[0]
            return probs

        if self.backend == "numpy":
            probs = self.model.predict_proba(x)[0]
            return np.asarray(probs, dtype=float)

        return np.array([1.0 / 3.0, 1.0 / 3.0, 1.0 / 3.0], dtype=float)

    def predict(self, features: MLFeatures) -> MLPrediction:
        if self.model is None:
            return MLPrediction("FLAT", 0.5, 0.0)

        x = np.array(
            [
                [
                    features.rsi_14,
                    features.macd_hist,
                    features.bb_position,
                    features.atr_pct,
                    features.volume_ratio,
                    features.fear_greed,
                    features.funding_rate,
                ]
            ],
            dtype=float,
        )
        probs = self._predict_proba(x)
        probs = np.asarray(probs, dtype=float)
        if probs.sum() <= 0:
            probs = np.array([1.0 / 3.0, 1.0 / 3.0, 1.0 / 3.0], dtype=float)
        else:
            probs = probs / probs.sum()

        direction = ["DOWN", "FLAT", "UP"][int(np.argmax(probs))]
        return MLPrediction(
            direction=direction,
            confidence=float(np.max(probs)),
            expected_return=float(probs[2] - probs[0]),
        )

    def save(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)

        if self.model is None:
            path.write_text(json.dumps({"backend": "none"}), encoding="utf-8")
            return

        if self.backend == "lightgbm":
            self.model.save_model(str(path))
            return

        if self.backend == "numpy":
            payload = self.model.to_dict()
            path.write_text(json.dumps(payload), encoding="utf-8")
            return

        raise RuntimeError("Unknown model backend")

    def load(self, path: Path):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            backend = payload.get("backend")
            if backend == "none":
                self.model = None
                self.backend = None
                return
            if backend == "numpy":
                self.model = _NumpyMultiClassModel.from_dict(payload)
                self.backend = "numpy"
                return
        except Exception:
            pass

        try:
            import lightgbm as lgb  # type: ignore

            self.model = lgb.Booster(model_file=str(path))
            self.backend = "lightgbm"
        except Exception as exc:
            raise RuntimeError(f"Unable to load model from {path}: {exc}") from exc
