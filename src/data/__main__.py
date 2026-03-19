"""Allow running the data package as: python -m src.data [command]

Must be run from the argus-terminal directory:
    cd argus-terminal
    python -m src.data download --symbol BTCUSDT --interval 1m --start 2024-01-01 --end 2024-03-01
    python -m src.data info BTCUSDT
    python -m src.data verify BTCUSDT --interval 1m
"""

from __future__ import annotations

import argparse
import logging
import sys


def _cmd_download(args: argparse.Namespace) -> None:
    """Download historical OHLCV from Binance."""
    from src.data.binance_downloader import BinanceDownloader
    from src.data.local_store import LocalStore

    downloader = BinanceDownloader(
        use_futures=not args.spot,
        rate_limit_sleep=0.25,
    )
    df = downloader.download(
        symbol=args.symbol,
        interval=args.interval,
        start_date=args.start,
        end_date=args.end,
    )

    if df.empty:
        print(f"[ERROR] No data downloaded for {args.symbol}")
        sys.exit(1)

    store = LocalStore(root=args.output)
    paths = store.save(df=df, symbol=args.symbol, interval=args.interval)

    print(f"[OK] {args.symbol} {args.interval}: {len(df)} bars -> {len(paths)} parquet file(s)")
    print(f"     Range: {df['timestamp'].iloc[0]} -> {df['timestamp'].iloc[-1]}")
    for p in paths:
        print(f"     {p}")


def _cmd_info(args: argparse.Namespace) -> None:
    """Show info about locally stored data."""
    from src.data.local_store import LocalStore

    store = LocalStore(root=args.output)

    if args.symbol:
        intervals = store.list_intervals(args.symbol)
        if not intervals:
            print(f"No data for {args.symbol}")
            return
        for iv in intervals:
            months = store.list_months(args.symbol, iv)
            result = store.verify_integrity(args.symbol, iv)
            print(f"  {args.symbol}/{iv}: {result['total_bars']} bars, "
                  f"{len(months)} months, gaps={result['gap_count']}")
            if result['date_range']:
                print(f"    Range: {result['date_range'][0]} -> {result['date_range'][1]}")
    else:
        symbols = store.list_symbols()
        if not symbols:
            print(f"No data in {store.root}")
            return
        print(f"Stored symbols ({len(symbols)}):")
        for sym in symbols:
            intervals = store.list_intervals(sym)
            for iv in intervals:
                result = store.verify_integrity(sym, iv)
                print(f"  {sym}/{iv}: {result['total_bars']} bars, gaps={result['gap_count']}")


def _cmd_verify(args: argparse.Namespace) -> None:
    """Verify integrity of stored data."""
    from src.data.local_store import LocalStore

    store = LocalStore(root=args.output)
    result = store.verify_integrity(args.symbol, args.interval)

    print(f"Integrity check: {args.symbol}/{args.interval}")
    print(f"  Total bars:    {result['total_bars']}")
    print(f"  Sorted:        {result['is_sorted']}")
    print(f"  Duplicates:    {result['has_duplicates']}")
    print(f"  Gaps:          {result['gap_count']}")
    if result['date_range']:
        print(f"  Date range:    {result['date_range'][0]} -> {result['date_range'][1]}")

    if result['gap_count'] > 0 or result['has_duplicates'] or not result['is_sorted']:
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="python -m src.data",
        description="ARGUS historical data management",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose logging")
    parser.add_argument("--output", default="data/binance", help="Storage root (default: data/binance)")

    sub = parser.add_subparsers(dest="command", help="Command to run")

    # download
    dl = sub.add_parser("download", help="Download OHLCV from Binance")
    dl.add_argument("--symbol", required=True, help="Symbol (e.g. BTCUSDT)")
    dl.add_argument("--interval", default="1m", help="Interval (default: 1m)")
    dl.add_argument("--start", default=None, help="Start date YYYY-MM-DD")
    dl.add_argument("--end", default=None, help="End date YYYY-MM-DD")
    dl.add_argument("--days", type=int, default=None, help="Last N days (alternative to --start)")
    dl.add_argument("--spot", action="store_true", help="Use spot endpoint")

    # info
    inf = sub.add_parser("info", help="Show stored data info")
    inf.add_argument("symbol", nargs="?", default=None, help="Symbol (omit to list all)")

    # verify
    ver = sub.add_parser("verify", help="Verify data integrity")
    ver.add_argument("symbol", help="Symbol to verify")
    ver.add_argument("--interval", default="1m", help="Interval (default: 1m)")

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Handle --days -> --start for download
    if args.command == "download" and args.days is not None and args.start is None:
        from datetime import datetime, timedelta, timezone
        args.start = (datetime.now(timezone.utc) - timedelta(days=args.days)).strftime("%Y-%m-%d")

    if args.command == "download":
        _cmd_download(args)
    elif args.command == "info":
        _cmd_info(args)
    elif args.command == "verify":
        _cmd_verify(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
