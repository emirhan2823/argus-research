"""Backtest report rendering."""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any


def write_report(path: str, *, title: str, sections: dict[str, Any]) -> str:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"# {title}", ""]
    for name, payload in sections.items():
        lines.append(f"## {name}")
        lines.append("")
        if hasattr(payload, "__dataclass_fields__"):
            data = asdict(payload)
        else:
            data = payload
        if isinstance(data, dict):
            for k, v in data.items():
                lines.append(f"- {k}: {v}")
        else:
            lines.append(str(data))
        lines.append("")
    content = "\n".join(lines).strip() + "\n"
    p.write_text(content, encoding="utf-8")
    return str(p)
