from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import json


@dataclass(frozen=True)
class MacroEvent:
    name: str
    start_ts: float
    end_ts: float
    action: str
    severity: str
    asset_classes: tuple[str, ...]
    symbols: tuple[str, ...]

    def is_active(self, ts: float) -> bool:
        return self.start_ts <= float(ts) <= self.end_ts

    def matches_asset(self, asset_class: str) -> bool:
        acl = str(asset_class or "").strip().lower()
        if not self.asset_classes:
            return True
        return "*" in self.asset_classes or acl in self.asset_classes

    def matches_symbol(self, symbol: str) -> bool:
        sym = str(symbol or "").strip().upper()
        if not self.symbols:
            return True
        return "*" in self.symbols or sym in self.symbols


class MacroEventGuard:
    """
    Blocking guard for high-impact macro windows.

    Input file format examples:
    - {"events": [{...}]}
    - [{...}, {...}]
    Fields:
      name, start_ts/end_ts (unix) or start_iso/end_iso,
      action (BLOCK_NEW_ENTRY default), severity, asset_classes, symbols.
    """

    def __init__(self, events_file: Path | str | None = None) -> None:
        self.events_file = Path(events_file) if events_file else None
        self._events: list[MacroEvent] = []
        self._last_mtime: float | None = None
        self.reload_if_needed()

    def reload_if_needed(self) -> None:
        if self.events_file is None:
            self._events = []
            self._last_mtime = None
            return
        if not self.events_file.exists():
            self._events = []
            self._last_mtime = None
            return
        mtime = float(self.events_file.stat().st_mtime)
        if self._last_mtime is not None and mtime <= self._last_mtime:
            return
        self._events = self._load_events(self.events_file)
        self._last_mtime = mtime

    def active_events(self, ts: float, asset_class: str, symbol: str) -> list[MacroEvent]:
        self.reload_if_needed()
        out: list[MacroEvent] = []
        for event in self._events:
            if not event.is_active(ts):
                continue
            if not event.matches_asset(asset_class):
                continue
            if not event.matches_symbol(symbol):
                continue
            out.append(event)
        return out

    def should_block_entry(self, ts: float, asset_class: str, symbol: str) -> tuple[bool, str]:
        active = self.active_events(ts=ts, asset_class=asset_class, symbol=symbol)
        if not active:
            return False, "no_active_macro_event"
        for event in active:
            action = str(event.action or "").upper()
            if action in {"BLOCK_NEW_ENTRY", "HALT_ENTRY"}:
                detail = (
                    f"{event.name} [{event.severity}] "
                    f"{datetime.fromtimestamp(event.start_ts, tz=timezone.utc).isoformat()} -> "
                    f"{datetime.fromtimestamp(event.end_ts, tz=timezone.utc).isoformat()}"
                )
                return True, detail
        return False, "active_macro_event_no_block_action"

    def _load_events(self, path: Path) -> list[MacroEvent]:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return []
        raw_events: Iterable[Dict[str, Any]]
        if isinstance(payload, dict):
            events_obj = payload.get("events", [])
            raw_events = events_obj if isinstance(events_obj, list) else []
        elif isinstance(payload, list):
            raw_events = payload
        else:
            raw_events = []
        out: list[MacroEvent] = []
        for item in raw_events:
            if not isinstance(item, dict):
                continue
            event = self._to_event(item)
            if event is not None:
                out.append(event)
        out.sort(key=lambda x: (x.start_ts, x.end_ts, x.name))
        return out

    @staticmethod
    def _to_event(item: Dict[str, Any]) -> Optional[MacroEvent]:
        name = str(item.get("name") or item.get("event") or "UNNAMED_EVENT").strip()
        start_ts = MacroEventGuard._parse_ts(item.get("start_ts"), item.get("start_iso"))
        end_ts = MacroEventGuard._parse_ts(item.get("end_ts"), item.get("end_iso"))
        if start_ts is None or end_ts is None or end_ts < start_ts:
            return None
        action = str(item.get("action") or "BLOCK_NEW_ENTRY").strip().upper()
        severity = str(item.get("severity") or "MEDIUM").strip().upper()
        acl = MacroEventGuard._normalize_list(item.get("asset_classes"), upper=False)
        syms = MacroEventGuard._normalize_list(item.get("symbols"), upper=True)
        return MacroEvent(
            name=name,
            start_ts=start_ts,
            end_ts=end_ts,
            action=action,
            severity=severity,
            asset_classes=tuple(acl),
            symbols=tuple(syms),
        )

    @staticmethod
    def _normalize_list(value: Any, upper: bool) -> list[str]:
        if value is None:
            return []
        items: list[str] = []
        if isinstance(value, str):
            chunks = [x.strip() for x in value.split(",")]
            items = [x for x in chunks if x]
        elif isinstance(value, list):
            items = [str(x).strip() for x in value if str(x).strip()]
        out: list[str] = []
        for item in items:
            out.append(item.upper() if upper else item.lower())
        return out

    @staticmethod
    def _parse_ts(raw_ts: Any, raw_iso: Any) -> Optional[float]:
        if raw_ts is not None:
            try:
                ts = float(raw_ts)
                if ts > 1_000_000_000_000:
                    ts /= 1000.0
                return ts
            except Exception:
                pass
        if raw_iso is not None:
            try:
                dt = datetime.fromisoformat(str(raw_iso).replace("Z", "+00:00"))
                return dt.timestamp()
            except Exception:
                return None
        return None


__all__ = ["MacroEvent", "MacroEventGuard"]
