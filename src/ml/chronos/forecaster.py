"""Chronos forecaster wrapper with graceful fallback."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np


@dataclass
class ChronosForecaster:
    model_name: str = "amazon/chronos-bolt-base"

    def __post_init__(self) -> None:
        self._backend = "naive"
        self._pipeline = None
        try:
            from chronos import ChronosPipeline  # type: ignore

            self._pipeline = ChronosPipeline.from_pretrained(self.model_name)
            self._backend = "chronos"
        except Exception:
            self._pipeline = None
            self._backend = "naive"

    @property
    def backend(self) -> str:
        return self._backend

    def forecast(self, price_series: Iterable[float], horizon: int = 1) -> dict[str, float]:
        values = np.array(list(price_series), dtype=float)
        if values.size == 0:
            return {"median": 0.0, "confidence_width": 0.0}

        if self._pipeline is not None:
            # Runtime-safe best-effort API usage for Chronos.
            try:
                preds = self._pipeline.predict(values.tolist(), prediction_length=horizon)
                # Expected shape: [quantiles x horizon] or dict; normalize defensively.
                arr = np.array(preds, dtype=float).reshape(-1)
                median = float(np.median(arr))
                width = float(np.percentile(arr, 90) - np.percentile(arr, 10))
                return {"median": median, "confidence_width": width}
            except Exception:
                pass

        # Fallback naive forecast
        median = float(values[-1])
        width = float(np.std(values[-min(50, values.size) :])) * 2.0
        return {"median": median, "confidence_width": width}
