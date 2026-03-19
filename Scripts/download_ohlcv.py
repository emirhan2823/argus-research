"""ARGUS -- Bulk Historical OHLCV Downloader via CCXT.

Downloads complete OHLCV data from Binance using ccxt's built-in
rate-limit handling. Saves directly via LocalStore for guaranteed
parquet format compatibility with ReplayLoader.

Usage:
    python scripts/download_ohlcv.py --symbol BTCUSDT --interval 15m --start 2025-11-01 --end 2026-02-27

    # Download multiple intervals:
    python scripts/download_ohlcv.py --symbol BTCUSDT --interval 1m --start 2025-11-01 --end 2026-02-27
    python scripts/download_ohlcv.py --symbol BTCUSDT --interval 15m --start 2025-11-01 --end 2026-02-27
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import ccxt
import pandas as pd

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.data.local_store import LocalStore


# Binance returns max 1000 candles per request for most intervals
MAX_CANDLES_PER_REQUEST = 1000

INTERVAL_MS: dict[str, int] = {
    "1m": 60_000,
    "3m": 3 * 60_000,
    "5m": 5 * 60_000,
    "15m": 15 * 60_000,
    "30m": 30 * 60_000,
    "1h": 3_600_000,
    "2h": 2 * 3_600_000,
    "4h": 4 * 3_600_000,
    "6h": 6 * 3_600_000,
    "8h": 8 * 3_600_000,
    "12h": 12 * 3_600_000,
    "1d": 86_400_000,
}


def download_ohlcv(
    *,
    symbol: str,
    interval: str,
    start: str,
    end: str,
    store_root: str = "data/binance",
) -> None:
    """Download OHLCV data from Binance and save to LocalStore."""
    
    # Parse date range
    start_dt = datetime.strptime(start, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    end_dt = datetime.strptime(end, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    start_ms = int(start_dt.timestamp() * 1000)
    end_ms = int(end_dt.timestamp() * 1000)
    
    interval_ms = INTERVAL_MS.get(interval)
    if interval_ms is None:
        print(f"[ERROR] Unknown interval: {interval}")
        print(f"  Supported: {', '.join(INTERVAL_MS.keys())}")
        sys.exit(1)
    
    # Estimate total candles
    total_candles_est = (end_ms - start_ms) // interval_ms
    total_requests_est = (total_candles_est // MAX_CANDLES_PER_REQUEST) + 1
    
    print(f"[download] {symbol} {interval}")
    print(f"  Range: {start} -> {end}")
    print(f"  Estimated: ~{total_candles_est:,} candles in ~{total_requests_est} API calls")
    print()
    
    # Initialize CCXT with rate limiting
    exchange = ccxt.binance({
        "enableRateLimit": True,
        "rateLimit": 100,  # ms between requests (Binance allows ~1200 req/min)
        "options": {"defaultType": "spot"},
    })
    
    # Convert symbol format: BTCUSDT -> BTC/USDT
    ccxt_symbol = symbol
    if "USDT" in symbol and "/" not in symbol:
        base = symbol.replace("USDT", "")
        ccxt_symbol = f"{base}/USDT"
    elif "USD" in symbol and "/" not in symbol:
        base = symbol.replace("USD", "")
        ccxt_symbol = f"{base}/USD"
    
    # Paginated fetch
    all_candles: list[list] = []
    since = start_ms
    request_count = 0
    
    while since < end_ms:
        try:
            candles = exchange.fetch_ohlcv(
                ccxt_symbol,
                timeframe=interval,
                since=since,
                limit=MAX_CANDLES_PER_REQUEST,
            )
        except ccxt.RateLimitExceeded:
            print("  [!] Rate limit hit -- waiting 30s...")
            time.sleep(30)
            continue
        except ccxt.NetworkError as e:
            print(f"  [!] Network error: {e} -- retrying in 5s...")
            time.sleep(5)
            continue
        except Exception as e:
            print(f"  [ERROR] {e}")
            break
        
        request_count += 1
        
        if not candles:
            print(f"  [done] No more data after {datetime.fromtimestamp(since/1000, tz=timezone.utc).strftime('%Y-%m-%d %H:%M')}")
            break
        
        # Filter out candles beyond our end date
        candles = [c for c in candles if c[0] <= end_ms]
        all_candles.extend(candles)
        
        # Advance cursor to after the last candle
        last_ts = candles[-1][0]
        since = last_ts + interval_ms
        
        # Progress
        fetched_dt = datetime.fromtimestamp(last_ts / 1000, tz=timezone.utc)
        pct = min(100, (last_ts - start_ms) / max(1, end_ms - start_ms) * 100)
        print(
            f"  [{request_count:3d}] {fetched_dt.strftime('%Y-%m-%d %H:%M')} "
            f"| {len(all_candles):>7,} bars | {pct:.0f}%"
        )
        
        if last_ts >= end_ms:
            break
    
    if not all_candles:
        print("[ERROR] No data downloaded!")
        sys.exit(1)
    
    # Convert to DataFrame
    df = pd.DataFrame(all_candles, columns=[
        "timestamp", "open", "high", "low", "close", "volume",
    ])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    
    # Deduplicate
    before = len(df)
    df = df.drop_duplicates(subset=["timestamp"]).sort_values("timestamp").reset_index(drop=True)
    dupes = before - len(df)
    
    print(f"\n[result] {len(df):,} unique bars downloaded ({dupes} duplicates removed)")
    print(f"  First: {df['timestamp'].iloc[0]}")
    print(f"  Last:  {df['timestamp'].iloc[-1]}")
    
    # Save via LocalStore (handles month partitioning + merge)
    store = LocalStore(root=store_root)
    paths = store.save(df=df, symbol=symbol, interval=interval)
    
    print(f"\n[saved] {len(paths)} parquet file(s):")
    for p in paths:
        month_df = pd.read_parquet(p)
        print(f"  {p} -> {len(month_df):,} bars")
    
    # Verify integrity
    integrity = store.verify_integrity(symbol, interval)
    print(f"\n[integrity] {integrity}")
    print("\n[OK] Download complete!")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Download OHLCV data from Binance via CCXT",
    )
    parser.add_argument("--symbol", default="BTCUSDT", help="Trading pair (e.g. BTCUSDT)")
    parser.add_argument("--interval", default="15m", help="Candle interval (e.g. 1m, 15m, 1h)")
    parser.add_argument("--start", default="2025-11-01", help="Start date YYYY-MM-DD")
    parser.add_argument("--end", default="2026-02-27", help="End date YYYY-MM-DD")
    parser.add_argument("--store-root", default="data/binance", help="LocalStore root directory")
    
    args = parser.parse_args()
    
    download_ohlcv(
        symbol=args.symbol,
        interval=args.interval,
        start=args.start,
        end=args.end,
        store_root=args.store_root,
    )


if __name__ == "__main__":
    main()
