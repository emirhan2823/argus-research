from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from argus_py.asset_router import AssetRouter
from argus_py.runner.v2_runtime import V2RuntimeBridge


@dataclass(frozen=True)
class RuntimeSelection:
    requested_mode: str
    final_mode: str
    reason: str
    asset_router: Any | None
    v2_bridge: Any | None
    asset_tags: Dict[str, str]


def _requested_tags(cfg: Dict[str, Any]) -> Dict[str, str]:
    asset_class = str(cfg.get("asset_class", "crypto")).lower()
    venue_id = str(cfg.get("venue_id", "auto")).lower()
    return {
        "asset_class": asset_class,
        "venue_id": venue_id,
        "asset_class_requested": asset_class,
        "venue_id_requested": venue_id,
        "adapter_id": "legacy",
    }


def select_runtime(
    cfg: Dict[str, Any],
    run_dir: Path,
    broker: Any,
    *,
    asset_router_factory: Callable[..., Any] = AssetRouter,
    v2_bridge_factory: Callable[..., Any] = V2RuntimeBridge,
) -> RuntimeSelection:
    requested_mode = str(cfg.get("mode", "legacy")).lower()
    tags = _requested_tags(cfg)

    if requested_mode != "v2":
        return RuntimeSelection(
            requested_mode=requested_mode,
            final_mode="legacy",
            reason="legacy_mode_requested",
            asset_router=None,
            v2_bridge=None,
            asset_tags=tags,
        )

    try:
        router = asset_router_factory(
            broker=broker,
            asset_class=str(cfg.get("asset_class", "crypto")),
            venue_id=str(cfg.get("venue_id", "auto")),
        )
        tags = router.telemetry_tags()
    except Exception as exc:
        return RuntimeSelection(
            requested_mode=requested_mode,
            final_mode="legacy",
            reason=f"v2_fallback_asset_router_init_failed:{type(exc).__name__}",
            asset_router=None,
            v2_bridge=None,
            asset_tags={**tags, "runtime_error": str(exc)},
        )

    try:
        bridge = v2_bridge_factory(cfg, run_dir, broker)
    except Exception as exc:
        return RuntimeSelection(
            requested_mode=requested_mode,
            final_mode="legacy",
            reason=f"v2_fallback_bridge_init_failed:{type(exc).__name__}",
            asset_router=None,
            v2_bridge=None,
            asset_tags={**tags, "runtime_error": str(exc)},
        )

    return RuntimeSelection(
        requested_mode=requested_mode,
        final_mode="v2",
        reason="v2_enabled",
        asset_router=router,
        v2_bridge=bridge,
        asset_tags=tags,
    )
