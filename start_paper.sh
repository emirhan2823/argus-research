#!/usr/bin/env bash
# ============================================================
#  ARGUS v2 Paper Trading Daemon - Linux/macOS Launcher
# ============================================================
#
#  Usage:
#    ./start_paper.sh              (default: crypto, 60s interval)
#    ./start_paper.sh --assets crypto,us_equity --interval 30
#
#  Requirements:
#    1. Python 3.10+ with venv at ./venv/
#    2. pip install -r requirements.txt
#    3. Ollama NOT required (unused in v2 pipeline)
#    4. No API keys needed for paper mode
#
#  Stop: Press Ctrl+C (graceful shutdown)
#  Logs: runs/paper_v2/paper_v2_daemon.log
#  Heartbeat: runs/paper_v2/heartbeat.json
# ============================================================

set -e
cd "$(dirname "$0")"

# --- Create output directories ---
mkdir -p runs/paper_v2
mkdir -p runs/v25

# --- Find Python ---
if [ -f "venv/bin/python" ]; then
    PYTHON="venv/bin/python"
elif [ -f ".venv/bin/python" ]; then
    PYTHON=".venv/bin/python"
else
    PYTHON="python3"
fi

echo "============================================================"
echo " ARGUS v2 Paper Trading Daemon"
echo "============================================================"
echo " Python: $PYTHON"
echo " Time:   $(date)"
echo ""

# --- Install deps check ---
if ! $PYTHON -c "import pandas_ta" 2>/dev/null; then
    echo "[WARN] pandas_ta not found. Installing dependencies..."
    $PYTHON -m pip install -r requirements.txt --quiet
    echo ""
fi

# --- Pre-flight: quick import check ---
if ! $PYTHON -c "from src.main import ArgusPipeline; print('[OK] Pipeline imports successful')"; then
    echo "[ERROR] Pipeline import failed. Check logs."
    exit 1
fi

echo ""
echo "Starting daemon... (Ctrl+C to stop)"
echo ""

# --- Run the daemon ---
exec $PYTHON Scripts/paper_v2_daemon.py \
    --mode paper \
    --assets crypto \
    --interval 60 \
    --v25 \
    --v25-db runs/v25/argus_v25.db \
    --run-dir runs/paper_v2 \
    "$@"
