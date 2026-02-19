from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd

from src.main import ArgusPipeline


def _sample_rows() -> list[list[object]]:
    return [
        [pd.Timestamp("2024-01-01T00:01:00Z"), 1.0, 1.2, 0.9, 1.1, 10.0],
        [pd.Timestamp("2024-01-01T00:02:00Z"), 1.1, 1.3, 1.0, 1.2, 11.0],
    ]


def test_replay_mode_forwards_replay_now_to_data_factory(monkeypatch) -> None:
    replay_now = pd.Timestamp("2024-01-01T00:10:00Z")
    pipeline = ArgusPipeline(
        mode="paper",
        assets=["crypto"],
        replay_now=replay_now,
        ohlcv_limit=10,
    )

    captured: dict[str, object] = {}

    def _fake_fetch_ohlcv(**kwargs):
        captured.update(kwargs)
        return _sample_rows()

    monkeypatch.setattr(pipeline.data_factory, "fetch_ohlcv", _fake_fetch_ohlcv)

    frame = pipeline._load_ohlcv(symbol="BTCUSDT", now=datetime.now(timezone.utc))

    assert captured["symbol"] == "BTCUSDT"
    assert captured["timeframe"] == "1m"
    assert captured["limit"] == 10
    assert captured["now"] == replay_now
    assert not frame.empty
    assert frame["timestamp"].iloc[0] == pd.Timestamp("2024-01-01T00:01:00Z")


def test_replay_mode_without_replay_now_passes_none(monkeypatch) -> None:
    pipeline = ArgusPipeline(
        mode="paper",
        assets=["crypto"],
        replay_now=None,
        ohlcv_limit=5,
    )
    pipeline.data_factory.mode = "replay"

    captured: dict[str, object] = {}

    def _fake_fetch_ohlcv(**kwargs):
        captured.update(kwargs)
        return _sample_rows()

    monkeypatch.setattr(pipeline.data_factory, "fetch_ohlcv", _fake_fetch_ohlcv)

    _ = pipeline._load_ohlcv(symbol="BTCUSDT", now=datetime.now(timezone.utc))
    assert captured["now"] is None
