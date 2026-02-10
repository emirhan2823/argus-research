from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import json


@dataclass(frozen=True)
class WatchdogStatus:
    generated_at_utc: str
    run_dir: str
    healthy: bool
    heartbeat_age_sec: Optional[float]
    error_ratio_pct: float
    bars_seen: int
    decisions_total: int
    trades_total: int
    rejects_total: int
    errors_total: int
    reasons: List[str]

    def to_json(self) -> Dict[str, object]:
        return asdict(self)


def _parse_iso_ts(value: object) -> Optional[datetime]:
    if value is None:
        return None
    raw = str(value)
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except Exception:
        return None


def _load_json(path: Path) -> Dict[str, object]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def evaluate_reliability(
    run_dir: Path,
    *,
    stale_after_sec: float = 120.0,
    max_error_ratio_pct: float = 5.0,
) -> WatchdogStatus:
    run_dir = Path(run_dir)
    hb = _load_json(run_dir / "heartbeat.json")
    metrics = _load_json(run_dir / "metrics.json")

    now = datetime.now(timezone.utc)
    reasons: List[str] = []

    hb_ts = _parse_iso_ts(hb.get("ts_iso")) if hb else None
    if hb_ts is None and (run_dir / "heartbeat.json").exists():
        hb_ts = datetime.fromtimestamp((run_dir / "heartbeat.json").stat().st_mtime, tz=timezone.utc)
    heartbeat_age_sec = (now - hb_ts).total_seconds() if hb_ts is not None else None

    bars_seen = int(metrics.get("bars_seen", 0) or 0)
    decisions_total = int(metrics.get("decisions_total", 0) or 0)
    trades_total = int(metrics.get("trades_total", 0) or 0)
    rejects_total = int(metrics.get("rejects_total", 0) or 0)
    errors_total = int(metrics.get("errors_total", 0) or 0)

    error_ratio_pct = (float(errors_total) / float(max(1, bars_seen))) * 100.0

    if heartbeat_age_sec is None:
        reasons.append("missing_heartbeat")
    elif heartbeat_age_sec > float(stale_after_sec):
        reasons.append("stale_heartbeat")

    if bars_seen <= 0:
        reasons.append("no_bars_seen")
    if error_ratio_pct > float(max_error_ratio_pct):
        reasons.append("error_ratio_too_high")
    if not (run_dir / "metrics.json").exists():
        reasons.append("missing_metrics")

    healthy = len(reasons) == 0
    return WatchdogStatus(
        generated_at_utc=now.isoformat(),
        run_dir=str(run_dir),
        healthy=healthy,
        heartbeat_age_sec=heartbeat_age_sec,
        error_ratio_pct=error_ratio_pct,
        bars_seen=bars_seen,
        decisions_total=decisions_total,
        trades_total=trades_total,
        rejects_total=rejects_total,
        errors_total=errors_total,
        reasons=reasons,
    )


def write_watchdog_report(status: WatchdogStatus, *, out_md: Path, out_json: Path) -> Tuple[Path, Path]:
    out_md = Path(out_md)
    out_json = Path(out_json)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_json.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        "# Reliability Watchdog",
        "",
        f"Generated: {status.generated_at_utc}",
        f"Run Dir: `{status.run_dir}`",
        "",
        f"- Healthy: `{'YES' if status.healthy else 'NO'}`",
        f"- Heartbeat age (sec): `{status.heartbeat_age_sec if status.heartbeat_age_sec is not None else 'N/A'}`",
        f"- Error ratio (%): `{status.error_ratio_pct:.4f}`",
        f"- Bars seen: `{status.bars_seen}`",
        f"- Decisions: `{status.decisions_total}`",
        f"- Trades: `{status.trades_total}`",
        f"- Rejects: `{status.rejects_total}`",
        f"- Errors: `{status.errors_total}`",
        "",
        "## Reasons",
        "",
    ]
    if not status.reasons:
        lines.append("- none")
    else:
        for reason in status.reasons:
            lines.append(f"- {reason}")

    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    out_json.write_text(json.dumps(status.to_json(), ensure_ascii=True, indent=2), encoding="utf-8")
    return out_md, out_json


__all__ = ["WatchdogStatus", "evaluate_reliability", "write_watchdog_report"]
