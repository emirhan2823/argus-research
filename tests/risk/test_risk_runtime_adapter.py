from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pandas as pd

import src.main as main_mod
from src.core.types import EngineSignal
from src.risk.risk_runtime_adapter import (
    RuntimeRiskConfigReloader,
    RuntimeRiskOverrides,
    UpdatedSignal,
    apply_runtime_risk_overrides,
    mode_supports_runtime_risk_overrides,
    runtime_risk_overrides_from_config,
)


def test_runtime_risk_reloader_detects_modified_config(tmp_path) -> None:
    path = tmp_path / "risk_config.json"
    path.write_text(
        '{"risk_parameters": {"atr_multiplier": 1.5, "rr_ratio": 2.0, "leverage_cap": 2.0, "volatility_threshold": 0.03}}',
        encoding="utf-8",
    )

    reloader = RuntimeRiskConfigReloader(path=path, poll_interval=timedelta(minutes=10))
    t0 = datetime(2026, 2, 21, 12, 0, tzinfo=timezone.utc)
    first = reloader.maybe_reload(now_utc=t0, force=True)
    assert first.changed is True
    assert first.payload is not None
    assert float(first.payload["risk_parameters"]["atr_multiplier"]) == 1.5

    path.write_text(
        '{"risk_parameters": {"atr_multiplier": 1.8, "rr_ratio": 2.5, "leverage_cap": 3.0, "volatility_threshold": 0.04}}',
        encoding="utf-8",
    )

    # Ensure mtime is bumped for the test
    import os, time
    time.sleep(0.01)
    os.utime(path, (time.time(), time.time()))

    second = reloader.maybe_reload(now_utc=t0 + timedelta(minutes=11))
    assert second.changed is True
    assert second.payload is not None
    assert float(second.payload["risk_parameters"]["atr_multiplier"]) == 1.8


def test_apply_runtime_risk_overrides_fallback_defaults() -> None:
    signal = EngineSignal(
        engine="TITAN",
        sub_strategy="trend",
        asset_class="crypto",
        symbol="BTCUSDT",
        bias="long",
        confidence=0.8,
        stop_distance=0.01,
        expected_return=0.02,
        atr=100.0,
    )
    out = apply_runtime_risk_overrides(signal=signal, market_features={"atr_14_pct": 0.02}, risk_config=None)
    assert out.runtime_risk.atr_multiplier == 1.5
    assert out.signal.stop_distance > 0.0
    assert out.signal.expected_return >= out.signal.stop_distance


def test_live_mode_does_not_invoke_runtime_risk_adapter(monkeypatch) -> None:
    def _fake_load_ohlcv(*, symbol: str, now: datetime):  # noqa: ANN001
        _ = symbol, now
        ts = pd.date_range("2024-01-01T00:00:00Z", periods=360, freq="min", tz="UTC")
        close = pd.Series([100.0 + (i * 0.01) for i in range(len(ts))], dtype=float)
        return pd.DataFrame(
            {
                "timestamp": ts,
                "open": close - 0.1,
                "high": close + 0.2,
                "low": close - 0.2,
                "close": close,
                "volume": [1200.0 for _ in range(len(ts))],
            }
        )

    def _route(*, regime, features, allow_crisis_override=False, **kwargs):  # noqa: ANN001
        _ = regime, allow_crisis_override
        return EngineSignal(
            engine="TITAN",
            sub_strategy="trend_follow",
            asset_class=features.asset_class,
            symbol=features.symbol,
            bias="long",
            confidence=0.82,
            stop_distance=0.005,
            expected_return=0.02,
            atr=max(features.atr_14, 1e-6),
        )

    def _must_not_be_called(*args, **kwargs):  # noqa: ANN001
        _ = args, kwargs
        raise AssertionError("apply_runtime_risk_overrides must not run in live mode")

    monkeypatch.setattr(main_mod, "apply_runtime_risk_overrides", _must_not_be_called)

    pipeline = main_mod.ArgusPipeline(mode="live", assets=["crypto"])
    monkeypatch.setattr(pipeline, "_load_ohlcv", _fake_load_ohlcv)
    monkeypatch.setattr(pipeline.sentinel, "validate", lambda inp: SimpleNamespace(score=1.0))
    monkeypatch.setattr(pipeline.router, "route", _route)
    monkeypatch.setattr(pipeline.rule_classifier, "classify", lambda inp: "TRENDING")
    monkeypatch.setattr(
        pipeline.consensus,
        "resolve",
        lambda votes: SimpleNamespace(regime="TRENDING", confidence=0.9, reason="forced"),
    )
    monkeypatch.setattr(pipeline, "_persist_validated_sizing", lambda pre, symbol: None)

    out = pipeline.run_once(now=datetime(2024, 1, 1, tzinfo=timezone.utc))
    assert out
    assert mode_supports_runtime_risk_overrides("live") is False
    assert mode_supports_runtime_risk_overrides("paper") is True


def test_paper_reads_risk_config_without_touching_live(monkeypatch, tmp_path) -> None:
    cfg_path = tmp_path / "risk_config.json"
    cfg_path.write_text(
        '{"risk_parameters":{"atr_multiplier":1.9,"rr_ratio":2.4,"leverage_cap":3.1,"volatility_threshold":0.04}}',
        encoding="utf-8",
    )

    def _fake_load_ohlcv(*, symbol: str, now: datetime):  # noqa: ANN001
        _ = symbol, now
        ts = pd.date_range("2024-01-01T00:00:00Z", periods=360, freq="min", tz="UTC")
        close = pd.Series([100.0 + (i * 0.01) for i in range(len(ts))], dtype=float)
        return pd.DataFrame(
            {
                "timestamp": ts,
                "open": close - 0.1,
                "high": close + 0.2,
                "low": close - 0.2,
                "close": close,
                "volume": [1200.0 for _ in range(len(ts))],
            }
        )

    def _route(*, regime, features, allow_crisis_override=False, **kwargs):  # noqa: ANN001
        _ = regime, allow_crisis_override
        return EngineSignal(
            engine="TITAN",
            sub_strategy="trend_follow",
            asset_class=features.asset_class,
            symbol=features.symbol,
            bias="long",
            confidence=0.82,
            stop_distance=0.005,
            expected_return=0.02,
            atr=max(features.atr_14, 1e-6),
        )

    captured: dict[str, object] = {}

    def _capture_apply(signal, market_features, risk_config):  # noqa: ANN001
        _ = market_features
        captured["risk_config"] = risk_config
        return UpdatedSignal(signal=signal, runtime_risk=RuntimeRiskOverrides())

    monkeypatch.setattr(main_mod, "apply_runtime_risk_overrides", _capture_apply)

    pipeline = main_mod.ArgusPipeline(
        mode="paper",
        assets=["crypto"],
        use_runtime_risk_config=True,
        runtime_risk_config_path=str(cfg_path),
    )
    monkeypatch.setattr(pipeline, "_load_ohlcv", _fake_load_ohlcv)
    monkeypatch.setattr(pipeline.sentinel, "validate", lambda inp: SimpleNamespace(score=1.0))
    monkeypatch.setattr(pipeline.router, "route", _route)
    monkeypatch.setattr(pipeline.rule_classifier, "classify", lambda inp: "TRENDING")
    monkeypatch.setattr(
        pipeline.consensus,
        "resolve",
        lambda votes: SimpleNamespace(regime="TRENDING", confidence=0.9, reason="forced"),
    )
    monkeypatch.setattr(pipeline, "_persist_validated_sizing", lambda pre, symbol: None)

    out = pipeline.run_once(now=datetime(2024, 1, 1, tzinfo=timezone.utc))
    assert out
    assert isinstance(captured.get("risk_config"), dict)
    loaded = captured.get("risk_config") or {}
    assert float(loaded["risk_parameters"]["atr_multiplier"]) == 1.9

    live_pipeline = main_mod.ArgusPipeline(
        mode="live",
        assets=["crypto"],
        use_runtime_risk_config=True,
        runtime_risk_config_path=str(cfg_path),
    )
    assert live_pipeline._runtime_risk_reloader is None


def test_runtime_risk_from_config_parses_nested_fields() -> None:
    cfg = runtime_risk_overrides_from_config(
        {
            "risk_parameters": {
                "atr_multiplier": 1.8,
                "rr_ratio": 2.4,
                "leverage_cap": 3.2,
                "volatility_threshold": 0.04,
            },
            "trailing_rules": {
                "breakeven_at_r": 1.0,
                "lock_in_at_r": 2.0,
                "lock_in_profit_r": 1.0,
            },
        }
    )
    assert cfg.atr_multiplier == 1.8
    assert cfg.rr_ratio == 2.4
    assert cfg.leverage_cap == 3.2
    assert cfg.volatility_threshold == 0.04
