#!/bin/bash
set -euo pipefail

# Repo Root Resolution
cd "$(dirname "$0")/.." || exit 1
REPO_ROOT=$(pwd)

# Config
LOG_DIR="logs/phase19_agent"
RUN_DIR="runs/phase19_paper/live_test"
mkdir -p "$LOG_DIR"
mkdir -p "$RUN_DIR"

TS=$(date +%Y%m%d_%H%M%S)
LOG="${LOG_DIR}/daemon_run_${TS}.log"
PID_FILE="${RUN_DIR}/daemon.pid"

# Check if already running
if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE")
    if ps -p "$OLD_PID" > /dev/null 2>&1; then
        echo "ERROR: Daemon already running (PID $OLD_PID). Use scripts/phase19_stop.sh first."
        exit 1
    else
        echo "WARN: Stale PID file found. Removing."
        rm "$PID_FILE"
    fi
fi

# Link latest log
ln -sf "$(basename "$LOG")" "${LOG_DIR}/latest_daemon.log"

echo "=== STARTING PAPER DAEMON ==="
echo "Log: $LOG"
echo "Dir: $RUN_DIR"

# Launch with Caffeinate (Prevent Sleep)
# -d: Display, -i: Idle, -m: Disk, -s: System, -u: User
nohup caffeinate -dimsu python3 -u scripts/paper_daemon.py >> "$LOG" 2>&1 &
PID=$!

echo "$PID" > "$PID_FILE"
echo "STARTED PID=$PID"
echo "Tail Log:"
sleep 1
tail -n 3 "$LOG"
