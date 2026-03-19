from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List


REQUIRED_BACKUP_FILES = ["daemon_state.json", "trades.csv", "decisions.csv", "rejects.csv"]


@dataclass
class RestoreValidation:
    valid: bool
    missing_files: List[str]


def validate_backup(backup_dir: Path) -> RestoreValidation:
    backup = Path(backup_dir)
    missing = [name for name in REQUIRED_BACKUP_FILES if not (backup / name).exists()]
    return RestoreValidation(valid=len(missing) == 0, missing_files=missing)
