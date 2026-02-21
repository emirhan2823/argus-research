import csv
import json
import os
import threading
from pathlib import Path
import sys

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from argus_py.telemetry.writer import (
    DecisionRow,
    RejectRow,
    TelemetryWriter,
    TradeRow,
)


def _read_rows(path: Path):
    with path.open("r", newline="", encoding="utf-8") as f:
        return list(csv.reader(f))


@pytest.fixture
def writer(tmp_path):
    w = TelemetryWriter(tmp_path)
    yield w
    w.close()


def test_init_creates_csv_files_with_headers(tmp_path):
    w = TelemetryWriter(tmp_path)
    w.close()

    decisions = _read_rows(tmp_path / "decisions.csv")
    trades = _read_rows(tmp_path / "trades.csv")
    rejects = _read_rows(tmp_path / "rejects.csv")

    assert decisions[0] == [
        "timestamp",
        "bar_ts",
        "symbol",
        "verdict",
        "direction",
        "score",
        "adx",
        "exp_move",
        "regime",
        "position_state",
    ]
    assert trades[0] == [
        "timestamp",
        "symbol",
        "event",
        "side",
        "price",
        "quantity",
        "commission",
        "pnl",
        "position_id",
        "reject_reason",
    ]
    assert rejects[0] == [
        "timestamp",
        "bar_ts",
        "symbol",
        "code",
        "detail",
        "position_state",
        "risk_level",
    ]


def test_write_decision_appends_valid_row(writer):
    row = DecisionRow(
        timestamp=100,
        bar_ts=99,
        symbol="BTCUSDT",
        verdict="GO",
        direction="LONG",
        score=0.9,
        adx=25.1,
        exp_move=12.3,
        regime="TREND",
        position_state="FLAT",
    )
    writer.write_decision(row)
    rows = _read_rows(writer.run_dir / "decisions.csv")
    assert len(rows) == 2
    assert rows[1][2] == "BTCUSDT"
    assert rows[1][3] == "GO"


def test_decision_invalid_verdict_raises(writer):
    with pytest.raises(ValueError):
        writer.write_decision(
            DecisionRow(
                timestamp=100,
                bar_ts=99,
                symbol="BTCUSDT",
                verdict="BLOCK",
                direction="LONG",
                score=0.2,
                adx=1.0,
                exp_move=2.0,
                regime="TREND",
                position_state="FLAT",
            )
        )


def test_decision_invalid_regime_raises(writer):
    with pytest.raises(ValueError):
        writer.write_decision(
            DecisionRow(
                timestamp=100,
                bar_ts=99,
                symbol="BTCUSDT",
                verdict="WAIT",
                direction="FLAT",
                score=0.2,
                adx=1.0,
                exp_move=2.0,
                regime="SIDEWAYS",
                position_state="FLAT",
            )
        )


def test_write_trade_rejected_without_reason_raises_value_error(writer):
    with pytest.raises(ValueError):
        writer.write_trade(
            TradeRow(
                timestamp=100,
                symbol="BTCUSDT",
                event="REJECTED",
                side="BUY",
                price=100.0,
                quantity=1.0,
                commission=0.1,
                pnl=0.0,
                position_id="p-1",
                reject_reason="",
            )
        )


def test_write_trade_rejected_with_reason_is_valid(writer):
    writer.write_trade(
        TradeRow(
            timestamp=100,
            symbol="BTCUSDT",
            event="REJECTED",
            side="BUY",
            price=100.0,
            quantity=1.0,
            commission=0.1,
            pnl=0.0,
            position_id="p-1",
            reject_reason="REJECT_RISK_CAP",
        )
    )
    rows = _read_rows(writer.run_dir / "trades.csv")
    assert len(rows) == 2
    assert rows[1][2] == "REJECTED"
    assert rows[1][9] == "REJECT_RISK_CAP"


def test_trade_invalid_event_raises(writer):
    with pytest.raises(ValueError):
        writer.write_trade(
            TradeRow(
                timestamp=100,
                symbol="BTCUSDT",
                event="PARTIAL",
                side="BUY",
                price=100.0,
                quantity=1.0,
                commission=0.1,
                pnl=0.0,
                position_id="p-1",
                reject_reason="",
            )
        )


def test_reject_invalid_code_raises(writer):
    with pytest.raises(ValueError):
        writer.write_reject(
            RejectRow(
                timestamp=100,
                bar_ts=99,
                symbol="BTCUSDT",
                code="BAD_CODE",
                detail="invalid",
                position_state="FLAT",
                risk_level="NORMAL",
            )
        )


def test_update_heartbeat_uses_atomic_replace(writer, monkeypatch):
    calls = []
    original_replace = writer.__class__.__module__
    assert original_replace == "argus_py.telemetry.writer"

    import argus_py.telemetry.writer as writer_mod

    real_replace = writer_mod.os.replace

    def fake_replace(src, dst):
        calls.append((str(src), str(dst)))
        return real_replace(src, dst)

    monkeypatch.setattr(writer_mod.os, "replace", fake_replace)

    writer.update_heartbeat({"risk_level": "NORMAL", "seq": 1})
    hb_path = writer.run_dir / "heartbeat.json"
    with hb_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    assert data["risk_level"] == "NORMAL"
    assert len(calls) == 1
    assert calls[0][0].endswith("heartbeat.json.tmp")
    assert calls[0][1].endswith("heartbeat.json")


def test_flush_persists_rows(writer):
    writer.write_decision(
        DecisionRow(
            timestamp=1,
            bar_ts=1,
            symbol="BTCUSDT",
            verdict="WAIT",
            direction="FLAT",
            score=0.1,
            adx=10.0,
            exp_move=1.0,
            regime="CHOP",
            position_state="FLAT",
        )
    )
    writer.flush()
    rows = _read_rows(writer.run_dir / "decisions.csv")
    assert len(rows) == 2


def test_thread_safe_concurrent_decision_writes(writer):
    total_threads = 8
    per_thread = 50

    def worker(tid: int):
        for i in range(per_thread):
            writer.write_decision(
                DecisionRow(
                    timestamp=tid * 100000 + i,
                    bar_ts=tid * 100000 + i,
                    symbol="BTCUSDT",
                    verdict="WAIT",
                    direction="FLAT",
                    score=0.01,
                    adx=1.0,
                    exp_move=1.0,
                    regime="CHOP",
                    position_state="FLAT",
                )
            )

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(total_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    writer.flush()
    rows = _read_rows(writer.run_dir / "decisions.csv")
    assert len(rows) == 1 + total_threads * per_thread


def test_thread_safe_mixed_trade_and_reject_writes(writer):
    total_threads = 4
    per_thread = 40

    def trade_worker(tid: int):
        for i in range(per_thread):
            writer.write_trade(
                TradeRow(
                    timestamp=tid * 10000 + i,
                    symbol="BTCUSDT",
                    event="OPEN",
                    side="BUY",
                    price=100.0 + i,
                    quantity=0.01,
                    commission=0.001,
                    pnl=0.0,
                    position_id=f"p-{tid}-{i}",
                    reject_reason="",
                )
            )

    def reject_worker(tid: int):
        for i in range(per_thread):
            writer.write_reject(
                RejectRow(
                    timestamp=tid * 10000 + i,
                    bar_ts=tid * 10000 + i,
                    symbol="BTCUSDT",
                    code="REJECT_TEST",
                    detail="test",
                    position_state="FLAT",
                    risk_level="NORMAL",
                )
            )

    threads = []
    for i in range(total_threads):
        threads.append(threading.Thread(target=trade_worker, args=(i,)))
        threads.append(threading.Thread(target=reject_worker, args=(i,)))

    for t in threads:
        t.start()
    for t in threads:
        t.join()

    writer.flush()
    trade_rows = _read_rows(writer.run_dir / "trades.csv")
    reject_rows = _read_rows(writer.run_dir / "rejects.csv")
    assert len(trade_rows) == 1 + total_threads * per_thread
    assert len(reject_rows) == 1 + total_threads * per_thread


def test_concurrent_heartbeat_updates_never_corrupt_json(writer):
    parse_errors = []
    stop = threading.Event()

    def updater(tid: int):
        for i in range(80):
            writer.update_heartbeat({"thread": tid, "seq": i, "risk_level": "NORMAL"})
        stop.set()

    def reader():
        hb = writer.run_dir / "heartbeat.json"
        while not stop.is_set():
            if not hb.exists():
                continue
            try:
                with hb.open("r", encoding="utf-8") as f:
                    json.load(f)
            except Exception as e:
                parse_errors.append(str(e))

    threads = [threading.Thread(target=updater, args=(i,)) for i in range(3)]
    r = threading.Thread(target=reader)
    r.start()
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    stop.set()
    r.join()

    if os.name == "nt":
        parse_errors = [
            err for err in parse_errors
            if "Permission denied" not in err and "WinError 5" not in err
        ]
    assert parse_errors == []
    with (writer.run_dir / "heartbeat.json").open("r", encoding="utf-8") as f:
        payload = json.load(f)
    assert "risk_level" in payload


def test_schema_validation_reject_row_type_errors(writer):
    with pytest.raises(ValueError):
        writer.write_reject(
            RejectRow(
                timestamp=1,
                bar_ts="2",  # type: ignore[arg-type]
                symbol="BTCUSDT",
                code="REJECT_TEST",
                detail="bad",
                position_state="FLAT",
                risk_level="NORMAL",
            )
        )
