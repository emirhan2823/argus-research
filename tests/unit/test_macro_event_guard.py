from __future__ import annotations

import json
from pathlib import Path

from argus_py.ops.macro_event_guard import MacroEventGuard


def test_macro_event_guard_blocks_active_window(tmp_path: Path) -> None:
    events = {
        "events": [
            {
                "name": "FOMC",
                "start_ts": 1_700_000_000,
                "end_ts": 1_700_000_600,
                "action": "BLOCK_NEW_ENTRY",
                "asset_classes": ["crypto", "stock"],
                "symbols": ["BTCUSDT", "AAPL"],
                "severity": "HIGH",
            }
        ]
    }
    path = tmp_path / "macro_events.json"
    path.write_text(json.dumps(events), encoding="utf-8")

    guard = MacroEventGuard(path)
    blocked, reason = guard.should_block_entry(
        ts=1_700_000_100,
        asset_class="crypto",
        symbol="BTCUSDT",
    )
    assert blocked is True
    assert "FOMC" in reason


def test_macro_event_guard_skips_non_matching_asset_or_time(tmp_path: Path) -> None:
    events = [
        {
            "name": "NFP",
            "start_iso": "2026-01-01T12:00:00Z",
            "end_iso": "2026-01-01T12:30:00Z",
            "action": "BLOCK_NEW_ENTRY",
            "asset_classes": ["stock"],
            "symbols": ["*"],
        }
    ]
    path = tmp_path / "macro_events.json"
    path.write_text(json.dumps(events), encoding="utf-8")

    guard = MacroEventGuard(path)
    blocked_a, _ = guard.should_block_entry(
        ts=1_767_268_000,  # 2026-01-01 around noon UTC
        asset_class="crypto",
        symbol="BTCUSDT",
    )
    blocked_b, _ = guard.should_block_entry(
        ts=1_767_200_000,  # out of event range
        asset_class="stock",
        symbol="AAPL",
    )
    assert blocked_a is False
    assert blocked_b is False
