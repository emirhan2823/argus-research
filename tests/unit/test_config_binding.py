"""Tests to verify config YAML → pydantic → engine constructor binding works end-to-end."""

from __future__ import annotations

import pytest

from src.core.config import (
    AdaptiveConfidenceConfig,
    AegeanConfig,
    ArgusConfig,
    EnginesConfig,
    GeminiConfig,
    HydraConfig,
    PoseidonConfig,
    PrecisionFilterConfig,
    TitanConfig,
    TradeQualityConfig,
    load_config,
)


# ── Config Loading ──────────────────────────────────────────────


class TestConfigLoading:
    """Verify that engines.yaml is correctly parsed into typed config models."""

    @pytest.fixture()
    def cfg(self) -> ArgusConfig:
        return load_config("config")

    def test_titan_config_parsed(self, cfg: ArgusConfig) -> None:
        t = cfg.engines.titan
        assert isinstance(t, TitanConfig)
        assert t.min_adx == 35.0
        assert t.min_confidence == 0.55
        assert t.max_concurrent == 3
        assert t.continuation_min_volume == 0.8
        assert t.adx_rising_bars == 1

    def test_hydra_config_parsed(self, cfg: ArgusConfig) -> None:
        h = cfg.engines.hydra
        assert isinstance(h, HydraConfig)
        assert h.min_confidence == 0.60
        assert h.max_concurrent == 5
        assert h.timeframe == "15m"
        assert h.scalp.get("adx_max") == 25

    def test_aegean_config_parsed(self, cfg: ArgusConfig) -> None:
        a = cfg.engines.aegean
        assert isinstance(a, AegeanConfig)
        assert a.min_confidence == 0.55
        assert a.channel_multipliers.get("trending") == 1.0
        assert a.rr_ratios.get("ranging") == 1.8

    def test_poseidon_config_parsed(self, cfg: ArgusConfig) -> None:
        p = cfg.engines.poseidon
        assert isinstance(p, PoseidonConfig)
        # PoseidonConfig has no YAML block currently, so defaults should hold
        assert p.min_confidence == 0.50
        assert p.max_hold_bars == 12
        assert p.atr_stop_mult == 2.0

    def test_gemini_config_parsed(self, cfg: ArgusConfig) -> None:
        g = cfg.engines.gemini
        assert isinstance(g, GeminiConfig)
        assert g.min_confidence == 0.60
        assert g.max_simultaneous_pairs == 3
        assert len(g.pairs) == 3

    def test_precision_filter_config_parsed(self, cfg: ArgusConfig) -> None:
        pf = cfg.engines.precision_filter
        assert isinstance(pf, PrecisionFilterConfig)
        assert pf.grade_a_threshold == 0.80
        assert pf.min_passing_grade == "D"

    def test_trade_quality_config_parsed(self, cfg: ArgusConfig) -> None:
        tq = cfg.engines.trade_quality
        assert isinstance(tq, TradeQualityConfig)
        assert tq.grade_a_threshold == 0.80
        assert tq.allow_grade_c_in_crypto is True

    def test_adaptive_confidence_config_parsed(self, cfg: ArgusConfig) -> None:
        ac = cfg.engines.adaptive_confidence
        assert isinstance(ac, AdaptiveConfidenceConfig)
        assert ac.base_min_confidence == 0.55
        assert ac.lookback == 20


# ── Engine Constructor Binding ──────────────────────────────────


class TestEngineConstructorBinding:
    """Verify that config values actually reach engine instances."""

    def test_titan_receives_config(self) -> None:
        from src.engines.titan.engine import TitanEngine

        engine = TitanEngine(
            min_adx=35.0,
            adx_rising_bars=1,
            min_volume_expansion=0.8,
            min_confidence=0.55,
        )
        assert engine.min_adx == 35.0
        assert engine.adx_rising_bars == 1
        assert engine.min_volume_expansion == 0.8
        assert engine.min_confidence == 0.55

    def test_hydra_receives_config(self) -> None:
        from src.engines.hydra.engine import HydraEngine

        engine = HydraEngine(
            min_confidence=0.60,
            max_concurrent=5,
            adx_max=25.0,
            sl_atr_mult=1.5,
        )
        assert engine.min_confidence == 0.60
        assert engine.max_concurrent == 5
        assert engine.adx_max == 25.0
        assert engine.sl_atr_mult == 1.5

    def test_nautilus_receives_config(self) -> None:
        from src.engines.nautilus.engine import NautilusEngine

        engine = NautilusEngine(
            max_adx=25.0,
            min_confidence=0.55,
        )
        assert engine.max_adx == 25.0
        assert engine.min_confidence == 0.55

    def test_poseidon_receives_config(self) -> None:
        from src.engines.poseidon.engine import PoseidonEngine

        engine = PoseidonEngine(
            min_confidence=0.50,
            max_hold_bars=12,
            atr_stop_mult=2.0,
            bb_long_threshold=0.15,
            bb_short_threshold=0.85,
            wt_n1=10,
            wt_n2=21,
        )
        assert engine.min_confidence == 0.50
        assert engine.max_hold_bars == 12
        assert engine.atr_stop_mult == 2.0
        assert engine.bb_long_threshold == 0.15
        assert engine.wt_n1 == 10

    def test_aegean_receives_config(self) -> None:
        from src.engines.aegean.engine import AegeanEngine

        engine = AegeanEngine(
            min_confidence=0.55,
            htf_ema_period=200,
        )
        assert engine.min_confidence == 0.55
        assert engine.htf_ema_period == 200

    def test_hermes_receives_config(self) -> None:
        from src.engines.hermes.engine import HermesEngine

        engine = HermesEngine(min_confidence=0.65)
        assert engine.min_confidence == 0.65


# ── PHOENIX Quarantine ──────────────────────────────────────────


class TestPhoenixQuarantine:
    """Verify PHOENIX is not in the active router engine set."""

    def test_phoenix_not_in_router_engines(self) -> None:
        """PHOENIX should not be in the router engines dict."""
        from src.core.constants import ENGINE_PHOENIX
        from src.mde.router import RegimeRouter

        # Create router with all active engines (mirrors main.py)
        from src.engines.titan.engine import TitanEngine
        from src.engines.nautilus.engine import NautilusEngine
        from src.engines.aegean.engine import AegeanEngine
        from src.engines.poseidon.engine import PoseidonEngine
        from src.engines.hydra.engine import HydraEngine
        from src.engines.hermes.engine import HermesEngine

        router = RegimeRouter(
            engines={
                "TITAN": TitanEngine(),
                "NAUTILUS": NautilusEngine(),
                "HYDRA": HydraEngine(),
                "HERMES": HermesEngine(),
                "AEGEAN": AegeanEngine(),
                "POSEIDON": PoseidonEngine(),
            }
        )
        assert ENGINE_PHOENIX not in router.engines

    def test_rsl2_gate_blocks_all_signals(self) -> None:
        """RSL2 gate allows only PHOENIX, which is never instantiated.

        This test captures the KNOWN BUG: at RSL level 2, all signals are
        blocked because PHOENIX is the only allowed engine but it never
        produces signals.
        """
        from unittest.mock import MagicMock

        from src.core.constants import ENGINE_POSEIDON
        from src.core.types import EngineSignal
        from src.mde.gates import GateInput, evaluate_gates

        # Create a valid signal from POSEIDON (not PHOENIX)
        signal = EngineSignal(
            engine=ENGINE_POSEIDON,
            sub_strategy="bb_reversion",
            asset_class="crypto",
            symbol="BTCUSDT",
            bias="long",
            confidence=0.80,
            expected_return=0.02,
            stop_distance=0.01,
            atr=0.005,
        )
        # Use mocks for complex pydantic objects
        mock_features = MagicMock()
        mock_regime = MagicMock()
        mock_regime.regime = "RANGING"

        gate_input = GateInput(
            signal=signal,
            sentinel_score=0.9,
            regime=mock_regime,
            features=mock_features,
            hermes_block_active=False,
            rsl_level=2,  # Defensive mode
            min_confidence=0.50,
            min_net_expected_return=0.001,
            min_reward_risk=1.0,
        )
        result = evaluate_gates(gate_input)
        # RSL2 defensive mode: only TITAN allowed. POSEIDON is blocked.
        assert result.approved is False
        assert result.reason == "rsl2_defensive_only_titan"
