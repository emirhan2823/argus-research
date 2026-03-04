"""Backtest-safe helpers for auto risk optimization scheduling + hot reload.

This module does not modify runtime behavior by itself. It provides:
- A simple monthly trigger decision function.
- JSON store/load for `risk_config.json`.
- A lightweight file reloader that can be polled by long-running processes.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping

from src.risk.dynamic_risk_manager import RiskConfig


DEFAULT_RISK_CONFIG_PATH = Path("runs/v25/risk_config.json")


@dataclass(frozen=True)
class StoredRiskConfig:
    engine: str
    updated_at: datetime
    config: RiskConfig
    raw: dict[str, Any]


def should_run_monthly_optimization(
    *,
    now_utc: datetime,
    last_run_utc: datetime | None,
    rolling_30d_performance: float | None,
    benchmark: float = 0.0,
    min_days: int = 30,
) -> bool:
    if last_run_utc is None:
        return True
    if now_utc.tzinfo is None:
        raise ValueError("now_utc must be timezone-aware (UTC)")
    if last_run_utc.tzinfo is None:
        raise ValueError("last_run_utc must be timezone-aware (UTC)")

    if now_utc - last_run_utc >= timedelta(days=int(min_days)):
        return True
    if rolling_30d_performance is not None and float(rolling_30d_performance) < float(benchmark):
        return True
    return False


def save_risk_config(
    path: Path = DEFAULT_RISK_CONFIG_PATH,
    *,
    config: RiskConfig,
    engine: str,
    updated_at: datetime | None = None,
    extra: Mapping[str, Any] | None = None,
) -> None:
    ts = updated_at or datetime.now(timezone.utc)
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)

    payload: dict[str, Any] = {
        "updated_at": ts.isoformat(),
        "engine": str(engine),
        "risk_parameters": {
            "atr_multiplier": float(config.atr_multiplier),
            "rr_ratio": float(config.rr_ratio),
            "leverage_cap": float(config.leverage_cap),
            "atr_multiplier_long": (
                float(config.atr_multiplier_long) if config.atr_multiplier_long is not None else None
            ),
            "atr_multiplier_short": (
                float(config.atr_multiplier_short) if config.atr_multiplier_short is not None else None
            ),
            "rr_ratio_long": float(config.rr_ratio_long) if config.rr_ratio_long is not None else None,
            "rr_ratio_short": float(config.rr_ratio_short) if config.rr_ratio_short is not None else None,
            "leverage_cap_long": (
                float(config.leverage_cap_long) if config.leverage_cap_long is not None else None
            ),
            "leverage_cap_short": (
                float(config.leverage_cap_short) if config.leverage_cap_short is not None else None
            ),
            "trailing_activation_long": float(config.trailing_activation_long),
            "trailing_activation_short": float(config.trailing_activation_short),
            "volatility_threshold": float(config.volatility_threshold),
            "low_volatility_threshold": float(config.low_volatility_threshold),
            "vol_k": float(config.vol_k),
            "drawdown_sensitivity": float(config.drawdown_sensitivity),
            "confidence_floor": float(config.confidence_floor),
        },
    }
    if extra:
        payload.update({str(k): v for k, v in extra.items()})

    path.write_text(json.dumps(payload, sort_keys=True, indent=2), encoding="utf-8")




def load_risk_config(path: Path = DEFAULT_RISK_CONFIG_PATH) -> StoredRiskConfig | None:
    try:
        raw_text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None

    data = json.loads(raw_text) if raw_text.strip() else {}
    if not isinstance(data, dict):
        raise ValueError("risk_config.json must contain a JSON object")

    updated_at_raw = data.get("updated_at")
    if isinstance(updated_at_raw, str) and updated_at_raw:
        updated_at = datetime.fromisoformat(updated_at_raw.replace("Z", "+00:00"))
        if updated_at.tzinfo is None:
            updated_at = updated_at.replace(tzinfo=timezone.utc)
    else:
        updated_at = datetime.fromtimestamp(0, tz=timezone.utc)

    engine = str(data.get("engine") or "")
    params = data.get("risk_parameters") or {}
    if not isinstance(params, dict):
        params = {}

    default = RiskConfig()
    cfg = RiskConfig(
        atr_multiplier=float(params.get("atr_multiplier", default.atr_multiplier)),
        rr_ratio=float(params.get("rr_ratio", default.rr_ratio)),
        leverage_cap=float(params.get("leverage_cap", default.leverage_cap)),
        atr_multiplier_long=(
            float(params.get("atr_multiplier_long"))
            if params.get("atr_multiplier_long") is not None
            else default.atr_multiplier_long
        ),
        atr_multiplier_short=(
            float(params.get("atr_multiplier_short"))
            if params.get("atr_multiplier_short") is not None
            else default.atr_multiplier_short
        ),
        rr_ratio_long=(
            float(params.get("rr_ratio_long")) if params.get("rr_ratio_long") is not None else default.rr_ratio_long
        ),
        rr_ratio_short=(
            float(params.get("rr_ratio_short")) if params.get("rr_ratio_short") is not None else default.rr_ratio_short
        ),
        leverage_cap_long=(
            float(params.get("leverage_cap_long"))
            if params.get("leverage_cap_long") is not None
            else default.leverage_cap_long
        ),
        leverage_cap_short=(
            float(params.get("leverage_cap_short"))
            if params.get("leverage_cap_short") is not None
            else default.leverage_cap_short
        ),
        trailing_activation_long=float(
            params.get("trailing_activation_long", default.trailing_activation_long)
        ),
        trailing_activation_short=float(
            params.get("trailing_activation_short", default.trailing_activation_short)
        ),
        volatility_threshold=float(params.get("volatility_threshold", default.volatility_threshold)),
        low_volatility_threshold=float(params.get("low_volatility_threshold", default.low_volatility_threshold)),
        vol_k=float(params.get("vol_k", default.vol_k)),
        drawdown_sensitivity=float(params.get("drawdown_sensitivity", default.drawdown_sensitivity)),
        confidence_floor=float(params.get("confidence_floor", default.confidence_floor)),
    )
    return StoredRiskConfig(engine=engine, updated_at=updated_at, config=cfg, raw=data)


class RiskConfigReloader:
    def __init__(self, path: Path = DEFAULT_RISK_CONFIG_PATH) -> None:
        self._path = Path(path)
        self._last_mtime_ns: int | None = None

    def maybe_reload(self) -> StoredRiskConfig | None:
        if not self._path.exists():
            return None
        stat = self._path.stat()
        mtime_ns = int(getattr(stat, "st_mtime_ns", int(stat.st_mtime * 1e9)))
        if self._last_mtime_ns is not None and mtime_ns == self._last_mtime_ns:
            return None
        loaded = load_risk_config(self._path)
        self._last_mtime_ns = mtime_ns
        return loaded
