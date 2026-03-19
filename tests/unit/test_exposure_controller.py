from __future__ import annotations

from argus_py.portfolio.exposure_controller import (
    ExposureController,
    ExposureLimits,
    PositionExposure,
)


def test_exposure_controller_accepts_trade_within_caps() -> None:
    controller = ExposureController(
        ExposureLimits(total_cap_pct=90.0, per_symbol_cap_pct=35.0, per_asset_caps_pct={"crypto": 80.0})
    )
    decision = controller.decide(
        equity=1000.0,
        existing_positions=[PositionExposure(symbol="ETHUSDT", asset_class="crypto", notional=120.0)],
        candidate_symbol="BTCUSDT",
        candidate_asset_class="crypto",
        candidate_notional=200.0,
    )
    assert decision.accepted
    assert decision.scale == 1.0
    assert decision.reason == "OK"


def test_exposure_controller_clamps_by_symbol_cap() -> None:
    controller = ExposureController(
        ExposureLimits(total_cap_pct=95.0, per_symbol_cap_pct=20.0, per_asset_caps_pct={"crypto": 90.0})
    )
    decision = controller.decide(
        equity=1000.0,
        existing_positions=[PositionExposure(symbol="BTCUSDT", asset_class="crypto", notional=150.0)],
        candidate_symbol="BTCUSDT",
        candidate_asset_class="crypto",
        candidate_notional=200.0,
    )
    assert decision.accepted
    assert 0.0 < decision.scale < 1.0
    assert decision.reason == "CLAMPED_BY_EXPOSURE_CAP"


def test_exposure_controller_rejects_when_no_room() -> None:
    controller = ExposureController(
        ExposureLimits(total_cap_pct=30.0, per_symbol_cap_pct=25.0, per_asset_caps_pct={"crypto": 25.0})
    )
    decision = controller.decide(
        equity=1000.0,
        existing_positions=[PositionExposure(symbol="BTCUSDT", asset_class="crypto", notional=260.0)],
        candidate_symbol="BTCUSDT",
        candidate_asset_class="crypto",
        candidate_notional=100.0,
    )
    assert not decision.accepted
    assert decision.scale == 0.0
    assert decision.reason in {"TOTAL_EXPOSURE_CAP_REACHED", "SYMBOL_EXPOSURE_CAP_REACHED", "ASSET_EXPOSURE_CAP_REACHED"}
