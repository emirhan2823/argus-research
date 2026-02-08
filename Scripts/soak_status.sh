#!/usr/bin/env bash
# ARGUS CORE INFRA - DO NOT DELETE
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN_DIR="${REPO_ROOT}/runs/year2/paper_main"
PID_FILE="${RUN_DIR}/daemon.pid"
LOG_FILE="${RUN_DIR}/daemon.log"
HEARTBEAT_FILE="${RUN_DIR}/heartbeat.json"

show_pid_state() {
  if [[ ! -f "${PID_FILE}" ]]; then
    echo "PID: not found"
    return
  fi

  PID="$(cat "${PID_FILE}" 2>/dev/null || true)"
  if [[ -z "${PID}" ]]; then
    echo "PID: invalid pidfile"
    return
  fi

  if kill -0 "${PID}" 2>/dev/null; then
    echo "PID: ${PID} (running)"
  else
    echo "PID: ${PID} (stale)"
  fi
}

show_heartbeat() {
  if [[ ! -f "${HEARTBEAT_FILE}" ]]; then
    echo "Heartbeat: missing"
    return
  fi

  python3 - "$HEARTBEAT_FILE" <<'PY'
import json
import sys
from datetime import datetime, timezone

p = sys.argv[1]
try:
    hb = json.load(open(p, "r", encoding="utf-8"))
except Exception as e:
    print(f"Heartbeat: unreadable ({e})")
    raise SystemExit(0)

ts = hb.get("ts_iso")
if not ts:
    print("Heartbeat: missing ts_iso")
    raise SystemExit(0)

try:
    dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    now = datetime.now(dt.tzinfo) if dt.tzinfo else datetime.now()
    age = (now - dt).total_seconds()
    print(f"Heartbeat: ts={ts} age_sec={age:.1f}")
except Exception:
    print(f"Heartbeat: ts={ts}")
PY
}

show_log_tail() {
  if [[ ! -f "${LOG_FILE}" ]]; then
    echo "Log: missing (${LOG_FILE})"
    return
  fi
  echo "Log tail (${LOG_FILE}):"
  tail -n 40 "${LOG_FILE}"
}

echo "=== ARGUS PAPER SOAK STATUS ==="
echo "Run dir: ${RUN_DIR}"
show_pid_state
show_heartbeat
show_log_tail
