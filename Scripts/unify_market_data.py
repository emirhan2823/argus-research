#!/usr/bin/env python3
"""Build unified market dataset from multi-provider raw parquet archives."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import logging
from pathlib import Path
import sys

import pandas as pd

# Allow running via: python Scripts/unify_market_data.py
_SCRIPT_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _SCRIPT_DIR.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from Scripts.data_coverage_validator import (
    _count_ohlc_violations,
    _count_zero_volume_anomalies,
    _expected_index,
    _iter_month_ranges,
)

LOG = logging.getLogger("unify_market_data")

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


def _parse_csv(raw: str) -> list[str]:
    return [item.strip() for item in raw.split(",") if item.strip()]


def _parse_date_utc(value: str) -> datetime:
    dt = datetime.strptime(value, "%Y-%m-%d")
    return dt.replace(tzinfo=timezone.utc)


def _empty_frame() -> pd.DataFrame:
    return pd.DataFrame(columns=KLINE_COLUMNS)


def _ensure_columns(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    for col in KLINE_COLUMNS:
        if col not in out.columns:
            out[col] = pd.NA
    out["timestamp"] = pd.to_datetime(out["timestamp"], utc=True)
    if "close_time" in out.columns:
        out["close_time"] = pd.to_datetime(out["close_time"], utc=True, errors="coerce")
    return out[KLINE_COLUMNS].copy()


def _read_provider_frame(
    *,
    raw_root: Path,
    provider: str,
    symbol: str,
    timeframe: str,
) -> pd.DataFrame:
    directory = raw_root / provider / _normalize_symbol(symbol) / timeframe
    if not directory.exists():
        return _empty_frame()
    frames: list[pd.DataFrame] = []
    for file_path in sorted(directory.glob("*.parquet"), key=lambda p: p.stem):
        try:
            frame = pd.read_parquet(file_path)
        except Exception as exc:  # pragma: no cover - defensive runtime path
            LOG.warning("Failed reading %s: %s", file_path, exc)
            continue
        if frame.empty or "timestamp" not in frame.columns:
            continue
        frames.append(_ensure_columns(frame))
    if not frames:
        return _empty_frame()
    merged = pd.concat(frames, ignore_index=True)
    merged = (
        merged.drop_duplicates(subset=["timestamp"], keep="last")
        .sort_values("timestamp")
        .reset_index(drop=True)
    )
    return merged[KLINE_COLUMNS].copy()


@dataclass(frozen=True)
class SegmentProviderScore:
    symbol: str
    month: str
    provider: str
    expected: int
    observed: int
    missing: int
    duplicates: int
    ohlc_violations: int
    zero_volume_anomalies: int
    coverage_pct: float

    @property
    def anomaly_score(self) -> int:
        return self.duplicates + self.ohlc_violations + self.zero_volume_anomalies


@dataclass(frozen=True)
class SegmentChoice:
    symbol: str
    month: str
    chosen_provider: str
    expected: int
    observed: int
    missing: int
    coverage_pct: float
    anomaly_score: int


def _segment_provider_score(
    *,
    symbol: str,
    provider: str,
    month: str,
    month_start: datetime,
    month_end: datetime,
    timeframe: str,
    frame: pd.DataFrame,
) -> tuple[SegmentProviderScore, pd.DataFrame]:
    if frame.empty:
        expected = len(_expected_index(month_start, month_end, timeframe))
        score = SegmentProviderScore(
            symbol=symbol,
            month=month,
            provider=provider,
            expected=expected,
            observed=0,
            missing=expected,
            duplicates=0,
            ohlc_violations=0,
            zero_volume_anomalies=0,
            coverage_pct=0.0,
        )
        return score, _empty_frame()

    month_raw = frame[(frame["timestamp"] >= month_start) & (frame["timestamp"] < month_end)].copy()
    expected_index = _expected_index(month_start, month_end, timeframe)
    expected = int(len(expected_index))

    if month_raw.empty:
        score = SegmentProviderScore(
            symbol=symbol,
            month=month,
            provider=provider,
            expected=expected,
            observed=0,
            missing=expected,
            duplicates=0,
            ohlc_violations=0,
            zero_volume_anomalies=0,
            coverage_pct=0.0,
        )
        return score, _empty_frame()

    duplicates = int(month_raw["timestamp"].duplicated().sum())
    unique_month = (
        month_raw.drop_duplicates(subset=["timestamp"], keep="last")
        .sort_values("timestamp")
        .reset_index(drop=True)
    )
    observed_index = pd.DatetimeIndex(unique_month["timestamp"])
    observed = int(len(observed_index))
    missing = int(len(expected_index.difference(observed_index)))
    coverage_pct = 0.0 if expected == 0 else round((observed / expected) * 100.0, 4)

    score = SegmentProviderScore(
        symbol=symbol,
        month=month,
        provider=provider,
        expected=expected,
        observed=observed,
        missing=missing,
        duplicates=duplicates,
        ohlc_violations=_count_ohlc_violations(month_raw),
        zero_volume_anomalies=_count_zero_volume_anomalies(month_raw),
        coverage_pct=coverage_pct,
    )
    return score, unique_month[KLINE_COLUMNS].copy()


def _choose_segment_provider(
    *,
    scores: list[SegmentProviderScore],
    provider_priority: dict[str, int],
) -> SegmentProviderScore:
    return sorted(
        scores,
        key=lambda item: (
            -item.coverage_pct,
            item.anomaly_score,
            item.missing,
            provider_priority.get(item.provider, 10_000),
        ),
    )[0]


def _merge_and_write_unified_years(
    *,
    unified_root: Path,
    symbol: str,
    timeframe: str,
    unified_frame: pd.DataFrame,
) -> list[Path]:
    if unified_frame.empty:
        return []
    unified_frame = (
        unified_frame.drop_duplicates(subset=["timestamp"], keep="last")
        .sort_values("timestamp")
        .reset_index(drop=True)
    )
    written: list[Path] = []
    years = sorted(set(unified_frame["timestamp"].dt.year.tolist()))
    for year in years:
        year_path = unified_root / _normalize_symbol(symbol) / timeframe / f"{year}.parquet"
        year_slice = unified_frame[unified_frame["timestamp"].dt.year == year].copy()
        if year_slice.empty:
            continue
        if year_path.exists():
            try:
                existing = _ensure_columns(pd.read_parquet(year_path))
            except Exception:
                existing = _empty_frame()
            merged = pd.concat([existing, year_slice], ignore_index=True)
            merged = (
                merged.drop_duplicates(subset=["timestamp"], keep="last")
                .sort_values("timestamp")
                .reset_index(drop=True)
            )
        else:
            merged = year_slice
        year_path.parent.mkdir(parents=True, exist_ok=True)
        merged.to_parquet(year_path, index=False)
        written.append(year_path)
    return written


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Unify provider raw parquet data into a canonical dataset.")
    parser.add_argument("--symbols", default=",".join(DEFAULT_SYMBOLS), help="Comma-separated symbols")
    parser.add_argument("--timeframe", default="1h", choices=["15m", "1h"])
    parser.add_argument("--start", default="2018-01-01", help="UTC start date YYYY-MM-DD")
    parser.add_argument("--end", default="2026-02-21", help="UTC end date YYYY-MM-DD (exclusive)")
    parser.add_argument(
        "--providers",
        default="binance,okx,kraken,bybit",
        help="Provider priority order (left has final tie-break priority).",
    )
    parser.add_argument("--raw-root", default="data/market", help="Raw provider root")
    parser.add_argument("--unified-out", default="data/market/unified", help="Unified output root")
    parser.add_argument("--report-path", default="reports/UNIFIED_DATA_REPORT.md", help="Markdown report output path")
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

    symbols = [_normalize_symbol(item) for item in _parse_csv(args.symbols)]
    providers = [item.lower() for item in _parse_csv(args.providers)]
    provider_priority = {name: idx for idx, name in enumerate(providers)}
    start = _parse_date_utc(args.start)
    end = _parse_date_utc(args.end)
    if start >= end:
        parser.error("--start must be earlier than --end")

    raw_root = Path(args.raw_root)
    unified_root = Path(args.unified_out)
    report_path = Path(args.report_path)

    all_segment_scores: list[SegmentProviderScore] = []
    all_choices: list[SegmentChoice] = []
    output_paths: list[Path] = []

    for symbol in symbols:
        provider_frames = {
            provider: _read_provider_frame(
                raw_root=raw_root,
                provider=provider,
                symbol=symbol,
                timeframe=args.timeframe,
            )
            for provider in providers
        }
        chosen_month_frames: list[pd.DataFrame] = []

        for month_key, month_start, month_end in _iter_month_ranges(start, end):
            monthly_scores: list[SegmentProviderScore] = []
            monthly_frames: dict[str, pd.DataFrame] = {}
            for provider in providers:
                score, unique_frame = _segment_provider_score(
                    symbol=symbol,
                    provider=provider,
                    month=month_key,
                    month_start=month_start,
                    month_end=month_end,
                    timeframe=args.timeframe,
                    frame=provider_frames[provider],
                )
                monthly_scores.append(score)
                monthly_frames[provider] = unique_frame
                all_segment_scores.append(score)

            chosen = _choose_segment_provider(scores=monthly_scores, provider_priority=provider_priority)
            all_choices.append(
                SegmentChoice(
                    symbol=symbol,
                    month=month_key,
                    chosen_provider=chosen.provider,
                    expected=chosen.expected,
                    observed=chosen.observed,
                    missing=chosen.missing,
                    coverage_pct=chosen.coverage_pct,
                    anomaly_score=chosen.anomaly_score,
                )
            )
            chosen_frame = monthly_frames.get(chosen.provider, _empty_frame())
            if not chosen_frame.empty:
                chosen_month_frames.append(chosen_frame)

        unified_frame = (
            pd.concat(chosen_month_frames, ignore_index=True)
            if chosen_month_frames
            else _empty_frame()
        )
        unified_frame = (
            unified_frame.drop_duplicates(subset=["timestamp"], keep="last")
            .sort_values("timestamp")
            .reset_index(drop=True)
        )
        written = _merge_and_write_unified_years(
            unified_root=unified_root,
            symbol=symbol,
            timeframe=args.timeframe,
            unified_frame=unified_frame,
        )
        output_paths.extend(written)
        LOG.info(
            "[unified] symbol=%s rows=%d files=%d",
            symbol,
            len(unified_frame),
            len(written),
        )

    lines: list[str] = []
    lines.append("# UNIFIED DATA REPORT")
    lines.append("")
    lines.append(f"- Generated (UTC): {datetime.now(timezone.utc).isoformat()}")
    lines.append(f"- Timeframe: `{args.timeframe}`")
    lines.append(f"- Range: `{start.date()}` -> `{end.date()}` (start inclusive, end exclusive)")
    lines.append(f"- Providers (priority): `{', '.join(providers)}`")
    lines.append(f"- Raw root: `{raw_root}`")
    lines.append(f"- Unified out: `{unified_root}`")
    lines.append("")
    lines.append("## Coverage Per Provider (By Symbol)")
    lines.append("")
    lines.append("| symbol | provider | observed | expected | coverage_pct | anomalies |")
    lines.append("|---|---|---:|---:|---:|---:|")
    for symbol in sorted(symbols):
        symbol_scores = [item for item in all_segment_scores if item.symbol == symbol]
        for provider in providers:
            provider_scores = [item for item in symbol_scores if item.provider == provider]
            observed = sum(item.observed for item in provider_scores)
            expected = sum(item.expected for item in provider_scores)
            anomalies = sum(item.anomaly_score for item in provider_scores)
            coverage = 0.0 if expected == 0 else round((observed / expected) * 100.0, 4)
            lines.append(
                f"| {symbol} | {provider} | {observed} | {expected} | {coverage:.4f} | {anomalies} |"
            )

    lines.append("")
    lines.append("## Chosen Provider Per Segment")
    lines.append("")
    lines.append("| symbol | month | chosen_provider | observed | expected | missing | coverage_pct | anomaly_score |")
    lines.append("|---|---|---|---:|---:|---:|---:|---:|")
    for choice in sorted(all_choices, key=lambda item: (item.symbol, item.month)):
        lines.append(
            f"| {choice.symbol} | {choice.month} | {choice.chosen_provider} | {choice.observed} | "
            f"{choice.expected} | {choice.missing} | {choice.coverage_pct:.4f} | {choice.anomaly_score} |"
        )

    lines.append("")
    lines.append("## Gaps")
    lines.append("")
    gap_rows = [row for row in all_choices if row.missing > 0]
    if not gap_rows:
        lines.append("- None")
    else:
        for row in sorted(gap_rows, key=lambda item: (item.symbol, item.month)):
            lines.append(
                f"- `{row.symbol}` `{row.month}` missing={row.missing} "
                f"(chosen={row.chosen_provider} coverage={row.coverage_pct:.4f}%)"
            )

    lines.append("")
    lines.append("## Output Files")
    lines.append("")
    if not output_paths:
        lines.append("- None")
    else:
        for path in sorted(set(output_paths)):
            lines.append(f"- `{path}`")

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    LOG.info("Wrote report: %s", report_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
