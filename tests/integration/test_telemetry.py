from __future__ import annotations

from datetime import datetime, timezone

from src.core.types import TelemetryEvent
from src.telemetry.event_logger import EventLogger


def test_event_logger_writes_and_reads_latest(tmp_path) -> None:
    db_path = tmp_path / "telemetry.db"
    logger = EventLogger(sqlite_path=str(db_path))

    evt = TelemetryEvent(
        event_type="signal_rejected",
        timestamp=datetime.now(timezone.utc),
        run_id="run-1",
        inputs_hash="abc123",
    )
    payload = {"gate_number": 5, "features_snapshot": {"symbol": "BTCUSDT"}}
    logger.log(evt, asset_class="crypto", reason="confidence_below_threshold", payload=payload)

    assert logger.count() == 1
    latest = logger.latest()
    assert latest["event_type"] == "signal_rejected"
    assert latest["asset_class"] == "crypto"
    assert latest["payload"]["features_snapshot"]["symbol"] == "BTCUSDT"
