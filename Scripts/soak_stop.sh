#!/usr/bin/env bash
# ARGUS CORE INFRA - DO NOT DELETE
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN_DIR="${REPO_ROOT}/runs/year2/paper_main"
PID_FILE="${RUN_DIR}/daemon.pid"

if [[ ! -f "${PID_FILE}" ]]; then
  echo "[soak_stop] pidfile not found (${PID_FILE})"
  exit 0
fi

PID="$(cat "${PID_FILE}" 2>/dev/null || true)"
if [[ -z "${PID}" ]]; then
  rm -f "${PID_FILE}"
  echo "[soak_stop] empty pidfile cleaned"
  exit 0
fi

if kill -0 "${PID}" 2>/dev/null; then
  echo "[soak_stop] stopping pid=${PID}"
  kill "${PID}" 2>/dev/null || true

  for _ in {1..20}; do
    if ! kill -0 "${PID}" 2>/dev/null; then
      break
    fi
    sleep 0.5
  done

  if kill -0 "${PID}" 2>/dev/null; then
    echo "[soak_stop] forcing kill -9 pid=${PID}"
    kill -9 "${PID}" 2>/dev/null || true
  fi
else
  echo "[soak_stop] stale pid=${PID}"
fi

rm -f "${PID_FILE}"
echo "[soak_stop] pidfile cleaned"
