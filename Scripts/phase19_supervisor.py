import os
import signal
import subprocess
import sys
import time
import json
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

# Profile configurations
PROFILE_CONFIGS = {
    "STRICT": {
        "run_dir": TWIN_ROOT / "STRICT",
        "min_adx": 35.0,
        "max_exp_move_bps": 80.0,
        "interval": "1m",
        "strategy": "council",
    },
    "SOFT": {
        "run_dir": TWIN_ROOT / "SOFT",
        "min_adx": 20.0,
        "max_exp_move_bps": 80.0,
        "interval": "1m",
        "strategy": "council",
        "soft_defense_override": True,
        "safe_paper": True,
    },
    "TOPHUNTER": {
        "run_dir": TWIN_ROOT / "TOPHUNTER",
        "min_adx": 20.0,
        "max_exp_move_bps": 120.0,
        "interval": "1h",
        "strategy": "tophunter_short_v1",
        "safe_paper": True,
        "tophunter_adx_max": 20.0,
        "tophunter_pivot_left": 2,
        "tophunter_pivot_right": 2,
        "tophunter_daily_loss_cap_pct": 1.5,
        "tophunter_max_risk_trade_pct": 0.5,
        "tophunter_max_open_positions": 1,
        "tophunter_loss_cooldown_bars": 3,
    },
}
DEFAULT_PROFILES = ["STRICT", "SOFT", "TOPHUNTER"]


def log(msg: str) -> None:
    ts = datetime.now().isoformat()
    entry = f"[{ts}] [SUPERVISOR] {msg}"
    print(entry)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    with open(LOG_DIR / "supervisor.log", "a", encoding="utf-8") as f:
        f.write(entry + "\n")


def parse_enabled_profiles() -> list[str]:
    raw = os.environ.get("ARGUS_SUPERVISOR_PROFILES", ",".join(DEFAULT_PROFILES))
    requested = [item.strip().upper() for item in raw.split(",") if item.strip()]
    enabled: list[str] = []
    for profile in requested:
        if profile in PROFILE_CONFIGS and profile not in enabled:
            enabled.append(profile)
    if not enabled:
        enabled = ["STRICT", "SOFT"]
    return enabled


class Supervisor:
    def __init__(self, profiles: list[str]):
        self.profiles = profiles
        self.state = {}

        for did in self.profiles:
            cfg = PROFILE_CONFIGS[did]
            cfg["run_dir"].mkdir(parents=True, exist_ok=True)
            self.state[did] = {
                "proc": None,
                "restarts": deque(),
                "config": cfg,
                "pid_file": cfg["run_dir"] / "daemon.pid",
                "hb_file": cfg["run_dir"] / "heartbeat.json",
                "log_prefix": f"daemon_{did}",
            }

    def check_running(self, did: str) -> bool:
        proc = self.state[did]["proc"]
        if proc is None:
            return False
        return proc.poll() is None

    def _build_command(self, did: str) -> list[str]:
        cfg = self.state[did]["config"]
        cmd = [
            "caffeinate",
            "-dimsu",
            sys.executable,
            "-u",
            str(REPO_ROOT / "Scripts/paper_daemon.py"),
            "--daemon_id",
            did,
            "--run_dir",
            str(cfg["run_dir"]),
            "--min_adx",
            str(cfg["min_adx"]),
            "--max_exp_move_bps",
            str(cfg.get("max_exp_move_bps", 80.0)),
            "--interval",
            str(cfg.get("interval", "1m")),
            "--strategy",
            str(cfg.get("strategy", "council")),
        ]

        if cfg.get("soft_defense_override", False):
            cmd.append("--soft_defense_override")
        if cfg.get("safe_paper", False):
            cmd.append("--safe_paper")

        if cfg.get("strategy") == "tophunter_short_v1":
            cmd.extend([
                "--tophunter_adx_max",
                str(cfg.get("tophunter_adx_max", 20.0)),
                "--tophunter_pivot_left",
                str(cfg.get("tophunter_pivot_left", 2)),
                "--tophunter_pivot_right",
                str(cfg.get("tophunter_pivot_right", 2)),
                "--tophunter_daily_loss_cap_pct",
                str(cfg.get("tophunter_daily_loss_cap_pct", 1.5)),
                "--tophunter_max_risk_trade_pct",
                str(cfg.get("tophunter_max_risk_trade_pct", 0.5)),
                "--tophunter_max_open_positions",
                str(cfg.get("tophunter_max_open_positions", 1)),
                "--tophunter_loss_cooldown_bars",
                str(cfg.get("tophunter_loss_cooldown_bars", 3)),
            ])

        return cmd

    def start_daemon(self, did: str) -> None:
        s = self.state[did]

        # Rate limit
        now = datetime.now()
        while s["restarts"] and (now - s["restarts"][0]) > timedelta(hours=1):
            s["restarts"].popleft()

        if len(s["restarts"]) >= MAX_RESTARTS_PER_HOUR:
            log(f"CRITICAL: [{did}] restart budget exceeded ({MAX_RESTARTS_PER_HOUR}/hr).")
            return

        log(f"Starting daemon [{did}]...")
        ts_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        d_log = LOG_DIR / f"{s['log_prefix']}_run_{ts_str}.log"
        cmd = self._build_command(did)

        try:
            with open(d_log, "a", encoding="utf-8") as out_f:
                s["proc"] = subprocess.Popen(
                    cmd,
                    stdout=out_f,
                    stderr=subprocess.STDOUT,
                    cwd=str(REPO_ROOT),
                    preexec_fn=os.setsid,
                )

            s["restarts"].append(now)
            log(f"Daemon [{did}] started PID={s['proc'].pid}. Log={d_log}")
            with open(s["pid_file"], "w", encoding="utf-8") as f:
                f.write(str(s["proc"].pid))

        except Exception as e:
            log(f"Failed to start daemon [{did}]: {e}")

    def check_heartbeat(self, did: str) -> bool:
        s = self.state[did]
        hb_file = s["hb_file"]
        if not hb_file.exists():
            return True

        try:
            with open(hb_file, "r", encoding="utf-8") as f:
                hb = json.load(f)
            ts_str = hb.get("ts_iso")
            if not ts_str:
                return True

            hb_ts = datetime.fromisoformat(ts_str)
            delta = (datetime.now() - hb_ts).total_seconds()
            if delta > STALE_THRESHOLD_SECONDS:
                log(f"HEARTBEAT STALE [{did}] {delta:.1f}s > {STALE_THRESHOLD_SECONDS}s.")
                return False
            return True
        except Exception as e:
            log(f"Heartbeat parse error [{did}]: {e}")
            return True

    def kill_daemon(self, did: str) -> None:
        s = self.state[did]
        if not s["proc"]:
            return

        pid = s["proc"].pid
        log(f"Stopping daemon [{did}] PID {pid}...")
        try:
            os.killpg(os.getpgid(pid), signal.SIGTERM)
            try:
                s["proc"].wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(os.getpgid(pid), signal.SIGKILL)
        except Exception as e:
            log(f"Stop error [{did}]: {e}")
        finally:
            s["proc"] = None

    def run(self) -> None:
        signal.signal(signal.SIGTERM, self.shutdown)
        signal.signal(signal.SIGINT, self.shutdown)

        TWIN_ROOT.mkdir(parents=True, exist_ok=True)
        LOG_DIR.mkdir(parents=True, exist_ok=True)

        sup_pid_file = TWIN_ROOT / "supervisor.pid"
        with open(sup_pid_file, "w", encoding="utf-8") as f:
            f.write(str(os.getpid()))

        log(f"Supervisor running with profiles: {', '.join(self.profiles)}")

        while True:
            for did in self.profiles:
                if not self.check_running(did):
                    log(f"Daemon [{did}] is down, starting...")
                    self.start_daemon(did)
                    time.sleep(2)
                else:
                    if not self.check_heartbeat(did):
                        self.kill_daemon(did)
            time.sleep(10)

    def cleanup(self) -> None:
        log("Cleanup started")
        for did in self.profiles:
            self.kill_daemon(did)

        sup_pid_file = TWIN_ROOT / "supervisor.pid"
        if sup_pid_file.exists():
            sup_pid_file.unlink()

    def shutdown(self, signum, _frame) -> None:
        log(f"Signal {signum} received, shutting down")
        self.cleanup()
        sys.exit(0)


if __name__ == "__main__":
    profiles = parse_enabled_profiles()
    Supervisor(profiles).run()
