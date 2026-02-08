from __future__ import annotations

import json
import threading
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class AuditEvent:
    timestamp: float
    action: str
    actor: str
    status: str
    detail: Optional[Dict[str, Any]] = None


class AuditLogger:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def log(
        self,
        action: str,
        actor: str,
        status: str,
        detail: Optional[Dict[str, Any]] = None,
    ) -> AuditEvent:
        event = AuditEvent(
            timestamp=time.time(),
            action=action,
            actor=actor,
            status=status,
            detail=detail,
        )
        with self._lock:
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(asdict(event), ensure_ascii=True) + "\n")
        return event

    def read_recent(self, limit: int = 100) -> List[AuditEvent]:
        if not self.path.exists():
            return []

        with self.path.open("r", encoding="utf-8") as handle:
            lines = handle.readlines()

        out: List[AuditEvent] = []
        for line in lines[-limit:]:
            row = json.loads(line)
            out.append(
                AuditEvent(
                    timestamp=float(row.get("timestamp", 0.0)),
                    action=str(row.get("action", "")),
                    actor=str(row.get("actor", "")),
                    status=str(row.get("status", "")),
                    detail=row.get("detail"),
                )
            )
        return out
