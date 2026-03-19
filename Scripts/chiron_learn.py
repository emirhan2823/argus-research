#!/usr/bin/env python3
"""
Weekly Chiron learning job.
Analyzes past week's trades and updates weight recommendations.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from argus_py.models.chiron.learner import ChironLearner


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir", help="Run directory with CSVs")
    parser.add_argument("--output", default="chiron_weights.json")
    parser.add_argument("--min_samples", type=int, default=5)
    args = parser.parse_args()

    run_dir = Path(args.run_dir)
    learner = ChironLearner(state_path=Path(args.output))

    count = learner.load_outcomes_from_csv(run_dir / "trades.csv", run_dir / "decisions.csv")
    print(f"Loaded {count} trade outcomes")

    for regime in ["TREND", "CHOP", "RISK_OFF", "NEUTRAL"]:
        weights = learner.optimize_weights(regime, min_samples=args.min_samples)
        if weights:
            record = learner.records[regime]
            print(f"\n{regime}:")
            print(f"  Samples: {record.sample_count}")
            print(f"  Win Rate: {record.win_rate:.1%}")
            print(f"  Sharpe: {record.sharpe:.2f}")
            print(f"  Weights: {weights}")

    learner.save_state()
    print(f"\nSaved to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
