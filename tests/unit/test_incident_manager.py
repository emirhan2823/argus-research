from __future__ import annotations

from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from argus_py.ops.incident_manager import IncidentManager, IncidentSeverity, IncidentStatus


def test_incident_manager_creates_and_resolves_incident(tmp_path) -> None:
    mgr = IncidentManager(tmp_path / "incidents")

    record = mgr.open_incident(
        title="Telemetry outage",
        severity=IncidentSeverity.SEV2,
        context={"service": "paper_daemon"},
        recovery_checklist=["heartbeat_restored", "metrics_restored"],
    )
    mgr.append_event(record.incident_id, "Heartbeat restarted", {"ok": True})

    resolved = mgr.resolve(
        record.incident_id,
        "Recovered after restart",
        checklist_state={"heartbeat_restored": True, "metrics_restored": True},
    )

    assert resolved.status == IncidentStatus.RESOLVED
    assert (tmp_path / "incidents" / f"{record.incident_id}.json").exists()
    assert (tmp_path / "incidents" / f"{record.incident_id}.md").exists()


def test_incident_manager_blocks_resolution_when_checklist_incomplete(tmp_path) -> None:
    mgr = IncidentManager(tmp_path / "inc")
    rec = mgr.open_incident(
        title="Risk anomaly",
        severity=IncidentSeverity.SEV1,
        recovery_checklist=["risk_ok", "fills_ok"],
    )

    try:
        mgr.resolve(rec.incident_id, "Attempted close", checklist_state={"risk_ok": True, "fills_ok": False})
    except ValueError as exc:
        assert "incomplete" in str(exc)
    else:
        raise AssertionError("expected ValueError")
