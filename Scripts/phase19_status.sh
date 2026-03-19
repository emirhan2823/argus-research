#!/bin/bash
set -euo pipefail

cd "$(dirname "$0")/.." || exit 1

RUN_DIR="runs/phase19_paper/live_test"
PID_FILE="${RUN_DIR}/daemon.pid"
LOG_DIR="logs/phase19_agent"

echo "=== DAEMON STATUS ==="

PID=""
if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if ps -p "$PID" > /dev/null 2>&1; then
        echo "Status: RUNNING (PID $PID)"
        ps -p "$PID" -o pid,etime,command | head -2
    else
        echo "Status: DOWN (Stale PID file $PID)"
    fi
else
    # Check manual run
    PID=$(ps aux | grep "python3 -u scripts/paper_daemon.py" | grep -v grep | awk '{print $2}' | head -1)
    if [ -n "$PID" ]; then
        echo "Status: RUNNING (Manual/Orphaned PID $PID)"
    else
        echo "Status: STOPPED"
    fi
fi

echo ""
echo "=== STATE FILE ==="
STATE_FILE="${RUN_DIR}/daemon_state.json"
if [ -f "$STATE_FILE" ]; then
    ls -lah "$STATE_FILE"
    echo "Last Modified: $(date -r "$STATE_FILE" "+%Y-%m-%d %H:%M:%S")"
else
    echo "WARNING: State file missing."
fi

echo ""
echo "=== HEARTBEAT LOG (Last 10) ==="
STATUS_LOG="${RUN_DIR}/status.log"
if [ -f "$STATUS_LOG" ]; then
    tail -n 10 "$STATUS_LOG"
else
    echo "No status.log found."
fi

echo ""
echo "=== RUN LOG (Last 20) ==="
# Find latest log
LATEST_LOG=$(ls -t "${LOG_DIR}"/daemon_run_*.log 2>/dev/null | head -1)
if [ -n "$LATEST_LOG" ]; then
    echo "Log: $LATEST_LOG"
    tail -n 20 "$LATEST_LOG"
else
    # Fallback to manual run logs if available?
    echo "No run logs found in $LOG_DIR."
fi
