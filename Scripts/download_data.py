"""Download historical OHLCV + news data for ARGUS backtesting.

Usage:
    python Scripts/download_data.py                     # Default: BTC,ETH,SOL 90 days
    python Scripts/download_data.py --days 180          # 6 months
    python Scripts/download_data.py --symbols BTC,ETH   # Specific symbols
    python Scripts/download_data.py --news              # Also fetch news headlines
    python Scripts/download_data.py --timeframe 1h      # Hourly bars
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
LOG = logging.getLogger("download_data")

DEFAULT_SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "DOGEUSDT", "AVAXUSDT", "LINKUSDT"]


def main():
    parser = argparse.ArgumentParser(description="Download historical data for ARGUS backtesting")
    parser.add_argument("--symbols", default=",".join(DEFAULT_SYMBOLS),
                        help="Comma-separated symbols (default: BTC,ETH,SOL,DOGE,AVAX,LINK)")
    parser.add_argument("--timeframe", default="1h", help="Candle timeframe (default: 1h)")
    parser.add_argument("--days", type=int, default=90, help="Days of history (default: 90)")
    parser.add_argument("--output", default="data/time_machine", help="Output directory")
    parser.add_argument("--news", action="store_true", help="Also download news headlines")
    parser.add_argument("--futures", action="store_true", default=True, help="Use futures endpoint")
    parser.add_argument("--spot", dest="futures", action="store_false", help="Use spot endpoint")
    args = parser.parse_args()

    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]

    LOG.info("=" * 60)
    LOG.info("ARGUS Historical Data Downloader")
    LOG.info("  Symbols:   %s", ", ".join(symbols))
    LOG.info("  Timeframe: %s", args.timeframe)
    LOG.info("  Days:      %d", args.days)
    LOG.info("  Output:    %s", args.output)
    LOG.info("  Endpoint:  %s", "Futures" if args.futures else "Spot")
    LOG.info("=" * 60)

    from src.data.exchange_clients import BinancePublicClient, HistoricalDataDownloader

    client = BinancePublicClient(use_futures=args.futures)
    downloader = HistoricalDataDownloader(client=client)

    paths = downloader.download_multiple(
        symbols=symbols,
        timeframe=args.timeframe,
        days=args.days,
        output_dir=args.output,
    )

    LOG.info("")
    LOG.info("Downloaded %d/%d symbols:", len(paths), len(symbols))
    for p in paths:
        LOG.info("  %s", p)

    if args.news:
        LOG.info("")
        LOG.info("Downloading news headlines...")
        from src.data.exchange_clients import CryptoNewsDownloader
        news = CryptoNewsDownloader()
        count = news.save_headlines(output_path="data/news/headlines.jsonl")
        LOG.info("Saved %d headlines to data/news/headlines.jsonl", count)

    LOG.info("")
    LOG.info("Done! Data ready for backtesting.")
    LOG.info("Use --evolve flag with paper daemon to replay this data.")


if __name__ == "__main__":
    main()
