#!/bin/bash
set -euo pipefail

cd "$(dirname "$0")/.." || exit 1
REPO_ROOT=$(pwd)

TWIN_ROOT="runs/phase19_twin"
LOG_DIR="logs/phase19_agent"
mkdir -p "$LOG_DIR"
mkdir -p "$TWIN_ROOT"

PID_FILE="${TWIN_ROOT}/supervisor.pid"
ALL_PROFILES=(STRICT SOFT TOPHUNTER)

CMD=${1:-twin-status}
ARG2=${2:-}

case "$CMD" in
    twin-start)
        PROFILES_ARG=${ARG2:-STRICT,SOFT,TOPHUNTER}

        if [ -f "$PID_FILE" ]; then
            PID=$(cat "$PID_FILE")
            if ps -p "$PID" > /dev/null 2>&1; then
                echo "Twin Supervisor already running (PID $PID)."
                exit 1
            fi
            echo "Removing stale supervisor PID file."
            rm "$PID_FILE"
        fi

        echo "Starting Twin Supervisor with profiles: $PROFILES_ARG"
        ARGUS_SUPERVISOR_PROFILES="$PROFILES_ARG" nohup python3 Scripts/phase19_supervisor.py > "${LOG_DIR}/supervisor.log" 2>&1 &
        echo "Launched. Check twin-status."
        ;;

    twin-stop)
        if [ -f "$PID_FILE" ]; then
            PID=$(cat "$PID_FILE")
            echo "Stopping Twin Supervisor (PID $PID)..."
            kill "$PID" || true
            sleep 2
            if ps -p "$PID" > /dev/null 2>&1; then
                echo "Force killing Supervisor..."
                kill -9 "$PID" || true
            fi
            rm "$PID_FILE"
        else
            echo "No Twin Supervisor PID file found."
        fi

        echo "Ensuring child daemons are stopped..."
        for D in "${ALL_PROFILES[@]}"; do
            DPID_FILE="${TWIN_ROOT}/${D}/daemon.pid"
            if [ -f "$DPID_FILE" ]; then
                DPID=$(cat "$DPID_FILE")
                kill "$DPID" 2>/dev/null || true
                rm "$DPID_FILE"
            fi
        done
        echo "Stopped."
        ;;

    twin-status)
        echo "=== TWIN SUPERVISOR ==="
        if [ -f "$PID_FILE" ]; then
            PID=$(cat "$PID_FILE")
            if ps -p "$PID" > /dev/null 2>&1; then
                echo "Status: RUNNING (PID $PID)"
                ps -p "$PID" -o pid,etime,command | head -2
            else
                echo "Status: CRASHED/DOWN (Stale PID)"
            fi
        else
            echo "Status: STOPPED"
        fi

        for D in "${ALL_PROFILES[@]}"; do
            echo ""
            echo "=== DAEMON [$D] ==="
            DPID_FILE="${TWIN_ROOT}/${D}/daemon.pid"
            if [ -f "$DPID_FILE" ]; then
                DPID=$(cat "$DPID_FILE")
                if ps -p "$DPID" > /dev/null 2>&1; then
                    echo "Process: RUNNING (PID $DPID)"
                else
                    echo "Process: STALE PID"
                fi
            else
                echo "Process: STOPPED"
            fi

            HB_FILE="${TWIN_ROOT}/${D}/heartbeat.json"
            if [ -f "$HB_FILE" ]; then
                AGE=$(python3 -c "import json,time,datetime; d=json.load(open('$HB_FILE')); ts=datetime.datetime.fromisoformat(d['ts_iso']); print(f'{time.time()-ts.timestamp():.1f}')" 2>/dev/null || echo "ERR")
                ERRS=$(python3 -c "import json; d=json.load(open('$HB_FILE')); print(d.get('health',{}).get('consecutive_errors',0))" 2>/dev/null || echo "0")
                echo "Heartbeat Age: ${AGE}s"
                echo "Consec Errors: ${ERRS}"
            else
                echo "Heartbeat: NONE"
            fi
        done
        ;;

    twin-ui)
        echo "Starting Twin Dashboard..."

        TARGET_PORT=""
        if [[ "$ARG2" =~ ^[0-9]+$ ]]; then
             TARGET_PORT="$ARG2"
        fi

        if [ -z "$TARGET_PORT" ]; then
            for P in 8501 8502 8503; do
                if ! lsof -i :$P > /dev/null; then
                    TARGET_PORT=$P
                    break
                fi
            done
            if [ -z "$TARGET_PORT" ]; then
                 TARGET_PORT=$(python3 -c 'import socket; s=socket.socket(); s.bind(("", 0)); print(s.getsockname()[1]); s.close()')
            fi
        fi

        echo "Using Port: $TARGET_PORT"

        nohup python3 -m streamlit run Scripts/phase19_dashboard.py --server.port $TARGET_PORT --server.address 0.0.0.0 > "${LOG_DIR}/ui.log" 2>&1 &
        echo "UI Launched at http://localhost:$TARGET_PORT"
        ;;

    tail)
        echo "Tailing Logs (Supervisor + Twin Daemons + UI)..."
        FILES="-f ${LOG_DIR}/supervisor.log"

        for D in "${ALL_PROFILES[@]}"; do
            LATEST=$(ls -t "${LOG_DIR}"/daemon_${D}_run_*.log 2>/dev/null | head -1)
            if [ -n "$LATEST" ]; then
                FILES="$FILES $LATEST"
            fi
        done

        if [ -f "${LOG_DIR}/ui.log" ]; then
            FILES="$FILES ${LOG_DIR}/ui.log"
        fi

        eval tail $FILES
        ;;

    lab-run)
        echo "Running Counterfactual Lab..."

        echo "Running Sanity Check..."
        if ! python3 Scripts/phase19_counterfactual_sanity.py; then
            echo "Sanity Check FAILED. Aborting Lab run."
            exit 1
        fi

        python3 Scripts/phase19_counterfactual.py

        echo "Generating Tuning Proposals..."
        python3 Scripts/phase19_tuning_proposals.py

        echo "Done. Check runs/phase19_twin/lab/"
        ;;

    *)
        echo "Usage: $0 {twin-start [STRICT,SOFT,TOPHUNTER]|twin-stop|twin-status|twin-ui [PORT]|tail|lab-run}"
        exit 1
        ;;
esac
