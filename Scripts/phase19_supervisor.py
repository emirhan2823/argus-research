
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
LOG_DIR = REPO_ROOT / "logs/phase19_agent"
TWIN_ROOT = REPO_ROOT / "runs/phase19_twin"

# Restart Policy
MAX_RESTARTS_PER_HOUR = 5
STALE_THRESHOLD_SECONDS = 180

# Daemon Configurations
DAEMONS = {
    "STRICT": {
        "run_dir": TWIN_ROOT / "STRICT",
        "min_adx": 35.0
    },
    "SOFT": {
        "run_dir": TWIN_ROOT / "SOFT",
        "min_adx": 20.0,
        "soft_defense_override": True
    }
}

def log(msg):
    ts = datetime.now().isoformat()
    entry = f"[{ts}] [SUPERVISOR] {msg}"
    print(entry)
    with open(LOG_DIR / "supervisor.log", "a") as f:
        f.write(entry + "\n")

class Supervisor:
    def __init__(self):
        # State per daemon: { "STRICT": { "proc": Popen, "restarts": deque, "pid_file": Path, "hb_file": Path } }
        self.state = {}
        for did, cfg in DAEMONS.items():
            self.state[did] = {
                "proc": None,
                "restarts": deque(),
                "config": cfg,
                "pid_file": cfg["run_dir"] / "daemon.pid",
                "hb_file": cfg["run_dir"] / "heartbeat.json",
                "log_prefix": f"daemon_{did}"
            }
            # Ensure dirs
            cfg["run_dir"].mkdir(parents=True, exist_ok=True)
            
    def check_running(self, did):
        proc = self.state[did]["proc"]
        if proc is None:
            return False
        return proc.poll() is None
        
    def start_daemon(self, did):
        s = self.state[did]
        
        # Rate Limit Check
        now = datetime.now()
        while s["restarts"] and (now - s["restarts"][0]) > timedelta(hours=1):
            s["restarts"].popleft()
            
        if len(s["restarts"]) >= MAX_RESTARTS_PER_HOUR:
            log(f"CRITICAL: [{did}] Max restarts ({MAX_RESTARTS_PER_HOUR}/hr) exceeded. Giving up on {did}.")
            return
            
        log(f"Starting Daemon [{did}]...")
        
        # Log File
        ts_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        d_log = LOG_DIR / f"{s['log_prefix']}_run_{ts_str}.log"
        
        # Command
        # python3 -u scripts/paper_daemon.py --daemon_id DID --run_dir PATH --min_adx VAL --max_exp_move_bps 80
        cmd = [
            "caffeinate", "-dimsu", 
            sys.executable, "-u", str(REPO_ROOT / "Scripts/paper_daemon.py"),
            "--daemon_id", did,
            "--run_dir", str(s["config"]["run_dir"]),
            "--min_adx", str(s["config"]["min_adx"]),
            "--max_exp_move_bps", "80.0"
        ]
        
        if s["config"].get("soft_defense_override", False):
            cmd.append("--soft_defense_override")
            
        if s["config"].get("safe_paper", False):
            cmd.append("--safe_paper")
        
        try:
            with open(d_log, "a") as out_f:
                s["proc"] = subprocess.Popen(
                    cmd,
                    stdout=out_f,
                    stderr=subprocess.STDOUT,
                    cwd=str(REPO_ROOT),
                    preexec_fn=os.setsid
                )
            
            s["restarts"].append(now)
            log(f"Daemon [{did}] Started. PID={s['proc'].pid}. Log={d_log}")
            
            # Write PID
            with open(s["pid_file"], "w") as f:
                f.write(str(s["proc"].pid))
                
        except Exception as e:
            log(f"Failed to start daemon [{did}]: {e}")
            
    def check_heartbeat(self, did):
        s = self.state[did]
        hb_file = s["hb_file"]
        
        if not hb_file.exists():
            # Grace period logic could be here, but simpler:
            # If proc is running, and file missing for long time -> stale.
            # For now, similar to before: ignore if missing (assuming startup)
            return True
            
        try:
            with open(hb_file, "r") as f:
                hb = json.load(f)
                
            ts_str = hb.get("ts_iso")
            if not ts_str: return True
            
            hb_ts = datetime.fromisoformat(ts_str)
            delta = (datetime.now() - hb_ts).total_seconds()
            
            if delta > STALE_THRESHOLD_SECONDS:
                log(f"HEARTBEAT STALE [{did}]: {delta:.1f}s > {STALE_THRESHOLD_SECONDS}s. Restarting...")
                return False
                
            return True
            
        except Exception as e:
            log(f"Error reading heartbeat [{did}]: {e}")
            return True

    def kill_daemon(self, did):
        s = self.state[did]
        if s["proc"]:
            log(f"Killing Daemon [{did}] PID {s['proc'].pid}...")
            try:
                os.killpg(os.getpgid(s["proc"].pid), signal.SIGTERM)
                try:
                    s["proc"].wait(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(os.getpgid(s["proc"].pid), signal.SIGKILL)
            except Exception as e:
                log(f"Kill error [{did}]: {e}")
            s["proc"] = None

    def run(self):
        # Register Signal Handler
        signal.signal(signal.SIGTERM, self.shutdown)
        signal.signal(signal.SIGINT, self.shutdown)
        
        # Write Supervisor PID
        TWIN_ROOT.mkdir(parents=True, exist_ok=True)
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        
        # We put supervisor PID in TWIN_ROOT
        sup_pid_file = TWIN_ROOT / "supervisor.pid"
        with open(sup_pid_file, "w") as f:
            f.write(str(os.getpid()))
            
        log("Twin Supervisor Running.")
        
        while True:
            for did in self.state:
                if not self.check_running(did):
                    log(f"Daemon [{did}] not running. Starting...")
                    self.start_daemon(did)
                    time.sleep(2) # Stagger starts
                else:
                    if not self.check_heartbeat(did):
                        self.kill_daemon(did)
            
            time.sleep(10)

    def cleanup(self):
        log("Cleaning up...")
        for did in self.state:
            self.kill_daemon(did)
            
        sup_pid_file = TWIN_ROOT / "supervisor.pid"
        if sup_pid_file.exists():
            os.remove(sup_pid_file)

    def shutdown(self, signum, frame):
        log(f"Received signal {signum}. Shutting down.")
        self.cleanup()
        sys.exit(0)

if __name__ == "__main__":
    sup = Supervisor()
    sup.run()
