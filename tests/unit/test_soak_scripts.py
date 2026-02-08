from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_soak_smoke_with_dummy_daemon(tmp_path):
    run_dir = tmp_path / "paper_main"
    daemon_py = tmp_path / "dummy_daemon.py"

    daemon_py.write_text(
        """
import argparse
import json
import signal
import time
from datetime import datetime
from pathlib import Path

alive = True

def stop(*_args):
    global alive
    alive = False

signal.signal(signal.SIGTERM, stop)
signal.signal(signal.SIGINT, stop)

p = argparse.ArgumentParser()
p.add_argument('--run_dir', required=True)
p.add_argument('--strategy', default='council')
p.add_argument('--daemon_id', default='DUMMY')
args, _ = p.parse_known_args()

run_dir = Path(args.run_dir)
run_dir.mkdir(parents=True, exist_ok=True)

while alive:
    hb = {
        'ts_iso': datetime.utcnow().isoformat(),
        'counters': {'bars_seen': 1, 'decisions_total': 1, 'trades_total': 0, 'rejects_total': 0},
        'risk_level': 'NORMAL',
        'health': {'consecutive_errors': 0, 'last_error': None},
    }
    (run_dir / 'heartbeat.json').write_text(json.dumps(hb), encoding='utf-8')
    time.sleep(0.2)
""".strip(),
        encoding="utf-8",
    )

    env = os.environ.copy()
    env["ARGUS_RUN_DIR"] = str(run_dir)
    env["ARGUS_PYTHON_BIN"] = sys.executable
    env["ARGUS_DAEMON_ENTRYPOINT"] = str(daemon_py)
    env["ARGUS_STARTUP_WAIT_SEC"] = "1"
    env["SOAK_SMOKE_WAIT_SEC"] = "1"

    proc = subprocess.run(
        ["bash", str(REPO_ROOT / "Scripts/soak_smoke.sh"), "council"],
        cwd=str(REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=20,
    )

    assert proc.returncode == 0, proc.stdout + "\n" + proc.stderr
    assert "[soak_smoke] OK" in proc.stdout
    assert (run_dir / "daemon.log").exists()
    assert not (run_dir / "daemon.pid").exists()
