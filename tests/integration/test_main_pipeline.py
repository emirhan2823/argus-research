from __future__ import annotations

import pytest

from src.main import ArgusPipeline


def test_main_pipeline_run_once_smoke() -> None:
    pytest.importorskip("pandas_ta")
    pipeline = ArgusPipeline(mode="paper", assets=["crypto", "us_equity"])
    out = pipeline.run_once()
    assert isinstance(out, list)
    assert len(out) >= 1
    assert {"symbol", "status", "reason"}.issubset(out[0].keys())
