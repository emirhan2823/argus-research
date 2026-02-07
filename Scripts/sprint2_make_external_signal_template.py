#!/usr/bin/env python3
import argparse
import csv
import os
from datetime import datetime, timedelta, timezone


def parse_args():
    p = argparse.ArgumentParser(description="Generate external signal CSV template.")
    p.add_argument(
        "--output",
        default="runs/templates/external_signals_template.csv",
        help="Output CSV path",
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()
    os.makedirs(os.path.dirname(args.output), exist_ok=True)

    now = datetime.now(timezone.utc).replace(microsecond=0)
    rows = [
        {
            "timestamp": (now - timedelta(minutes=15)).isoformat().replace("+00:00", "Z"),
            "symbol": "BTCUSDT",
            "source": "news_feed",
            "direction": "BUY",
            "confidence": 0.72,
            "note": "ETF flow headline positive",
        },
        {
            "timestamp": (now - timedelta(minutes=10)).isoformat().replace("+00:00", "Z"),
            "symbol": "BTCUSDT",
            "source": "trader_alpha",
            "direction": "SELL",
            "confidence": 0.81,
            "note": "High-winrate trader short update",
        },
        {
            "timestamp": (now - timedelta(minutes=5)).isoformat().replace("+00:00", "Z"),
            "symbol": "BTCUSDT",
            "source": "news_feed",
            "direction": "NEUTRAL",
            "confidence": 0.40,
            "note": "Mixed macro tone",
        },
    ]

    with open(args.output, "w", newline="") as f:
        w = csv.DictWriter(
            f,
            fieldnames=["timestamp", "symbol", "source", "direction", "confidence", "note"],
        )
        w.writeheader()
        w.writerows(rows)

    print(f"TEMPLATE_WRITTEN={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
