"""Feature store writer for ML datasets."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


def write_features(path: str, frame: pd.DataFrame) -> str:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(out, index=False)
    return str(out)
