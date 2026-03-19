from pathlib import Path
import sys

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from argus_py.models.aether.aether import AetherComponents, AetherEngine, MacroRegime
from argus_py.models.aether.data_sources import AetherDataSources
import argus_py.models.aether.data_sources as ds_mod


@pytest.mark.anyio
async def test_evaluate_returns_macro_regime_enum(monkeypatch):
    engine = AetherEngine(cache_ttl=300)

    async def fg():
        return 20

    async def gm():
        return {
            "market_cap_percentage": {"btc": 39.0},
            "market_cap_change_percentage_24h_usd": 4.0,
        }

    async def dxy():
        return {"value": 101.2, "trend": "DOWN"}

    async def fr(symbol="BTCUSDT"):
        return -0.002

    monkeypatch.setattr(engine, "_fetch_fear_greed", fg)
    monkeypatch.setattr(engine, "_fetch_global_metrics", gm)
    monkeypatch.setattr(engine, "_fetch_funding_rate", fr)
    monkeypatch.setattr(engine._sources, "fetch_dxy_snapshot", dxy)

    result = await engine.evaluate()

    assert isinstance(result.regime, MacroRegime)
    assert result.regime == MacroRegime.RISK_ON
    assert result.score >= 60


def test_score_logic_risk_on_bias():
    engine = AetherEngine()
    score = engine._calculate_score(
        AetherComponents(
            fear_greed=20,
            btc_dominance=38,
            total_mcap_change=5,
            dxy_trend="DOWN",
            funding_rate=-0.002,
        )
    )
    assert score > 70
    assert engine._determine_regime(score) == MacroRegime.RISK_ON


def test_score_logic_risk_off_bias():
    engine = AetherEngine()
    score = engine._calculate_score(
        AetherComponents(
            fear_greed=90,
            btc_dominance=56,
            total_mcap_change=-5,
            dxy_trend="UP",
            funding_rate=0.003,
        )
    )
    assert score < 40
    assert engine._determine_regime(score) == MacroRegime.RISK_OFF


def test_determine_regime_thresholds():
    engine = AetherEngine()
    assert engine._determine_regime(60) == MacroRegime.RISK_ON
    assert engine._determine_regime(40) == MacroRegime.RISK_OFF
    assert engine._determine_regime(50) == MacroRegime.NEUTRAL


@pytest.mark.anyio
async def test_cache_prevents_excessive_api_calls(monkeypatch):
    engine = AetherEngine(cache_ttl=999)
    calls = {"fg": 0, "gm": 0, "dxy": 0, "fr": 0}

    async def fg():
        calls["fg"] += 1
        return 50

    async def gm():
        calls["gm"] += 1
        return {"market_cap_percentage": {"btc": 50}, "market_cap_change_percentage_24h_usd": 0}

    async def dxy():
        calls["dxy"] += 1
        return {"value": 100, "trend": "FLAT"}

    async def fr(symbol="BTCUSDT"):
        calls["fr"] += 1
        return 0.0

    monkeypatch.setattr(engine, "_fetch_fear_greed", fg)
    monkeypatch.setattr(engine, "_fetch_global_metrics", gm)
    monkeypatch.setattr(engine, "_fetch_funding_rate", fr)
    monkeypatch.setattr(engine._sources, "fetch_dxy_snapshot", dxy)

    r1 = await engine.evaluate()
    r2 = await engine.evaluate()

    assert r1 is r2
    assert calls == {"fg": 1, "gm": 1, "dxy": 1, "fr": 1}


@pytest.mark.anyio
async def test_force_refresh_bypasses_cache(monkeypatch):
    engine = AetherEngine(cache_ttl=999)
    calls = {"fg": 0}

    async def fg():
        calls["fg"] += 1
        return 50

    async def gm():
        return {"market_cap_percentage": {"btc": 50}, "market_cap_change_percentage_24h_usd": 0}

    async def dxy():
        return {"value": 100, "trend": "FLAT"}

    async def fr(symbol="BTCUSDT"):
        return 0.0

    monkeypatch.setattr(engine, "_fetch_fear_greed", fg)
    monkeypatch.setattr(engine, "_fetch_global_metrics", gm)
    monkeypatch.setattr(engine, "_fetch_funding_rate", fr)
    monkeypatch.setattr(engine._sources, "fetch_dxy_snapshot", dxy)

    await engine.evaluate()
    await engine.evaluate(force_refresh=True)

    assert calls["fg"] == 2


@pytest.mark.anyio
async def test_fetch_failures_fallback_to_neutral(monkeypatch):
    engine = AetherEngine()

    async def boom(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(engine, "_fetch_fear_greed", boom)
    monkeypatch.setattr(engine, "_fetch_global_metrics", boom)
    monkeypatch.setattr(engine, "_fetch_funding_rate", boom)
    monkeypatch.setattr(engine._sources, "fetch_dxy_snapshot", boom)

    result = await engine.evaluate(force_refresh=True)

    assert result.regime == MacroRegime.NEUTRAL
    assert result.score == 50.0


@pytest.mark.anyio
async def test_coingecko_rate_limit_sleep(monkeypatch):
    src = AetherDataSources(min_coingecko_interval=6.0)
    src._coingecko_last_call = 96.0

    sleep_calls = []

    async def fake_sleep(seconds):
        sleep_calls.append(seconds)

    times = iter([100.0, 100.0])

    monkeypatch.setattr(ds_mod.asyncio, "sleep", fake_sleep)
    monkeypatch.setattr(ds_mod.time, "time", lambda: next(times))

    await src._respect_coingecko_rate_limit()

    assert len(sleep_calls) == 1
    assert abs(sleep_calls[0] - 2.0) < 1e-9


@pytest.mark.anyio
async def test_fetch_dxy_wrapper_returns_float(monkeypatch):
    engine = AetherEngine()

    async def dxy_snapshot():
        return {"value": 103.2, "trend": "UP"}

    monkeypatch.setattr(engine._sources, "fetch_dxy_snapshot", dxy_snapshot)

    value = await engine._fetch_dxy()
    assert value == 103.2


def test_reasoning_includes_components():
    engine = AetherEngine()
    comp = AetherComponents(30, 48, 1.2, "FLAT", 0.0)
    text = engine._build_reasoning(comp, 52.0, MacroRegime.NEUTRAL)
    assert "Regime=NEUTRAL" in text
    assert "FG=30.0" in text
