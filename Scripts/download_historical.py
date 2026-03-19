"""Download historical OHLCV data from Binance into month-partitioned Parquet.

This is the production downloader that saves to data/binance/{SYM}/{interval}/{YYYY-MM}.parquet.
Can be run from any directory — auto-detects project root.

Usage:
    python Scripts/download_historical.py --symbol BTCUSDT --interval 1m --start 2024-01-01 --end 2024-03-01
    python Scripts/download_historical.py --symbol ETHUSDT --interval 1h --days 30
    python Scripts/download_historical.py --symbol SOLUSDT --interval 5m --days 90 --spot
    python Scripts/download_historical.py --all --interval 1m --days 90
    python Scripts/download_historical.py --info
    python Scripts/download_historical.py --info BTCUSDT
    python Scripts/download_historical.py --verify BTCUSDT
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# --- Auto-detect project root and fix sys.path ---
_SCRIPT_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _SCRIPT_DIR.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
LOG = logging.getLogger("download_historical")

DEFAULT_SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "DOGEUSDT", "AVAXUSDT", "LINKUSDT"]


def cmd_download(args: argparse.Namespace) -> None:
    """Download OHLCV for one or more symbols."""
    from src.data.binance_downloader import BinanceDownloader
    from src.data.local_store import LocalStore

    symbols = (
        DEFAULT_SYMBOLS if args.all
        else [s.strip().upper() for s in args.symbol.split(",") if s.strip()]
    )

    store = LocalStore(root=args.output)
    downloader = BinanceDownloader(use_futures=not args.spot)

    start_date = args.start
    if args.days is not None and start_date is None:
        start_date = (datetime.now(timezone.utc) - timedelta(days=args.days)).strftime("%Y-%m-%d")

    LOG.info("=" * 60)
    LOG.info("ARGUS Historical Data Downloader (Partitioned Parquet)")
    LOG.info("  Symbols:   %s", ", ".join(symbols))
    LOG.info("  Interval:  %s", args.interval)
    LOG.info("  Start:     %s", start_date or "(90 days ago)")
    LOG.info("  End:       %s", args.end or "(now)")
    LOG.info("  Endpoint:  %s", "Spot" if args.spot else "Futures")
    LOG.info("  Output:    %s", args.output)
    LOG.info("=" * 60)

    success = 0
    for sym in symbols:
        LOG.info("")
        LOG.info("--- %s ---", sym)
        try:
            df = downloader.download(
                symbol=sym,
                interval=args.interval,
                start_date=start_date,
                end_date=args.end,
            )
            if df.empty:
                LOG.warning("  No data for %s", sym)
                continue

            paths = store.save(df=df, symbol=sym, interval=args.interval)
            LOG.info(
                "  [OK] %d bars -> %d parquet file(s): %s .. %s",
                len(df), len(paths),
                df["timestamp"].iloc[0].strftime("%Y-%m-%d %H:%M"),
                df["timestamp"].iloc[-1].strftime("%Y-%m-%d %H:%M"),
            )
            success += 1

        except Exception as exc:
            LOG.error("  [FAIL] %s: %s", sym, exc)

        # Small delay between symbols
        import time
        time.sleep(1.0)

    LOG.info("")
    LOG.info("Done: %d/%d symbols downloaded to %s", success, len(symbols), args.output)


def cmd_info(args: argparse.Namespace) -> None:
    """Show stored data info."""
    from src.data.local_store import LocalStore

    store = LocalStore(root=args.output)

    if args.info_symbol:
        sym = args.info_symbol.upper().replace("/", "").replace("_", "").replace("-", "")
        intervals = store.list_intervals(sym)
        if not intervals:
            print(f"No data found for {sym} in {store.root}")
            return
        for iv in intervals:
            months = store.list_months(sym, iv)
            result = store.verify_integrity(sym, iv)
            print(f"  {sym}/{iv}: {result['total_bars']} bars, "
                  f"{len(months)} months, gaps={result['gap_count']}")
            if result["date_range"]:
                print(f"    Range: {result['date_range'][0]} -> {result['date_range'][1]}")
            print(f"    Files: {', '.join(m + '.parquet' for m in months)}")
    else:
        symbols = store.list_symbols()
        if not symbols:
            print(f"No data in {store.root}")
            return
        print(f"Stored data ({store.root}):")
        print(f"  {len(symbols)} symbol(s): {', '.join(symbols)}")
        print()
        for sym in symbols:
            intervals = store.list_intervals(sym)
            for iv in intervals:
                result = store.verify_integrity(sym, iv)
                bars = result["total_bars"]
                gaps = result["gap_count"]
                dr = result["date_range"]
                status = "OK" if gaps == 0 else f"GAPS={gaps}"
                range_str = f"  {dr[0][:10]} -> {dr[1][:10]}" if dr else ""
                print(f"  {sym}/{iv}: {bars:>8} bars  [{status}]{range_str}")


def cmd_verify(args: argparse.Namespace) -> None:
    """Verify data integrity."""
    from src.data.local_store import LocalStore

    store = LocalStore(root=args.output)
    sym = args.verify_symbol.upper().replace("/", "").replace("_", "").replace("-", "")
    result = store.verify_integrity(sym, args.interval)

    print(f"Integrity: {sym}/{args.interval}")
    print(f"  Bars:       {result['total_bars']}")
    print(f"  Sorted:     {result['is_sorted']}")
    print(f"  Duplicates: {result['has_duplicates']}")
    print(f"  Gaps:       {result['gap_count']}")
    if result["date_range"]:
        print(f"  Range:      {result['date_range'][0]} -> {result['date_range'][1]}")

    if result["gap_count"] > 0 or result["has_duplicates"] or not result["is_sorted"]:
        print("\n  [FAIL] Data has integrity issues!")
        sys.exit(1)
    else:
        print("\n  [OK] Data is clean.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="ARGUS Historical Data Downloader & Manager",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Download 3 months of BTCUSDT 1m data (futures):
    python Scripts/download_historical.py --symbol BTCUSDT --interval 1m --start 2024-01-01 --end 2024-03-01

  Download last 90 days for all default symbols:
    python Scripts/download_historical.py --all --interval 1m --days 90

  Download last 30 days hourly from spot:
    python Scripts/download_historical.py --symbol ETHUSDT --interval 1h --days 30 --spot

  Show all stored data:
    python Scripts/download_historical.py --info

  Show data for specific symbol:
    python Scripts/download_historical.py --info BTCUSDT

  Verify data integrity:
    python Scripts/download_historical.py --verify BTCUSDT --interval 1m
        """,
    )

    # Mode flags (mutually exclusive)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--info", nargs="?", const="", default=None, dest="info_symbol",
                       metavar="SYMBOL", help="Show stored data info (optionally for a symbol)")
    mode.add_argument("--verify", dest="verify_symbol", metavar="SYMBOL",
                       help="Verify integrity for a symbol")

    # Download options
    parser.add_argument("--symbol", default=None, help="Symbol(s) to download (comma-separated)")
    parser.add_argument("--all", action="store_true", help="Download all default symbols")
    parser.add_argument("--interval", default="1m", help="Candle interval (default: 1m)")
    parser.add_argument("--start", default=None, help="Start date YYYY-MM-DD")
    parser.add_argument("--end", default=None, help="End date YYYY-MM-DD")
    parser.add_argument("--days", type=int, default=None, help="Last N days (alternative to --start)")
    parser.add_argument("--spot", action="store_true", help="Use spot endpoint (default: futures)")
    parser.add_argument("--output", default=str(_PROJECT_ROOT / "data" / "binance"),
                        help="Output directory (default: data/binance)")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose logging")

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Route to subcommand
    if args.info_symbol is not None:
        cmd_info(args)
    elif args.verify_symbol:
        cmd_verify(args)
    elif args.symbol or args.all:
        cmd_download(args)
    else:
        parser.print_help()
        print("\n[ERROR] Specify --symbol BTCUSDT, --all, --info, or --verify BTCUSDT")
        sys.exit(1)


if __name__ == "__main__":
    main()
