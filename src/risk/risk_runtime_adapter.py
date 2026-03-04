"""Runtime risk adapter for paper/backtest execution paths.

This module is intentionally isolated from live mode behavior.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping

from src.core.types import EngineSignal, FeatureVector


DEFAULT_RUNTIME_RISK_PATH = Path("runs/v25/risk_config.json")


def mode_supports_runtime_risk_overrides(mode: str) -> bool:
    return str(mode).strip().lower() in {"paper", "backtest"}


def _clamp(value: float, low: float, high: float) -> float:
    return max(float(low), min(float(high), float(value)))


def _safe_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _as_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


@dataclass(frozen=True)
class TrailingRulesOverride:
    breakeven_at_r: float = 1.0
    lock_in_at_r: float = 2.0
    lock_in_profit_r: float = 1.0

    def as_dict(self) -> dict[str, float]:
        return {
            "breakeven_at_r": float(self.breakeven_at_r),
            "lock_in_at_r": float(self.lock_in_at_r),
            "lock_in_profit_r": float(self.lock_in_profit_r),
        }


@dataclass(frozen=True)
class RuntimeRiskOverrides:
    atr_multiplier: float = 1.5
    rr_ratio: float = 2.0
    leverage_cap: float = 2.0
    volatility_threshold: float = 0.03
    trailing_rules: TrailingRulesOverride = field(default_factory=TrailingRulesOverride)

    def as_dict(self) -> dict[str, Any]:
        return {
            "atr_multiplier": float(self.atr_multiplier),
            "rr_ratio": float(self.rr_ratio),
            "leverage_cap": float(self.leverage_cap),
            "volatility_threshold": float(self.volatility_threshold),
            "trailing_rules": self.trailing_rules.as_dict(),
        }


@dataclass(frozen=True)
class UpdatedSignal:
    signal: EngineSignal
    runtime_risk: RuntimeRiskOverrides


@dataclass(frozen=True)
class RuntimeRiskReloadResult:
    changed: bool
    payload: dict[str, Any] | None
    mtime_ns: int | None


def _parse_trailing_rules(raw: Mapping[str, Any], default: TrailingRulesOverride) -> TrailingRulesOverride:
    return TrailingRulesOverride(
        breakeven_at_r=max(0.0, _safe_float(raw.get("breakeven_at_r"), default.breakeven_at_r)),
        lock_in_at_r=max(0.0, _safe_float(raw.get("lock_in_at_r"), default.lock_in_at_r)),
        lock_in_profit_r=max(0.0, _safe_float(raw.get("lock_in_profit_r"), default.lock_in_profit_r)),
    )


def runtime_risk_overrides_from_config(risk_config: Mapping[str, Any] | None) -> RuntimeRiskOverrides:
    default = RuntimeRiskOverrides()
    raw = _as_mapping(risk_config)
    raw_params = _as_mapping(raw.get("risk_parameters"))
    raw_trailing = _as_mapping(raw.get("trailing_rules"))
    if not raw_trailing:
        raw_trailing = _as_mapping(raw_params.get("trailing_rules"))

    atr_multiplier = max(0.1, _safe_float(raw_params.get("atr_multiplier", raw.get("atr_multiplier")), default.atr_multiplier))
    rr_ratio = max(0.1, _safe_float(raw_params.get("rr_ratio", raw.get("rr_ratio")), default.rr_ratio))
    leverage_cap = max(1.0, _safe_float(raw_params.get("leverage_cap", raw.get("leverage_cap")), default.leverage_cap))
    volatility_threshold = max(
        0.0001,
        _safe_float(raw_params.get("volatility_threshold", raw.get("volatility_threshold")), default.volatility_threshold),
    )
    trailing_rules = _parse_trailing_rules(raw_trailing, default.trailing_rules)

    return RuntimeRiskOverrides(
        atr_multiplier=float(atr_multiplier),
        rr_ratio=float(rr_ratio),
        leverage_cap=float(leverage_cap),
        volatility_threshold=float(volatility_threshold),
        trailing_rules=trailing_rules,
    )


def _extract_atr_pct(market_features: FeatureVector | Mapping[str, Any] | None) -> float | None:
    if market_features is None:
        return None
    if isinstance(market_features, FeatureVector):
        return float(market_features.atr_14_pct)
    mf = _as_mapping(market_features)
    if "atr_14_pct" in mf:
        return _safe_float(mf.get("atr_14_pct"), 0.0)
    if "atr_pct" in mf:
        return _safe_float(mf.get("atr_pct"), 0.0)
    return None


def apply_runtime_risk_overrides(
    signal: EngineSignal,
    market_features: FeatureVector | Mapping[str, Any] | None,
    risk_config: Mapping[str, Any] | None,
) -> UpdatedSignal:
    """Apply runtime risk overrides to signal-level stop/target fields.

    The function never raises and always returns a valid `UpdatedSignal`.
    """

    try:
        overrides = runtime_risk_overrides_from_config(risk_config)
        base_stop = max(0.0001, float(signal.stop_distance))
        atr_scale = float(overrides.atr_multiplier) / 1.5
        atr_pct = _extract_atr_pct(market_features)
        if atr_pct is not None and atr_pct > float(overrides.volatility_threshold):
            atr_scale *= 1.10
        elif atr_pct is not None and atr_pct < (0.5 * float(overrides.volatility_threshold)):
            atr_scale *= 0.95

        stop_distance = _clamp(base_stop * atr_scale, 0.0001, 0.10)
        expected_return = max(stop_distance * float(overrides.rr_ratio), 0.0)
        updated_signal = signal.model_copy(
            update={
                "stop_distance": float(stop_distance),
                "expected_return": float(expected_return),
            }
        )
        return UpdatedSignal(signal=updated_signal, runtime_risk=overrides)
    except Exception:
        return UpdatedSignal(signal=signal, runtime_risk=RuntimeRiskOverrides())


def load_runtime_risk_payload(path: Path | str = DEFAULT_RUNTIME_RISK_PATH) -> tuple[dict[str, Any] | None, int | None]:
    p = Path(path)
    if not p.exists():
        return None, None
    try:
        stat = p.stat()
        mtime_ns = int(getattr(stat, "st_mtime_ns", int(stat.st_mtime * 1e9)))
        raw_text = p.read_text(encoding="utf-8")
        if not raw_text.strip():
            return {}, mtime_ns
        payload = json.loads(raw_text)
        if not isinstance(payload, dict):
            return {}, mtime_ns
        return payload, mtime_ns
    except Exception:
        return None, None


class RuntimeRiskConfigReloader:
    def __init__(
        self,
        *,
        path: Path | str = DEFAULT_RUNTIME_RISK_PATH,
        poll_interval: timedelta = timedelta(minutes=10),
    ) -> None:
        self._path = Path(path)
        self._poll_interval = poll_interval
        self._last_check_utc: datetime | None = None
        self._mtime_ns: int | None = None
        self._payload: dict[str, Any] | None = None

    def maybe_reload(
        self,
        *,
        now_utc: datetime | None = None,
        force: bool = False,
    ) -> RuntimeRiskReloadResult:
        now = now_utc or datetime.now(timezone.utc)
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        else:
            now = now.astimezone(timezone.utc)

        if not force and self._last_check_utc is not None:
            if now - self._last_check_utc < self._poll_interval:
                return RuntimeRiskReloadResult(changed=False, payload=self._payload, mtime_ns=self._mtime_ns)

        self._last_check_utc = now
        payload, mtime_ns = load_runtime_risk_payload(self._path)
        changed = (mtime_ns != self._mtime_ns) or force

        # File removed after prior successful load.
        if mtime_ns is None and self._mtime_ns is not None:
            changed = True

        if changed:
            self._mtime_ns = mtime_ns
            self._payload = payload

        return RuntimeRiskReloadResult(changed=bool(changed), payload=self._payload, mtime_ns=self._mtime_ns)
