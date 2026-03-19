"""Tests for Scale-In (DCA) Orchestrator."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from src.risk.scale_in_orchestrator import (
    ScaleInConfig,
    ScaleInLayer,
    ScaleInPosition,
    add_layer,
    compute_avg_entry,
    compute_layer_size,
    initial_position_size_pct,
    should_scale_in,
)


def _now() -> datetime:
    return datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)


def _cfg(**overrides) -> ScaleInConfig:
    defaults = dict(
        enabled=True,
        scout_pct=0.30,
        reinforcement_pct=0.70,
        max_layers=3,
        min_price_improvement_pct=0.01,
        cooldown_minutes=15,
    )
    defaults.update(overrides)
    return ScaleInConfig(**defaults)


def _empty_position(symbol="BTCUSDT", side="long", budget=1.0) -> ScaleInPosition:
    return ScaleInPosition(
        position_id="pos-test-1",
        symbol=symbol,
        side=side,
        total_risk_budget=budget,
    )


# --- Scout Entry Tests ---


class TestScoutEntry:
    def test_scout_entry_uses_30pct_of_budget(self):
        """NORMAL signal → scout entry uses 30% of total risk budget."""
        pos = _empty_position()
        cfg = _cfg()
        decision = should_scale_in(
            position=pos, current_price=65000.0,
            signal_strength="NORMAL", now=_now(), config=cfg,
        )
        assert decision.should_add is True
        assert decision.layer_size_pct == pytest.approx(0.30)
        assert decision.reason == "scout_entry"
        assert decision.layer_index == 0

    def test_strong_signal_scout_gets_50pct(self):
        """STRONG signal → scout gets scout_pct + 0.20 = 50%."""
        pos = _empty_position()
        cfg = _cfg()
        size = initial_position_size_pct(
            full_position_size=0.10, signal_strength="STRONG", config=cfg,
        )
        assert size == pytest.approx(0.10 * 0.50)

    def test_disabled_config_passthrough(self):
        """When disabled, initial_position_size_pct returns full size."""
        cfg = _cfg(enabled=False)
        size = initial_position_size_pct(
            full_position_size=0.10, signal_strength="NORMAL", config=cfg,
        )
        assert size == pytest.approx(0.10)

    def test_disabled_config_no_scale_in(self):
        """When disabled, should_scale_in returns should_add=False."""
        pos = _empty_position()
        cfg = _cfg(enabled=False)
        decision = should_scale_in(
            position=pos, current_price=65000.0,
            signal_strength="NORMAL", now=_now(), config=cfg,
        )
        assert decision.should_add is False
        assert "disabled" in decision.reason


# --- Reinforcement Entry Tests ---


class TestReinforcementEntry:
    def test_reinforcement_uses_remaining_70pct(self):
        """STRONG signal after price improvement → up to 70% reinforcement."""
        pos = _empty_position(budget=1.0)
        # Add scout layer first
        add_layer(
            position=pos, entry_price=65000.0, quantity=1.0,
            risk_budget_used=0.30, signal_strength="NORMAL",
            timestamp=_now(),
        )
        cfg = _cfg()
        # Price drops to 63700 (2% improvement for long)
        decision = should_scale_in(
            position=pos, current_price=63700.0,
            signal_strength="STRONG",
            now=_now() + timedelta(minutes=20),
            config=cfg,
        )
        assert decision.should_add is True
        assert decision.layer_size_pct == pytest.approx(0.70)
        assert "reinforcement" in decision.reason

    def test_no_scale_in_without_price_improvement(self):
        """Same price → no reinforcement."""
        pos = _empty_position(budget=1.0)
        add_layer(
            position=pos, entry_price=65000.0, quantity=1.0,
            risk_budget_used=0.30, signal_strength="NORMAL",
            timestamp=_now(),
        )
        cfg = _cfg()
        decision = should_scale_in(
            position=pos, current_price=65000.0,
            signal_strength="STRONG",
            now=_now() + timedelta(minutes=20),
            config=cfg,
        )
        assert decision.should_add is False
        assert "price_improvement" in decision.reason

    def test_normal_signal_reinforcement_gets_half(self):
        """NORMAL signal at improved price → 35% (half of reinforcement)."""
        pos = _empty_position(budget=1.0)
        add_layer(
            position=pos, entry_price=65000.0, quantity=1.0,
            risk_budget_used=0.30, signal_strength="NORMAL",
            timestamp=_now(),
        )
        cfg = _cfg()
        decision = should_scale_in(
            position=pos, current_price=63700.0,
            signal_strength="NORMAL",
            now=_now() + timedelta(minutes=20),
            config=cfg,
        )
        assert decision.should_add is True
        assert decision.layer_size_pct == pytest.approx(0.35)


# --- Constraints Tests ---


class TestConstraints:
    def test_max_layers_respected(self):
        """Cannot add more than max_layers."""
        pos = _empty_position(budget=1.0)
        cfg = _cfg(max_layers=2)
        t = _now()
        # Add 2 layers
        add_layer(position=pos, entry_price=65000.0, quantity=1.0,
                  risk_budget_used=0.30, signal_strength="NORMAL", timestamp=t)
        add_layer(position=pos, entry_price=63700.0, quantity=2.0,
                  risk_budget_used=0.70, signal_strength="STRONG",
                  timestamp=t + timedelta(minutes=20))

        decision = should_scale_in(
            position=pos, current_price=62000.0,
            signal_strength="STRONG",
            now=t + timedelta(minutes=40),
            config=cfg,
        )
        assert decision.should_add is False
        assert "max_layers" in decision.reason

    def test_cooldown_between_layers(self):
        """Must wait min cooldown between layers."""
        pos = _empty_position(budget=1.0)
        cfg = _cfg(cooldown_minutes=15)
        t = _now()
        add_layer(position=pos, entry_price=65000.0, quantity=1.0,
                  risk_budget_used=0.30, signal_strength="NORMAL", timestamp=t)

        # Try adding only 5 minutes later (below cooldown)
        decision = should_scale_in(
            position=pos, current_price=63700.0,
            signal_strength="STRONG",
            now=t + timedelta(minutes=5),
            config=cfg,
        )
        assert decision.should_add is False
        assert "cooldown" in decision.reason

    def test_risk_budget_exhausted(self):
        """Cannot add when risk budget is fully used."""
        pos = _empty_position(budget=1.0)
        add_layer(position=pos, entry_price=65000.0, quantity=1.0,
                  risk_budget_used=1.0, signal_strength="STRONG", timestamp=_now())

        cfg = _cfg()
        decision = should_scale_in(
            position=pos, current_price=63000.0,
            signal_strength="STRONG",
            now=_now() + timedelta(minutes=20),
            config=cfg,
        )
        assert decision.should_add is False
        assert "budget" in decision.reason


# --- Average Entry Tests ---


class TestAvgEntry:
    def test_avg_entry_single_layer(self):
        """Single layer → avg = entry price."""
        layers = [
            ScaleInLayer(0, 65000.0, 1.0, 0.30, "NORMAL", _now()),
        ]
        assert compute_avg_entry(layers) == pytest.approx(65000.0)

    def test_avg_entry_two_layers(self):
        """Two layers → weighted average."""
        layers = [
            ScaleInLayer(0, 65000.0, 1.0, 0.30, "NORMAL", _now()),
            ScaleInLayer(1, 63000.0, 2.0, 0.70, "STRONG", _now()),
        ]
        # (65000*1 + 63000*2) / (1+2) = (65000 + 126000) / 3 = 63666.67
        expected = (65000.0 * 1.0 + 63000.0 * 2.0) / 3.0
        assert compute_avg_entry(layers) == pytest.approx(expected)

    def test_avg_entry_empty_layers(self):
        assert compute_avg_entry([]) == 0.0


# --- Add Layer Tests ---


class TestAddLayer:
    def test_add_layer_updates_status_scout(self):
        pos = _empty_position(budget=1.0)
        add_layer(position=pos, entry_price=65000.0, quantity=1.0,
                  risk_budget_used=0.30, signal_strength="NORMAL", timestamp=_now())
        assert pos.status == "scout"
        assert pos.risk_used == pytest.approx(0.30)
        assert len(pos.layers) == 1

    def test_add_layer_updates_status_reinforced(self):
        pos = _empty_position(budget=1.0)
        add_layer(position=pos, entry_price=65000.0, quantity=1.0,
                  risk_budget_used=0.30, signal_strength="NORMAL", timestamp=_now())
        add_layer(position=pos, entry_price=63000.0, quantity=1.5,
                  risk_budget_used=0.40, signal_strength="STRONG", timestamp=_now())
        assert pos.status == "reinforced"
        assert pos.risk_used == pytest.approx(0.70)

    def test_add_layer_updates_status_full(self):
        pos = _empty_position(budget=1.0)
        add_layer(position=pos, entry_price=65000.0, quantity=1.0,
                  risk_budget_used=0.30, signal_strength="NORMAL", timestamp=_now())
        add_layer(position=pos, entry_price=63000.0, quantity=2.0,
                  risk_budget_used=0.70, signal_strength="STRONG", timestamp=_now())
        assert pos.status == "full"
        assert pos.risk_used == pytest.approx(1.0)

    def test_avg_entry_updated_on_add(self):
        pos = _empty_position(budget=1.0)
        add_layer(position=pos, entry_price=65000.0, quantity=1.0,
                  risk_budget_used=0.30, signal_strength="NORMAL", timestamp=_now())
        assert pos.avg_entry_price == pytest.approx(65000.0)

        add_layer(position=pos, entry_price=63000.0, quantity=2.0,
                  risk_budget_used=0.70, signal_strength="STRONG", timestamp=_now())
        expected = (65000.0 * 1.0 + 63000.0 * 2.0) / 3.0
        assert pos.avg_entry_price == pytest.approx(expected)


# --- Short Side Tests ---


class TestShortSide:
    def test_short_price_improvement_requires_price_increase(self):
        """For shorts, price must go UP for a better entry."""
        pos = _empty_position(side="short", budget=1.0)
        cfg = _cfg(min_price_improvement_pct=0.01)
        add_layer(position=pos, entry_price=65000.0, quantity=1.0,
                  risk_budget_used=0.30, signal_strength="NORMAL", timestamp=_now())

        # Price goes up to 65700 (>1% improvement for short)
        decision = should_scale_in(
            position=pos, current_price=65700.0,
            signal_strength="STRONG",
            now=_now() + timedelta(minutes=20),
            config=cfg,
        )
        assert decision.should_add is True

    def test_short_no_improvement_when_price_drops(self):
        """For shorts, price going DOWN is not an improvement."""
        pos = _empty_position(side="short", budget=1.0)
        cfg = _cfg(min_price_improvement_pct=0.01)
        add_layer(position=pos, entry_price=65000.0, quantity=1.0,
                  risk_budget_used=0.30, signal_strength="NORMAL", timestamp=_now())

        decision = should_scale_in(
            position=pos, current_price=64000.0,
            signal_strength="STRONG",
            now=_now() + timedelta(minutes=20),
            config=cfg,
        )
        assert decision.should_add is False


# --- Layer Size Computation Tests ---


class TestLayerSize:
    def test_scout_layer_size(self):
        cfg = _cfg(scout_pct=0.30)
        size = compute_layer_size(cfg, total_budget=1.0, risk_used=0.0,
                                  signal_strength="NORMAL", layer_index=0)
        assert size == pytest.approx(0.30)

    def test_reinforcement_strong_uses_full_reinforcement(self):
        cfg = _cfg(scout_pct=0.30, reinforcement_pct=0.70)
        size = compute_layer_size(cfg, total_budget=1.0, risk_used=0.30,
                                  signal_strength="STRONG", layer_index=1)
        assert size == pytest.approx(0.70)

    def test_reinforcement_capped_by_remaining(self):
        """If 60% already used of budget=1.0, can't fire 70% more."""
        cfg = _cfg(reinforcement_pct=0.70)
        size = compute_layer_size(cfg, total_budget=1.0, risk_used=0.60,
                                  signal_strength="STRONG", layer_index=2)
        assert size == pytest.approx(0.40)  # only 40% remaining

    def test_zero_remaining_returns_zero(self):
        cfg = _cfg()
        size = compute_layer_size(cfg, total_budget=1.0, risk_used=1.0,
                                  signal_strength="STRONG", layer_index=1)
        assert size == 0.0
