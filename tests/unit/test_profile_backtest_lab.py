from __future__ import annotations

import sqlite3
from pathlib import Path

import yaml

from Scripts.profile_backtest_lab import (
    _build_variants,
    _compute_metrics,
    _load_strategy_profile_node,
    _score_metrics,
)


def test_build_variants_contains_expected_profiles(tmp_path: Path) -> None:
    path = tmp_path / "strategy_profiles.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "strategy_profiles": {
                    "enabled": False,
                    "defaults": {"confidence_shift": 0.0, "sl_mult": 1.0, "tp_mult": 1.0},
                    "profiles": {
                        "trend": {
                            "long": {
                                "normal_vol": {
                                    "min_confidence": 0.6,
                                    "min_rr": 2.0,
                                    "crypto_min_rr": 2.1,
                                    "confluence_min_factors": 3,
                                    "confluence_min_score": 0.5,
                                    "tp_mult": 1.1,
                                    "sl_mult": 1.0,
                                }
                            }
                        }
                    },
                }
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    base = _load_strategy_profile_node(path)
    variants = _build_variants(base)
    assert "baseline_no_profiles" in variants
    assert "matrix_default" in variants
    assert "trend_long_bias" in variants
    assert variants["baseline_no_profiles"]["enabled"] is False
    assert variants["matrix_default"]["enabled"] is True


def test_compute_metrics_reads_trade_rows(tmp_path: Path) -> None:
    db_path = tmp_path / "v25.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        """
        CREATE TABLE trades (
            side TEXT,
            net_pnl_pct REAL,
            entry_time TEXT,
            exit_time TEXT
        )
        """
    )
    conn.executemany(
        "INSERT INTO trades(side, net_pnl_pct, entry_time, exit_time) VALUES (?, ?, ?, ?)",
        [
            ("long", 1.2, "2024-01-01T00:00:00Z", "2024-01-01T01:00:00Z"),
            ("short", -0.5, "2024-01-01T02:00:00Z", "2024-01-01T03:00:00Z"),
            ("long", 0.7, "2024-01-01T04:00:00Z", "2024-01-01T05:00:00Z"),
        ],
    )
    conn.commit()
    conn.close()

    metrics = _compute_metrics(db_path)
    assert int(metrics["trades"]) == 3
    assert float(metrics["total_return"]) == 1.4
    assert int(metrics["long_trades"]) == 2
    assert int(metrics["short_trades"]) == 1
    assert _score_metrics(metrics) > -1000

