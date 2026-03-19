#!/usr/bin/env bash
# ============================================================
#  ARGUS Historical Data Downloader - Linux/macOS Launcher
# ============================================================
#
#  Downloads Binance OHLCV data into month-partitioned Parquet.
#  Can be run from any directory.
#
#  Usage:
#    ./download_data.sh --symbol BTCUSDT --interval 1m --start 2024-01-01 --end 2024-03-01
#    ./download_data.sh --symbol ETHUSDT --interval 1h --days 30
#    ./download_data.sh --all --interval 1m --days 90
#    ./download_data.sh --info
#    ./download_data.sh --info BTCUSDT
#    ./download_data.sh --verify BTCUSDT --interval 1m
#
#  Output: data/binance/{SYMBOL}/{interval}/{YYYY-MM}.parquet
# ============================================================

set -e
cd "$(dirname "$0")"

# --- Find Python ---
if [ -f "venv/bin/python" ]; then
    PYTHON="venv/bin/python"
elif [ -f ".venv/bin/python" ]; then
    PYTHON=".venv/bin/python"
else
    PYTHON="python3"
fi

# --- Pre-flight ---
if ! $PYTHON -c "from src.data.binance_downloader import BinanceDownloader; print('[OK] Imports verified')" 2>/dev/null; then
    echo "[ERROR] Import check failed. Install dependencies:"
    echo "  $PYTHON -m pip install -r requirements.txt"
    exit 1
fi

# --- Run ---
exec $PYTHON Scripts/download_historical.py "$@"
