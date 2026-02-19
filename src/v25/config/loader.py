"""Config loader and invariants for ARGUS v2.5 Package 0."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


class ConfigValidationError(Exception):
    """Raised when v2.5 config invariants are violated."""

    def __init__(self, violations: list[str]) -> None:
        self.violations = violations
        super().__init__("Config validation failed: " + "; ".join(violations))


@dataclass(frozen=True)
class FeeModelConfig:
    maker_fee_pct: float
    taker_fee_pct: float
    spread_estimate_pct: float
    slippage_base_pct: float
    slippage_per_10k: float
    backtest_cost_mult: float


@dataclass(frozen=True)
class GlobalCapsConfig:
    per_trade_risk_cap: float
    min_risk_pct: float
    max_position_size: float
    max_leverage_core: float
    max_leverage_accel: float
    max_leverage_global: float


@dataclass(frozen=True)
class PhaseConfig:
    phase_risk: float
    max_leverage: float


@dataclass(frozen=True)
class GrowthSizerConfig:
    phases: dict[str, PhaseConfig]


@dataclass(frozen=True)
class RiskConfig:
    global_caps: GlobalCapsConfig
    growth_sizer: GrowthSizerConfig
    fee_model: FeeModelConfig


@dataclass(frozen=True)
class AccelConfig:
    required_sub_regime: str
    min_alignment: float
    min_sqs: float
    required_kill_switch: int
    max_rolling_vol: float
    max_dd_for_activation: float
    max_slippage_err: float
    slippage_lookback_orders: int
    min_orders_for_accel: int


@dataclass(frozen=True)
class DualSpeedConfig:
    accel: AccelConfig


@dataclass(frozen=True)
class GeminiPairConfig:
    symbol_a: str
    symbol_b: str
    pair_id: str


@dataclass(frozen=True)
class GeminiCorrelationConfig:
    window: int = 100
    min_correlation: float = 0.60
    entry_zscore: float = 2.0
    exit_zscore: float = 0.5
    max_half_life: float = 50.0


@dataclass(frozen=True)
class GeminiConfig:
    pairs: list[GeminiPairConfig]
    correlation: GeminiCorrelationConfig = GeminiCorrelationConfig()
    max_simultaneous_pairs: int = 3


@dataclass(frozen=True)
class DynamicExitConfig:
    r_breakeven: float = 0.5
    r_profit_capture: float = 1.5
    r_trend_rider: float = 3.0
    atr_mult_profit_capture: float = 2.0
    atr_mult_trend_rider: float = 1.2
    partial_fraction_profit_capture: float = 0.30
    partial_fraction_trend_rider: float = 0.20


@dataclass(frozen=True)
class EnginesConfig:
    dual_speed: DualSpeedConfig
    dynamic_exit: DynamicExitConfig = DynamicExitConfig()
    gemini: GeminiConfig | None = None


@dataclass(frozen=True)
class V25Config:
    risk: RiskConfig
    engines: EnginesConfig


def load_v25_config(
    risk_yaml_path: str = "config/risk.yaml",
    engines_yaml_path: str = "config/engines.yaml",
) -> V25Config:
    """Load + validate v2.5 risk/engine configuration."""

    risk_root = _read_yaml(risk_yaml_path)
    engines_root = _read_yaml(engines_yaml_path)

    risk_node = risk_root.get("risk", risk_root)
    engines_node = engines_root.get("engines", engines_root)

    global_caps = _parse_global_caps(risk_node)
    growth_sizer = _parse_growth_sizer(risk_node)
    fee_model = _parse_fee_model(risk_node)
    accel = _parse_accel_config(engines_node)

    dynamic_exit = _parse_dynamic_exit_config(engines_node)
    gemini = _parse_gemini_config(engines_node)

    cfg = V25Config(
        risk=RiskConfig(
            global_caps=global_caps,
            growth_sizer=growth_sizer,
            fee_model=fee_model,
        ),
        engines=EnginesConfig(
            dual_speed=DualSpeedConfig(accel=accel),
            dynamic_exit=dynamic_exit,
            gemini=gemini,
        ),
    )

    violations = _validate_v25_config(cfg)
    if violations:
        raise ConfigValidationError(violations=violations)
    return cfg


def _read_yaml(path: str) -> dict[str, Any]:
    payload = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if payload is None:
        return {}
    if not isinstance(payload, dict):
        raise ConfigValidationError([f"YAML root must be mapping: {path}"])
    return payload


def _as_float(obj: Any, key_path: str) -> float:
    try:
        return float(obj)
    except Exception as exc:  # pragma: no cover - defensive
        raise ConfigValidationError([f"{key_path} must be numeric"]) from exc


def _as_int(obj: Any, key_path: str) -> int:
    try:
        return int(obj)
    except Exception as exc:  # pragma: no cover - defensive
        raise ConfigValidationError([f"{key_path} must be int"]) from exc


def _required(node: dict[str, Any], key: str, key_path: str) -> Any:
    if key not in node:
        raise ConfigValidationError([f"{key_path} is required"])
    return node[key]


def _parse_global_caps(risk_node: dict[str, Any]) -> GlobalCapsConfig:
    global_caps_node = risk_node.get("global_caps", {})
    sizing_node = risk_node.get("sizing", {})

    per_trade_risk_cap = _as_float(
        global_caps_node.get("per_trade_risk_cap", sizing_node.get("max_risk_pct", 0.03)),
        "risk.global_caps.per_trade_risk_cap",
    )
    min_risk_pct = _as_float(
        global_caps_node.get("min_risk_pct", sizing_node.get("min_risk_pct", 0.005)),
        "risk.global_caps.min_risk_pct",
    )
    max_position_size = _as_float(
        global_caps_node.get("max_position_size", sizing_node.get("max_position_size", 0.15)),
        "risk.global_caps.max_position_size",
    )
    max_leverage_core = _as_float(
        global_caps_node.get("max_leverage_core", sizing_node.get("max_leverage", 2.0)),
        "risk.global_caps.max_leverage_core",
    )
    max_leverage_accel = _as_float(
        global_caps_node.get("max_leverage_accel", 3.0),
        "risk.global_caps.max_leverage_accel",
    )
    max_leverage_global = _as_float(
        global_caps_node.get("max_leverage_global", max(max_leverage_core, max_leverage_accel)),
        "risk.global_caps.max_leverage_global",
    )

    return GlobalCapsConfig(
        per_trade_risk_cap=per_trade_risk_cap,
        min_risk_pct=min_risk_pct,
        max_position_size=max_position_size,
        max_leverage_core=max_leverage_core,
        max_leverage_accel=max_leverage_accel,
        max_leverage_global=max_leverage_global,
    )


def _parse_growth_sizer(risk_node: dict[str, Any]) -> GrowthSizerConfig:
    gs_node = risk_node.get("growth_sizer", {})
    phases_node = gs_node.get("phases", {})
    parsed: dict[str, PhaseConfig] = {}
    for phase_name, phase_data in phases_node.items():
        if not isinstance(phase_data, dict):
            continue
        parsed[phase_name.upper()] = PhaseConfig(
            phase_risk=_as_float(
                phase_data.get("phase_risk", phase_data.get("max_risk_pct", 0.0)),
                f"risk.growth_sizer.phases.{phase_name}.phase_risk",
            ),
            max_leverage=_as_float(
                phase_data.get("max_leverage", 1.0),
                f"risk.growth_sizer.phases.{phase_name}.max_leverage",
            ),
        )
    return GrowthSizerConfig(phases=parsed)


def _parse_fee_model(risk_node: dict[str, Any]) -> FeeModelConfig:
    fee_node = risk_node.get("fee_model", {})
    return FeeModelConfig(
        maker_fee_pct=_as_float(
            _required(fee_node, "maker_fee_pct", "risk.fee_model.maker_fee_pct"),
            "risk.fee_model.maker_fee_pct",
        ),
        taker_fee_pct=_as_float(
            _required(fee_node, "taker_fee_pct", "risk.fee_model.taker_fee_pct"),
            "risk.fee_model.taker_fee_pct",
        ),
        spread_estimate_pct=_as_float(
            _required(fee_node, "spread_estimate_pct", "risk.fee_model.spread_estimate_pct"),
            "risk.fee_model.spread_estimate_pct",
        ),
        slippage_base_pct=_as_float(
            _required(fee_node, "slippage_base_pct", "risk.fee_model.slippage_base_pct"),
            "risk.fee_model.slippage_base_pct",
        ),
        slippage_per_10k=_as_float(
            _required(fee_node, "slippage_per_10k", "risk.fee_model.slippage_per_10k"),
            "risk.fee_model.slippage_per_10k",
        ),
        backtest_cost_mult=_as_float(
            _required(fee_node, "backtest_cost_mult", "risk.fee_model.backtest_cost_mult"),
            "risk.fee_model.backtest_cost_mult",
        ),
    )


def _parse_accel_config(engines_node: dict[str, Any]) -> AccelConfig:
    dual_speed = engines_node.get("dual_speed", {})
    accel_node = dual_speed.get("accel", {})
    return AccelConfig(
        required_sub_regime=str(accel_node.get("required_sub_regime", "STRONG_TREND")),
        min_alignment=_as_float(accel_node.get("min_alignment", 0.95), "engines.dual_speed.accel.min_alignment"),
        min_sqs=_as_float(accel_node.get("min_sqs", 0.85), "engines.dual_speed.accel.min_sqs"),
        required_kill_switch=_as_int(
            accel_node.get("required_kill_switch", 0),
            "engines.dual_speed.accel.required_kill_switch",
        ),
        max_rolling_vol=_as_float(
            accel_node.get("max_rolling_vol", 0.04),
            "engines.dual_speed.accel.max_rolling_vol",
        ),
        max_dd_for_activation=_as_float(
            accel_node.get("max_dd_for_activation", 0.02),
            "engines.dual_speed.accel.max_dd_for_activation",
        ),
        max_slippage_err=_as_float(
            accel_node.get("max_slippage_err", 0.001),
            "engines.dual_speed.accel.max_slippage_err",
        ),
        slippage_lookback_orders=_as_int(
            accel_node.get("slippage_lookback_orders", 10),
            "engines.dual_speed.accel.slippage_lookback_orders",
        ),
        min_orders_for_accel=_as_int(
            accel_node.get("min_orders_for_accel", 20),
            "engines.dual_speed.accel.min_orders_for_accel",
        ),
    )


def _parse_gemini_config(engines_node: dict[str, Any]) -> GeminiConfig | None:
    gemini_node = engines_node.get("gemini", {})
    if not gemini_node:
        return None
    pairs_raw = gemini_node.get("pairs", [])
    if not pairs_raw:
        return None
    pairs = []
    for p in pairs_raw:
        pairs.append(
            GeminiPairConfig(
                symbol_a=str(p["symbol_a"]),
                symbol_b=str(p["symbol_b"]),
                pair_id=str(p.get("pair_id", f"{p['symbol_a']}_{p['symbol_b']}")),
            )
        )
    corr_node = gemini_node.get("correlation", {})
    correlation = GeminiCorrelationConfig(
        window=_as_int(corr_node.get("window", 100), "engines.gemini.correlation.window"),
        min_correlation=_as_float(corr_node.get("min_correlation", 0.60), "engines.gemini.correlation.min_correlation"),
        entry_zscore=_as_float(corr_node.get("entry_zscore", 2.0), "engines.gemini.correlation.entry_zscore"),
        exit_zscore=_as_float(corr_node.get("exit_zscore", 0.5), "engines.gemini.correlation.exit_zscore"),
        max_half_life=_as_float(corr_node.get("max_half_life", 50.0), "engines.gemini.correlation.max_half_life"),
    )
    return GeminiConfig(
        pairs=pairs,
        correlation=correlation,
        max_simultaneous_pairs=_as_int(
            gemini_node.get("max_simultaneous_pairs", 3), "engines.gemini.max_simultaneous_pairs"
        ),
    )


def _parse_dynamic_exit_config(engines_node: dict[str, Any]) -> DynamicExitConfig:
    hermes_node = engines_node.get("hermes", {})
    de_node = hermes_node.get("dynamic_exit", {})
    if not de_node:
        return DynamicExitConfig()
    return DynamicExitConfig(
        r_breakeven=_as_float(de_node.get("r_breakeven", 0.5), "engines.hermes.dynamic_exit.r_breakeven"),
        r_profit_capture=_as_float(de_node.get("r_profit_capture", 1.5), "engines.hermes.dynamic_exit.r_profit_capture"),
        r_trend_rider=_as_float(de_node.get("r_trend_rider", 3.0), "engines.hermes.dynamic_exit.r_trend_rider"),
        atr_mult_profit_capture=_as_float(
            de_node.get("atr_mult_profit_capture", 2.0), "engines.hermes.dynamic_exit.atr_mult_profit_capture"
        ),
        atr_mult_trend_rider=_as_float(
            de_node.get("atr_mult_trend_rider", 1.2), "engines.hermes.dynamic_exit.atr_mult_trend_rider"
        ),
        partial_fraction_profit_capture=_as_float(
            de_node.get("partial_fraction_profit_capture", 0.30), "engines.hermes.dynamic_exit.partial_fraction_profit_capture"
        ),
        partial_fraction_trend_rider=_as_float(
            de_node.get("partial_fraction_trend_rider", 0.20), "engines.hermes.dynamic_exit.partial_fraction_trend_rider"
        ),
    )


def _validate_v25_config(config: V25Config) -> list[str]:
    violations: list[str] = []

    global_caps = config.risk.global_caps
    for phase_name, phase in config.risk.growth_sizer.phases.items():
        if phase.phase_risk > global_caps.per_trade_risk_cap:
            violations.append(
                f"{phase_name}.phase_risk {phase.phase_risk} exceeds "
                f"global_caps.per_trade_risk_cap {global_caps.per_trade_risk_cap}"
            )
        if phase.max_leverage > global_caps.max_leverage_global:
            violations.append(
                f"{phase_name}.max_leverage {phase.max_leverage} exceeds "
                f"global_caps.max_leverage_global {global_caps.max_leverage_global}"
            )

    if global_caps.max_leverage_core > global_caps.max_leverage_global:
        violations.append(
            f"global_caps.max_leverage_core {global_caps.max_leverage_core} exceeds "
            f"global_caps.max_leverage_global {global_caps.max_leverage_global}"
        )
    if global_caps.max_leverage_accel > global_caps.max_leverage_global:
        violations.append(
            f"global_caps.max_leverage_accel {global_caps.max_leverage_accel} exceeds "
            f"global_caps.max_leverage_global {global_caps.max_leverage_global}"
        )

    for field_name in (
        "maker_fee_pct",
        "taker_fee_pct",
        "spread_estimate_pct",
        "slippage_base_pct",
        "slippage_per_10k",
        "backtest_cost_mult",
    ):
        value = getattr(config.risk.fee_model, field_name)
        if value <= 0:
            violations.append(f"risk.fee_model.{field_name} must be > 0")

    # Dynamic exit R-threshold ordering invariant
    de = config.engines.dynamic_exit
    if not (0 < de.r_breakeven < de.r_profit_capture < de.r_trend_rider):
        violations.append(
            f"dynamic_exit R thresholds must be strictly increasing: "
            f"r_breakeven={de.r_breakeven} < r_profit_capture={de.r_profit_capture} < r_trend_rider={de.r_trend_rider}"
        )
    for field_name in ("atr_mult_profit_capture", "atr_mult_trend_rider"):
        value = getattr(de, field_name)
        if value <= 0:
            violations.append(f"dynamic_exit.{field_name} must be > 0")
    for field_name in ("partial_fraction_profit_capture", "partial_fraction_trend_rider"):
        value = getattr(de, field_name)
        if not (0 < value <= 1.0):
            violations.append(f"dynamic_exit.{field_name} must be in (0, 1.0]")

    return violations
