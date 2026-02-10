from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

import json


@dataclass(frozen=True)
class StrategyDisableState:
    disabled: bool
    reason: str
    source: str


class StrategyRegistryGuard:
    """
    Reads strategy disable state from one or more governance files.

    Supported schemas:
    1) strategy_registry.json:
       {"strategies": {"ID": {"enabled": false, "disable_reason": "..."}}}
    2) disabled_strategies.json:
       {"disabled_strategies": [{"strategy_id": "ID", "reason": "..."}]}
    """

    def __init__(self, paths: Iterable[Path | str]) -> None:
        self.paths = [Path(p) for p in paths]
        self._mtimes: Dict[str, float] = {}
        self._disabled_map: Dict[str, StrategyDisableState] = {}
        self.reload_if_needed(force=True)

    def reload_if_needed(self, force: bool = False) -> None:
        changed = force
        for path in self.paths:
            key = str(path)
            if not path.exists():
                if key in self._mtimes:
                    changed = True
                    self._mtimes.pop(key, None)
                continue
            mtime = float(path.stat().st_mtime)
            if self._mtimes.get(key) != mtime:
                changed = True
                self._mtimes[key] = mtime
        if not changed:
            return
        merged: Dict[str, StrategyDisableState] = {}
        for path in self.paths:
            if not path.exists():
                continue
            for sid, state in self._parse_file(path).items():
                merged[sid] = state
        self._disabled_map = merged

    def is_disabled(self, strategy_id: str) -> tuple[bool, str]:
        self.reload_if_needed()
        sid = str(strategy_id or "").strip().upper()
        if not sid:
            return False, "empty_strategy_id"
        state = self._disabled_map.get(sid)
        if state is None:
            return False, "enabled_or_not_listed"
        return bool(state.disabled), state.reason

    def snapshot(self) -> Dict[str, Dict[str, str]]:
        self.reload_if_needed()
        out: Dict[str, Dict[str, str]] = {}
        for sid, state in self._disabled_map.items():
            out[sid] = {"reason": state.reason, "source": state.source}
        return out

    def _parse_file(self, path: Path) -> Dict[str, StrategyDisableState]:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}

        out: Dict[str, StrategyDisableState] = {}
        source = str(path)

        if isinstance(payload, dict):
            strategies = payload.get("strategies")
            if isinstance(strategies, dict):
                for sid_raw, row in strategies.items():
                    sid = str(sid_raw).strip().upper()
                    if not sid or not isinstance(row, dict):
                        continue
                    enabled = bool(row.get("enabled", True))
                    if enabled:
                        continue
                    reason = str(row.get("disable_reason") or "disabled_by_registry").strip()
                    out[sid] = StrategyDisableState(disabled=True, reason=reason, source=source)

            disabled_arr = payload.get("disabled_strategies")
            if isinstance(disabled_arr, list):
                for row in disabled_arr:
                    if not isinstance(row, dict):
                        continue
                    sid = str(row.get("strategy_id") or "").strip().upper()
                    if not sid:
                        continue
                    reason = str(row.get("reason") or "disabled_by_governance").strip()
                    out[sid] = StrategyDisableState(disabled=True, reason=reason, source=source)
        return out


__all__ = ["StrategyRegistryGuard", "StrategyDisableState"]
