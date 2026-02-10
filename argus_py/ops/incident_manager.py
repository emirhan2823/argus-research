from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional

import json


class IncidentSeverity(str, Enum):
    INFO = "INFO"
    WARN = "WARN"
    SEV2 = "SEV2"
    SEV1 = "SEV1"


class IncidentStatus(str, Enum):
    OPEN = "OPEN"
    MITIGATED = "MITIGATED"
    RESOLVED = "RESOLVED"


@dataclass
class IncidentEvent:
    ts_utc: str
    message: str
    data: Dict[str, object] = field(default_factory=dict)


@dataclass
class IncidentRecord:
    incident_id: str
    title: str
    severity: IncidentSeverity
    status: IncidentStatus
    opened_at_utc: str
    context: Dict[str, object] = field(default_factory=dict)
    recovery_checklist: List[str] = field(default_factory=list)
    events: List[IncidentEvent] = field(default_factory=list)
    resolved_at_utc: Optional[str] = None
    resolution_notes: Optional[str] = None


class IncidentManager:
    """Incident log + recovery enforcement for paper/live operations."""

    def __init__(self, incident_dir: Path = Path("reports/year2/incidents")) -> None:
        self.incident_dir = Path(incident_dir)
        self.incident_dir.mkdir(parents=True, exist_ok=True)

    def open_incident(
        self,
        title: str,
        severity: IncidentSeverity,
        *,
        context: Optional[Dict[str, object]] = None,
        recovery_checklist: Optional[List[str]] = None,
    ) -> IncidentRecord:
        incident_id = self._new_incident_id()
        now = self._utc_now()
        record = IncidentRecord(
            incident_id=incident_id,
            title=str(title),
            severity=severity,
            status=IncidentStatus.OPEN,
            opened_at_utc=now,
            context=dict(context or {}),
            recovery_checklist=list(recovery_checklist or []),
        )
        self._append_event(record, "Incident opened", context or {})
        self._save(record)
        return record

    def append_event(
        self,
        incident_id: str,
        message: str,
        data: Optional[Dict[str, object]] = None,
    ) -> IncidentRecord:
        record = self.load(incident_id)
        self._append_event(record, message, data or {})
        self._save(record)
        return record

    def enforce_recovery(self, incident_id: str, checklist_state: Dict[str, bool]) -> bool:
        record = self.load(incident_id)
        for item in record.recovery_checklist:
            if not bool(checklist_state.get(item, False)):
                self._append_event(record, "Recovery check failed", {"missing_item": item})
                self._save(record)
                return False
        self._append_event(record, "Recovery checklist passed", {})
        record.status = IncidentStatus.MITIGATED
        self._save(record)
        return True

    def resolve(
        self,
        incident_id: str,
        resolution_notes: str,
        *,
        checklist_state: Optional[Dict[str, bool]] = None,
        allow_incomplete_checklist: bool = False,
    ) -> IncidentRecord:
        record = self.load(incident_id)
        if record.recovery_checklist and not allow_incomplete_checklist:
            if checklist_state is None:
                raise ValueError("checklist_state is required for incidents with recovery checklist")
            if not self.enforce_recovery(incident_id, checklist_state):
                raise ValueError("recovery checklist is incomplete")
            record = self.load(incident_id)

        record.status = IncidentStatus.RESOLVED
        record.resolved_at_utc = self._utc_now()
        record.resolution_notes = str(resolution_notes)
        self._append_event(record, "Incident resolved", {"notes": record.resolution_notes})
        self._save(record)
        self._write_markdown(record)
        return record

    def load(self, incident_id: str) -> IncidentRecord:
        path = self._incident_path(incident_id)
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["severity"] = IncidentSeverity(payload["severity"])
        payload["status"] = IncidentStatus(payload["status"])
        payload["events"] = [IncidentEvent(**event) for event in payload.get("events", [])]
        return IncidentRecord(**payload)

    def _append_event(self, record: IncidentRecord, message: str, data: Dict[str, object]) -> None:
        record.events.append(IncidentEvent(ts_utc=self._utc_now(), message=str(message), data=dict(data)))

    def _save(self, record: IncidentRecord) -> None:
        payload = asdict(record)
        payload["severity"] = record.severity.value
        payload["status"] = record.status.value
        path = self._incident_path(record.incident_id)
        path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")

    def _write_markdown(self, record: IncidentRecord) -> None:
        lines = [
            f"# Incident {record.incident_id}",
            "",
            f"- Title: {record.title}",
            f"- Severity: {record.severity.value}",
            f"- Status: {record.status.value}",
            f"- Opened: {record.opened_at_utc}",
            f"- Resolved: {record.resolved_at_utc or '-'}",
            "",
            "## Events",
            "",
        ]
        for event in record.events:
            lines.append(f"- {event.ts_utc} | {event.message} | {event.data}")
        if record.resolution_notes:
            lines.extend(["", "## Resolution Notes", "", record.resolution_notes])

        md_path = self.incident_dir / f"{record.incident_id}.md"
        md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _new_incident_id(self) -> str:
        ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        suffix = 1
        while True:
            incident_id = f"INC-{ts}-{suffix:02d}"
            if not self._incident_path(incident_id).exists():
                return incident_id
            suffix += 1

    def _incident_path(self, incident_id: str) -> Path:
        return self.incident_dir / f"{incident_id}.json"

    @staticmethod
    def _utc_now() -> str:
        return datetime.now(timezone.utc).isoformat()


__all__ = [
    "IncidentManager",
    "IncidentRecord",
    "IncidentSeverity",
    "IncidentStatus",
    "IncidentEvent",
]
