from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import shutil


@dataclass
class BackupConfig:
    backup_dir: Path
    max_backups: int = 24
    interval_minutes: int = 60


class BackupManager:
    def __init__(self, run_dir: Path, config: BackupConfig):
        self.run_dir = Path(run_dir)
        self.config = config

    def create_backup(self) -> Path:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = self.config.backup_dir / f"backup_{timestamp}"
        backup_path.mkdir(parents=True, exist_ok=True)

        for filename in ["daemon_state.json", "trades.csv", "decisions.csv", "rejects.csv"]:
            src = self.run_dir / filename
            if src.exists():
                shutil.copy2(src, backup_path / filename)

        self._cleanup_old_backups()
        return backup_path

    def restore_latest(self) -> bool:
        backups = sorted(self.config.backup_dir.glob("backup_*"))
        if not backups:
            return False
        latest = backups[-1]
        for f in latest.iterdir():
            shutil.copy2(f, self.run_dir / f.name)
        return True

    def _cleanup_old_backups(self):
        backups = sorted(self.config.backup_dir.glob("backup_*"))
        while len(backups) > self.config.max_backups:
            shutil.rmtree(backups.pop(0))
