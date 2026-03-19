#!/usr/bin/env python3
import argparse
import os
import sys
from datetime import date, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from argus_py.data.binance_downloader import BinanceDownloader


def add_months(d: date, months: int) -> date:
    month_idx = (d.month - 1) + months
    year = d.year + (month_idx // 12)
    month = (month_idx % 12) + 1
    return date(year, month, 1)


def month_windows(start_date: date, end_date: date):
    cur = date(start_date.year, start_date.month, 1)
    while cur < end_date:
        nxt = add_months(cur, 1)
        if nxt > end_date:
            nxt = end_date
        yield cur, nxt
        cur = nxt


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Backfill Binance monthly cache files for walk-forward ranges."
    )
    p.add_argument("--symbol", default="BTCUSDT")
    p.add_argument("--start_date", default="2024-07-01")
    p.add_argument("--end_date", default="2025-02-01")
    p.add_argument("--data_dir", default="argus_py/data/cache")
    p.add_argument("--skip_existing", action="store_true", default=True)
    p.add_argument("--dry_run", action="store_true")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    os.makedirs(args.data_dir, exist_ok=True)

    start_dt = datetime.strptime(args.start_date, "%Y-%m-%d").date()
    end_dt = datetime.strptime(args.end_date, "%Y-%m-%d").date()
    if end_dt <= start_dt:
        raise ValueError("end_date must be after start_date")

    total = 0
    downloaded = 0
    skipped = 0
    failed = 0

    for ws, we in month_windows(start_dt, end_dt):
        total += 1
        s = ws.strftime("%Y-%m-%d")
        e = we.strftime("%Y-%m-%d")
        out = os.path.join(args.data_dir, f"{args.symbol}_1m_{s}_{e}.csv")
        if args.skip_existing and os.path.exists(out):
            skipped += 1
            print(f"SKIP {s}->{e} (exists)")
            continue

        if args.dry_run:
            print(f"DRY  {s}->{e}")
            continue

        print(f"GET  {s}->{e}")
        ok = BinanceDownloader.download_binance_klines(
            symbol=args.symbol,
            start_date=s,
            end_date=e,
            output_dir=args.data_dir,
            interval="1m",
        )
        if ok:
            downloaded += 1
        else:
            failed += 1
            print(f"FAIL {s}->{e}")

    print(
        "BACKFILL_SUMMARY "
        f"windows={total} downloaded={downloaded} skipped={skipped} failed={failed}"
    )
    return 1 if failed > 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())
