"""ARGUS v2.0 — YAML config loader with typed pydantic models.

Loads from config/ directory. Merges base.yaml with section-specific yamls.
All config sections are pydantic models for type safety.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional

import yaml  # type: ignore[import-untyped]
from pydantic import BaseModel, Field


# ── Config Models ─────────────────────────────────────────────────


class SystemConfig(BaseModel):
    name: str = "argus"
    version: str = "2.0.0"
    mode: str = "paper"  # "paper" | "live" | "backtest"
    log_level: str = "INFO"


class AssetClassConfig(BaseModel):
    enabled: bool = False
    execution_mode: str = "auto"  # "auto" | "advisory"
    exchange: Optional[str] = None
    symbols: list[str] = Field(default_factory=list)


class TimeframesConfig(BaseModel):
    primary: str = "1h"
    confirmation: str = "4h"
    direction: str = "1d"


class ExchangesConfig(BaseModel):
    primary: str = "bingx"
    fallback: str = "binance"


class BaseConfig(BaseModel):
    system: SystemConfig = Field(default_factory=SystemConfig)
    asset_classes: dict[str, AssetClassConfig] = Field(default_factory=dict)
    timeframes: TimeframesConfig = Field(default_factory=TimeframesConfig)
    exchanges: ExchangesConfig = Field(default_factory=ExchangesConfig)


# ── Regime Config ─────────────────────────────────────────────────


class RegimeThresholds(BaseModel):
    trending: dict[str, Any] = Field(default_factory=dict)
    ranging: dict[str, Any] = Field(default_factory=dict)
    volatile: dict[str, Any] = Field(default_factory=dict)
    crisis: dict[str, Any] = Field(default_factory=dict)


class RegimeConfirmation(BaseModel):
    trending_to_ranging: int = 3
    ranging_to_trending: int = 3
    to_volatile: int = 2
    to_crisis: int = 0
    crisis_to_volatile: int = 12


class RegimeHysteresis(BaseModel):
    min_candles_before_transition: int = 6
    crisis_exempt: bool = True
    volatile_to_normal_min: int = 4


class HermesOverrides(BaseModel):
    critical_news_forces_crisis: bool = True
    negative_news_blocks_entry_threshold: float = -50.0


class RegimeConfig(BaseModel):
    states: list[str] = Field(default_factory=lambda: ["TRENDING", "RANGING", "VOLATILE", "CRISIS"])
    default: str = "RANGING"
    thresholds: RegimeThresholds = Field(default_factory=RegimeThresholds)
    confirmation: RegimeConfirmation = Field(default_factory=RegimeConfirmation)
    hysteresis: RegimeHysteresis = Field(default_factory=RegimeHysteresis)
    hermes_overrides: HermesOverrides = Field(default_factory=HermesOverrides)


# ── Engine Configs ────────────────────────────────────────────────


class TitanConfig(BaseModel):
    active_regimes: list[str] = Field(default_factory=lambda: ["TRENDING"])
    min_adx: float = 25.0
    min_confidence: float = 0.55
    max_concurrent: int = 2
    trend_follow: dict[str, Any] = Field(default_factory=dict)
    breakout: dict[str, Any] = Field(default_factory=dict)


class NautilusConfig(BaseModel):
    active_regimes: list[str] = Field(default_factory=lambda: ["RANGING"])
    max_adx: float = 22.0
    min_confidence: float = 0.55
    bb_reversion: dict[str, Any] = Field(default_factory=dict)
    funding_reversion: dict[str, Any] = Field(default_factory=dict)


class PhoenixConfig(BaseModel):
    active_regimes: list[str] = Field(default_factory=lambda: ["TRENDING", "RANGING", "VOLATILE"])
    min_confidence: float = 0.60
    funding_harvest: dict[str, Any] = Field(default_factory=dict)
    basis_trade: dict[str, Any] = Field(default_factory=dict)


class HermesPositionManagement(BaseModel):
    critical_news_close_immediately: bool = True
    high_news_tighten_sl: bool = True
    positive_news_trail_tp: bool = True
    dynamic_exit_shadow_enabled: bool = True
    dynamic_exit_noop_debug_sample_n: int = 100


class HermesConfig(BaseModel):
    active_regimes: list[str] = Field(
        default_factory=lambda: ["TRENDING", "RANGING", "VOLATILE", "CRISIS"]
    )
    min_confidence: float = 0.65
    news_fetch_interval_s: int = 60
    llm_backend: str = "ollama"  # "ollama" | "groq"
    ollama_url: str = "http://127.0.0.1:11434/api/generate"
    ollama_model: str = "llama3.1:8b"
    groq_model: str = "llama-3.3-70b-versatile"
    position_management: HermesPositionManagement = Field(
        default_factory=HermesPositionManagement
    )
    feeds: dict[str, list[str]] = Field(default_factory=dict)


class AtlasConfig(BaseModel):
    risk_on_mult: list[float] = Field(default_factory=lambda: [1.0, 1.5])
    risk_neutral_mult: list[float] = Field(default_factory=lambda: [0.7, 1.0])
    risk_off_mult: list[float] = Field(default_factory=lambda: [0.2, 0.5])
    crisis_mult: float = 0.0


class EnginesConfig(BaseModel):
    titan: TitanConfig = Field(default_factory=TitanConfig)
    nautilus: NautilusConfig = Field(default_factory=NautilusConfig)
    phoenix: PhoenixConfig = Field(default_factory=PhoenixConfig)
    hermes: HermesConfig = Field(default_factory=HermesConfig)
    atlas: AtlasConfig = Field(default_factory=AtlasConfig)


# ── Risk Config ───────────────────────────────────────────────────


class SizingConfig(BaseModel):
    base_risk_pct: float = 0.02
    min_risk_pct: float = 0.005
    max_risk_pct: float = 0.03
    max_position_size: float = 0.15
    max_leverage: float = 2.0


class StopLossConfig(BaseModel):
    min_stop: float = 0.01
    max_stop: float = 0.05
    stock_max_stop: float = 0.08
    multipliers: dict[str, float] = Field(default_factory=dict)


class DrawdownConfig(BaseModel):
    dd_caution: float = 0.02
    dd_defensive: float = 0.04
    dd_halt: float = 0.06
    dd_lockdown: float = 0.10
    dd_multipliers: dict[str, float] = Field(default_factory=dict)


class DailyLimitsConfig(BaseModel):
    soft_cap: float = -0.015
    hard_cap: float = -0.025
    max_trades: int = 15


class KillSwitchConfig(BaseModel):
    levels: list[int] = Field(default_factory=lambda: [0, 1, 2, 3, 4])
    size_multipliers: list[float] = Field(default_factory=lambda: [1.0, 0.75, 0.40, 0.0, 0.0])
    de_escalation_hours: dict[str, int] = Field(default_factory=dict)


class GuardsConfig(BaseModel):
    correlation_max: float = 0.6
    funding_settlement_blackout_min: int = 15
    weekend_size_mult: float = 0.5
    consecutive_loss_cooldown: int = 3
    equity_curve_ma_period: int = 20
    single_trade_max_loss: float = 0.03


class PortfolioAllocationConfig(BaseModel):
    max_crypto_pct: float = 0.50
    max_equity_pct: float = 0.40
    max_commodity_pct: float = 0.20
    min_cash_pct: float = 0.10


class RiskConfig(BaseModel):
    sizing: SizingConfig = Field(default_factory=SizingConfig)
    stop_loss: StopLossConfig = Field(default_factory=StopLossConfig)
    drawdown: DrawdownConfig = Field(default_factory=DrawdownConfig)
    daily_limits: DailyLimitsConfig = Field(default_factory=DailyLimitsConfig)
    kill_switch: KillSwitchConfig = Field(default_factory=KillSwitchConfig)
    guards: GuardsConfig = Field(default_factory=GuardsConfig)
    portfolio_allocation: PortfolioAllocationConfig = Field(
        default_factory=PortfolioAllocationConfig
    )


# ── Telemetry Config ──────────────────────────────────────────────


class TelegramAlertConfig(BaseModel):
    enabled: bool = True
    levels: list[str] = Field(default_factory=lambda: ["URGENT", "CRITICAL", "EMERGENCY"])


class LogAlertConfig(BaseModel):
    enabled: bool = True
    levels: list[str] = Field(
        default_factory=lambda: ["INFO", "URGENT", "CRITICAL", "EMERGENCY"]
    )


class AlertsConfig(BaseModel):
    telegram: TelegramAlertConfig = Field(default_factory=TelegramAlertConfig)
    log: LogAlertConfig = Field(default_factory=LogAlertConfig)


class RetentionConfig(BaseModel):
    heartbeat_days: int = 90
    features_days: int = 180
    decisions: str = "indefinite"
    trades: str = "indefinite"


class AdvisoryConfig(BaseModel):
    telegram_chat_id: Optional[str] = None
    alert_format: str = "detailed"  # "brief" | "detailed"
    include_charts: bool = False


class TelemetryConfig(BaseModel):
    sqlite_path: str = "data/trade_logs/argus.db"
    heartbeat_interval_s: int = 60
    alerts: AlertsConfig = Field(default_factory=AlertsConfig)
    retention: RetentionConfig = Field(default_factory=RetentionConfig)
    advisory: AdvisoryConfig = Field(default_factory=AdvisoryConfig)


# ── Root Config ───────────────────────────────────────────────────


class ArgusConfig(BaseModel):
    """Root configuration combining all sections."""

    base: BaseConfig = Field(default_factory=BaseConfig)
    regime: RegimeConfig = Field(default_factory=RegimeConfig)
    engines: EnginesConfig = Field(default_factory=EnginesConfig)
    risk: RiskConfig = Field(default_factory=RiskConfig)
    telemetry: TelemetryConfig = Field(default_factory=TelemetryConfig)


# ── Loader ────────────────────────────────────────────────────────


def _load_yaml(path: Path) -> dict[str, Any]:
    """Load a single YAML file and return its contents as a dict."""
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data if isinstance(data, dict) else {}


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge override into base. Override wins on conflicts."""
    merged = base.copy()
    for key, value in override.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_config(
    config_dir: str | Path = "config",
    mode_override: Optional[str] = None,
) -> ArgusConfig:
    """Load and merge all YAML config files into a typed ArgusConfig.

    Load order:
    1. config/base.yaml
    2. config/regimes.yaml
    3. config/engines.yaml
    4. config/risk.yaml
    5. config/telemetry.yaml
    6. config/{mode}.yaml (if exists) — overrides for paper/live/backtest

    Args:
        config_dir: Path to config directory.
        mode_override: If set, overrides system.mode from base.yaml.

    Returns:
        Fully typed ArgusConfig instance.
    """
    config_path = Path(config_dir)

    # Load individual config files
    base_data = _load_yaml(config_path / "base.yaml")
    regime_data = _load_yaml(config_path / "regimes.yaml")
    engines_data = _load_yaml(config_path / "engines.yaml")
    risk_data = _load_yaml(config_path / "risk.yaml")
    telemetry_data = _load_yaml(config_path / "telemetry.yaml")

    # Determine mode for mode-specific overrides
    mode = mode_override or base_data.get("system", {}).get("mode", "paper")
    mode_data = _load_yaml(config_path / f"{mode}.yaml")

    # Build root config dict
    combined: dict[str, Any] = {
        "base": base_data,
        "regime": regime_data.get("regime", {}),
        "engines": engines_data.get("engines", {}),
        "risk": risk_data.get("risk", {}),
        "telemetry": telemetry_data.get("telemetry", {}),
    }

    # Apply mode overrides
    if mode_data:
        combined = _deep_merge(combined, mode_data)

    # Apply mode override to system config
    if mode_override:
        if "base" not in combined:
            combined["base"] = {}
        if "system" not in combined["base"]:
            combined["base"]["system"] = {}
        combined["base"]["system"]["mode"] = mode_override

    return ArgusConfig(**combined)
