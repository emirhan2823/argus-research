from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict

import hashlib
import json
import random
import subprocess
from datetime import datetime

import numpy as np


@dataclass
class RunManifest:
    run_id: str
    seed: int
    timestamp: str
    git_commit: str
    config_hash: str
    data_hash: str
    result_hash: str


class DeterminismManager:
    """Ensures reproducible backtest runs."""

    def __init__(self, seed: int = 42):
        self.seed = seed

    def initialize(self) -> None:
        random.seed(self.seed)
        np.random.seed(self.seed)

    def hash_config(self, config: Dict[str, Any]) -> str:
        config_str = json.dumps(config, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(config_str.encode("utf-8")).hexdigest()[:16]

    def hash_data(self, data_path: Path) -> str:
        path = Path(data_path)
        if path.is_file():
            return hashlib.sha256(path.read_bytes()).hexdigest()[:16]

        file_hashes = []
        for f in sorted(path.glob("*.csv")):
            file_hashes.append(hashlib.sha256(f.read_bytes()).hexdigest())

        return hashlib.sha256("".join(file_hashes).encode("utf-8")).hexdigest()[:16]

    def hash_results(self, trades_csv: Path) -> str:
        path = Path(trades_csv)
        if path.exists():
            return hashlib.sha256(path.read_bytes()).hexdigest()[:16]
        return "NO_TRADES"

    def get_git_commit(self) -> str:
        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                check=False,
            )
            commit = result.stdout.strip()
            return commit[:8] if commit else "UNKNOWN"
        except Exception:
            return "UNKNOWN"

    def create_manifest(
        self,
        run_id: str,
        config: Dict[str, Any],
        data_path: Path,
        trades_csv: Path,
    ) -> RunManifest:
        return RunManifest(
            run_id=run_id,
            seed=self.seed,
            timestamp=datetime.now().isoformat(),
            git_commit=self.get_git_commit(),
            config_hash=self.hash_config(config),
            data_hash=self.hash_data(data_path),
            result_hash=self.hash_results(trades_csv),
        )

    def save_manifest(self, manifest: RunManifest, path: Path) -> None:
        payload = {
            "run_id": manifest.run_id,
            "seed": manifest.seed,
            "timestamp": manifest.timestamp,
            "git_commit": manifest.git_commit,
            "config_hash": manifest.config_hash,
            "data_hash": manifest.data_hash,
            "result_hash": manifest.result_hash,
        }
        Path(path).write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def compare_runs(self, manifest1: RunManifest, manifest2: RunManifest) -> Dict[str, bool]:
        return {
            "same_seed": manifest1.seed == manifest2.seed,
            "same_config": manifest1.config_hash == manifest2.config_hash,
            "same_data": manifest1.data_hash == manifest2.data_hash,
            "same_result": manifest1.result_hash == manifest2.result_hash,
            "is_deterministic": manifest1.result_hash == manifest2.result_hash,
        }
