"""Tests for CryptoFeeConfig loading and defaults."""

from __future__ import annotations

import pytest

from src.core.config import ArgusConfig, CryptoFeeConfig, load_config


class TestCryptoFeeConfig:
    """CryptoFeeConfig model and loader tests."""

    def test_defaults(self):
        """CryptoFeeConfig has correct defaults."""
        cfg = CryptoFeeConfig()
        assert cfg.enabled is False
        assert cfg.taker_fee_bps == 3.0
        assert cfg.min_rr == 2.0
        assert cfg.min_tp_pct == 0.01
        assert cfg.min_edge == 0.0
        assert cfg.tq_min_grade == "B"
        assert cfg.grade_a_size_mult == 1.25
        assert cfg.grade_b_size_mult == 1.10
        assert cfg.mr_max_adx == 22.0
        assert cfg.mr_max_atr_pctl == 0.60
        assert cfg.ranging_engines == ["NAUTILUS", "HYDRA"]
        assert cfg.tp_adx_rising_mult == 1.15

    def test_argus_config_includes_crypto_fee(self):
        """ArgusConfig root includes crypto_fee section."""
        cfg = ArgusConfig()
        assert hasattr(cfg, "crypto_fee")
        assert isinstance(cfg.crypto_fee, CryptoFeeConfig)
        assert cfg.crypto_fee.enabled is False

    def test_load_config_reads_crypto_fee(self):
        """load_config correctly reads crypto_fee from engines.yaml."""
        cfg = load_config("config")
        assert cfg.crypto_fee.enabled is True  # engines.yaml sets enabled: true
        assert cfg.crypto_fee.taker_fee_bps == 3.0
        assert cfg.crypto_fee.min_rr == 2.0
        assert cfg.crypto_fee.grade_a_size_mult == 1.25
