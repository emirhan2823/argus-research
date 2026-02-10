"""SQLite event logger for ARGUS telemetry."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Optional

from src.core.types import TelemetryEvent


@dataclass
class EventLogger:
    sqlite_path: str

    def __post_init__(self) -> None:
        path = Path(self.sqlite_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.sqlite_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS telemetry_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_type TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    run_id TEXT NOT NULL,
                    inputs_hash TEXT,
                    asset_class TEXT,
                    reason TEXT,
                    payload_json TEXT NOT NULL
                )
                """
            )
            conn.commit()

    def log(
        self,
        event: TelemetryEvent,
        *,
        asset_class: str,
        reason: Optional[str] = None,
        payload: Optional[Mapping[str, Any]] = None,
    ) -> None:
        raw_payload = dict(payload or {})
        raw_payload.setdefault("event_type", event.event_type)
        raw_payload.setdefault("run_id", event.run_id)
        if reason is not None:
            raw_payload.setdefault("reason", reason)

        with sqlite3.connect(self.sqlite_path) as conn:
            conn.execute(
                """
                INSERT INTO telemetry_events(
                    event_type, timestamp, run_id, inputs_hash, asset_class, reason, payload_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event.event_type,
                    event.timestamp.isoformat(),
                    event.run_id,
                    event.inputs_hash,
                    asset_class,
                    reason,
                    json.dumps(raw_payload, sort_keys=True),
                ),
            )
            conn.commit()

    def count(self) -> int:
        with sqlite3.connect(self.sqlite_path) as conn:
            row = conn.execute("SELECT COUNT(*) FROM telemetry_events").fetchone()
        return int(row[0]) if row else 0

    def latest(self) -> dict[str, Any]:
        with sqlite3.connect(self.sqlite_path) as conn:
            row = conn.execute(
                """
                SELECT event_type, timestamp, run_id, inputs_hash, asset_class, reason, payload_json
                FROM telemetry_events
                ORDER BY id DESC
                LIMIT 1
                """
            ).fetchone()
        if row is None:
            return {}
        return {
            "event_type": row[0],
            "timestamp": row[1],
            "run_id": row[2],
            "inputs_hash": row[3],
            "asset_class": row[4],
            "reason": row[5],
            "payload": json.loads(row[6]),
        }
