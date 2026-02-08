from pathlib import Path
import time
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from argus_py.recovery.backup import BackupConfig, BackupManager
from argus_py.recovery.restore import validate_backup


def _write_run_files(run_dir: Path):
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "daemon_state.json").write_text('{"ok": true}', encoding="utf-8")
    (run_dir / "trades.csv").write_text("ts,pnl\n1,2\n", encoding="utf-8")
    (run_dir / "decisions.csv").write_text("ts,decision\n1,GO\n", encoding="utf-8")
    (run_dir / "rejects.csv").write_text("ts,code\n1,X\n", encoding="utf-8")


def test_create_backup_copies_critical_files(tmp_path):
    run_dir = tmp_path / "run"
    backup_dir = tmp_path / "backups"
    _write_run_files(run_dir)

    bm = BackupManager(run_dir, BackupConfig(backup_dir=backup_dir, max_backups=5))
    out = bm.create_backup()

    assert out.exists()
    assert (out / "daemon_state.json").exists()
    assert (out / "trades.csv").exists()


def test_restore_latest_recovers_files(tmp_path):
    run_dir = tmp_path / "run"
    backup_dir = tmp_path / "backups"
    _write_run_files(run_dir)

    bm = BackupManager(run_dir, BackupConfig(backup_dir=backup_dir, max_backups=5))
    _ = bm.create_backup()

    (run_dir / "daemon_state.json").write_text("{}", encoding="utf-8")
    ok = bm.restore_latest()

    assert ok is True
    assert (run_dir / "daemon_state.json").read_text(encoding="utf-8") == '{"ok": true}'


def test_cleanup_old_backups_respects_max(tmp_path):
    run_dir = tmp_path / "run"
    backup_dir = tmp_path / "backups"
    _write_run_files(run_dir)

    bm = BackupManager(run_dir, BackupConfig(backup_dir=backup_dir, max_backups=2))
    bm.create_backup()
    time.sleep(1)
    bm.create_backup()
    time.sleep(1)
    bm.create_backup()

    backups = sorted(backup_dir.glob("backup_*"))
    assert len(backups) == 2


def test_restore_latest_returns_false_when_no_backups(tmp_path):
    run_dir = tmp_path / "run"
    run_dir.mkdir(parents=True)
    backup_dir = tmp_path / "backups"

    bm = BackupManager(run_dir, BackupConfig(backup_dir=backup_dir, max_backups=2))
    assert bm.restore_latest() is False


def test_validate_backup_reports_missing_files(tmp_path):
    bdir = tmp_path / "backup_1"
    bdir.mkdir(parents=True)
    (bdir / "daemon_state.json").write_text("{}", encoding="utf-8")

    result = validate_backup(bdir)
    assert result.valid is False
    assert "trades.csv" in result.missing_files
