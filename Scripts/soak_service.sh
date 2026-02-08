#!/usr/bin/env bash
# ARGUS CORE INFRA - DO NOT DELETE
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN_DIR="${ARGUS_RUN_DIR:-${REPO_ROOT}/runs/year2/paper_main}"
PYTHON_BIN="${ARGUS_PYTHON_BIN:-${REPO_ROOT}/venv/bin/python}"
DAEMON_ENTRYPOINT="${ARGUS_DAEMON_ENTRYPOINT:-${REPO_ROOT}/Scripts/paper_daemon.py}"

LABEL="com.argus.paper.soak"
PLIST_PATH="${HOME}/Library/LaunchAgents/${LABEL}.plist"
DOMAIN="gui/$(id -u)"

usage() {
  echo "Usage: $0 {install [strategy]|start|stop|status|uninstall|logs}"
}

ensure_prereqs() {
  if [[ ! -x "${PYTHON_BIN}" ]]; then
    echo "[soak_service] ERROR: python not executable at ${PYTHON_BIN}"
    exit 1
  fi
  if [[ ! -f "${DAEMON_ENTRYPOINT}" ]]; then
    echo "[soak_service] ERROR: daemon entrypoint missing at ${DAEMON_ENTRYPOINT}"
    exit 1
  fi
  mkdir -p "${RUN_DIR}"
  mkdir -p "$(dirname "${PLIST_PATH}")"
}

write_plist() {
  local strategy="$1"
  cat >"${PLIST_PATH}" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>${LABEL}</string>
  <key>ProgramArguments</key>
  <array>
    <string>${PYTHON_BIN}</string>
    <string>${DAEMON_ENTRYPOINT}</string>
    <string>--daemon_id</string>
    <string>YEAR2_SOAK_SERVICE</string>
    <string>--run_dir</string>
    <string>${RUN_DIR}</string>
    <string>--strategy</string>
    <string>${strategy}</string>
  </array>
  <key>WorkingDirectory</key>
  <string>${REPO_ROOT}</string>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>StandardOutPath</key>
  <string>${RUN_DIR}/service.log</string>
  <key>StandardErrorPath</key>
  <string>${RUN_DIR}/service.log</string>
</dict>
</plist>
PLIST
}

install_service() {
  local strategy="${1:-council}"
  ensure_prereqs
  write_plist "${strategy}"

  launchctl bootout "${DOMAIN}/${LABEL}" >/dev/null 2>&1 || true
  launchctl bootstrap "${DOMAIN}" "${PLIST_PATH}"
  launchctl enable "${DOMAIN}/${LABEL}" || true

  echo "[soak_service] installed: ${PLIST_PATH}"
  echo "[soak_service] strategy=${strategy}"
}

start_service() {
  launchctl kickstart -k "${DOMAIN}/${LABEL}"
  echo "[soak_service] started ${LABEL}"
}

stop_service() {
  launchctl bootout "${DOMAIN}/${LABEL}" >/dev/null 2>&1 || true
  echo "[soak_service] stopped ${LABEL}"
}

status_service() {
  launchctl print "${DOMAIN}/${LABEL}" >/dev/null 2>&1 && {
    launchctl print "${DOMAIN}/${LABEL}" | sed -n '1,80p'
    return 0
  }
  echo "[soak_service] ${LABEL} not loaded"
}

uninstall_service() {
  stop_service
  rm -f "${PLIST_PATH}"
  echo "[soak_service] uninstalled ${LABEL}"
}

show_logs() {
  if [[ -f "${RUN_DIR}/service.log" ]]; then
    tail -n 80 "${RUN_DIR}/service.log"
  else
    echo "[soak_service] service log missing (${RUN_DIR}/service.log)"
  fi
}

cmd="${1:-}"
case "${cmd}" in
  install)
    install_service "${2:-council}"
    ;;
  start)
    start_service
    ;;
  stop)
    stop_service
    ;;
  status)
    status_service
    ;;
  uninstall)
    uninstall_service
    ;;
  logs)
    show_logs
    ;;
  *)
    usage
    exit 1
    ;;
esac
