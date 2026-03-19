"""Execution mode selector by asset class."""

from __future__ import annotations

from typing import Any


def get_execution_mode(asset_class: str, config: dict[str, Any]) -> str:
    asset_cfg = config.get("asset_classes", {}).get(asset_class)
    if not asset_cfg:
        return "advisory"
    return str(asset_cfg.get("execution_mode", "advisory"))
