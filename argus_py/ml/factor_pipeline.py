from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, Iterable, List, Optional, Sequence

import pandas as pd

from .builtin_factors import FactorFn, builtin_factor_map


@dataclass(frozen=True)
class FactorPipelineResult:
    factors: pd.DataFrame
    target: Optional[pd.Series] = None


class FactorPipeline:
    """Zipline-inspired factor pipeline for OHLCV features."""

    REQUIRED_COLUMNS = ("open", "high", "low", "close", "volume")

    def __init__(self, factor_map: Optional[Dict[str, FactorFn]] = None) -> None:
        self._factor_map: Dict[str, FactorFn] = dict(factor_map or builtin_factor_map())

    def register(self, name: str, fn: FactorFn) -> None:
        if not name:
            raise ValueError("factor name must be non-empty")
        self._factor_map[str(name)] = fn

    def available_factors(self) -> List[str]:
        return sorted(self._factor_map.keys())

    def compute(
        self,
        ohlcv: pd.DataFrame,
        factor_names: Optional[Sequence[str]] = None,
        dropna: bool = True,
    ) -> pd.DataFrame:
        self._validate_input(ohlcv)
        names = list(factor_names) if factor_names is not None else self.available_factors()

        output: Dict[str, pd.Series] = {}
        for name in names:
            if name not in self._factor_map:
                raise KeyError(f"unknown factor: {name}")
            series = self._factor_map[name](ohlcv)
            if not isinstance(series, pd.Series):
                raise TypeError(f"factor '{name}' must return pandas Series")
            if len(series) != len(ohlcv):
                raise ValueError(f"factor '{name}' length mismatch")
            output[name] = series.astype(float)

        frame = pd.DataFrame(output, index=ohlcv.index)
        if dropna:
            frame = frame.dropna(axis=0, how="any")
        return frame

    def build_dataset(
        self,
        ohlcv: pd.DataFrame,
        factor_names: Optional[Sequence[str]] = None,
        horizon: int = 1,
        target_name: str = "target_ret",
    ) -> FactorPipelineResult:
        if horizon < 1:
            raise ValueError("horizon must be >= 1")
        factors = self.compute(ohlcv, factor_names=factor_names, dropna=False)
        target = ohlcv["close"].pct_change(horizon).shift(-horizon).rename(target_name)
        joined = factors.join(target, how="left").dropna(axis=0, how="any")
        return FactorPipelineResult(
            factors=joined[factors.columns].copy(),
            target=joined[target_name].copy(),
        )

    def _validate_input(self, ohlcv: pd.DataFrame) -> None:
        missing = [c for c in self.REQUIRED_COLUMNS if c not in ohlcv.columns]
        if missing:
            raise ValueError(f"missing required columns: {missing}")
        if len(ohlcv) < 30:
            raise ValueError("at least 30 rows are required")
        if not ohlcv.index.is_monotonic_increasing:
            raise ValueError("ohlcv index must be monotonic increasing")


__all__ = ["FactorPipeline", "FactorPipelineResult", "FactorFn"]
