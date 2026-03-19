"""Tests for Market Structure Detector."""

from __future__ import annotations

import pytest

from src.features.market_structure import (
    MarketStructure,
    MarketStructureConfig,
    SwingLevel,
    StructureAdjustedResult,
    adjust_sl_tp_for_structure,
    build_market_structure,
    cluster_levels,
    detect_swing_levels,
)


# ---------------------------------------------------------------------------
# Helpers — synthetic OHLCV data
# ---------------------------------------------------------------------------


def _make_v_pattern(n: int = 30, base: float = 100.0, dip: float = 95.0) -> tuple[list[float], list[float]]:
    """Create a V-pattern: price descends to `dip` at the midpoint, then recovers.

    This creates one clear swing low at the bottom of the V.
    """
    mid = n // 2
    highs: list[float] = []
    lows: list[float] = []
    for i in range(n):
        if i <= mid:
            # Descending
            frac = i / mid
            price = base - (base - dip) * frac
        else:
            # Ascending
            frac = (i - mid) / (n - mid - 1) if (n - mid - 1) > 0 else 1.0
            price = dip + (base - dip) * frac
        highs.append(price + 0.5)  # High slightly above
        lows.append(price - 0.5)   # Low slightly below
    return highs, lows


def _make_inverted_v(n: int = 30, base: float = 100.0, peak: float = 110.0) -> tuple[list[float], list[float]]:
    """Create an inverted-V: price ascends to `peak` at midpoint, then drops.

    This creates one clear swing high at the top.
    """
    mid = n // 2
    highs: list[float] = []
    lows: list[float] = []
    for i in range(n):
        if i <= mid:
            frac = i / mid
            price = base + (peak - base) * frac
        else:
            frac = (i - mid) / (n - mid - 1) if (n - mid - 1) > 0 else 1.0
            price = peak - (peak - base) * frac
        highs.append(price + 0.5)
        lows.append(price - 0.5)
    return highs, lows


def _flat_data(n: int = 30, price: float = 100.0) -> tuple[list[float], list[float]]:
    """Flat price data — no swings should be detected."""
    return [price + 0.5] * n, [price - 0.5] * n


# ---------------------------------------------------------------------------
# Swing Detection Tests
# ---------------------------------------------------------------------------


class TestSwingDetection:
    def test_v_pattern_detects_swing_low(self):
        """V-pattern should detect a swing low at the bottom."""
        highs, lows = _make_v_pattern(n=30, base=100.0, dip=90.0)
        levels = detect_swing_levels(highs, lows, window=5)
        supports = [l for l in levels if l.level_type == "support"]
        assert len(supports) >= 1
        # The lowest support should be near the dip
        lowest = min(supports, key=lambda l: l.price)
        assert lowest.price < 92.0  # Near the dip value

    def test_inverted_v_detects_swing_high(self):
        """Inverted-V should detect a swing high at the peak."""
        highs, lows = _make_inverted_v(n=30, base=100.0, peak=110.0)
        levels = detect_swing_levels(highs, lows, window=5)
        resistances = [l for l in levels if l.level_type == "resistance"]
        assert len(resistances) >= 1
        highest = max(resistances, key=lambda l: l.price)
        assert highest.price > 108.0  # Near the peak value

    def test_non_repainting_last_n_bars_no_signal(self):
        """The last N=window bars must never produce swing signals.

        This is the non-repainting guarantee: the right window hasn't closed.
        """
        highs, lows = _make_v_pattern(n=30, base=100.0, dip=90.0)
        window = 5
        levels = detect_swing_levels(highs, lows, window=window)
        n = len(highs)
        last_valid = n - 1 - window  # = 24
        for level in levels:
            assert level.bar_index <= last_valid, (
                f"Level at bar {level.bar_index} exceeds last valid {last_valid}"
            )

    def test_flat_data_no_swings(self):
        """Completely flat price data should produce no swings."""
        highs, lows = _flat_data(n=30, price=100.0)
        levels = detect_swing_levels(highs, lows, window=5)
        assert len(levels) == 0

    def test_insufficient_data_returns_empty(self):
        """Data shorter than 2*window+1 should return empty."""
        levels = detect_swing_levels([100.0] * 5, [99.0] * 5, window=5)
        assert levels == []

    def test_mismatched_lengths_raises(self):
        """highs and lows of different length should raise ValueError."""
        with pytest.raises(ValueError, match="equal length"):
            detect_swing_levels([100.0, 101.0], [99.0], window=1)

    def test_age_bars_computed_correctly(self):
        """age_bars should be current_bar_index - bar_index."""
        highs, lows = _make_v_pattern(n=30)
        levels = detect_swing_levels(highs, lows, window=5, current_bar_index=29)
        for level in levels:
            assert level.age_bars == 29 - level.bar_index


# ---------------------------------------------------------------------------
# Clustering Tests
# ---------------------------------------------------------------------------


class TestClustering:
    def test_nearby_levels_merge(self):
        """Two levels 0.1% apart should merge into one with strength=2."""
        levels = [
            SwingLevel(price=100.0, bar_index=10, level_type="support", strength=1, age_bars=20),
            SwingLevel(price=100.05, bar_index=15, level_type="support", strength=1, age_bars=15),
        ]
        clustered = cluster_levels(levels, tolerance_pct=0.003)
        assert len(clustered) == 1
        assert clustered[0].strength == 2
        # Should use the most recent bar_index
        assert clustered[0].bar_index == 15

    def test_distant_levels_stay_separate(self):
        """Two levels 2% apart should NOT merge."""
        levels = [
            SwingLevel(price=100.0, bar_index=10, level_type="support", strength=1, age_bars=20),
            SwingLevel(price=102.0, bar_index=15, level_type="support", strength=1, age_bars=15),
        ]
        clustered = cluster_levels(levels, tolerance_pct=0.003)
        assert len(clustered) == 2

    def test_triple_cluster_sums_strength(self):
        """Three nearby levels → one cluster with strength=3."""
        levels = [
            SwingLevel(price=100.0, bar_index=5, level_type="support", strength=1, age_bars=25),
            SwingLevel(price=100.1, bar_index=10, level_type="support", strength=1, age_bars=20),
            SwingLevel(price=100.2, bar_index=15, level_type="support", strength=1, age_bars=15),
        ]
        clustered = cluster_levels(levels, tolerance_pct=0.003)
        assert len(clustered) == 1
        assert clustered[0].strength == 3

    def test_empty_input(self):
        assert cluster_levels([], tolerance_pct=0.003) == []


# ---------------------------------------------------------------------------
# Builder Tests
# ---------------------------------------------------------------------------


class TestBuildMarketStructure:
    def test_disabled_returns_empty(self):
        """When disabled, returns empty structure."""
        cfg = MarketStructureConfig(enabled=False)
        highs, lows = _make_v_pattern(n=30)
        ms = build_market_structure(highs, lows, current_price=100.0, config=cfg)
        assert ms.supports == []
        assert ms.resistances == []

    def test_enabled_builds_structure(self):
        """When enabled, should detect supports and resistances."""
        cfg = MarketStructureConfig(enabled=True, swing_window=3, min_age_bars=1)
        highs, lows = _make_v_pattern(n=30, base=100.0, dip=90.0)
        ms = build_market_structure(highs, lows, current_price=100.0, config=cfg)
        assert len(ms.supports) > 0 or len(ms.resistances) > 0

    def test_min_age_filters_recent(self):
        """Swing levels younger than min_age_bars should be filtered."""
        cfg = MarketStructureConfig(enabled=True, swing_window=3, min_age_bars=100)
        highs, lows = _make_v_pattern(n=30)
        ms = build_market_structure(highs, lows, current_price=100.0, config=cfg)
        # All levels will be younger than 100 bars → filtered
        assert ms.supports == []
        assert ms.resistances == []

    def test_max_levels_respected(self):
        """Should return at most max_levels per side."""
        cfg = MarketStructureConfig(enabled=True, swing_window=2, max_levels=2, min_age_bars=0)
        # Create data with many swings
        n = 60
        highs = []
        lows = []
        for i in range(n):
            # Oscillating pattern creates many swings
            phase = i % 10
            if phase < 5:
                price = 100.0 + phase * 2
            else:
                price = 100.0 + (10 - phase) * 2
            highs.append(price + 0.5)
            lows.append(price - 0.5)
        ms = build_market_structure(highs, lows, current_price=100.0, config=cfg)
        assert len(ms.supports) <= 2
        assert len(ms.resistances) <= 2

    def test_sorted_nearest_first(self):
        """Levels should be sorted by proximity to current_price."""
        cfg = MarketStructureConfig(enabled=True, swing_window=2, min_age_bars=0, max_levels=10)
        # Oscillating data
        n = 40
        highs = []
        lows = []
        for i in range(n):
            phase = i % 8
            if phase < 4:
                price = 100.0 + phase * 3
            else:
                price = 100.0 + (8 - phase) * 3
            highs.append(price + 0.5)
            lows.append(price - 0.5)
        ms = build_market_structure(highs, lows, current_price=105.0, config=cfg)
        if len(ms.supports) >= 2:
            distances = [abs(s.price - 105.0) for s in ms.supports]
            assert distances == sorted(distances), "Supports not sorted nearest-first"


# ---------------------------------------------------------------------------
# SL Shield Tests
# ---------------------------------------------------------------------------


class TestSLShield:
    def test_long_sl_pushed_behind_support(self):
        """Long: support at $63,800, ATR SL at $63,500 → SL pushed below support."""
        structure = MarketStructure(
            supports=[SwingLevel(63800.0, 100, "support", 3, 20)],
            resistances=[],
            current_price=65000.0,
        )
        result = adjust_sl_tp_for_structure(
            side="long",
            sl_price=63500.0,  # ATR-based SL
            tp_price=67000.0,
            entry_price=65000.0,
            structure=structure,
        )
        # Support at 63800 is between SL (63500) and entry (65000)
        # Shield pushes SL behind support: 63800 * 0.998 = 63672.4
        # SL moves UP from 63500 to 63672 (behind the wall, structurally protected)
        assert result.sl_adjusted is True
        assert result.sl_price < 63800.0  # Below support level
        assert result.sl_price > 63500.0  # Moved UP from original SL
        assert "sl_shield" in result.reason

    def test_long_sl_no_support_outside_range(self):
        """Support below the SL → not in shieldable range → no adjustment."""
        structure = MarketStructure(
            supports=[SwingLevel(63000.0, 100, "support", 2, 15)],
            resistances=[],
            current_price=65000.0,
        )
        result = adjust_sl_tp_for_structure(
            side="long",
            sl_price=63500.0,
            tp_price=67000.0,
            entry_price=65000.0,
            structure=structure,
        )
        # Support at 63000 is BELOW SL (63500) → not between (SL, entry) → no shield
        assert result.sl_adjusted is False
        assert result.sl_price == pytest.approx(63500.0)

    def test_short_sl_pushed_behind_resistance(self):
        """Short: resistance at $66,200, ATR SL at $66,500 → SL pushed below to behind resistance."""
        structure = MarketStructure(
            supports=[],
            resistances=[SwingLevel(66200.0, 100, "resistance", 2, 15)],
            current_price=65000.0,
        )
        result = adjust_sl_tp_for_structure(
            side="short",
            sl_price=66500.0,
            tp_price=63000.0,
            entry_price=65000.0,
            structure=structure,
        )
        # Resistance at 66200 between entry (65000) and SL (66500)
        # Shield: 66200 * 1.002 = 66332.4 — just above resistance, below original SL
        # SL moves DOWN from 66500 to 66332 (behind the wall)
        assert result.sl_adjusted is True
        assert result.sl_price > 66200.0  # Above resistance
        assert result.sl_price < 66500.0  # Moved DOWN from original SL
        assert "sl_shield" in result.reason

    def test_sl_max_expansion_respected(self):
        """SL cannot expand beyond max_expansion_pct of original distance."""
        structure = MarketStructure(
            supports=[SwingLevel(60000.0, 50, "support", 2, 30)],
            resistances=[],
            current_price=65000.0,
        )
        result = adjust_sl_tp_for_structure(
            side="long",
            sl_price=63500.0,  # Original dist = 1500
            tp_price=67000.0,
            entry_price=65000.0,
            structure=structure,
            sl_max_expansion_pct=0.1,  # Max 10% expansion = 150 more
        )
        # Support at 60000 is very far — expansion would be huge → capped
        assert result.sl_adjusted is False

    def test_no_structure_no_adjustment(self):
        """Empty structure → passthrough."""
        structure = MarketStructure(current_price=65000.0)
        result = adjust_sl_tp_for_structure(
            side="long",
            sl_price=63500.0,
            tp_price=67000.0,
            entry_price=65000.0,
            structure=structure,
        )
        assert result.sl_adjusted is False
        assert result.tp_adjusted is False
        assert result.sl_price == pytest.approx(63500.0)
        assert result.tp_price == pytest.approx(67000.0)


# ---------------------------------------------------------------------------
# TP Magnet Tests
# ---------------------------------------------------------------------------


class TestTPMagnet:
    def test_long_tp_pulled_before_resistance(self):
        """Long: resistance at $66,800, ATR TP at $67,000 → TP pulled below resistance."""
        structure = MarketStructure(
            supports=[],
            resistances=[SwingLevel(66800.0, 100, "resistance", 3, 20)],
            current_price=65000.0,
        )
        result = adjust_sl_tp_for_structure(
            side="long",
            sl_price=63500.0,
            tp_price=67000.0,  # ATR TP
            entry_price=65000.0,
            structure=structure,
            tp_magnet_zone_pct=0.20,
        )
        # TP range = 67000 - 65000 = 2000
        # Magnet zone starts at 65000 + 2000*0.80 = 66600
        # Resistance at 66800 is in [66600, 67000] → magnet activates
        assert result.tp_adjusted is True
        assert result.tp_price < 66800.0  # Pulled below resistance
        assert result.tp_price > 65000.0  # Still profitable
        assert "tp_magnet" in result.reason

    def test_long_tp_not_pulled_outside_zone(self):
        """Resistance too far from TP → no magnetization."""
        structure = MarketStructure(
            supports=[],
            resistances=[SwingLevel(65500.0, 100, "resistance", 3, 20)],
            current_price=65000.0,
        )
        result = adjust_sl_tp_for_structure(
            side="long",
            sl_price=63500.0,
            tp_price=67000.0,
            entry_price=65000.0,
            structure=structure,
            tp_magnet_zone_pct=0.20,
        )
        # Resistance at 65500 is NOT in last 20% zone [66600, 67000]
        assert result.tp_adjusted is False
        assert result.tp_price == pytest.approx(67000.0)

    def test_both_sl_and_tp_adjusted(self):
        """Both SL Shield and TP Magnet can fire simultaneously."""
        structure = MarketStructure(
            supports=[SwingLevel(63800.0, 80, "support", 2, 20)],
            resistances=[SwingLevel(66800.0, 90, "resistance", 3, 15)],
            current_price=65000.0,
        )
        result = adjust_sl_tp_for_structure(
            side="long",
            sl_price=63500.0,
            tp_price=67000.0,
            entry_price=65000.0,
            structure=structure,
        )
        assert result.sl_adjusted is True
        assert result.tp_adjusted is True
        assert "sl_shield" in result.reason
        assert "tp_magnet" in result.reason
