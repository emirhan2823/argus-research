import csv
import json
import math
import os
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from argus_py.telemetry.schemas import (
    DECISION_DIRECTIONS,
    DECISION_HEADERS,
    DECISION_REGIMES,
    DECISION_VERDICTS,
    REJECT_HEADERS,
    TRADE_EVENTS,
    TRADE_HEADERS,
)


@dataclass
class DecisionRow:
    timestamp: int
    bar_ts: int
    symbol: str
    verdict: str      # GO|WAIT|EXIT|SKIP
    direction: str    # LONG|SHORT|FLAT
    score: float
    adx: float
    exp_move: float
    regime: str       # TREND|CHOP|UNCERTAIN
    position_state: str


@dataclass
class TradeRow:
    timestamp: int
    symbol: str
    event: str        # OPEN|CLOSE|REJECTED
    side: str
    price: float
    quantity: float
    commission: float
    pnl: float
    position_id: str
    reject_reason: str  # Required if event=REJECTED


@dataclass
class RejectRow:
    timestamp: int
    bar_ts: int
    symbol: str
    code: str         # REJECT_* enum
    detail: str
    position_state: str
    risk_level: str


class TelemetryWriter:
    def __init__(self, run_dir: Path) -> None:
        self.run_dir = Path(run_dir)
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

        self._decisions_path = self.run_dir / "decisions.csv"
        self._trades_path = self.run_dir / "trades.csv"
        self._rejects_path = self.run_dir / "rejects.csv"
        self._heartbeat_path = self.run_dir / "heartbeat.json"

        self._ensure_csv(self._decisions_path, DECISION_HEADERS)
        self._ensure_csv(self._trades_path, TRADE_HEADERS)
        self._ensure_csv(self._rejects_path, REJECT_HEADERS)

        self._decisions_fh = self._decisions_path.open("a", newline="", encoding="utf-8")
        self._trades_fh = self._trades_path.open("a", newline="", encoding="utf-8")
        self._rejects_fh = self._rejects_path.open("a", newline="", encoding="utf-8")

        self._decisions_writer = csv.writer(self._decisions_fh)
        self._trades_writer = csv.writer(self._trades_fh)
        self._rejects_writer = csv.writer(self._rejects_fh)

    def _ensure_csv(self, path: Path, headers: tuple[str, ...]) -> None:
        if path.exists():
            return
        with path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(headers)

    @staticmethod
    def _is_int(value: object) -> bool:
        return isinstance(value, int) and not isinstance(value, bool)

    @staticmethod
    def _is_number(value: object) -> bool:
        if isinstance(value, bool):
            return False
        if not isinstance(value, (int, float)):
            return False
        return math.isfinite(float(value))

    @staticmethod
    def _required_text(value: Optional[str], field_name: str) -> str:
        if not isinstance(value, str):
            raise ValueError(f"{field_name} must be str")
        text = value.strip()
        if not text:
            raise ValueError(f"{field_name} must be non-empty")
        return text

    def _validate_decision(self, row: DecisionRow) -> None:
        if not self._is_int(row.timestamp):
            raise ValueError("timestamp must be int")
        if not self._is_int(row.bar_ts):
            raise ValueError("bar_ts must be int")
        self._required_text(row.symbol, "symbol")
        if row.verdict not in DECISION_VERDICTS:
            raise ValueError(f"invalid verdict: {row.verdict}")
        if row.direction not in DECISION_DIRECTIONS:
            raise ValueError(f"invalid direction: {row.direction}")
        if not self._is_number(row.score):
            raise ValueError("score must be numeric")
        if not self._is_number(row.adx):
            raise ValueError("adx must be numeric")
        if not self._is_number(row.exp_move):
            raise ValueError("exp_move must be numeric")
        if row.regime not in DECISION_REGIMES:
            raise ValueError(f"invalid regime: {row.regime}")
        self._required_text(row.position_state, "position_state")

    def _validate_trade(self, row: TradeRow) -> None:
        if not self._is_int(row.timestamp):
            raise ValueError("timestamp must be int")
        self._required_text(row.symbol, "symbol")
        if row.event not in TRADE_EVENTS:
            raise ValueError(f"invalid event: {row.event}")
        self._required_text(row.side, "side")
        if not self._is_number(row.price):
            raise ValueError("price must be numeric")
        if not self._is_number(row.quantity):
            raise ValueError("quantity must be numeric")
        if not self._is_number(row.commission):
            raise ValueError("commission must be numeric")
        if not self._is_number(row.pnl):
            raise ValueError("pnl must be numeric")
        self._required_text(row.position_id, "position_id")
        if row.event == "REJECTED":
            self._required_text(row.reject_reason, "reject_reason")

    def _validate_reject(self, row: RejectRow) -> None:
        if not self._is_int(row.timestamp):
            raise ValueError("timestamp must be int")
        if not self._is_int(row.bar_ts):
            raise ValueError("bar_ts must be int")
        self._required_text(row.symbol, "symbol")
        code = self._required_text(row.code, "code")
        if not code.startswith("REJECT_"):
            raise ValueError("code must start with REJECT_")
        self._required_text(row.detail, "detail")
        self._required_text(row.position_state, "position_state")
        self._required_text(row.risk_level, "risk_level")

    def write_decision(self, row: DecisionRow) -> None:
        self._validate_decision(row)
        with self._lock:
            self._decisions_writer.writerow(
                [
                    row.timestamp,
                    row.bar_ts,
                    row.symbol,
                    row.verdict,
                    row.direction,
                    row.score,
                    row.adx,
                    row.exp_move,
                    row.regime,
                    row.position_state,
                ]
            )
            self._decisions_fh.flush()

    def write_trade(self, row: TradeRow) -> None:
        self._validate_trade(row)
        with self._lock:
            self._trades_writer.writerow(
                [
                    row.timestamp,
                    row.symbol,
                    row.event,
                    row.side,
                    row.price,
                    row.quantity,
                    row.commission,
                    row.pnl,
                    row.position_id,
                    row.reject_reason,
                ]
            )
            self._trades_fh.flush()

    def write_reject(self, row: RejectRow) -> None:
        self._validate_reject(row)
        with self._lock:
            self._rejects_writer.writerow(
                [
                    row.timestamp,
                    row.bar_ts,
                    row.symbol,
                    row.code,
                    row.detail,
                    row.position_state,
                    row.risk_level,
                ]
            )
            self._rejects_fh.flush()

    def update_heartbeat(self, state: dict) -> None:
        if not isinstance(state, dict):
            raise ValueError("state must be dict")
        tmp_path = self.run_dir / "heartbeat.json.tmp"
        with self._lock:
            payload = json.dumps(state, ensure_ascii=True, sort_keys=True)
            with tmp_path.open("w", encoding="utf-8") as f:
                f.write(payload)
                f.flush()
                os.fsync(f.fileno())
            replaced = False
            for attempt in range(10):
                try:
                    os.replace(tmp_path, self._heartbeat_path)
                    replaced = True
                    break
                except PermissionError:
                    if attempt == 9:
                        break
                    time.sleep(0.002 * (attempt + 1))

            if not replaced:
                if tmp_path.exists():
                    tmp_path.unlink()

    def flush(self) -> None:
        with self._lock:
            self._decisions_fh.flush()
            self._trades_fh.flush()
            self._rejects_fh.flush()
            os.fsync(self._decisions_fh.fileno())
            os.fsync(self._trades_fh.fileno())
            os.fsync(self._rejects_fh.fileno())

    def close(self) -> None:
        with self._lock:
            self._decisions_fh.close()
            self._trades_fh.close()
            self._rejects_fh.close()

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            pass
