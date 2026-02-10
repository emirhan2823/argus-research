"""Meta-label agreement filter."""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray


def meta_label_filter(
    *,
    direction_pred: NDArray[np.float64] | NDArray[np.int_],
    meta_prob: NDArray[np.float64],
    threshold: float = 0.55,
) -> NDArray[np.float64]:
    direction_pred_arr = np.asarray(direction_pred, dtype=float)
    meta_prob_arr = np.asarray(meta_prob, dtype=float)
    agree = meta_prob_arr >= threshold
    return np.where(agree, direction_pred_arr, 0.0)
