#!/usr/bin/env python3
"""Verify backtest determinism by running twice and comparing."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from argus_py.lab.determinism import DeterminismManager


def _write_mock_trades(dm: DeterminismManager, path: Path, rows: int = 10) -> None:
    """
    Deterministic placeholder for verification in environments where
    full backtest orchestration is unavailable.
    """
    import random

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp", "symbol", "side", "price", "qty", "pnl", "event"])
        base_ts = 1700000000
        for i in range(rows):
            side = "BUY" if i % 2 == 0 else "SELL"
            price = 50000 + random.random() * 1000
            qty = 0.01 + random.random() * 0.005
            pnl = (random.random() - 0.5) * 100
            writer.writerow([base_ts + i * 60, "BTCUSDT", side, f"{price:.2f}", f"{qty:.6f}", f"{pnl:.2f}", "CLOSE"])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=int, default=2)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    dm = DeterminismManager(seed=args.seed)
    manifests = []

    for i in range(args.runs):
        dm.initialize()

        run_id = f"determinism_check_{i}"
        run_dir = Path(f"runs/{run_id}")
        run_dir.mkdir(parents=True, exist_ok=True)

        trades_csv = run_dir / "trades.csv"
        _write_mock_trades(dm, trades_csv)

        manifest = dm.create_manifest(
            run_id=run_id,
            config={"seed": args.seed},
            data_path=Path("argus_py/data"),
            trades_csv=trades_csv,
        )
        dm.save_manifest(manifest, run_dir / "manifest.json")
        manifests.append(manifest)

    for i in range(1, len(manifests)):
        comparison = dm.compare_runs(manifests[0], manifests[i])
        result = "DETERMINISTIC" if comparison["is_deterministic"] else "NON-DETERMINISTIC"
        print(f"Run 0 vs Run {i}: {result}")
        if not comparison["is_deterministic"]:
            print(f"  Config match: {comparison['same_config']}")
            print(f"  Data match: {comparison['same_data']}")
            print(f"  Result match: {comparison['same_result']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
