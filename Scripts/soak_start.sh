#!/usr/bin/env bash
# ARGUS CORE INFRA - DO NOT DELETE
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN_DIR="${ARGUS_RUN_DIR:-${REPO_ROOT}/runs/year2/paper_main}"
PID_FILE="${ARGUS_PID_FILE:-${RUN_DIR}/daemon.pid}"
LOG_FILE="${ARGUS_LOG_FILE:-${RUN_DIR}/daemon.log}"
PYTHON_BIN="${ARGUS_PYTHON_BIN:-${REPO_ROOT}/venv/bin/python}"
DAEMON_ENTRYPOINT="${ARGUS_DAEMON_ENTRYPOINT:-${REPO_ROOT}/Scripts/paper_daemon.py}"
STARTUP_WAIT_SEC="${ARGUS_STARTUP_WAIT_SEC:-2}"

mkdir -p "${RUN_DIR}"
mkdir -p "$(dirname "${LOG_FILE}")"
touch "${LOG_FILE}"

log_banner() {
  {
    echo ""
    echo "============================================================"
    echo "[soak_start] $(date -u +"%Y-%m-%dT%H:%M:%SZ")"
    echo "run_dir=${RUN_DIR}"
    echo "pid_file=${PID_FILE}"
    echo "strategy=${STRATEGY:-unknown}"
    echo "============================================================"
  } >>"${LOG_FILE}"
}

if [[ ! -x "${PYTHON_BIN}" ]]; then
  echo "[soak_start] ERROR: python not found at ${PYTHON_BIN}"
  echo "[soak_start] ACTION: create venv and install deps, e.g."
  echo "  python3 -m venv venv"
  echo "  venv/bin/pip install -r requirements.txt"
  exit 1
fi

if [[ ! -f "${DAEMON_ENTRYPOINT}" ]]; then
  ALT_ENTRYPOINT="${REPO_ROOT}/scripts/paper_daemon.py"
  if [[ -f "${ALT_ENTRYPOINT}" ]]; then
    DAEMON_ENTRYPOINT="${ALT_ENTRYPOINT}"
  else
    echo "[soak_start] ERROR: daemon entrypoint not found"
    echo "  checked: ${DAEMON_ENTRYPOINT}"
    echo "  checked: ${ALT_ENTRYPOINT}"
    exit 1
  fi
fi

if [[ -f "${PID_FILE}" ]]; then
  OLD_PID="$(cat "${PID_FILE}" 2>/dev/null || true)"
  if [[ -n "${OLD_PID}" ]] && kill -0 "${OLD_PID}" 2>/dev/null; then
    echo "[soak_start] already running (pid=${OLD_PID})"
    exit 0
  fi
  rm -f "${PID_FILE}"
fi

STRATEGY="council"
if [[ $# -gt 0 ]] && [[ "${1}" != -* ]]; then
  STRATEGY="$1"
  shift
fi
if [[ $# -gt 0 ]] && [[ "${1}" == "--strategy" ]]; then
  if [[ $# -lt 2 ]]; then
    echo "[soak_start] ERROR: --strategy requires a value"
    exit 1
  fi
  STRATEGY="$2"
  shift 2
fi

CMD=(
  "${PYTHON_BIN}" "${DAEMON_ENTRYPOINT}"
  --daemon_id "YEAR2_SOAK"
  --run_dir "${RUN_DIR}"
  --strategy "${STRATEGY}"
)

if [[ $# -gt 0 ]]; then
  CMD+=("$@")
fi

log_banner
printf '[soak_start] cmd=%q ' "${CMD[@]}" >>"${LOG_FILE}"
echo "" >>"${LOG_FILE}"

nohup "${CMD[@]}" >>"${LOG_FILE}" 2>&1 &
NEW_PID="$!"
echo "${NEW_PID}" >"${PID_FILE}"

sleep "${STARTUP_WAIT_SEC}"
if ! kill -0 "${NEW_PID}" 2>/dev/null; then
  echo "[soak_start] ERROR: daemon failed to stay alive (pid=${NEW_PID})"
  echo "[soak_start] last log lines:"
  tail -n 60 "${LOG_FILE}" || true
  rm -f "${PID_FILE}"
  exit 1
fi

echo "[soak_start] started"
echo "  pid=${NEW_PID}"
echo "  strategy=${STRATEGY}"
echo "  run_dir=${RUN_DIR}"
echo "  log=${LOG_FILE}"
