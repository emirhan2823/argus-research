from __future__ import annotations

from src.main import ArgusPipeline


def test_execution_mode_falls_back_to_advisory_without_bingx_keys(monkeypatch) -> None:
    monkeypatch.delenv("BINGX_API_KEY", raising=False)
    monkeypatch.delenv("BINGX_API_SECRET", raising=False)
    # Paper mode allows auto execution (simulated, no real orders)
    pipeline = ArgusPipeline(mode="paper", assets=["crypto"])
    assert pipeline._execution_mode("crypto") == "auto"
    # Live mode without keys falls back to advisory
    pipeline_live = ArgusPipeline(mode="live", assets=["crypto"])
    assert pipeline_live._execution_mode("crypto") == "advisory"


def test_execution_mode_auto_with_bingx_keys(monkeypatch) -> None:
    monkeypatch.setenv("BINGX_API_KEY", "k")
    monkeypatch.setenv("BINGX_API_SECRET", "s")
    pipeline = ArgusPipeline(mode="paper", assets=["crypto"])
    assert pipeline._execution_mode("crypto") == "auto"


def test_execution_mode_bist_stays_advisory(monkeypatch) -> None:
    monkeypatch.setenv("BINGX_API_KEY", "k")
    monkeypatch.setenv("BINGX_API_SECRET", "s")
    pipeline = ArgusPipeline(mode="paper", assets=["bist"])
    assert pipeline._execution_mode("bist") == "advisory"
