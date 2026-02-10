"""Meta-label agreement filter."""

from __future__ import annotations

import numpy as np


def meta_label_filter(
    *,
    direction_pred: np.ndarray,
    meta_prob: np.ndarray,
    threshold: float = 0.55,
) -> np.ndarray:
    direction_pred = np.asarray(direction_pred)
    meta_prob = np.asarray(meta_prob)
    agree = meta_prob >= threshold
    return np.where(agree, direction_pred, 0)
