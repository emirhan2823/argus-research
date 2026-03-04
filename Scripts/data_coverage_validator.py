#!/usr/bin/env python3
"""Validate historical kline coverage/integrity from yearly parquet files.

Expected layout:
    data/binance/{symbol}/{timeframe}/YYYY.parquet
"""

from __future__ import annotations

import argparse
import logging
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import pandas as pd

LOG = logging.getLogger("data_coverage_validator")

DEFAULT_SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT"]
SUPPORTED_TIMEFRAMES = {"15m": "15min", "1h": "1h"}
INTERVAL_DELTA = {
    "15m": pd.Timedelta(minutes=15),
    "1h": pd.Timedelta(hours=1),
}
REQUIRED_OHLC_COLUMNS = ("open", "high", "low", "close")


def _normalize_symbol(symbol: str) -> str:
    return symbol.upper().replace("/", "").replace("_", "").replace("-", "")


def _parse_date_utc(value: str) -> datetime:
    dt = datetime.strptime(value, "%Y-%m-%d")
    return dt.replace(tzinfo=timezone.utc)


def _parse_csv(raw: str) -> list[str]:
    return [item.strip() for item in raw.split(",") if item.strip()]


def _empty_frame() -> pd.DataFrame:
    return pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume"])


def _expected_index(start: datetime, end: datetime, timeframe: str) -> pd.DatetimeIndex:
    if start >= end:
        return pd.DatetimeIndex([])
    return pd.date_range(start=start, end=end, freq=SUPPORTED_TIMEFRAMES[timeframe], inclusive="left")


def _next_month_start(dt: datetime) -> datetime:
    if dt.month == 12:
        return datetime(dt.year + 1, 1, 1, tzinfo=timezone.utc)
    return datetime(dt.year, dt.month + 1, 1, tzinfo=timezone.utc)


def _iter_month_ranges(start: datetime, end: datetime) -> Iterable[tuple[str, datetime, datetime]]:
    cursor = datetime(start.year, start.month, 1, tzinfo=timezone.utc)
    while cursor < end:
        next_cursor = _next_month_start(cursor)
        month_start = max(start, cursor)
        month_end = min(end, next_cursor)
        if month_start < month_end:
            yield cursor.strftime("%Y-%m"), month_start, month_end
        cursor = next_cursor


def _count_gaps_gt_2_intervals(
    timestamps: pd.Series,
    *,
    timeframe: str,
) -> int:
    if len(timestamps) < 2:
        return 0
    diffs = timestamps.diff().dropna()
    threshold = INTERVAL_DELTA[timeframe] * 2
    return int((diffs > threshold).sum())


def _count_ohlc_violations(frame: pd.DataFrame) -> int:
    if frame.empty:
        return 0
    if any(col not in frame.columns for col in REQUIRED_OHLC_COLUMNS):
        return 0
    high = pd.to_numeric(frame["high"], errors="coerce")
    low = pd.to_numeric(frame["low"], errors="coerce")
    open_ = pd.to_numeric(frame["open"], errors="coerce")
    close = pd.to_numeric(frame["close"], errors="coerce")
    valid_high = high >= pd.concat([open_, close, low], axis=1).max(axis=1)
    valid_low = low <= pd.concat([open_, close, high], axis=1).min(axis=1)
    violations = ~(valid_high & valid_low)
    return int(violations.sum())


def _count_zero_volume_anomalies(frame: pd.DataFrame) -> int:
    if frame.empty or "volume" not in frame.columns:
        return 0
    volume = pd.to_numeric(frame["volume"], errors="coerce").fillna(0.0)
    return int((volume <= 0.0).sum())


@dataclass(frozen=True)
class MonthlyCoverageRow:
    symbol: str
    timeframe: str
    month: str
    expected_candles: int
    observed_candles: int
    missing_candles: int
    duplicate_timestamps: int
    gaps_gt_2_intervals: int
    coverage_pct: float
    ohlc_violations: int
    zero_volume_anomalies: int
    status: str


@dataclass(frozen=True)
class SymbolIntegritySummary:
    symbol: str
    timeframe: str
    total_candles: int
    expected_candles: int
    missing_count: int
    duplicate_timestamps: int
    gaps_gt_2_intervals: int
    coverage_pct: float
    strictly_increasing: bool
    ohlc_violations: int
    zero_volume_anomalies: int
    first_timestamp: str | None
    last_timestamp: str | None


def load_symbol_frame(
    *,
    data_root: Path,
    symbol: str,
    timeframe: str,
) -> pd.DataFrame:
    symbol_dir = data_root / _normalize_symbol(symbol) / timeframe
    if not symbol_dir.exists():
        return _empty_frame()

    frames: list[pd.DataFrame] = []
    year_files = sorted(symbol_dir.glob("*.parquet"), key=lambda path: path.stem)
    for year_file in year_files:
        try:
            frame = pd.read_parquet(year_file)
        except Exception as exc:  # pragma: no cover - defensive runtime path
            LOG.warning("Failed reading %s: %s", year_file, exc)
            continue
        if frame.empty or "timestamp" not in frame.columns:
            continue
        frame = frame.copy()
        frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True)
        frames.append(frame)
    if not frames:
        return _empty_frame()
    return pd.concat(frames, ignore_index=True)


def analyze_symbol_coverage(
    *,
    data_root: Path,
    symbol: str,
    timeframe: str,
    start: datetime,
    end: datetime,
) -> tuple[SymbolIntegritySummary, list[MonthlyCoverageRow]]:
    frame = load_symbol_frame(data_root=data_root, symbol=symbol, timeframe=timeframe)
    if frame.empty:
        frame = _empty_frame()
    if "timestamp" not in frame.columns:
        frame["timestamp"] = pd.Series(dtype="datetime64[ns, UTC]")

    in_range_mask = (frame["timestamp"] >= start) & (frame["timestamp"] < end)
    raw_range = frame.loc[in_range_mask].copy()

    raw_timestamps = raw_range["timestamp"] if not raw_range.empty else pd.Series(dtype="datetime64[ns, UTC]")
    duplicate_total = int(raw_timestamps.duplicated().sum()) if not raw_range.empty else 0
    strictly_increasing = bool(raw_timestamps.is_monotonic_increasing and duplicate_total == 0)

    unique_sorted = (
        raw_range.sort_values("timestamp")
        .drop_duplicates(subset=["timestamp"], keep="last")
        .reset_index(drop=True)
    )
    observed_index = pd.DatetimeIndex(unique_sorted["timestamp"]) if not unique_sorted.empty else pd.DatetimeIndex([])
    expected_index = _expected_index(start, end, timeframe)

    missing_total = len(expected_index.difference(observed_index))
    total_candles = int(len(observed_index))
    expected_candles = int(len(expected_index))
    coverage_pct = 0.0 if expected_candles == 0 else round((total_candles / expected_candles) * 100.0, 4)

    gaps_total = _count_gaps_gt_2_intervals(
        unique_sorted["timestamp"] if not unique_sorted.empty else pd.Series(dtype="datetime64[ns, UTC]"),
        timeframe=timeframe,
    )
    ohlc_violations = _count_ohlc_violations(raw_range)
    zero_volume_anomalies = _count_zero_volume_anomalies(raw_range)

    first_ts = None if observed_index.empty else observed_index[0].isoformat()
    last_ts = None if observed_index.empty else observed_index[-1].isoformat()

    summary = SymbolIntegritySummary(
        symbol=_normalize_symbol(symbol),
        timeframe=timeframe,
        total_candles=total_candles,
        expected_candles=expected_candles,
        missing_count=int(missing_total),
        duplicate_timestamps=duplicate_total,
        gaps_gt_2_intervals=gaps_total,
        coverage_pct=coverage_pct,
        strictly_increasing=strictly_increasing,
        ohlc_violations=ohlc_violations,
        zero_volume_anomalies=zero_volume_anomalies,
        first_timestamp=first_ts,
        last_timestamp=last_ts,
    )

    monthly_rows: list[MonthlyCoverageRow] = []
    for month_key, month_start, month_end in _iter_month_ranges(start, end):
        month_mask = (raw_range["timestamp"] >= month_start) & (raw_range["timestamp"] < month_end)
        month_raw = raw_range.loc[month_mask].copy()
        month_dups = int(month_raw["timestamp"].duplicated().sum()) if not month_raw.empty else 0
        month_unique = (
            month_raw.sort_values("timestamp")
            .drop_duplicates(subset=["timestamp"], keep="last")
            .reset_index(drop=True)
        )
        month_observed = pd.DatetimeIndex(month_unique["timestamp"]) if not month_unique.empty else pd.DatetimeIndex([])
        month_expected = _expected_index(month_start, month_end, timeframe)

        month_expected_count = int(len(month_expected))
        month_observed_count = int(len(month_observed))
        month_missing = int(len(month_expected.difference(month_observed)))
        month_coverage = 0.0 if month_expected_count == 0 else round((month_observed_count / month_expected_count) * 100.0, 4)
        month_gaps = _count_gaps_gt_2_intervals(
            month_unique["timestamp"] if not month_unique.empty else pd.Series(dtype="datetime64[ns, UTC]"),
            timeframe=timeframe,
        )
        month_ohlc_viol = _count_ohlc_violations(month_raw)
        month_zero_volume = _count_zero_volume_anomalies(month_raw)

        status_parts: list[str] = []
        if month_missing > 0:
            status_parts.append("MISSING")
        if month_dups > 0:
            status_parts.append("DUPLICATES")
        if month_gaps > 0:
            status_parts.append("GAPS")
        if month_ohlc_viol > 0:
            status_parts.append("OHLC")
        if month_zero_volume > 0:
            status_parts.append("ZERO_VOLUME")
        status = "OK" if not status_parts else "|".join(status_parts)

        monthly_rows.append(
            MonthlyCoverageRow(
                symbol=_normalize_symbol(symbol),
                timeframe=timeframe,
                month=month_key,
                expected_candles=month_expected_count,
                observed_candles=month_observed_count,
                missing_candles=month_missing,
                duplicate_timestamps=month_dups,
                gaps_gt_2_intervals=month_gaps,
                coverage_pct=month_coverage,
                ohlc_violations=month_ohlc_viol,
                zero_volume_anomalies=month_zero_volume,
                status=status,
            )
        )

    return summary, monthly_rows


def _write_matrix_csv(path: Path, monthly_rows: list[MonthlyCoverageRow]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame([asdict(row) for row in monthly_rows])
    if frame.empty:
        frame = pd.DataFrame(
            columns=[
                "symbol",
                "timeframe",
                "month",
                "expected_candles",
                "observed_candles",
                "missing_candles",
                "duplicate_timestamps",
                "gaps_gt_2_intervals",
                "coverage_pct",
                "ohlc_violations",
                "zero_volume_anomalies",
                "status",
            ]
        )
    frame.to_csv(path, index=False)


def _write_report_md(
    path: Path,
    *,
    summaries: list[SymbolIntegritySummary],
    monthly_rows: list[MonthlyCoverageRow],
    timeframe: str,
    start: datetime,
    end: datetime,
    data_root: Path,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    lines.append("# DATA COVERAGE REPORT")
    lines.append("")
    lines.append(f"- Generated (UTC): {datetime.now(timezone.utc).isoformat()}")
    lines.append(f"- Data root: `{data_root}`")
    lines.append(f"- Timeframe: `{timeframe}`")
    lines.append(f"- Range: `{start.date()}` -> `{end.date()}` (start inclusive, end exclusive)")
    lines.append("")
    lines.append("## Symbol Integrity Summary")
    lines.append("")
    lines.append(
        "| symbol | total_candles | expected_candles | missing_count | coverage_pct | duplicates | "
        "gaps_gt_2 | strictly_increasing | ohlc_violations | zero_volume_anomalies | first_timestamp | last_timestamp |"
    )
    lines.append(
        "|---|---:|---:|---:|---:|---:|---:|---|---:|---:|---|---|"
    )
    for summary in sorted(summaries, key=lambda item: item.symbol):
        lines.append(
            f"| {summary.symbol} | {summary.total_candles} | {summary.expected_candles} | "
            f"{summary.missing_count} | {summary.coverage_pct:.4f} | {summary.duplicate_timestamps} | "
            f"{summary.gaps_gt_2_intervals} | {summary.strictly_increasing} | {summary.ohlc_violations} | "
            f"{summary.zero_volume_anomalies} | {summary.first_timestamp or '-'} | {summary.last_timestamp or '-'} |"
        )

    lines.append("")
    lines.append("## Warnings")
    lines.append("")
    warning_found = False
    for summary in sorted(summaries, key=lambda item: item.symbol):
        issues: list[str] = []
        if summary.missing_count > 0:
            issues.append(f"missing={summary.missing_count}")
        if summary.duplicate_timestamps > 0:
            issues.append(f"duplicates={summary.duplicate_timestamps}")
        if summary.gaps_gt_2_intervals > 0:
            issues.append(f"gaps_gt_2={summary.gaps_gt_2_intervals}")
        if summary.ohlc_violations > 0:
            issues.append(f"ohlc_violations={summary.ohlc_violations}")
        if summary.zero_volume_anomalies > 0:
            issues.append(f"zero_volume={summary.zero_volume_anomalies}")
        if not summary.strictly_increasing:
            issues.append("timestamps_not_strictly_increasing")
        if issues:
            warning_found = True
            lines.append(f"- `{summary.symbol}`: " + ", ".join(issues))
    if not warning_found:
        lines.append("- None")

    lines.append("")
    lines.append("## Monthly Coverage (All Symbols)")
    lines.append("")
    lines.append(
        "| symbol | month | expected | observed | missing | coverage_pct | duplicates | gaps_gt_2 | status |"
    )
    lines.append("|---|---|---:|---:|---:|---:|---:|---:|---|")
    for row in sorted(monthly_rows, key=lambda item: (item.symbol, item.month)):
        lines.append(
            f"| {row.symbol} | {row.month} | {row.expected_candles} | {row.observed_candles} | "
            f"{row.missing_candles} | {row.coverage_pct:.4f} | {row.duplicate_timestamps} | "
            f"{row.gaps_gt_2_intervals} | {row.status} |"
        )

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate yearly parquet candle coverage and integrity.")
    parser.add_argument(
        "--symbols",
        default=",".join(DEFAULT_SYMBOLS),
        help="Comma-separated symbols",
    )
    parser.add_argument("--timeframe", default="1h", choices=sorted(SUPPORTED_TIMEFRAMES))
    parser.add_argument("--start", default="2018-01-01", help="UTC start date YYYY-MM-DD")
    parser.add_argument("--end", default="2026-01-01", help="UTC end date YYYY-MM-DD (exclusive)")
    parser.add_argument("--data-root", default="data/binance", help="Backfill root")
    parser.add_argument("--report-dir", default="reports", help="Output directory for reports")
    parser.add_argument("-v", "--verbose", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    symbols = [_normalize_symbol(s) for s in _parse_csv(args.symbols)]
    start = _parse_date_utc(args.start)
    end = _parse_date_utc(args.end)
    if start >= end:
        parser.error("--start must be earlier than --end")

    data_root = Path(args.data_root)
    report_dir = Path(args.report_dir)
    report_md = report_dir / "DATA_COVERAGE_REPORT.md"
    matrix_csv = report_dir / "DATA_COVERAGE_MATRIX.csv"

    summaries: list[SymbolIntegritySummary] = []
    all_monthly_rows: list[MonthlyCoverageRow] = []
    for symbol in symbols:
        summary, monthly_rows = analyze_symbol_coverage(
            data_root=data_root,
            symbol=symbol,
            timeframe=args.timeframe,
            start=start,
            end=end,
        )
        summaries.append(summary)
        all_monthly_rows.extend(monthly_rows)
        LOG.info(
            "[summary] %s candles=%d missing=%d coverage=%.4f%% dups=%d gaps=%d",
            summary.symbol,
            summary.total_candles,
            summary.missing_count,
            summary.coverage_pct,
            summary.duplicate_timestamps,
            summary.gaps_gt_2_intervals,
        )

    _write_matrix_csv(matrix_csv, all_monthly_rows)
    _write_report_md(
        report_md,
        summaries=summaries,
        monthly_rows=all_monthly_rows,
        timeframe=args.timeframe,
        start=start,
        end=end,
        data_root=data_root,
    )

    LOG.info("Wrote report: %s", report_md)
    LOG.info("Wrote matrix: %s", matrix_csv)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
