"""Purged k-fold splitter (time-series aware)."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class PurgedFold:
    train_idx: np.ndarray
    test_idx: np.ndarray


def purged_kfold_indices(n_rows: int, k: int, purge: int = 0) -> list[PurgedFold]:
    if n_rows <= 0 or k <= 1:
        return []
    fold_size = n_rows // k
    folds: list[PurgedFold] = []
    idx = np.arange(n_rows)
    for i in range(k):
        start = i * fold_size
        end = n_rows if i == k - 1 else (i + 1) * fold_size
        test_idx = idx[start:end]
        left_end = max(0, start - purge)
        right_start = min(n_rows, end + purge)
        train_idx = np.concatenate([idx[:left_end], idx[right_start:]])
        folds.append(PurgedFold(train_idx=train_idx, test_idx=test_idx))
    return folds
