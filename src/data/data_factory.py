"""Historical OHLCV source orchestration with local-first evolve mode.

Modes:
    mock   - Existing behavior (exchange client or local fallback)
    live   - REST fetch latest from exchange client
    replay - Deterministic load from month-partitioned Parquet (data/binance/)
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Literal, Protocol

import pandas as pd

_LOG = logging.getLogger(__name__)


_OHLCV_ALIASES: dict[str, tuple[str, ...]] = {
    "open": ("open", "o", "Open"),
    "high": ("high", "h", "High"),
    "low": ("low", "l", "Low"),
    "close": ("close", "c", "Close"),
    "volume": ("volume", "v", "Volume", "vol"),
}
_TIME_CANDIDATES: tuple[str, ...] = ("timestamp", "time", "datetime", "date", "ts")


class ExchangeClient(Protocol):
    def fetch_ohlcv(
        self,
        *,
        symbol: str,
        timeframe: str = "1m",
        limit: int = 500,
    ) -> list[list[Any]]:
        ...


def normalize_symbol(symbol: str) -> str:
    """Normalize trading symbol into canonical BASE_QUOTE format."""
    cleaned = str(symbol).strip().upper()
    cleaned = cleaned.replace("-", "/").replace("_", "/")
    parts = [p for p in re.split(r"/+", cleaned) if p]
    if len(parts) >= 2:
        return f"{parts[0]}_{parts[1]}"

    token = re.sub(r"[^A-Z0-9]", "", cleaned)
    if token.endswith("USDT") and len(token) > 4:
        return f"{token[:-4]}_USDT"
    if token.endswith("USD") and len(token) > 3:
        return f"{token[:-3]}_USD"
    return token


def _symbol_key(symbol: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", normalize_symbol(symbol))


@dataclass
class LocalDataProvider:
    root: Path | str = Path("data/time_machine")

    def __post_init__(self) -> None:
        self.root = Path(self.root)

    def resolve_parquet_path(self, symbol: str) -> Path:
        canonical = normalize_symbol(symbol)
        direct = self.root / f"{canonical}.parquet"
        if direct.exists():
            return direct

        target_key = _symbol_key(symbol)
        for candidate in self.root.glob("*.parquet"):
            if _symbol_key(candidate.stem) == target_key:
                return candidate
        return direct

    def map_symbol_to_path(self, symbol: str) -> Path:
        return self.resolve_parquet_path(symbol)

    def load(self, symbol: str) -> pd.DataFrame:
        path = self.resolve_parquet_path(symbol)
        if not path.exists():
            raise FileNotFoundError(f"LocalData parquet not found for symbol={symbol} path={path}")
        return self._read_parquet(path)

    @staticmethod
    def _read_parquet(path: Path) -> pd.DataFrame:
        return pd.read_parquet(path)


@dataclass
class DataFactory:
    """Data source selector for backtest/live/evolve paths.

    Modes:
        "mock"   - (default) ExchangeClient first, local fallback.
        "live"   - Same as mock; explicit alias for real-time data.
        "replay" - Deterministic load from month-partitioned Parquet
                   (data/binance/{SYMBOL}/{interval}/{YYYY-MM}.parquet).

    - In evolve mode, history is strictly loaded from LocalDataProvider.
    - In non-evolve mode, ExchangeClient is used first, then local fallback.
    """

    data_root: Path | str = Path("data/time_machine")
    evolve: bool = False
    exchange_client: ExchangeClient | None = None
    local_provider: LocalDataProvider | None = None
    extreme_gap_floor: pd.Timedelta = pd.Timedelta(days=30)
    mode: str = "mock"  # "mock" | "live" | "replay"
    replay_root: Path | str = Path("data/binance")
    _frame_cache: dict[str, pd.DataFrame] = field(default_factory=dict)
    _cursor: dict[str, int] = field(default_factory=dict)
    _replay_loader: Any = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if self.local_provider is None:
            self.local_provider = LocalDataProvider(root=self.data_root)

        # Lazily initialize replay loader when mode is "replay"
        if self.mode == "replay" and self._replay_loader is None:
            try:
                from src.data.replay_loader import ReplayLoader
                self._replay_loader = ReplayLoader(root=self.replay_root)
                _LOG.info("DataFactory: replay mode enabled (root=%s)", self.replay_root)
            except Exception as exc:
                _LOG.warning("Failed to init ReplayLoader: %s. Falling back to mock.", exc)
                self.mode = "mock"

    def reset_timeline(self, symbol: str) -> None:
        self._cursor[_symbol_key(symbol)] = 0

    def fetch_ohlcv(
        self,
        *,
        symbol: str,
        timeframe: str = "1m",
        limit: int = 500,
        now: datetime | pd.Timestamp | None = None,
    ) -> list[list[Any]]:
        if self.evolve:
            # In evolve mode never call exchange; we want deterministic local replay.
            return self._fetch_local(symbol=symbol, limit=limit, now=now, advance=True)

        # Replay mode: deterministic load from month-partitioned Parquet
        if self.mode == "replay" and self._replay_loader is not None:
            try:
                rows = self._replay_loader.load_ohlcv_rows(
                    symbol=symbol,
                    interval=timeframe,
                    limit=limit,
                    now=now,
                )
                if rows:
                    return rows
            except FileNotFoundError:
                _LOG.debug("Replay data not found for %s/%s, falling back.", symbol, timeframe)

        if self.exchange_client is not None:
            remote = self.exchange_client.fetch_ohlcv(symbol=symbol, timeframe=timeframe, limit=limit)
            if remote:
                return remote

        return self._fetch_local(symbol=symbol, limit=limit, now=now, advance=False)

    def get_ohlcv(
        self,
        *,
        symbol: str,
        timeframe: str = "1m",
        limit: int = 500,
        now: datetime | pd.Timestamp | None = None,
    ) -> list[list[Any]]:
        return self.fetch_ohlcv(
            symbol=symbol,
            timeframe=timeframe,
            limit=limit,
            now=now,
        )

    def map_symbol_to_path(self, symbol: str) -> Path:
        assert self.local_provider is not None
        return self.local_provider.resolve_parquet_path(symbol)

    def load_frame(
        self,
        *,
        symbol: str,
        now: datetime | pd.Timestamp | None = None,
    ) -> pd.DataFrame:
        key = _symbol_key(symbol)
        if key in self._frame_cache:
            return self._frame_cache[key].copy()

        assert self.local_provider is not None
        raw = self.local_provider.load(symbol)
        frame = self._normalize_ohlcv(raw)

        now_ts = self._to_utc_timestamp(now)
        last_ts = frame["timestamp"].iloc[-1]
        first_ts = frame["timestamp"].iloc[0]
        span = max(last_ts - first_ts, pd.Timedelta(minutes=1))
        gap = abs(now_ts - last_ts)
        extreme_threshold = max(self.extreme_gap_floor, span * 3)
        extreme_gap = gap > extreme_threshold

        if self.evolve or extreme_gap:
            # Use parquet time as absolute truth and start replay from row 0.
            runtime_ts = frame["timestamp"]
        else:
            shift = now_ts - last_ts
            runtime_ts = frame["timestamp"] + shift

        out = frame.copy()
        out["timestamp"] = pd.to_datetime(runtime_ts, utc=True)
        out["relative_index"] = range(len(out))
        out = out.reset_index(drop=True)
        self._frame_cache[key] = out
        self._cursor.setdefault(key, 0)
        return out.copy()

    def _fetch_local(
        self,
        *,
        symbol: str,
        limit: int,
        now: datetime | pd.Timestamp | None,
        advance: bool,
    ) -> list[list[Any]]:
        key = _symbol_key(symbol)
        frame = self.load_frame(symbol=symbol, now=now)
        if frame.empty:
            return []

        if advance:
            start = self._cursor.get(key, 0)
            end = min(len(frame), start + max(1, int(limit)))
            chunk = frame.iloc[start:end]
            self._cursor[key] = end
        else:
            chunk = frame.tail(max(1, int(limit)))

        if chunk.empty:
            return []
        return [
            [
                row.timestamp,
                float(row.open),
                float(row.high),
                float(row.low),
                float(row.close),
                float(row.volume),
            ]
            for row in chunk.itertuples(index=False)
        ]

    @staticmethod
    def _to_utc_timestamp(value: datetime | pd.Timestamp | None) -> pd.Timestamp:
        if value is None:
            return pd.Timestamp.now(tz="UTC")
        ts = pd.Timestamp(value)
        if ts.tzinfo is None:
            return ts.tz_localize("UTC")
        return ts.tz_convert("UTC")

    def _normalize_ohlcv(self, frame: pd.DataFrame) -> pd.DataFrame:
        if frame.empty:
            raise ValueError("Loaded parquet frame is empty")

        if isinstance(frame.index, pd.DatetimeIndex) and "timestamp" not in frame.columns:
            index_name = frame.index.name or "index"
            frame = frame.reset_index().rename(columns={index_name: "timestamp"})

        time_col = self._find_time_column(frame)
        ts = self._coerce_timestamp_series(frame[time_col])
        if ts.isna().all():
            raise ValueError("Unable to parse any timestamp values from local parquet")

        normalized = pd.DataFrame({"timestamp": ts})
        for target in ("open", "high", "low", "close", "volume"):
            source = self._find_column(frame, _OHLCV_ALIASES[target])
            if source is None:
                raise ValueError(f"Missing required OHLCV column: {target}")
            normalized[target] = pd.to_numeric(frame[source], errors="coerce")

        normalized = normalized.dropna(subset=["timestamp", "open", "high", "low", "close", "volume"])
        if normalized.empty:
            raise ValueError("No valid OHLCV rows after normalization")

        normalized = normalized.sort_values("timestamp").drop_duplicates(subset=["timestamp"]).reset_index(drop=True)
        return normalized

    def _find_time_column(self, frame: pd.DataFrame) -> str:
        column_map = {str(col).strip().casefold(): str(col) for col in frame.columns}
        for name in _TIME_CANDIDATES:
            match = column_map.get(name.casefold())
            if match is not None:
                return match
        raise ValueError(f"No timestamp column found. Expected one of {_TIME_CANDIDATES}")

    @staticmethod
    def _find_column(frame: pd.DataFrame, aliases: tuple[str, ...]) -> str | None:
        lower_map = {str(c).lower(): str(c) for c in frame.columns}
        for alias in aliases:
            col = lower_map.get(alias.lower())
            if col is not None:
                return col
        return None

    @staticmethod
    def _coerce_timestamp_series(series: pd.Series) -> pd.Series:
        numeric = pd.to_numeric(series, errors="coerce")
        numeric_ratio = float(numeric.notna().mean())

        if numeric_ratio >= 0.8:
            abs_max = float(numeric.abs().max(skipna=True))
            candidate_units: tuple[str, ...]
            if abs_max >= 1e17:
                candidate_units = ("ns", "us", "ms", "s")
            elif abs_max >= 1e14:
                candidate_units = ("us", "ms", "s")
            elif abs_max >= 1e11:
                candidate_units = ("ms", "s")
            else:
                candidate_units = ("s", "ms")

            for unit in candidate_units:
                parsed = pd.to_datetime(numeric, unit=unit, utc=True, errors="coerce")
                if DataFactory._timestamps_look_plausible(parsed):
                    return parsed

        return pd.to_datetime(series, utc=True, errors="coerce")

    @staticmethod
    def _timestamps_look_plausible(ts: pd.Series) -> bool:
        valid = ts.dropna()
        if valid.empty:
            return False
        year_median = float(valid.dt.year.median())
        return 1990 <= year_median <= 2100
