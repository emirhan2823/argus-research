from __future__ import annotations

import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_incident_drill_script_runs(tmp_path: Path) -> None:
    incident_dir = tmp_path / "incidents"
    report = tmp_path / "incident_drill.md"

    cmd = [
        sys.executable,
        str(REPO_ROOT / "Scripts/incident_drill.py"),
        "--incident-dir",
        str(incident_dir),
        "--report",
        str(report),
    ]
    proc = subprocess.run(cmd, cwd=str(REPO_ROOT), capture_output=True, text=True, timeout=20)
    assert proc.returncode == 0, proc.stdout + "\n" + proc.stderr
    assert report.exists()
    json_files = sorted(incident_dir.glob("INC-*.json"))
    md_files = sorted(incident_dir.glob("INC-*.md"))
    assert json_files
    assert md_files
