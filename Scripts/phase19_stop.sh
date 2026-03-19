#!/bin/bash
set -euo pipefail

cd "$(dirname "$0")/.." || exit 1

RUN_DIR="runs/phase19_paper/live_test"
PID_FILE="${RUN_DIR}/daemon.pid"

if [ ! -f "$PID_FILE" ]; then
    echo "No PID file found at $PID_FILE."
    # Fallback search
    PID=$(ps aux | grep "python3 -u scripts/paper_daemon.py" | grep -v grep | awk '{print $2}' | head -1)
    if [ -n "$PID" ]; then
        echo "Found orphaned process PID=$PID. Killing..."
        kill "$PID" || true
        exit 0
    fi
    echo "Daemon does not appear to be running."
    exit 0
fi

PID=$(cat "$PID_FILE")

if ! ps -p "$PID" > /dev/null 2>&1; then
    echo "PID $PID not found. Cleaning up stale PID file."
    rm "$PID_FILE"
    exit 0
fi

echo "Stopping Daemon (PID $PID)..."
kill "$PID"

# Wait Loop
COUNT=0
while ps -p "$PID" > /dev/null 2>&1; do
    sleep 1
    COUNT=$((COUNT+1))
    echo -n "."
    if [ "$COUNT" -gt 10 ]; then
        echo ""
        echo "Force killing..."
        kill -9 "$PID" || true
        break
    fi
done

echo ""
echo "STOPPED."
if [ -f "$PID_FILE" ]; then
    rm "$PID_FILE"
fi
