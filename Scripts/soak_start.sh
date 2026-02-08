#!/usr/bin/env bash
# ARGUS CORE INFRA - DO NOT DELETE
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN_DIR="${REPO_ROOT}/runs/year2/paper_main"
PID_FILE="${RUN_DIR}/daemon.pid"
LOG_FILE="${RUN_DIR}/daemon.log"

mkdir -p "${RUN_DIR}"
touch "${LOG_FILE}"

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
    echo "[soak_start] --strategy needs a value"
    exit 1
  fi
  STRATEGY="$2"
  shift 2
fi

PYTHON_BIN="${REPO_ROOT}/venv/bin/python"
if [[ ! -x "${PYTHON_BIN}" ]]; then
  PYTHON_BIN="python3"
fi

CMD=(
  "${PYTHON_BIN}" "${REPO_ROOT}/Scripts/paper_daemon.py"
  --daemon_id "YEAR2_SOAK"
  --run_dir "${RUN_DIR}"
  --strategy "${STRATEGY}"
)

if [[ $# -gt 0 ]]; then
  CMD+=("$@")
fi

nohup "${CMD[@]}" >>"${LOG_FILE}" 2>&1 &
NEW_PID="$!"
echo "${NEW_PID}" >"${PID_FILE}"

echo "[soak_start] started"
echo "  pid=${NEW_PID}"
echo "  strategy=${STRATEGY}"
echo "  run_dir=${RUN_DIR}"
echo "  log=${LOG_FILE}"
