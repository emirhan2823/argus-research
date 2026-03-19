from __future__ import annotations

from src.ml.chronos.forecaster import ChronosForecaster


def test_chronos_forecaster_returns_forecast_dict() -> None:
    fc = ChronosForecaster()
    out = fc.forecast([100.0, 101.0, 99.5, 100.2], horizon=1)
    assert "median" in out
    assert "confidence_width" in out
    assert isinstance(out["median"], float)
    assert isinstance(out["confidence_width"], float)
