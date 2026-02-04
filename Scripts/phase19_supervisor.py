
import sys
import os
import time
import json
import subprocess
import signal
import psutil
from datetime import datetime, timedelta
from pathlib import Path
from collections import deque

# --- CONFIG ---
REPO_ROOT = Path(__file__).resolve().parent.parent
RUN_DIR = REPO_ROOT / "runs/phase19_paper/live_test"
LOG_DIR = REPO_ROOT / "logs/phase19_agent"
HEARTBEAT_FILE = RUN_DIR / "heartbeat.json"
SUPERVISOR_PID_FILE = RUN_DIR / "supervisor.pid"
DAEMON_PID_FILE = RUN_DIR / "daemon.pid"

# Restart Policy
MAX_RESTARTS_PER_HOUR = 5
STALE_THRESHOLD_SECONDS = 180

def log(msg):
    ts = datetime.now().isoformat()
    entry = f"[{ts}] [SUPERVISOR] {msg}"
    print(entry)
    with open(LOG_DIR / "supervisor.log", "a") as f:
        f.write(entry + "\n")

class Supervisor:
    def __init__(self):
        self.restarts = deque()
        self.daemon_proc = None
        
    def check_daemon_running(self):
        if self.daemon_proc is None:
            return False
        return self.daemon_proc.poll() is None
        
    def start_daemon(self):
        # Rate Limit Check
        now = datetime.now()
        # Prune old
        while self.restarts and (now - self.restarts[0]) > timedelta(hours=1):
            self.restarts.popleft()
            
        if len(self.restarts) >= MAX_RESTARTS_PER_HOUR:
            log(f"CRITICAL: Max restarts ({MAX_RESTARTS_PER_HOUR}/hr) exceeded. Aborting.")
            self.cleanup()
            sys.exit(1)
            
        log("Starting Daemon with Caffeinate...")
        
        # Log File for Daemon
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        d_log = LOG_DIR / f"daemon_run_{ts}.log"
        
        # Command: caffeinate -dimsu python3 -u scripts/paper_daemon.py
        # Use simple Popen
        cmd = ["caffeinate", "-dimsu", sys.executable, "-u", str(REPO_ROOT / "scripts/paper_daemon.py")]
        
        try:
            with open(d_log, "a") as out_f:
                self.daemon_proc = subprocess.Popen(
                    cmd,
                    stdout=out_f,
                    stderr=subprocess.STDOUT,
                    cwd=str(REPO_ROOT),
                    preexec_fn=os.setsid # process group for easier killing
                )
            
            self.restarts.append(now)
            log(f"Daemon Started. PID={self.daemon_proc.pid}. Log={d_log}")
            
            # Write PID
            with open(DAEMON_PID_FILE, "w") as f:
                f.write(str(self.daemon_proc.pid))
                
        except Exception as e:
            log(f"Failed to start daemon: {e}")

    def check_heartbeat(self):
        if not HEARTBEAT_FILE.exists():
            return True # Allow startup grace period? 
            # Actually if startup is > 3 mins, something wrong.
            # But let's assume if process is running, file *should* exist shortly.
        
        try:
            with open(HEARTBEAT_FILE, "r") as f:
                hb = json.load(f)
                
            ts_str = hb.get("ts_iso")
            if not ts_str: return True
            
            hb_ts = datetime.fromisoformat(ts_str)
            delta = (datetime.now() - hb_ts).total_seconds()
            
            if delta > STALE_THRESHOLD_SECONDS:
                log(f"HEARTBEAT STALE: {delta:.1f}s > {STALE_THRESHOLD_SECONDS}s. Restarting...")
                return False
                
            return True
            
        except Exception as e:
            log(f"Error reading heartbeat: {e}")
            return True # Don't kill on read error immediately

    def kill_daemon(self):
        if self.daemon_proc:
            log(f"Killing Daemon PID {self.daemon_proc.pid}...")
            try:
                os.killpg(os.getpgid(self.daemon_proc.pid), signal.SIGTERM)
                try:
                    self.daemon_proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(os.getpgid(self.daemon_proc.pid), signal.SIGKILL)
            except Exception as e:
                log(f"Kill error: {e}")
            self.daemon_proc = None

    def run(self):
        # Register Signal Handler
        signal.signal(signal.SIGTERM, self.shutdown)
        signal.signal(signal.SIGINT, self.shutdown)
        
        # Write Supervisor PID
        RUN_DIR.mkdir(parents=True, exist_ok=True)
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        
        with open(SUPERVISOR_PID_FILE, "w") as f:
            f.write(str(os.getpid()))
            
        log("Supervisor Running.")
        
        while True:
            if not self.check_daemon_running():
                log("Daemon not running. Starting...")
                self.start_daemon()
                # Give it some startup grace period for heartbeat?
                time.sleep(10) 
            else:
                if not self.check_heartbeat():
                    self.kill_daemon()
                    continue
            
            time.sleep(10)

    def cleanup(self):
        log("Cleaning up...")
        self.kill_daemon()
        if SUPERVISOR_PID_FILE.exists():
            os.remove(SUPERVISOR_PID_FILE)

    def shutdown(self, signum, frame):
        log(f"Received signal {signum}. Shutting down.")
        self.cleanup()
        sys.exit(0)

if __name__ == "__main__":
    sup = Supervisor()
    sup.run()
