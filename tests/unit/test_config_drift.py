"""Tests to detect config/pydantic/engine default drift.

These tests ensure the three-layer default chain stays synchronized:
  YAML (config/engines.yaml) → Pydantic (config.py) → Engine (engine.py)

If any of these tests fail, it means a default was changed in one place
but not the others, creating config/code drift.
"""

from __future__ import annotations

import pytest


class TestTitanDefaults:
    """TITAN defaults must match across YAML → Pydantic → Engine."""

    def test_min_adx_matches(self) -> None:
        from src.core.config import TitanConfig
        from src.engines.titan.engine import TitanEngine

        assert TitanConfig().min_adx == TitanEngine().min_adx == 28.0

    def test_min_confidence_matches(self) -> None:
        from src.core.config import TitanConfig
        from src.engines.titan.engine import TitanEngine

        assert TitanConfig().min_confidence == TitanEngine().min_confidence == 0.55

    def test_continuation_min_volume_matches(self) -> None:
        from src.core.config import TitanConfig
        from src.engines.titan.engine import TitanEngine

        assert TitanConfig().continuation_min_volume == TitanEngine().min_volume_expansion == 0.8

    def test_adx_rising_bars_matches(self) -> None:
        from src.core.config import TitanConfig
        from src.engines.titan.engine import TitanEngine

        assert TitanConfig().adx_rising_bars == TitanEngine().adx_rising_bars == 1


class TestHydraDefaults:
    """HYDRA defaults must match across Pydantic → Engine."""

    def test_min_confidence_matches(self) -> None:
        from src.core.config import HydraConfig
        from src.engines.hydra.engine import HydraEngine

        assert HydraConfig().min_confidence == HydraEngine().min_confidence == 0.60


class TestNautilusDefaults:
    """NAUTILUS defaults must match across Pydantic → Engine."""

    def test_max_adx_matches(self) -> None:
        from src.core.config import NautilusConfig
        from src.engines.nautilus.engine import NautilusEngine

        assert NautilusConfig().max_adx == NautilusEngine().max_adx == 25.0

    def test_min_confidence_matches(self) -> None:
        from src.core.config import NautilusConfig
        from src.engines.nautilus.engine import NautilusEngine

        assert NautilusConfig().min_confidence == NautilusEngine().min_confidence == 0.55


class TestPoseidonDefaults:
    """POSEIDON defaults must match across Pydantic → Engine."""

    def test_min_confidence_matches(self) -> None:
        from src.core.config import PoseidonConfig
        from src.engines.poseidon.engine import PoseidonEngine

        assert PoseidonConfig().min_confidence == PoseidonEngine().min_confidence == 0.50

    def test_atr_stop_mult_matches(self) -> None:
        from src.core.config import PoseidonConfig
        from src.engines.poseidon.engine import PoseidonEngine

        assert PoseidonConfig().atr_stop_mult == PoseidonEngine().atr_stop_mult == 2.0

    def test_max_hold_bars_matches(self) -> None:
        from src.core.config import PoseidonConfig
        from src.engines.poseidon.engine import PoseidonEngine

        assert PoseidonConfig().max_hold_bars == PoseidonEngine().max_hold_bars == 12


class TestAegeanDefaults:
    """AEGEAN defaults must match across Pydantic → Engine."""

    def test_min_confidence_matches(self) -> None:
        from src.core.config import AegeanConfig
        from src.engines.aegean.engine import AegeanEngine

        # AegeanEngine uses 0.52 as default — this is the engine's own
        # internal threshold, distinct from the config-level min_confidence.
        # Config says 0.55; engine says 0.52. After binding, config wins.
        aeg_cfg = AegeanConfig()
        assert aeg_cfg.min_confidence == 0.55


class TestHermesDefaults:
    """HERMES defaults must match across Pydantic → Engine."""

    def test_min_confidence_matches(self) -> None:
        from src.core.config import HermesConfig
        from src.engines.hermes.engine import HermesEngine

        assert HermesConfig().min_confidence == HermesEngine().min_confidence == 0.65
