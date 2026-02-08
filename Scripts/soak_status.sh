#!/usr/bin/env bash
# ARGUS CORE INFRA - DO NOT DELETE
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN_DIR="${ARGUS_RUN_DIR:-${REPO_ROOT}/runs/year2/paper_main}"
PID_FILE="${ARGUS_PID_FILE:-${RUN_DIR}/daemon.pid}"
LOG_FILE="${ARGUS_LOG_FILE:-${RUN_DIR}/daemon.log}"
HEARTBEAT_FILE="${ARGUS_HEARTBEAT_FILE:-${RUN_DIR}/heartbeat.json}"
METRICS_FILE="${ARGUS_METRICS_FILE:-${RUN_DIR}/metrics.json}"

print_log_hints() {
  if [[ ! -f "${LOG_FILE}" ]]; then
    echo "Log: missing (${LOG_FILE})"
    return
  fi

  echo "Log hints (tail error-ish lines):"
  grep -Ei "traceback|error|exception|critical|failed" "${LOG_FILE}" | tail -n 10 || true
}

show_pid_state() {
  if [[ ! -f "${PID_FILE}" ]]; then
    echo "PID: not found"
    print_log_hints
    return
  fi

  PID="$(cat "${PID_FILE}" 2>/dev/null || true)"
  if [[ -z "${PID}" ]]; then
    echo "PID: invalid pidfile"
    print_log_hints
    return
  fi

  if kill -0 "${PID}" 2>/dev/null; then
    echo "PID: ${PID} (running)"
  else
    echo "PID: ${PID} (stale)"
    print_log_hints
  fi
}

show_heartbeat_and_counters() {
  if [[ ! -f "${HEARTBEAT_FILE}" ]]; then
    echo "Heartbeat: missing"
    return
  fi

  python3 - "$HEARTBEAT_FILE" <<'PY'
import json
import sys
from datetime import datetime

p = sys.argv[1]
try:
    hb = json.load(open(p, "r", encoding="utf-8"))
except Exception as e:
    print(f"Heartbeat: unreadable ({e})")
    raise SystemExit(0)

ts = hb.get("ts_iso")
if ts:
    try:
        dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        now = datetime.now(dt.tzinfo) if dt.tzinfo else datetime.now()
        age = (now - dt).total_seconds()
        print(f"Heartbeat: ts={ts} age_sec={age:.1f}")
    except Exception:
        print(f"Heartbeat: ts={ts}")
else:
    print("Heartbeat: missing ts_iso")

c = hb.get("counters", {}) or {}
print(
    "Counters: "
    f"bars_seen={c.get('bars_seen', 0)} "
    f"decisions_total={c.get('decisions_total', 0)} "
    f"trades_total={c.get('trades_total', 0)} "
    f"rejects_total={c.get('rejects_total', 0)}"
)

health = hb.get("health", {}) or {}
if health:
    print(
        "Health: "
        f"consecutive_errors={health.get('consecutive_errors', 0)} "
        f"last_error={health.get('last_error')}"
    )

risk = hb.get("risk_level", "UNKNOWN")
print(f"RiskLevel: {risk}")
PY
}

show_metrics_summary() {
  if [[ ! -f "${METRICS_FILE}" ]]; then
    echo "Metrics: missing (${METRICS_FILE})"
    return
  fi
  python3 - "$METRICS_FILE" <<'PY'
import json
import sys

p = sys.argv[1]
try:
    data = json.load(open(p, "r", encoding="utf-8"))
except Exception as e:
    print(f"Metrics: unreadable ({e})")
    raise SystemExit(0)

print(
    "Metrics: "
    f"bars_seen={data.get('bars_seen', 0)} "
    f"trades_total={data.get('trades_total', 0)} "
    f"rejects_total={data.get('rejects_total', 0)} "
    f"errors_total={data.get('errors_total', 0)}"
)

last_error = data.get("last_error")
if last_error:
    print(f"Metrics last_error: {last_error}")

breakdown = data.get("strategy_id_breakdown", {}) or {}
if breakdown:
    print(f"Metrics strategy_id_breakdown: {breakdown}")
PY
}

show_log_tail() {
  if [[ ! -f "${LOG_FILE}" ]]; then
    return
  fi
  echo "Log tail (${LOG_FILE}):"
  tail -n 40 "${LOG_FILE}" || true
}

echo "=== ARGUS PAPER SOAK STATUS ==="
echo "Run dir: ${RUN_DIR}"
show_pid_state
show_heartbeat_and_counters
show_metrics_summary
show_log_tail
