#!/bin/bash
set -euo pipefail

cd "$(dirname "$0")/.." || exit 1
REPO_ROOT=$(pwd)

RUN_DIR="runs/phase19_paper/live_test"
PID_FILE="${RUN_DIR}/supervisor.pid"
DAEMON_PID_FILE="${RUN_DIR}/daemon.pid"
LOG_DIR="logs/phase19_agent"
mkdir -p "$LOG_DIR"

CMD=${1:-status}
PORT_ARG=${2:-} # Optional port arg or logic handling

case "$CMD" in
    start)
        if [ -f "$PID_FILE" ]; then
            PID=$(cat "$PID_FILE")
            if ps -p "$PID" > /dev/null 2>&1; then
                echo "Supervisor already running (PID $PID)."
                exit 1
            fi
            echo "Removing stale supervisor PID file."
            rm "$PID_FILE"
        fi
        
        echo "Starting Supervisor..."
        nohup python3 scripts/phase19_supervisor.py > "${LOG_DIR}/supervisor.log" 2>&1 &
        echo "Launched. Check status."
        ;;
        
    stop)
        if [ -f "$PID_FILE" ]; then
            PID=$(cat "$PID_FILE")
            echo "Stopping Supervisor (PID $PID)..."
            kill "$PID" || true
            sleep 2
            if ps -p "$PID" > /dev/null 2>&1; then
                echo "Force killing Supervisor..."
                kill -9 "$PID" || true
            fi
            rm "$PID_FILE"
        else
            echo "No Supervisor PID file found."
        fi
        
        # Ensure Daemon is gone too
        if [ -f "$DAEMON_PID_FILE" ]; then
            DPID=$(cat "$DAEMON_PID_FILE")
             if ps -p "$DPID" > /dev/null 2>&1; then
                echo "Stopping residual Daemon (PID $DPID)..."
                kill "$DPID" || true
            fi
            rm "$DAEMON_PID_FILE"
        fi
        echo "Stopped."
        ;;
        
    status)
        echo "=== SUPERVISOR STATUS ==="
        if [ -f "$PID_FILE" ]; then
            PID=$(cat "$PID_FILE")
            if ps -p "$PID" > /dev/null 2>&1; then
                echo "Supervisor: RUNNING (PID $PID)"
                ps -p "$PID" -o pid,etime,command | head -2
            else
                echo "Supervisor: CRASHED/DOWN (Stale PID)"
            fi
        else
            echo "Supervisor: STOPPED"
        fi
        
        echo ""
        echo "=== DAEMON STATUS ==="
        if [ -f "$DAEMON_PID_FILE" ]; then
            DPID=$(cat "$DAEMON_PID_FILE")
            if ps -p "$DPID" > /dev/null 2>&1; then
                echo "Daemon: RUNNING (PID $DPID)"
                ps -p "$DPID" -o pid,etime,command | head -2
            else
                echo "Daemon: DOWN (Stale PID)"
            fi
        else
             echo "Daemon: STOPPED"
        fi
        
        echo ""
        echo "=== HEARTBEAT ==="
        HEARTBEAT="${RUN_DIR}/heartbeat.json"
        if [ -f "$HEARTBEAT" ]; then
            cat "$HEARTBEAT"
            echo ""
            # Calculate freshness
            TS=$(date -r "$HEARTBEAT" "+%H:%M:%S")
            echo "File Mod Time: $TS"
        else
            echo "No Heartbeat file."
        fi
        ;;
    
    ui)
        echo "Starting Dashboard..."
        
        # Port Auto-Selection
        TARGET_PORT=""
        
        # If user passed --port N, use it (rudimentary parse)
        if [[ "$PORT_ARG" == "--port" && -n "${3:-}" ]]; then
             TARGET_PORT="$3"
        elif [[ "$PORT_ARG" =~ ^[0-9]+$ ]]; then
             TARGET_PORT="$PORT_ARG"
        fi
        
        if [ -z "$TARGET_PORT" ]; then
            # Try 8501, 8502, 8503
            for P in 8501 8502 8503; do
                if ! lsof -i :$P > /dev/null; then
                    TARGET_PORT=$P
                    break
                fi
            done
            if [ -z "$TARGET_PORT" ]; then
                echo "All default ports (8501-8503) busy. Choosing random free port..."
                TARGET_PORT=$(python3 -c 'import socket; s=socket.socket(); s.bind(("", 0)); print(s.getsockname()[1]); s.close()')
            fi
        fi
        
        echo "Using Port: $TARGET_PORT"
        
        # ensure requirements
        # pip install -r requirements_phase19_ui.txt > /dev/null 2>&1 || true
        
        nohup python3 -m streamlit run Scripts/phase19_dashboard.py --server.port $TARGET_PORT --server.Address 0.0.0.0 > "${LOG_DIR}/ui.log" 2>&1 &
        echo "UI Launched in background. Log: ${LOG_DIR}/ui.log"
        echo "Access at http://localhost:$TARGET_PORT"
        ;;

    tail)
        echo "Tailing Logs (Supervisor + UI + Latest Daemon)..."
        LATEST_DAEMON=$(ls -t "${LOG_DIR}"/daemon_run_*.log 2>/dev/null | head -1)
        FILES="-f ${LOG_DIR}/supervisor.log"
        if [ -n "$LATEST_DAEMON" ]; then FILES="$FILES $LATEST_DAEMON"; fi
        if [ -f "${LOG_DIR}/ui.log" ]; then FILES="$FILES ${LOG_DIR}/ui.log"; fi
        
        tail $FILES
        ;;
        
    *)
        echo "Usage: $0 {start|stop|status|ui|tail}"
        exit 1
        ;;
esac
