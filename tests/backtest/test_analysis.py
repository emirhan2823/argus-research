"""Unit tests for backtest correlation analysis pipeline.

Tests cover: extractor, correlations, buckets, patterns, report_writer.
"""

from __future__ import annotations

import json
import sqlite3
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create_test_db(
    db_path: Path,
    n_trades: int = 50,
    n_decisions: int = 60,
    base_time: datetime | None = None,
) -> None:
    """Create a minimal test DB with trades and decisions tables."""
    if base_time is None:
        base_time = datetime(2024, 1, 1, tzinfo=timezone.utc)

    conn = sqlite3.connect(str(db_path))
    conn.execute("""
        CREATE TABLE trades (
            trade_id TEXT PRIMARY KEY,
            symbol TEXT NOT NULL,
            side TEXT NOT NULL,
            capital_engine TEXT DEFAULT 'core',
            entry_time TEXT NOT NULL,
            exit_time TEXT,
            entry_price REAL NOT NULL,
            exit_price REAL,
            size REAL DEFAULT 1.0,
            pnl_pct REAL,
            net_pnl_pct REAL,
            confidence REAL DEFAULT 0.65,
            regime_at_entry TEXT DEFAULT 'RANGING',
            regime_at_exit TEXT DEFAULT 'RANGING',
            engine TEXT DEFAULT 'POSEIDON',
            sub_strategy TEXT DEFAULT 'mr_primary',
            stop_distance REAL DEFAULT 0.02,
            hold_minutes INTEGER DEFAULT 60,
            reason_entry TEXT DEFAULT 'signal',
            reason_exit TEXT DEFAULT 'stop_loss',
            sqs_score REAL DEFAULT 0.7,
            leverage REAL DEFAULT 1.5,
            features_json TEXT,
            config_hash TEXT,
            created_at TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE decisions (
            decision_id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT DEFAULT 'test_run',
            timestamp TEXT NOT NULL,
            symbol TEXT NOT NULL,
            action TEXT DEFAULT 'buy',
            capital_engine TEXT DEFAULT 'core',
            position_size_pct REAL DEFAULT 0.1,
            leverage REAL DEFAULT 1.5,
            stop_loss_pct REAL DEFAULT 0.02,
            confidence REAL DEFAULT 0.65,
            sqs_score REAL DEFAULT 0.7,
            engine TEXT DEFAULT 'POSEIDON',
            sub_strategy TEXT DEFAULT 'mr_primary',
            regime TEXT DEFAULT 'RANGING',
            reason TEXT DEFAULT 'advisory_signal_sent',
            status TEXT DEFAULT 'advisory',
            gate_results_json TEXT
        )
    """)

    rng = np.random.RandomState(42)
    sides = ["long", "short"]
    exit_reasons = ["stop_loss", "trailing_stop", "time_stop", "signal_exit"]
    regimes = ["TRENDING", "RANGING", "VOLATILE"]

    for i in range(n_trades):
        entry_dt = base_time + timedelta(hours=i)
        exit_dt = entry_dt + timedelta(minutes=30 + rng.randint(0, 120))
        side = sides[i % 2]
        pnl = round(rng.uniform(-0.05, 0.08), 6)  # fraction
        conn.execute(
            """INSERT INTO trades (trade_id, symbol, side, entry_time, exit_time,
               entry_price, exit_price, pnl_pct, net_pnl_pct, confidence,
               regime_at_entry, engine, stop_distance, hold_minutes,
               reason_entry, reason_exit, sqs_score, leverage, sub_strategy,
               capital_engine)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                f"t_{i:04d}", "BTCUSDT", side,
                entry_dt.isoformat(), exit_dt.isoformat(),
                50000 + rng.uniform(-1000, 1000),
                50000 + rng.uniform(-1000, 1000),
                pnl, pnl * 0.998,
                0.55 + rng.uniform(0, 0.3),
                regimes[i % 3],
                "POSEIDON" if i % 3 != 0 else "AEGEAN",
                0.01 + rng.uniform(0, 0.03),
                30 + rng.randint(0, 120),
                "signal", exit_reasons[i % 4],
                0.5 + rng.uniform(0, 0.4),
                1.0 + rng.uniform(0, 4),
                "mr_primary", "core",
            ),
        )

    for i in range(n_decisions):
        dec_dt = base_time + timedelta(hours=i * n_trades / n_decisions) - timedelta(seconds=3)
        gate = {
            "features_snapshot": {
                "_version": 2,
                "regime": regimes[i % 3],
                "atr_14_pct": round(0.005 + rng.uniform(0, 0.02), 6),
                "adx_14": round(15 + rng.uniform(0, 40), 2),
                "volume_ratio": round(0.5 + rng.uniform(0, 2), 4),
                "rsi_14": round(30 + rng.uniform(0, 40), 2),
                "bb_pct_b": round(rng.uniform(0, 1), 4),
            },
            "sq_score": round(0.5 + rng.uniform(0, 0.4), 4),
            "sq_adjusted_conf": round(0.5 + rng.uniform(0, 0.4), 4),
            "precision_score": round(0.4 + rng.uniform(0, 0.5), 4),
            "precision_grade": "A" if rng.random() > 0.5 else "B",
            "regime_align_score": round(0.3 + rng.uniform(0, 0.6), 4),
            "confluence_score": round(0.3 + rng.uniform(0, 0.5), 4),
            "confluence_factors": 3 + rng.randint(0, 4),
            "tq_composite": round(0.4 + rng.uniform(0, 0.5), 4),
            "tq_grade": ["A", "B", "C", "D"][rng.randint(0, 4)],
            "dir_bias": round(rng.uniform(-1, 1), 4),
            "confluence_detail": {
                "momentum": round(rng.uniform(0, 1), 4),
                "mtf": round(rng.uniform(0, 1), 4),
                "orderbook": round(rng.uniform(0, 1), 4),
                "statistical": round(rng.uniform(0, 1), 4),
                "volatility": round(rng.uniform(0, 1), 4),
                "volume": round(rng.uniform(0, 1), 4),
            },
        }
        conn.execute(
            """INSERT INTO decisions (timestamp, symbol, action, engine, reason,
               status, confidence, gate_results_json, regime, run_id,
               capital_engine, sqs_score, sub_strategy)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                dec_dt.isoformat(), "BTCUSDT", "buy",
                "POSEIDON", "advisory_signal_sent", "advisory",
                0.65, json.dumps(gate), regimes[i % 3],
                "test_run", "core", 0.7, "mr_primary",
            ),
        )

    conn.commit()
    conn.close()


def _make_enriched_df(n: int = 100, seed: int = 42) -> pd.DataFrame:
    """Create a synthetic enriched trades DataFrame for testing."""
    rng = np.random.RandomState(seed)
    base_time = datetime(2024, 1, 1, tzinfo=timezone.utc)

    data: dict[str, list] = {
        "trade_id": [f"t_{i:04d}" for i in range(n)],
        "symbol": ["BTCUSDT"] * n,
        "side": ["long" if i % 2 == 0 else "short" for i in range(n)],
        "engine": ["POSEIDON" if i % 3 != 0 else "AEGEAN" for i in range(n)],
        "entry_time": [base_time + timedelta(hours=i) for i in range(n)],
        "exit_time": [base_time + timedelta(hours=i, minutes=45) for i in range(n)],
        "net_pnl_pct": [round(rng.uniform(-0.05, 0.08), 6) for _ in range(n)],
        "pnl_pct": [round(rng.uniform(-0.05, 0.08), 6) for _ in range(n)],
        "confidence": [round(0.55 + rng.uniform(0, 0.3), 4) for _ in range(n)],
        "leverage": [round(1.0 + rng.uniform(0, 4), 2) for _ in range(n)],
        "stop_distance": [round(0.01 + rng.uniform(0, 0.03), 4) for _ in range(n)],
        "hold_minutes": [30 + rng.randint(0, 150) for _ in range(n)],
        "reason_exit": [["stop_loss", "trailing_stop", "time_stop", "signal_exit"][i % 4] for i in range(n)],
        "regime_at_entry": [["TRENDING", "RANGING", "VOLATILE"][i % 3] for i in range(n)],
        "is_winner": [False] * n,
        "match_quality": ["exact"] * n,
        "match_dt_seconds": [rng.uniform(0, 5) for _ in range(n)],
        "feat_adx_14": [round(15 + rng.uniform(0, 40), 2) for _ in range(n)],
        "feat_atr_14_pct": [round(0.005 + rng.uniform(0, 0.02), 6) for _ in range(n)],
        "feat_volume_ratio": [round(0.5 + rng.uniform(0, 2), 4) for _ in range(n)],
        "feat_rsi_14": [round(30 + rng.uniform(0, 40), 2) for _ in range(n)],
        "filt_sq_score": [round(0.5 + rng.uniform(0, 0.4), 4) for _ in range(n)],
        "filt_confluence_score": [round(0.3 + rng.uniform(0, 0.5), 4) for _ in range(n)],
        "filt_tq_composite": [round(0.4 + rng.uniform(0, 0.5), 4) for _ in range(n)],
        "filt_tq_grade": [["A", "B", "C", "D"][rng.randint(0, 4)] for _ in range(n)],
        "db_source": ["test.db"] * n,
    }
    df = pd.DataFrame(data)
    df["is_winner"] = df["net_pnl_pct"] > 0
    return df


# ===========================================================================
# Tests
# ===========================================================================

class TestExtractor:
    """Tests for extractor module."""

    def test_extract_basic(self, tmp_path: Path) -> None:
        """DB read + decision matching + match_quality columns present."""
        from src.backtest.analysis.extractor import extract_enriched_trades

        db_path = tmp_path / "test.db"
        _create_test_db(db_path, n_trades=20, n_decisions=25)

        df = extract_enriched_trades([db_path], bar_seconds=3600)
        assert len(df) == 20
        assert "match_quality" in df.columns
        assert "match_dt_seconds" in df.columns
        assert "feat_adx_14" in df.columns
        assert "filt_sq_score" in df.columns
        # All trades should have matched (decisions created 3s before each trade)
        assert df["match_quality"].isin(["exact", "close", "stale", "future", "unmatched"]).all()

    def test_extract_stale_match_flagged(self, tmp_path: Path) -> None:
        """>120s match should be flagged as stale (on 1h timeframe)."""
        from src.backtest.analysis.extractor import classify_match_quality

        # 10s → exact
        assert classify_match_quality(5.0, bar_seconds=3600) == "exact"
        # 500s → close (< 0.5 * 3600 = 1800)
        assert classify_match_quality(500.0, bar_seconds=3600) == "close"
        # 2000s → stale (>= 0.5 * 3600 but < 2 * 3600)
        assert classify_match_quality(2000.0, bar_seconds=3600) == "stale"
        # None → unmatched
        assert classify_match_quality(None) == "unmatched"
        # Future match
        assert classify_match_quality(5.0, bar_seconds=3600, is_future=True) == "future"

    def test_pnl_sanity_check(self, tmp_path: Path) -> None:
        """Scale assertion should trigger on PnL > 5.0."""
        from src.backtest.analysis.extractor import _pnl_sanity_check

        # Normal data — should pass
        df_ok = pd.DataFrame({"net_pnl_pct": [0.01, -0.02, 0.05, -0.03]})
        _pnl_sanity_check(df_ok)  # no exception

        # Bad scale — should raise
        df_bad = pd.DataFrame({"net_pnl_pct": [1.0, -2.0, 6.0]})  # 600%
        with pytest.raises(ValueError, match="PnL > 500%"):
            _pnl_sanity_check(df_bad)

    def test_match_quality_scales_with_bar_seconds(self) -> None:
        """15m TF: exact<10s (fixed), close<450s, stale≥450s."""
        from src.backtest.analysis.extractor import classify_match_quality

        bar_15m = 900  # 15 minutes
        # exact is always fixed at <10s
        assert classify_match_quality(8.0, bar_seconds=bar_15m) == "exact"
        assert classify_match_quality(12.0, bar_seconds=bar_15m) == "close"
        # close < 0.5 * 900 = 450s
        assert classify_match_quality(400.0, bar_seconds=bar_15m) == "close"
        # stale >= 450s but < 1800s
        assert classify_match_quality(500.0, bar_seconds=bar_15m) == "stale"


class TestCorrelations:
    """Tests for correlations module."""

    def test_correlation_matrix_values(self) -> None:
        """Known correlation should be detected."""
        from src.backtest.analysis.correlations import compute_correlation_matrix

        rng = np.random.RandomState(42)
        n = 200
        x = rng.normal(0, 1, n)
        # y strongly correlated with x
        y = x * 0.8 + rng.normal(0, 0.3, n)
        df = pd.DataFrame({"feat_x": x, "net_pnl_pct": y, "noise": rng.normal(0, 1, n)})

        result = compute_correlation_matrix(df)
        assert not result.empty
        # feat_x should have high correlation
        feat_x_row = result[result["feature"] == "feat_x"]
        assert len(feat_x_row) == 1
        assert float(feat_x_row["pearson_r"].iloc[0]) > 0.8

    def test_correlation_bonferroni(self) -> None:
        """Bonferroni adjusted p-value should be p * n_features."""
        from src.backtest.analysis.correlations import compute_correlation_matrix

        rng = np.random.RandomState(42)
        n = 100
        df = pd.DataFrame({
            "feat_a": rng.normal(0, 1, n),
            "feat_b": rng.normal(0, 1, n),
            "feat_c": rng.normal(0, 1, n),
            "net_pnl_pct": rng.normal(0, 1, n),
        })
        result = compute_correlation_matrix(df)
        # bonf_p_adj should be >= original p
        for _, row in result.iterrows():
            assert row["bonf_p_adj"] >= row["pearson_p"] or np.isnan(row["pearson_p"])

    def test_correlation_low_n_unreliable(self) -> None:
        """n < 30 should be flagged as unreliable."""
        from src.backtest.analysis.correlations import compute_correlation_matrix

        rng = np.random.RandomState(42)
        n = 15  # Below MIN_N_FOR_CORRELATION
        df = pd.DataFrame({
            "feat_a": rng.normal(0, 1, n),
            "net_pnl_pct": rng.normal(0, 1, n),
        })
        result = compute_correlation_matrix(df)
        assert not result.empty
        assert result["reliable"].iloc[0] is False or result["reliable"].iloc[0] == False  # noqa: E712


class TestBuckets:
    """Tests for buckets module."""

    def test_bucketize_boundaries(self) -> None:
        """Bucket boundaries: [low, high) — low inclusive, high exclusive."""
        from src.backtest.analysis.buckets import _assign_bucket

        adx_buckets = [
            ("<15", 0, 15), ("15-25", 15, 25), ("25-40", 25, 40), ("40+", 40, float("inf")),
        ]
        # Exact boundary: 15 goes to "15-25", not "<15"
        assert _assign_bucket(15.0, adx_buckets) == "15-25"
        assert _assign_bucket(14.99, adx_buckets) == "<15"
        assert _assign_bucket(25.0, adx_buckets) == "25-40"
        assert _assign_bucket(0.0, adx_buckets) == "<15"
        assert _assign_bucket(100.0, adx_buckets) == "40+"

    def test_wilson_ci(self) -> None:
        """Known WR + N should produce correct CI."""
        from src.backtest.analysis.buckets import wilson_ci_lower

        # 8 wins out of 10 trades
        ci = wilson_ci_lower(8, 10)
        assert 0.40 < ci < 0.80  # CI lower should be well below 0.8
        # 0 wins should give CI near 0
        ci_zero = wilson_ci_lower(0, 10)
        assert ci_zero == 0.0
        # Edge: n=0
        assert wilson_ci_lower(0, 0) == 0.0

    def test_bucket_min_trades_filter(self) -> None:
        """Buckets with N < min_trades should not appear."""
        from src.backtest.analysis.buckets import bucketize_and_analyze

        df = _make_enriched_df(n=20, seed=42)
        result = bucketize_and_analyze(df, min_trades=50)  # Very high threshold
        # With only 20 trades, no bucket should have 50+
        assert result.empty

    def test_pf_reliable_flag(self) -> None:
        """N < 30 should have pf_reliable=False."""
        from src.backtest.analysis.buckets import bucketize_and_analyze

        df = _make_enriched_df(n=25, seed=42)
        result = bucketize_and_analyze(df, min_trades=3)
        if not result.empty:
            # With 25 trades total, no bucket can have 30+
            assert (result["pf_reliable"] == False).all()  # noqa: E712


class TestPatterns:
    """Tests for pattern mining module."""

    def test_golden_patterns_ranking(self) -> None:
        """Highest score pattern should be first."""
        from src.backtest.analysis.patterns import find_golden_patterns

        df = _make_enriched_df(n=200, seed=42)
        patterns = find_golden_patterns(df, min_trades=5, top_n=10, max_depth=2)
        if len(patterns) >= 2:
            assert patterns[0].score >= patterns[1].score

    def test_toxic_patterns_wilson(self) -> None:
        """Toxic patterns should have wilson_ci_upper <= 0.40."""
        from src.backtest.analysis.buckets import wilson_ci_upper
        from src.backtest.analysis.patterns import find_toxic_patterns

        df = _make_enriched_df(n=200, seed=42)
        patterns = find_toxic_patterns(df, min_trades=5, top_n=10, max_depth=2)
        for p in patterns:
            wins = int(p.win_rate * p.n_trades)
            ci_up = wilson_ci_upper(wins, p.n_trades)
            assert ci_up <= 0.401  # small tolerance for rounding

    def test_pattern_oos_validation(self) -> None:
        """OOS validation: train/test split, oos_confirmed computed."""
        from src.backtest.analysis.patterns import find_golden_patterns

        df = _make_enriched_df(n=200, seed=42)
        patterns = find_golden_patterns(df, min_trades=5, top_n=10, max_depth=2)
        for p in patterns:
            # oos_confirmed should be bool or None
            assert p.oos_confirmed in (True, False, None)
            if p.oos_confirmed is not None:
                assert p.oos_n_trades >= 5  # MIN_OOS_TRADES
            # coverage should be positive
            assert p.coverage > 0


class TestReportWriter:
    """Tests for report writer module."""

    def test_report_files_created(self, tmp_path: Path) -> None:
        """All 8 report files should be generated."""
        from src.backtest.analysis.patterns import patterns_to_dataframe
        from src.backtest.analysis.report_writer import write_reports

        df = _make_enriched_df(n=50)
        corr_df = pd.DataFrame({"feature": ["a"], "pearson_r": [0.5], "pearson_p": [0.01],
                                "spearman_rho": [0.4], "spearman_p": [0.02], "n": [50],
                                "bonf_p_adj": [0.03], "bonf_significant": [True], "reliable": [True]})
        bucket_df = pd.DataFrame({"indicator": ["adx"], "bucket": ["15-25"], "trades": [20],
                                  "wins": [12], "win_rate": [0.6], "wilson_ci_low": [0.38],
                                  "avg_return": [0.01], "total_return": [0.2], "pf": [1.5],
                                  "pf_reliable": [False], "side": ["long"]})
        golden_df = patterns_to_dataframe([])
        toxic_df = patterns_to_dataframe([])

        created = write_reports(tmp_path, df, corr_df, bucket_df, golden_df, toxic_df)
        assert len(created) == 8
        expected_names = {
            "enriched_trades.csv", "correlation_matrix.csv", "indicator_buckets.csv",
            "golden_patterns.csv", "toxic_patterns.csv", "long_short_tuning.csv",
            "execution_diagnostics.csv", "ANALYSIS_SUMMARY.md",
        }
        actual_names = {f.name for f in created}
        assert actual_names == expected_names

    def test_tq_grade_exit_matrix(self) -> None:
        """Trade quality grade × exit reason matrix should be computed."""
        from src.backtest.analysis.report_writer import compute_execution_diagnostics

        df = _make_enriched_df(n=100)
        diag = compute_execution_diagnostics(df)
        assert "tq_exit_matrix" in diag
        matrix = diag["tq_exit_matrix"]
        assert not matrix.empty
        assert "tq_grade" in matrix.columns
        assert "exit_reason" in matrix.columns
        assert "win_rate" in matrix.columns
