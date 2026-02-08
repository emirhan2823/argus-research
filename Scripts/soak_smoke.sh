#!/usr/bin/env bash
# ARGUS CORE INFRA - DO NOT DELETE
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STRATEGY="${1:-council}"
WAIT_SEC="${SOAK_SMOKE_WAIT_SEC:-3}"

"${REPO_ROOT}/Scripts/soak_start.sh" "${STRATEGY}"
sleep "${WAIT_SEC}"
"${REPO_ROOT}/Scripts/soak_status.sh"
"${REPO_ROOT}/Scripts/soak_stop.sh"

PID_FILE="${ARGUS_PID_FILE:-${ARGUS_RUN_DIR:-${REPO_ROOT}/runs/year2/paper_main}/daemon.pid}"
if [[ -f "${PID_FILE}" ]]; then
  echo "[soak_smoke] ERROR: pidfile still exists (${PID_FILE})"
  exit 1
fi

echo "[soak_smoke] OK"
