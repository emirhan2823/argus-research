#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Tuple
import sys

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from argus_py.ml.signal_model import SignalModel


FEATURE_COLUMNS = [
    "rsi_14",
    "macd_hist",
    "bb_position",
    "atr_pct",
    "volume_ratio",
    "fear_greed",
    "funding_rate",
]


def _load_with_pandas(path: Path) -> Tuple[np.ndarray, np.ndarray]:
    import pandas as pd  # type: ignore

    df = pd.read_csv(path)
    features = df[FEATURE_COLUMNS].values.astype(float)
    labels = df["outcome"].values.astype(int)
    return features, labels


def _load_with_csv(path: Path) -> Tuple[np.ndarray, np.ndarray]:
    feature_rows = []
    labels = []

    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        missing = [col for col in FEATURE_COLUMNS + ["outcome"] if col not in (reader.fieldnames or [])]
        if missing:
            raise ValueError(f"Missing required columns: {missing}")

        for row in reader:
            feature_rows.append([float(row[col]) for col in FEATURE_COLUMNS])
            labels.append(int(float(row["outcome"])))

    return np.asarray(feature_rows, dtype=float), np.asarray(labels, dtype=int)


def load_training_data(path: Path) -> Tuple[np.ndarray, np.ndarray]:
    try:
        return _load_with_pandas(path)
    except Exception:
        return _load_with_csv(path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Train Argus ML signal model")
    parser.add_argument("--input", type=Path, default=Path("runs/training_data.csv"))
    parser.add_argument("--output", type=Path, default=Path("models/signal_model.lgb"))
    args = parser.parse_args()

    if not args.input.exists():
        raise SystemExit(f"Training file not found: {args.input}")

    features, labels = load_training_data(args.input)
    if features.size == 0:
        raise SystemExit("Training file has no rows")

    model = SignalModel()
    model.train(features, labels)
    model.save(args.output)

    print(f"Model trained and saved to {args.output}")
    print(f"Rows: {len(labels)} | Features: {features.shape[1]} | Backend: {model.backend or 'none'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
