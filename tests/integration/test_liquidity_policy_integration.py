from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pandas as pd

from src.core.types import EngineSignal
from src.main import ArgusPipeline


def test_liquidity_policy_blocks_hydra_on_15m(tmp_path, monkeypatch) -> None:
    cfg_path = tmp_path / "high_liq.yaml"
    cfg_path.write_text(
        "\n".join(
            [
                "high_liquidity_filters:",
                "  enabled: true",
                "  target_symbols: [BTCUSDT, ETHUSDT]",
                "  policies:",
                "    \"15m\":",
                "      engines:",
                "        HYDRA:",
                "          mode: off",
            ]
        ),
        encoding="utf-8",
    )

    pipeline = ArgusPipeline(
        mode="backtest",
        assets=["crypto"],
        replay_now=pd.Timestamp("2024-02-24T00:00:00Z"),
        liquidity_policy_config_path=cfg_path,
    )
    pipeline._primary_tf = "15m"

    monkeypatch.setattr(pipeline.sentinel, "validate", lambda inp: SimpleNamespace(score=1.0))

    def _fake_route(*, regime, features, allow_crisis_override=False, orchestrator_decision=None):
        _ = regime, allow_crisis_override, orchestrator_decision
        return EngineSignal(
            engine="HYDRA",
            sub_strategy="scalp",
            asset_class=features.asset_class,
            symbol=features.symbol,
            bias="long",
            confidence=0.92,
            stop_distance=0.01,
            expected_return=0.03,
            atr=max(float(features.atr_14), 1e-6),
        )

    monkeypatch.setattr(pipeline.router, "route", _fake_route)

    out = pipeline.run_once(now=datetime(2024, 2, 24, 0, 0, tzinfo=timezone.utc))
    assert len(out) >= 1
    assert any(str(row.get("reason", "")).startswith("liquidity_policy_engine_block:HYDRA") for row in out)


def test_liquidity_policy_does_not_block_hydra_on_1h(tmp_path, monkeypatch) -> None:
    cfg_path = tmp_path / "high_liq.yaml"
    cfg_path.write_text(
        "\n".join(
            [
                "high_liquidity_filters:",
                "  enabled: true",
                "  target_symbols: [BTCUSDT, ETHUSDT]",
                "  policies:",
                "    \"15m\":",
                "      engines:",
                "        HYDRA:",
                "          mode: off",
            ]
        ),
        encoding="utf-8",
    )

    pipeline = ArgusPipeline(
        mode="backtest",
        assets=["crypto"],
        replay_now=pd.Timestamp("2024-02-24T00:00:00Z"),
        liquidity_policy_config_path=cfg_path,
    )
    pipeline._primary_tf = "1h"

    monkeypatch.setattr(pipeline.sentinel, "validate", lambda inp: SimpleNamespace(score=1.0))

    def _fake_route(*, regime, features, allow_crisis_override=False, orchestrator_decision=None):
        _ = regime, allow_crisis_override, orchestrator_decision
        return EngineSignal(
            engine="HYDRA",
            sub_strategy="scalp",
            asset_class=features.asset_class,
            symbol=features.symbol,
            bias="long",
            confidence=0.92,
            stop_distance=0.01,
            expected_return=0.03,
            atr=max(float(features.atr_14), 1e-6),
        )

    monkeypatch.setattr(pipeline.router, "route", _fake_route)

    out = pipeline.run_once(now=datetime(2024, 2, 24, 0, 0, tzinfo=timezone.utc))
    assert len(out) >= 1
    assert not any(str(row.get("reason", "")).startswith("liquidity_policy_engine_block:HYDRA") for row in out)
