from __future__ import annotations

from pathlib import Path

from argus_py.ops.advisory_cards import write_advisory_card


def test_write_advisory_card_creates_card_and_index(tmp_path: Path) -> None:
    out = write_advisory_card(
        run_dir=tmp_path,
        symbol="BTCUSDT",
        side="BUY",
        entry_price=100.0,
        stop_price=98.0,
        take_profit_levels=[102.0, 104.0],
        rationale="test rationale",
        strategy_id="COUNCIL_BASELINE",
        asset_class="crypto",
        venue_id="sim",
        bar_timestamp=1_700_000_000.0,
    )
    assert out.exists()
    index_path = tmp_path / "advisory_cards" / "_index.md"
    assert index_path.exists()
    text = out.read_text(encoding="utf-8")
    assert "BTCUSDT" in text
    assert "COUNCIL_BASELINE" in text
