"""Phase C – DB tables & telemetry tests."""

from __future__ import annotations

import sqlite3

import pytest

from src.v25.db.migrations import TABLE_DDL, INDEX_DDL
from src.v25.telemetry.log_writer import log_correlation, log_precision_entry


# ── helpers ──────────────────────────────────────────────────────────

def _create_schema(conn: sqlite3.Connection) -> None:
    """Run all TABLE_DDL and INDEX_DDL on the connection."""
    for ddl in TABLE_DDL:
        conn.execute(ddl)
    for ddl in INDEX_DDL:
        conn.execute(ddl)
    conn.commit()


@pytest.fixture()
def mem_conn() -> sqlite3.Connection:
    """In-memory SQLite with full v25 schema applied."""
    conn = sqlite3.connect(":memory:")
    _create_schema(conn)
    yield conn
    conn.close()


# ── C-01 .. C-05: new tables exist ──────────────────────────────────

NEW_TABLES = [
    "correlation_logs",
    "correlation_signals",
    "pyramid_layers",
    "hermes_fusion_log",
    "precision_entries",
]


def test_migration_creates_all_new_tables(mem_conn: sqlite3.Connection) -> None:
    rows = mem_conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()
    existing = {r[0] for r in rows}
    for table in NEW_TABLES:
        assert table in existing, f"Missing table: {table}"


# ── C-09: new indexes exist ─────────────────────────────────────────

NEW_INDEXES = [
    "idx_corr_logs_pair",
    "idx_corr_logs_time",
    "idx_corr_signals_pair",
    "idx_corr_signals_time",
    "idx_pyramid_position",
    "idx_pyramid_time",
    "idx_hermes_fusion_time",
    "idx_hermes_fusion_symbol",
    "idx_precision_entries_time",
    "idx_precision_entries_symbol",
]


def test_new_indexes_exist(mem_conn: sqlite3.Connection) -> None:
    rows = mem_conn.execute(
        "SELECT name FROM sqlite_master WHERE type='index'"
    ).fetchall()
    existing = {r[0] for r in rows}
    for idx in NEW_INDEXES:
        assert idx in existing, f"Missing index: {idx}"


# ── C-10: log_correlation ───────────────────────────────────────────

def test_log_correlation_inserts(mem_conn: sqlite3.Connection) -> None:
    log_correlation(
        mem_conn,
        pair_id="BTCETH",
        symbol_a="BTC",
        symbol_b="ETH",
        correlation=0.87,
        spread_zscore=1.5,
        half_life_bars=12.3,
        is_cointegrated=True,
        regime="TRENDING",
        timestamp="2025-06-01T00:00:00Z",
    )
    mem_conn.commit()

    row = mem_conn.execute(
        "SELECT pair_id, symbol_a, symbol_b, correlation, spread_zscore, "
        "half_life_bars, is_cointegrated, regime FROM correlation_logs"
    ).fetchone()
    assert row is not None
    pair_id, sym_a, sym_b, corr, zscore, hl, coint, regime = row
    assert pair_id == "BTCETH"
    assert sym_a == "BTC"
    assert sym_b == "ETH"
    assert corr == pytest.approx(0.87)
    assert zscore == pytest.approx(1.5)
    assert hl == pytest.approx(12.3)
    assert coint == 1
    assert regime == "TRENDING"


# ── C-11: log_precision_entry ───────────────────────────────────────

def test_log_precision_entry_inserts(mem_conn: sqlite3.Connection) -> None:
    log_precision_entry(
        mem_conn,
        symbol="ETH",
        direction="long",
        order_type="limit",
        precision_price=3200.50,
        obi=0.15,
        spread_pct=0.02,
        vwap_dev_pct=-0.3,
        timeout_bars=5,
        reason="OBI favorable + tight spread",
        timestamp="2025-06-01T00:00:00Z",
    )
    mem_conn.commit()

    row = mem_conn.execute(
        "SELECT symbol, direction, order_type, precision_price, obi, "
        "spread_pct, vwap_dev_pct, timeout_bars, reason FROM precision_entries"
    ).fetchone()
    assert row is not None
    sym, direction, otype, pprice, obi, spread, vwap, bars, reason = row
    assert sym == "ETH"
    assert direction == "long"
    assert otype == "limit"
    assert pprice == pytest.approx(3200.50)
    assert obi == pytest.approx(0.15)
    assert spread == pytest.approx(0.02)
    assert vwap == pytest.approx(-0.3)
    assert bars == 5
    assert reason == "OBI favorable + tight spread"


# ── tuple-length sanity checks ──────────────────────────────────────

def test_table_count_total() -> None:
    assert len(TABLE_DDL) == 21, f"Expected 21 TABLE_DDL entries, got {len(TABLE_DDL)}"


def test_index_count_total() -> None:
    assert len(INDEX_DDL) == 37, f"Expected 37 INDEX_DDL entries, got {len(INDEX_DDL)}"
