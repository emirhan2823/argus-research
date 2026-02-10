"""Kill switch with persistent level state."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import IntEnum
from pathlib import Path


class RiskLevel(IntEnum):
    NORMAL = 0
    CAUTION = 1
    DEFENSIVE = 2
    HALT = 3
    LOCKDOWN = 4


@dataclass(frozen=True)
class KillSwitchThresholds:
    dd_caution: float = 0.02
    dd_defensive: float = 0.04
    dd_halt: float = 0.06
    dd_lockdown: float = 0.10


class KillSwitch:
    def __init__(
        self,
        *,
        db_path: str = "data/trade_logs/argus.db",
        thresholds: KillSwitchThresholds = KillSwitchThresholds(),
    ) -> None:
        self.db_path = db_path
        self.thresholds = thresholds
        self.level = RiskLevel.NORMAL
        self._ensure_db()
        self._load()

    def update_from_drawdown(self, *, drawdown: float, hermes_critical: bool = False) -> RiskLevel:
        # drawdown expected as positive ratio, e.g. 0.04 for 4%
        if drawdown >= self.thresholds.dd_lockdown:
            drawdown_level = RiskLevel.LOCKDOWN
        elif drawdown >= self.thresholds.dd_halt:
            drawdown_level = RiskLevel.HALT
        elif drawdown >= self.thresholds.dd_defensive:
            drawdown_level = RiskLevel.DEFENSIVE
        elif drawdown >= self.thresholds.dd_caution:
            drawdown_level = RiskLevel.CAUTION
        else:
            drawdown_level = RiskLevel.NORMAL

        floor = RiskLevel.HALT if hermes_critical else RiskLevel.NORMAL
        target = max(drawdown_level, floor)

        self.level = target
        self._save()
        return self.level

    def size_multiplier(self) -> float:
        return {
            RiskLevel.NORMAL: 1.0,
            RiskLevel.CAUTION: 0.75,
            RiskLevel.DEFENSIVE: 0.40,
            RiskLevel.HALT: 0.0,
            RiskLevel.LOCKDOWN: 0.0,
        }[self.level]

    def can_trade(self) -> bool:
        return self.level < RiskLevel.HALT

    def _ensure_db(self) -> None:
        path = Path(self.db_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS kill_switch_state (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    level INTEGER NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.commit()

    def _load(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute("SELECT level FROM kill_switch_state WHERE id = 1").fetchone()
        if row is not None:
            self.level = RiskLevel(int(row[0]))

    def _save(self) -> None:
        ts = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO kill_switch_state(id, level, updated_at)
                VALUES(1, ?, ?)
                ON CONFLICT(id) DO UPDATE SET level = excluded.level, updated_at = excluded.updated_at
                """,
                (int(self.level), ts),
            )
            conn.commit()
