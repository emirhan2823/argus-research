import csv
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional


def _parse_ts(value: str) -> float:
    value = (value or "").strip()
    if not value:
        raise ValueError("timestamp is empty")
    if value.isdigit():
        ts = float(value)
        # ms -> s
        if ts > 1_000_000_000_000:
            ts /= 1000.0
        return ts
    # ISO time fallback: 2026-02-07T12:34:56 or with trailing Z.
    iso = value.replace("Z", "+00:00")
    return datetime.fromisoformat(iso).timestamp()


def _normalize_direction(value: str) -> str:
    raw = (value or "").strip().upper()
    if raw in {"BUY", "LONG", "BULL"}:
        return "BUY"
    if raw in {"SELL", "SHORT", "BEAR"}:
        return "SELL"
    return "NEUTRAL"


@dataclass(frozen=True)
class ExternalSignal:
    timestamp: float
    symbol: str
    source: str
    direction: str
    confidence: float
    note: str = ""


class ExternalSignalProvider:
    def __init__(self, signals: List[ExternalSignal]):
        self._signals = sorted(signals, key=lambda s: s.timestamp)

    @property
    def size(self) -> int:
        return len(self._signals)

    @classmethod
    def from_csv(cls, path: str, symbol: Optional[str] = None) -> "ExternalSignalProvider":
        wanted_symbol = symbol.upper() if symbol else None
        parsed: List[ExternalSignal] = []
        with open(path, "r") as f:
            reader = csv.DictReader(f)
            for row in reader:
                row_symbol = (row.get("symbol") or "").strip().upper()
                if wanted_symbol and row_symbol and row_symbol != wanted_symbol:
                    continue
                ts = _parse_ts(row.get("timestamp", ""))
                direction = _normalize_direction(row.get("direction", ""))
                confidence = float(row.get("confidence", 0.0))
                confidence = max(0.0, min(1.0, confidence))
                source = (row.get("source") or "external").strip() or "external"
                note = (row.get("note") or "").strip()
                parsed.append(
                    ExternalSignal(
                        timestamp=ts,
                        symbol=row_symbol or (wanted_symbol or ""),
                        source=source,
                        direction=direction,
                        confidence=confidence,
                        note=note,
                    )
                )
        return cls(parsed)

    def latest_for(self, bar_ts: float, max_age_sec: int) -> Optional[ExternalSignal]:
        if not self._signals:
            return None
        # Linear scan is enough for current dataset size.
        best: Optional[ExternalSignal] = None
        for sig in self._signals:
            if sig.timestamp <= bar_ts:
                best = sig
            else:
                break
        if best is None:
            return None
        age = bar_ts - best.timestamp
        if age < 0:
            return None
        if max_age_sec >= 0 and age > max_age_sec:
            return None
        return best
