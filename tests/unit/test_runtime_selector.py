from __future__ import annotations

from pathlib import Path

from argus_py.runner.runtime_selector import select_runtime


class _DummyBroker:
    pass


class _RouterOK:
    def __init__(self, *, broker, asset_class: str, venue_id: str) -> None:
        self._asset_class = asset_class
        self._venue_id = venue_id

    def telemetry_tags(self):
        return {
            "asset_class": self._asset_class,
            "venue_id": self._venue_id,
            "asset_class_requested": self._asset_class,
            "venue_id_requested": self._venue_id,
            "adapter_id": "dummy_router",
        }


class _BridgeOK:
    def __init__(self, cfg, run_dir: Path, broker) -> None:
        self.cfg = dict(cfg)
        self.run_dir = Path(run_dir)
        self.broker = broker


def test_select_runtime_legacy_mode() -> None:
    cfg = {"mode": "legacy", "asset_class": "crypto", "venue_id": "auto"}
    res = select_runtime(cfg, Path("."), _DummyBroker())
    assert res.requested_mode == "legacy"
    assert res.final_mode == "legacy"
    assert res.reason == "legacy_mode_requested"
    assert res.asset_router is None
    assert res.v2_bridge is None
    assert res.asset_tags["asset_class"] == "crypto"
    assert res.asset_tags["adapter_id"] == "legacy"


def test_select_runtime_v2_success() -> None:
    cfg = {"mode": "v2", "asset_class": "stock", "venue_id": "sim"}
    res = select_runtime(
        cfg,
        Path("."),
        _DummyBroker(),
        asset_router_factory=_RouterOK,
        v2_bridge_factory=_BridgeOK,
    )
    assert res.requested_mode == "v2"
    assert res.final_mode == "v2"
    assert res.reason == "v2_enabled"
    assert res.asset_router is not None
    assert res.v2_bridge is not None
    assert res.asset_tags["asset_class"] == "stock"
    assert res.asset_tags["venue_id"] == "sim"
    assert res.asset_tags["adapter_id"] == "dummy_router"


def test_select_runtime_v2_router_failure_fallback() -> None:
    class _RouterFail:
        def __init__(self, **kwargs) -> None:
            raise RuntimeError("router down")

    cfg = {"mode": "v2", "asset_class": "defi", "venue_id": "sim"}
    res = select_runtime(
        cfg,
        Path("."),
        _DummyBroker(),
        asset_router_factory=_RouterFail,
        v2_bridge_factory=_BridgeOK,
    )
    assert res.requested_mode == "v2"
    assert res.final_mode == "legacy"
    assert res.reason.startswith("v2_fallback_asset_router_init_failed:")
    assert res.asset_router is None
    assert res.v2_bridge is None
    assert "runtime_error" in res.asset_tags


def test_select_runtime_v2_bridge_failure_fallback() -> None:
    class _BridgeFail:
        def __init__(self, cfg, run_dir: Path, broker) -> None:
            raise ValueError("bridge down")

    cfg = {"mode": "v2", "asset_class": "crypto", "venue_id": "auto"}
    res = select_runtime(
        cfg,
        Path("."),
        _DummyBroker(),
        asset_router_factory=_RouterOK,
        v2_bridge_factory=_BridgeFail,
    )
    assert res.requested_mode == "v2"
    assert res.final_mode == "legacy"
    assert res.reason.startswith("v2_fallback_bridge_init_failed:")
    assert res.asset_router is None
    assert res.v2_bridge is None
    assert "runtime_error" in res.asset_tags
