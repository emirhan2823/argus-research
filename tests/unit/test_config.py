"""Tests for YAML config loader."""

from pathlib import Path

from src.core.config import load_config, ArgusConfig


CONFIG_DIR = Path(__file__).resolve().parents[2] / "config"


class TestConfigLoader:
    def test_loads_all_sections(self):
        cfg = load_config(config_dir=CONFIG_DIR)
        assert isinstance(cfg, ArgusConfig)
        assert cfg.base.system.name == "argus"
        assert cfg.base.system.version == "2.0.0"

    def test_base_has_asset_classes(self):
        cfg = load_config(config_dir=CONFIG_DIR)
        assert "crypto" in cfg.base.asset_classes
        assert "us_equity" in cfg.base.asset_classes
        assert cfg.base.asset_classes["crypto"].enabled is True
        assert cfg.base.asset_classes["bist"].execution_mode == "advisory"

    def test_regime_config(self):
        cfg = load_config(config_dir=CONFIG_DIR)
        assert "TRENDING" in cfg.regime.states
        assert cfg.regime.default == "RANGING"
        assert cfg.regime.confirmation.crisis_to_volatile == 12

    def test_engines_config(self):
        cfg = load_config(config_dir=CONFIG_DIR)
        assert cfg.engines.titan.min_adx == 25
        assert cfg.engines.hermes.llm_backend == "ollama"
        assert cfg.engines.hermes.position_management.critical_news_close_immediately is True

    def test_risk_config(self):
        cfg = load_config(config_dir=CONFIG_DIR)
        assert cfg.risk.sizing.base_risk_pct == 0.015
        assert cfg.risk.portfolio_allocation.max_crypto_pct == 0.50
        assert cfg.risk.stop_loss.stock_max_stop == 0.08

    def test_telemetry_config(self):
        cfg = load_config(config_dir=CONFIG_DIR)
        assert cfg.telemetry.heartbeat_interval_s == 60
        assert cfg.telemetry.advisory.alert_format == "detailed"

    def test_mode_override(self):
        cfg = load_config(config_dir=CONFIG_DIR, mode_override="live")
        assert cfg.base.system.mode == "live"

    def test_missing_config_dir_returns_defaults(self):
        cfg = load_config(config_dir="/nonexistent/path")
        assert isinstance(cfg, ArgusConfig)
        assert cfg.base.system.name == "argus"
