#!/usr/bin/env python3
"""Multi-provider historical OHLCV backfill (resume-safe, yearly parquet).

Compatibility output:
    data/binance/{symbol}/{timeframe}/YYYY.parquet

Raw provider output:
    data/market/{provider}/{symbol}/{timeframe}/YYYY.parquet
"""

from __future__ import annotations

import argparse
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import sys

import pandas as pd

# Allow running via: python Scripts/backfill.py
_SCRIPT_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _SCRIPT_DIR.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from Scripts.providers import available_providers, create_provider
from Scripts.providers.base import INTERVAL_MS, OHLCVProvider, OHLCVRow

LOG = logging.getLogger("backfill")

DEFAULT_SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT"]
KLINE_COLUMNS = [
    "timestamp",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "close_time",
    "quote_volume",
    "num_trades",
    "taker_buy_volume",
    "taker_buy_quote_volume",
]


def _normalize_symbol(symbol: str) -> str:
    return symbol.upper().replace("/", "").replace("_", "").replace("-", "")


def _parse_date_utc(value: str) -> datetime:
    parsed = datetime.strptime(value, "%Y-%m-%d")
    return parsed.replace(tzinfo=timezone.utc)


def _to_ms(dt: datetime) -> int:
    return int(dt.timestamp() * 1000)


def _align_ms_floor(ts_ms: int, interval_ms: int) -> int:
    return (ts_ms // interval_ms) * interval_ms


def _ts_col_to_ms(series: "pd.Series") -> "pd.Series":
    """Convert a tz-aware timestamp column to milliseconds (portable across pandas 2/3)."""
    return series.apply(lambda t: int(t.timestamp() * 1000))


def _empty_kline_frame() -> pd.DataFrame:
    return pd.DataFrame(columns=KLINE_COLUMNS)


def _ensure_utc_timestamp(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df.copy()
    out = df.copy()
    out["timestamp"] = pd.to_datetime(out["timestamp"], utc=True)
    if "close_time" in out.columns:
        out["close_time"] = pd.to_datetime(out["close_time"], utc=True)
    return out


def _read_year_parquet(path: Path) -> pd.DataFrame:
    if not path.exists():
        return _empty_kline_frame()
    try:
        frame = pd.read_parquet(path)
    except Exception as exc:  # pragma: no cover - defensive runtime path
        LOG.warning("Failed to read parquet %s: %s", path, exc)
        return _empty_kline_frame()
    if frame.empty:
        return _empty_kline_frame()
    frame = _ensure_utc_timestamp(frame)
    for col in KLINE_COLUMNS:
        if col not in frame.columns:
            frame[col] = pd.NA
    return frame[KLINE_COLUMNS].copy()


def _merge_dedup_aligned(
    existing: pd.DataFrame,
    incoming: pd.DataFrame,
    *,
    interval_ms: int,
) -> pd.DataFrame:
    if existing.empty and incoming.empty:
        return _empty_kline_frame()
    if existing.empty:
        merged = incoming.copy()
    elif incoming.empty:
        merged = existing.copy()
    else:
        merged = pd.concat([existing, incoming], ignore_index=True)
    if merged.empty:
        return _empty_kline_frame()

    merged = _ensure_utc_timestamp(merged)
    ts_ms = _ts_col_to_ms(merged["timestamp"])
    aligned_ms = (ts_ms // interval_ms) * interval_ms
    merged["timestamp"] = pd.to_datetime(aligned_ms, unit="ms", utc=True)
    merged["close_time"] = pd.to_datetime(aligned_ms + interval_ms - 1, unit="ms", utc=True)
    merged = (
        merged.drop_duplicates(subset=["timestamp"], keep="last")
        .sort_values("timestamp")
        .reset_index(drop=True)
    )
    for col in KLINE_COLUMNS:
        if col not in merged.columns:
            merged[col] = pd.NA
    return merged[KLINE_COLUMNS].copy()


def _compat_year_path(root: Path, symbol: str, timeframe: str, year: int) -> Path:
    return root / _normalize_symbol(symbol) / timeframe / f"{year}.parquet"


def _raw_year_path(raw_root: Path, provider: str, symbol: str, timeframe: str, year: int) -> Path:
    return raw_root / provider / _normalize_symbol(symbol) / timeframe / f"{year}.parquet"


def _rows_to_frame(rows: list[OHLCVRow], *, interval_ms: int) -> pd.DataFrame:
    if not rows:
        return _empty_kline_frame()
    records: list[dict[str, object]] = []
    for row in rows:
        close_time_ms = row.close_time_ms if row.close_time_ms is not None else row.timestamp_ms + interval_ms - 1
        records.append(
            {
                "timestamp": pd.to_datetime(row.timestamp_ms, unit="ms", utc=True),
                "open": float(row.open),
                "high": float(row.high),
                "low": float(row.low),
                "close": float(row.close),
                "volume": float(row.volume),
                "close_time": pd.to_datetime(close_time_ms, unit="ms", utc=True),
                "quote_volume": row.quote_volume,
                "num_trades": row.num_trades,
                "taker_buy_volume": row.taker_buy_volume,
                "taker_buy_quote_volume": row.taker_buy_quote_volume,
            }
        )
    frame = pd.DataFrame.from_records(records)
    for col in KLINE_COLUMNS:
        if col not in frame.columns:
            frame[col] = pd.NA
    frame = frame[KLINE_COLUMNS].copy()
    frame = (
        frame.drop_duplicates(subset=["timestamp"], keep="last")
        .sort_values("timestamp")
        .reset_index(drop=True)
    )
    return frame


def _parse_csv_list(raw: str) -> list[str]:
    return [item.strip() for item in raw.split(",") if item.strip()]


def _unique_provider_chain(primary: str, fallbacks: str) -> list[str]:
    chain = [primary.strip().lower()]
    for item in _parse_csv_list(fallbacks):
        name = item.strip().lower()
        if name and name not in chain:
            chain.append(name)
    return chain


@dataclass(frozen=True)
class BackfillStats:
    symbol: str
    timeframe: str
    years_written: int
    candles_total: int
    failures: int
    fallback_hits: int


def _download_window_with_fallback(
    *,
    providers: dict[str, OHLCVProvider],
    provider_chain: list[str],
    symbol: str,
    timeframe: str,
    start_ms: int,
    end_ms: int,
    interval_ms: int,
    chunk_limit: int,
) -> tuple[pd.DataFrame, dict[str, pd.DataFrame], int]:
    if start_ms >= end_ms:
        return _empty_kline_frame(), {}, 0

    cursor_ms = start_ms
    all_chunks: list[pd.DataFrame] = []
    provider_chunks: dict[str, list[pd.DataFrame]] = {name: [] for name in provider_chain}
    fallback_hits = 0
    end_filter = pd.to_datetime(end_ms, unit="ms", utc=True)

    while cursor_ms < end_ms:
        chunk_df: pd.DataFrame | None = None
        used_provider: str | None = None

        for provider_index, provider_name in enumerate(provider_chain):
            provider = providers[provider_name]
            try:
                rows = provider.fetch_ohlcv(
                    symbol=symbol,
                    timeframe=timeframe,
                    start_ts=cursor_ms,
                    end_ts=end_ms,
                    limit=min(chunk_limit, provider.max_limit),
                )
            except Exception as exc:  # pragma: no cover - network/runtime failure path
                LOG.warning(
                    "[provider_fail] provider=%s symbol=%s tf=%s cursor=%s err=%s",
                    provider_name,
                    symbol,
                    timeframe,
                    pd.to_datetime(cursor_ms, unit="ms", utc=True).isoformat(),
                    exc,
                )
                continue

            candidate = _rows_to_frame(rows, interval_ms=interval_ms)
            if candidate.empty:
                continue

            start_filter = pd.to_datetime(cursor_ms, unit="ms", utc=True)
            candidate = candidate[
                (candidate["timestamp"] >= start_filter) & (candidate["timestamp"] < end_filter)
            ].copy()
            if candidate.empty:
                continue

            chunk_df = candidate
            used_provider = provider_name
            if provider_index > 0:
                fallback_hits += 1
            break

        if chunk_df is None or used_provider is None:
            LOG.warning(
                "[chunk_missing] symbol=%s tf=%s cursor=%s no provider produced data",
                symbol,
                timeframe,
                pd.to_datetime(cursor_ms, unit="ms", utc=True).isoformat(),
            )
            break

        all_chunks.append(chunk_df)
        provider_chunks[used_provider].append(chunk_df)
        last_ms = int(chunk_df["timestamp"].iloc[-1].timestamp() * 1000)
        next_ms = last_ms + interval_ms
        if next_ms <= cursor_ms:
            LOG.warning(
                "[chunk_stall] symbol=%s tf=%s cursor=%d next=%d",
                symbol,
                timeframe,
                cursor_ms,
                next_ms,
            )
            break
        cursor_ms = next_ms

    if not all_chunks:
        return _empty_kline_frame(), {}, fallback_hits

    merged = pd.concat(all_chunks, ignore_index=True)
    merged = (
        merged.drop_duplicates(subset=["timestamp"], keep="last")
        .sort_values("timestamp")
        .reset_index(drop=True)
    )
    provider_frames: dict[str, pd.DataFrame] = {}
    for provider_name, chunks in provider_chunks.items():
        if not chunks:
            continue
        frame = pd.concat(chunks, ignore_index=True)
        frame = (
            frame.drop_duplicates(subset=["timestamp"], keep="last")
            .sort_values("timestamp")
            .reset_index(drop=True)
        )
        provider_frames[provider_name] = frame[KLINE_COLUMNS].copy()

    return merged[KLINE_COLUMNS].copy(), provider_frames, fallback_hits


def _backfill_symbol_timeframe(
    *,
    output_root: Path,
    raw_root: Path,
    providers: dict[str, OHLCVProvider],
    provider_chain: list[str],
    symbol: str,
    timeframe: str,
    start_dt: datetime,
    end_dt: datetime,
    chunk_limit: int,
) -> BackfillStats:
    interval_ms = INTERVAL_MS[timeframe]
    years_written = 0
    candles_total = 0
    failures = 0
    fallback_hits = 0

    for year in range(start_dt.year, end_dt.year + 1):
        year_start = max(start_dt, datetime(year, 1, 1, tzinfo=timezone.utc))
        year_end = min(end_dt, datetime(year + 1, 1, 1, tzinfo=timezone.utc))
        if year_start >= year_end:
            continue

        compat_path = _compat_year_path(output_root, symbol, timeframe, year)
        existing_compat = _read_year_parquet(compat_path)

        start_ms = _align_ms_floor(_to_ms(year_start), interval_ms)
        end_ms = _align_ms_floor(_to_ms(year_end), interval_ms)
        resume_ms = start_ms
        if not existing_compat.empty:
            max_existing_ms = int(_ts_col_to_ms(existing_compat["timestamp"]).max())
            resume_ms = max(start_ms, max_existing_ms + interval_ms)

        if resume_ms >= end_ms:
            LOG.info(
                "[resume] %s %s %d already covered (resume=%s)",
                symbol,
                timeframe,
                year,
                pd.to_datetime(resume_ms, unit="ms", utc=True).isoformat(),
            )
            candles_total += int(len(existing_compat))
            continue

        LOG.info(
            "[backfill] %s %s %d: %s -> %s providers=%s",
            symbol,
            timeframe,
            year,
            pd.to_datetime(resume_ms, unit="ms", utc=True).isoformat(),
            pd.to_datetime(end_ms, unit="ms", utc=True).isoformat(),
            ",".join(provider_chain),
        )
        incoming, raw_provider_frames, fallback_count = _download_window_with_fallback(
            providers=providers,
            provider_chain=provider_chain,
            symbol=symbol,
            timeframe=timeframe,
            start_ms=resume_ms,
            end_ms=end_ms,
            interval_ms=interval_ms,
            chunk_limit=chunk_limit,
        )
        fallback_hits += fallback_count

        if incoming.empty:
            failures += 1
            LOG.error("[year_fail] %s %s %d no incoming rows", symbol, timeframe, year)
            continue

        for provider_name, provider_frame in raw_provider_frames.items():
            provider_path = _raw_year_path(raw_root, provider_name, symbol, timeframe, year)
            existing_raw = _read_year_parquet(provider_path)
            merged_raw = _merge_dedup_aligned(existing_raw, provider_frame, interval_ms=interval_ms)
            provider_path.parent.mkdir(parents=True, exist_ok=True)
            merged_raw.to_parquet(provider_path, index=False)
            LOG.info(
                "[saved_raw] provider=%s path=%s rows=%d incoming=%d",
                provider_name,
                provider_path,
                len(merged_raw),
                len(provider_frame),
            )

        merged_compat = _merge_dedup_aligned(existing_compat, incoming, interval_ms=interval_ms)
        compat_path.parent.mkdir(parents=True, exist_ok=True)
        merged_compat.to_parquet(compat_path, index=False)
        years_written += 1
        candles_total += int(len(merged_compat))
        LOG.info(
            "[saved_compat] path=%s rows=%d incoming=%d",
            compat_path,
            len(merged_compat),
            len(incoming),
        )

    return BackfillStats(
        symbol=_normalize_symbol(symbol),
        timeframe=timeframe,
        years_written=years_written,
        candles_total=candles_total,
        failures=failures,
        fallback_hits=fallback_hits,
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Multi-provider historical backfill to yearly parquet (resume-safe).",
    )
    parser.add_argument(
        "--symbols",
        default=",".join(DEFAULT_SYMBOLS),
        help="Comma-separated symbols (default: BTCUSDT,ETHUSDT,SOLUSDT,XRPUSDT,DOGEUSDT)",
    )
    parser.add_argument(
        "--timeframe",
        default="1h",
        help="Comma-separated timeframes (recommended: 1h or 15m).",
    )
    parser.add_argument("--start", default="2018-01-01", help="UTC start date (YYYY-MM-DD)")
    parser.add_argument("--end", default="2026-01-01", help="UTC end date (YYYY-MM-DD, exclusive)")
    parser.add_argument(
        "--provider",
        default="binance",
        help="Primary provider (binance|okx|kraken|bybit).",
    )
    parser.add_argument(
        "--fallback-providers",
        default="",
        help="Comma-separated fallback providers.",
    )
    parser.add_argument(
        "--output-root",
        default="data/binance",
        help="Compatibility output root (default: data/binance).",
    )
    parser.add_argument(
        "--raw-root",
        default="data/market",
        help="Raw provider output root (default: data/market).",
    )
    parser.add_argument(
        "--unified-out",
        default="data/market/unified",
        help="Unified output root for merge stage.",
    )
    parser.add_argument("--spot", action="store_true", help="Use Binance spot endpoint when provider=binance")
    parser.add_argument("--timeout", type=float, default=20.0, help="HTTP timeout seconds")
    parser.add_argument("--max-retries", type=int, default=5, help="Max request retries")
    parser.add_argument("--backoff-base", type=float, default=1.0, help="Retry backoff base seconds")
    parser.add_argument("--max-backoff", type=float, default=30.0, help="Retry backoff cap seconds")
    parser.add_argument("--rate-limit-sleep", type=float, default=0.2, help="Sleep after successful requests")
    parser.add_argument("--breaker-failures", type=int, default=5, help="Circuit breaker failure threshold")
    parser.add_argument(
        "--breaker-cooldown-seconds",
        type=float,
        default=60.0,
        help="Circuit breaker cooldown period.",
    )
    parser.add_argument("--chunk-limit", type=int, default=1000, help="Requested candles per API call")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose logging")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    symbols = [_normalize_symbol(s) for s in _parse_csv_list(args.symbols)]
    timeframes = _parse_csv_list(args.timeframe)
    for tf in timeframes:
        if tf not in INTERVAL_MS:
            parser.error(f"Unsupported timeframe: {tf}. Supported: {sorted(INTERVAL_MS)}")

    start_dt = _parse_date_utc(args.start)
    end_dt = _parse_date_utc(args.end)
    if start_dt >= end_dt:
        parser.error("--start must be earlier than --end")

    provider_chain = _unique_provider_chain(args.provider, args.fallback_providers)
    supported = set(available_providers())
    for provider_name in provider_chain:
        if provider_name not in supported:
            parser.error(
                f"Unsupported provider '{provider_name}'. Available: {', '.join(sorted(supported))}"
            )

    providers: dict[str, OHLCVProvider] = {}
    for provider_name in provider_chain:
        kwargs = {
            "timeout": args.timeout,
            "max_retries": args.max_retries,
            "backoff_base": args.backoff_base,
            "max_backoff": args.max_backoff,
            "rate_limit_sleep": args.rate_limit_sleep,
            "breaker_failures": args.breaker_failures,
            "breaker_cooldown_seconds": args.breaker_cooldown_seconds,
        }
        if provider_name == "binance":
            kwargs["use_spot"] = bool(args.spot)
        providers[provider_name] = create_provider(provider_name, **kwargs)

    output_root = Path(args.output_root)
    raw_root = Path(args.raw_root)
    LOG.info(
        "Starting backfill symbols=%s timeframes=%s range=%s..%s provider_chain=%s "
        "compat_root=%s raw_root=%s unified_out=%s",
        ",".join(symbols),
        ",".join(timeframes),
        start_dt.date(),
        end_dt.date(),
        ",".join(provider_chain),
        output_root,
        raw_root,
        args.unified_out,
    )

    overall_failures = 0
    overall_fallback_hits = 0
    for timeframe in timeframes:
        for symbol in symbols:
            stats = _backfill_symbol_timeframe(
                output_root=output_root,
                raw_root=raw_root,
                providers=providers,
                provider_chain=provider_chain,
                symbol=symbol,
                timeframe=timeframe,
                start_dt=start_dt,
                end_dt=end_dt,
                chunk_limit=max(1, args.chunk_limit),
            )
            overall_failures += stats.failures
            overall_fallback_hits += stats.fallback_hits
            LOG.info(
                "[summary] %s %s years_written=%d candles_total=%d failures=%d fallback_hits=%d",
                stats.symbol,
                stats.timeframe,
                stats.years_written,
                stats.candles_total,
                stats.failures,
                stats.fallback_hits,
            )

    if overall_failures > 0:
        LOG.warning(
            "Backfill finished with failures=%d (fallback_hits=%d).",
            overall_failures,
            overall_fallback_hits,
        )
        return 2

    LOG.info("Backfill completed successfully (fallback_hits=%d).", overall_fallback_hits)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
