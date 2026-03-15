"""High-liquidity policy resolver (BTC/ETH filter overrides).

Resolves per-symbol/per-timeframe/per-engine/per-side overrides used by
the main gate chain for precision, confluence, RR/TP and trade-quality.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


_GRADE_ORDER = {"A": 4, "B": 3, "C": 2, "D": 1, "F": 0}


def _safe_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _safe_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _norm_symbol(value: str) -> str:
    return str(value or "").upper().replace("/", "").replace("-", "").replace("_", "")


def _norm_side(value: str) -> str:
    return "short" if str(value).lower() == "short" else "long"


def _norm_grade(value: str | None) -> str | None:
    if value is None:
        return None
    grade = str(value).strip().upper()
    return grade if grade in _GRADE_ORDER else None


def _to_opt_float(node: dict[str, Any], key: str) -> float | None:
    raw = node.get(key)
    if raw is None:
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _to_opt_bool(node: dict[str, Any], key: str) -> bool | None:
    if key not in node:
        return None
    raw = node.get(key)
    if isinstance(raw, bool):
        return raw
    text = str(raw).strip().lower()
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off"}:
        return False
    return None


def _to_opt_int(node: dict[str, Any], key: str) -> int | None:
    raw = node.get(key)
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _merge_into(dst: dict[str, Any], src: dict[str, Any]) -> None:
    for k, v in src.items():
        if isinstance(v, dict) and isinstance(dst.get(k), dict):
            _merge_into(dst[k], v)
        else:
            dst[k] = v


@dataclass(frozen=True)
class LiquidityPolicyResolution:
    policy_name: str
    symbol: str
    timeframe: str
    engine: str
    side: str
    engine_allowed: bool | None
    engine_mode: str | None
    precision_min_grade: str | None
    precision_min_score: float | None
    confluence_min_factors: int | None
    confluence_min_score: float | None
    min_rr: float | None
    crypto_min_rr: float | None
    min_tp_pct: float | None
    tq_grade_a_threshold: float | None
    tq_grade_b_threshold: float | None
    tq_grade_c_threshold: float | None
    tq_grade_c_min_confidence: float | None
    tq_allow_grade_c_in_crypto: bool | None

    def has_any_override(self) -> bool:
        return any(
            [
                self.engine_allowed is not None,
                self.precision_min_grade is not None,
                self.precision_min_score is not None,
                self.confluence_min_factors is not None,
                self.confluence_min_score is not None,
                self.min_rr is not None,
                self.crypto_min_rr is not None,
                self.min_tp_pct is not None,
                self.tq_grade_a_threshold is not None,
                self.tq_grade_b_threshold is not None,
                self.tq_grade_c_threshold is not None,
                self.tq_grade_c_min_confidence is not None,
                self.tq_allow_grade_c_in_crypto is not None,
            ]
        )


def resolve_liquidity_policy(
    *,
    config: dict[str, Any] | None,
    symbol: str,
    timeframe: str,
    engine: str,
    side: str,
) -> LiquidityPolicyResolution | None:
    """Resolve high-liquidity override set for one signal context."""
    cfg = _safe_dict(config)
    if not bool(cfg.get("enabled", False)):
        return None

    symbol_norm = _norm_symbol(symbol)
    engine_norm = str(engine or "").upper()
    side_norm = _norm_side(side)
    tf_norm = str(timeframe or "").strip().lower() or "1h"

    targets = {_norm_symbol(x) for x in _safe_list(cfg.get("target_symbols"))}
    if targets and symbol_norm not in targets:
        return None

    policies = _safe_dict(cfg.get("policies"))
    tf_node = _safe_dict(policies.get(tf_norm))
    if not tf_node:
        tf_node = _safe_dict(policies.get("default"))
    if not tf_node:
        return None

    merged: dict[str, Any] = {}
    _merge_into(merged, _safe_dict(tf_node.get("defaults")))
    _merge_into(merged, _safe_dict(_safe_dict(tf_node.get("sides")).get(side_norm)))

    engine_node = _safe_dict(_safe_dict(tf_node.get("engines")).get(engine_norm))
    _merge_into(merged, _safe_dict(engine_node))
    _merge_into(merged, _safe_dict(_safe_dict(engine_node.get("sides")).get(side_norm)))

    _mode_raw = merged.get("mode", None)
    if isinstance(_mode_raw, bool):
        engine_mode = "strict" if _mode_raw else "off"
    else:
        engine_mode_raw = str(_mode_raw or "").strip().lower()
        engine_mode = engine_mode_raw if engine_mode_raw in {"off", "strict", "normal"} else None
    engine_allowed: bool | None = None
    if engine_mode == "off":
        engine_allowed = False
    elif engine_mode in {"strict", "normal"}:
        engine_allowed = True

    precision_node = _safe_dict(merged.get("precision"))
    confluence_node = _safe_dict(merged.get("confluence"))
    risk_node = _safe_dict(merged.get("risk"))
    tq_node = _safe_dict(merged.get("trade_quality"))

    out = LiquidityPolicyResolution(
        policy_name=f"high_liquidity.{tf_norm}.{engine_norm}.{side_norm}",
        symbol=symbol_norm,
        timeframe=tf_norm,
        engine=engine_norm,
        side=side_norm,
        engine_allowed=engine_allowed,
        engine_mode=engine_mode,
        precision_min_grade=_norm_grade(precision_node.get("min_grade")),
        precision_min_score=_to_opt_float(precision_node, "min_score"),
        confluence_min_factors=_to_opt_int(confluence_node, "min_factors"),
        confluence_min_score=_to_opt_float(confluence_node, "min_score"),
        min_rr=_to_opt_float(risk_node, "min_rr"),
        crypto_min_rr=_to_opt_float(risk_node, "crypto_min_rr"),
        min_tp_pct=_to_opt_float(risk_node, "min_tp_pct"),
        tq_grade_a_threshold=_to_opt_float(tq_node, "grade_a_threshold"),
        tq_grade_b_threshold=_to_opt_float(tq_node, "grade_b_threshold"),
        tq_grade_c_threshold=_to_opt_float(tq_node, "grade_c_threshold"),
        tq_grade_c_min_confidence=_to_opt_float(tq_node, "grade_c_min_confidence"),
        tq_allow_grade_c_in_crypto=_to_opt_bool(tq_node, "allow_grade_c_in_crypto"),
    )
    if not out.has_any_override():
        return None
    return out
