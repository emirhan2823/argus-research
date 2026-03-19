from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional


def write_advisory_card(
    *,
    run_dir: Path,
    symbol: str,
    side: str,
    entry_price: float,
    stop_price: Optional[float],
    take_profit_levels: Iterable[float],
    rationale: str,
    strategy_id: str,
    asset_class: str,
    venue_id: str,
    bar_timestamp: float,
    quality_score: Optional[float] = None,
    quality_grade: Optional[str] = None,
) -> Path:
    cards_dir = Path(run_dir) / "advisory_cards"
    cards_dir.mkdir(parents=True, exist_ok=True)

    ts = datetime.fromtimestamp(float(bar_timestamp), tz=timezone.utc)
    stamp = ts.strftime("%Y%m%d_%H%M%S")
    file_name = f"{stamp}_{symbol}_{side}".replace("/", "_").replace(" ", "_").upper() + ".md"
    out = cards_dir / file_name

    tp_levels = [float(x) for x in take_profit_levels if x is not None]
    tp_levels.sort(reverse=str(side).upper() == "SELL")

    lines = [
        f"# Advisory Trade Card — {symbol}",
        "",
        f"- Timestamp (UTC): {ts.isoformat()}",
        f"- Strategy: `{strategy_id}`",
        f"- Asset Class: `{asset_class}`",
        f"- Venue: `{venue_id}`",
        f"- Trade Quality: `{quality_grade}` ({float(quality_score):.3f})"
        if quality_score is not None
        else "- Trade Quality: `N/A`",
        "",
        "## Entry",
        "",
        f"- Side: **{str(side).upper()}**",
        f"- Suggested Entry: `{float(entry_price):.6f}`",
        "",
        "## Risk Plan",
        "",
        f"- Stop Loss: `{float(stop_price):.6f}`" if stop_price is not None else "- Stop Loss: `N/A`",
    ]
    if tp_levels:
        lines.append("- Take Profit Levels:")
        for i, level in enumerate(tp_levels, start=1):
            lines.append(f"  TP{i}: `{level:.6f}`")
    else:
        lines.append("- Take Profit Levels: `N/A`")

    lines.extend(
        [
            "",
            "## Rationale",
            "",
            f"- {rationale or 'No rationale provided.'}",
            "",
            "## Execution Note",
            "",
            "- This card is advisory; user executes manually.",
        ]
    )
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")

    index_path = cards_dir / "_index.md"
    row = f"- `{ts.isoformat()}` | `{symbol}` | `{str(side).upper()}` | `{strategy_id}` | `{out.name}`"
    if not index_path.exists():
        index_path.write_text(
            "# Advisory Cards Index\n\n- `timestamp` | `symbol` | `side` | `strategy` | `file`\n",
            encoding="utf-8",
        )
    with index_path.open("a", encoding="utf-8") as f:
        f.write(row + "\n")

    return out


__all__ = ["write_advisory_card"]
