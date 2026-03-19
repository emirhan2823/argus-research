"""Triple-barrier labeling utilities."""

from __future__ import annotations

import pandas as pd


def triple_barrier_label(
    close: pd.Series,
    *,
    take_profit_pct: float,
    stop_loss_pct: float,
    horizon: int,
) -> pd.Series:
    labels = []
    values = close.values.astype(float)
    n = len(values)
    for i in range(n):
        entry = values[i]
        tp = entry * (1.0 + take_profit_pct)
        sl = entry * (1.0 - stop_loss_pct)
        end = min(n, i + horizon + 1)
        out = 0
        for j in range(i + 1, end):
            px = values[j]
            if px >= tp:
                out = 1
                break
            if px <= sl:
                out = -1
                break
        labels.append(out)
    return pd.Series(labels, index=close.index, name="label")
