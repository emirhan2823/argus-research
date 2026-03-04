"""Per-trade reporting helpers for paper/backtest observability."""

from __future__ import annotations

import csv
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _to_utc(value: str | datetime | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    text = str(value).strip()
    if not text:
        return None
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


def _parse_features_json(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if raw is None:
        return {}
    try:
        parsed = json.loads(str(raw))
    except Exception:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _heuristic_notes(
    *,
    net_pnl_pct: float,
    max_favorable_excursion: float,
    max_adverse_excursion: float,
    regime_at_entry: str,
    regime_at_exit: str,
    confidence_at_entry: float,
    volume_ratio_at_entry: float,
    trailing_activated: bool,
) -> tuple[str, str, str]:
    if net_pnl_pct > 0.0 and regime_at_entry == regime_at_exit and confidence_at_entry >= 0.60:
        right = "Regime and confidence alignment held through the trade."
    elif net_pnl_pct > 0.0 and volume_ratio_at_entry >= 1.20:
        right = "Above-average volume supported follow-through."
    elif trailing_activated and max_favorable_excursion > 0.0:
        right = "Trailing logic protected gains during extension."
    else:
        right = "Risk stayed bounded by predefined stop/target discipline."

    if max_adverse_excursion < -0.010:
        wrong = "Adverse excursion was elevated early in the trade."
    elif net_pnl_pct < 0.0:
        wrong = "Momentum failed to sustain after entry."
    else:
        wrong = "No major execution fault detected."

    if max_adverse_excursion < -0.010:
        suggestion = "Tighten entry timing and wait for stronger confirmation."
    elif volume_ratio_at_entry < 1.0:
        suggestion = "Prioritize entries with volume support above baseline."
    elif net_pnl_pct < 0.0:
        suggestion = "Consider reducing hold time in weak follow-through conditions."
    else:
        suggestion = "Current setup quality is acceptable; keep sizing discipline unchanged."

    return right, wrong, suggestion


def _markdown_report(title: str, records: list[dict[str, Any]]) -> str:
    trade_count = len(records)
    wins = sum(1 for rec in records if _safe_float(rec.get("net_pnl_pct")) > 0.0)
    win_rate = (wins / trade_count) if trade_count else 0.0
    total_return = sum(_safe_float(rec.get("net_pnl_pct")) for rec in records)

    per_engine: dict[str, float] = {}
    for rec in records:
        engine = str(rec.get("engine") or "UNKNOWN")
        per_engine[engine] = per_engine.get(engine, 0.0) + _safe_float(rec.get("net_pnl_pct"))

    if per_engine:
        best_engine = max(per_engine.items(), key=lambda x: x[1])[0]
        worst_engine = min(per_engine.items(), key=lambda x: x[1])[0]
    else:
        best_engine = "n/a"
        worst_engine = "n/a"

    max_drawdown = min([_safe_float(rec.get("drawdown_during_trade")) for rec in records] or [0.0])
    if trade_count == 0:
        observation = "No closed trades for this period."
    elif total_return > 0.0 and win_rate >= 0.50:
        observation = "Positive expectancy with stable hit-rate."
    elif total_return > 0.0:
        observation = "Net positive period with uneven win distribution."
    else:
        observation = "Protective risk posture advised until consistency recovers."

    lines = [
        f"## {title}",
        "",
        f"Trades: {trade_count}",
        f"Win rate: {win_rate * 100.0:.2f}%",
        f"Total return: {total_return * 100.0:.2f}%",
        f"Best engine: {best_engine}",
        f"Worst engine: {worst_engine}",
        f"Max drawdown: {max_drawdown * 100.0:.2f}%",
        "Observations:",
        f"- {observation}",
    ]
    return "\n".join(lines) + "\n"


class TradeReportManager:
    """Writes per-trade JSON + index + daily/monthly summaries from closed trades."""

    def __init__(
        self,
        *,
        conn: sqlite3.Connection,
        run_dir: Path | str,
        run_id: str,
        run_started_at: datetime | None = None,
    ) -> None:
        self._conn = conn
        self._run_root = Path(run_dir) / str(run_id)
        self._trades_dir = self._run_root / "trades"
        self._index_path = self._run_root / "trades_index.csv"
        self._daily_dir = self._run_root / "daily_reports"
        self._monthly_dir = self._run_root / "monthly_reports"
        self._run_started_at = _to_utc(run_started_at) or _utc_now()
        self._processed: set[str] = set()

        self._trades_dir.mkdir(parents=True, exist_ok=True)
        self._daily_dir.mkdir(parents=True, exist_ok=True)
        self._monthly_dir.mkdir(parents=True, exist_ok=True)
        self._bootstrap_processed_trade_ids()

    def sync_closed_trades(self) -> list[dict[str, Any]]:
        rows = self._fetch_closed_trade_rows()
        new_records: list[dict[str, Any]] = []
        touched_days: set[str] = set()
        touched_months: set[str] = set()

        for row in rows:
            trade_id = str(row.get("trade_id") or "").strip()
            if not trade_id or trade_id in self._processed:
                continue

            entry_dt = _to_utc(row.get("entry_time"))
            if entry_dt is not None and entry_dt < self._run_started_at:
                continue

            payload = self._build_trade_payload(row)
            self._write_trade_json(payload)
            self._append_index_row(payload)
            self._processed.add(trade_id)
            new_records.append(payload)

            exit_time = str(payload.get("exit_time") or "")
            if len(exit_time) >= 10:
                touched_days.add(exit_time[:10])
            if len(exit_time) >= 7:
                touched_months.add(exit_time[:7])

        for day in sorted(touched_days):
            self._write_daily_report(day)
        for month in sorted(touched_months):
            self._write_monthly_report(month)
        return new_records

    def _bootstrap_processed_trade_ids(self) -> None:
        if not self._index_path.exists():
            return
        try:
            with self._index_path.open("r", encoding="utf-8", newline="") as fh:
                reader = csv.DictReader(fh)
                for row in reader:
                    tid = str(row.get("trade_id") or "").strip()
                    if tid:
                        self._processed.add(tid)
        except Exception:
            return

    def _fetch_closed_trade_rows(self) -> list[dict[str, Any]]:
        cur = self._conn.execute(
            """
            SELECT
              trade_id, symbol, side, engine, entry_time, exit_time, hold_minutes,
              size, entry_price, exit_price, pnl_pct, net_pnl_pct, confidence,
              regime_at_entry, regime_at_exit, stop_distance, reason_entry, reason_exit, features_json
            FROM trades
            WHERE exit_time IS NOT NULL
            ORDER BY exit_time ASC, trade_id ASC
            """
        )
        columns = [str(col[0]) for col in cur.description or ()]
        rows: list[dict[str, Any]] = []
        for raw in cur.fetchall():
            rows.append({columns[i]: raw[i] for i in range(len(columns))})
        return rows

    def _build_trade_payload(self, row: dict[str, Any]) -> dict[str, Any]:
        entry_dt = _to_utc(row.get("entry_time")) or _utc_now()
        exit_dt = _to_utc(row.get("exit_time")) or entry_dt
        hold_minutes = _safe_int(row.get("hold_minutes"), default=0)
        if hold_minutes <= 0:
            hold_minutes = max(0, int((exit_dt - entry_dt).total_seconds() // 60))

        features = _parse_features_json(row.get("features_json"))
        pnl_pct = _safe_float(row.get("pnl_pct"), 0.0)
        net_pnl_pct = _safe_float(row.get("net_pnl_pct"), pnl_pct)
        stop_distance = max(0.0001, abs(_safe_float(row.get("stop_distance"), 0.01)))
        max_favorable_excursion = _safe_float(features.get("max_favorable_excursion"), max(pnl_pct, 0.0))
        max_adverse_excursion = _safe_float(features.get("max_adverse_excursion"), min(pnl_pct, 0.0))
        drawdown_during_trade = _safe_float(
            features.get("drawdown_during_trade"),
            min(0.0, max_adverse_excursion),
        )
        reason_exit = str(row.get("reason_exit") or "")
        trailing_activated = bool(features.get("trailing_activated")) or ("trail" in reason_exit.lower())
        trailing_exit = bool(features.get("trailing_exit")) or ("trail" in reason_exit.lower())
        confidence_at_entry = _safe_float(row.get("confidence"), 0.0)
        atr_at_entry = _safe_float(
            features.get("atr_at_entry"),
            _safe_float(features.get("atr_14_pct"), stop_distance),
        )
        volatility_at_entry = _safe_float(
            features.get("volatility_at_entry"),
            _safe_float(features.get("atr_14_pct"), 0.0),
        )
        volume_ratio_at_entry = _safe_float(
            features.get("volume_ratio_at_entry"),
            _safe_float(features.get("volume_ratio"), 1.0),
        )
        leverage = _safe_float(features.get("leverage"), 1.0)
        position_size_pct = _safe_float(features.get("position_size_pct"), _safe_float(row.get("size"), 0.0))

        regime_at_entry = str(row.get("regime_at_entry") or "UNKNOWN")
        regime_at_exit = str(row.get("regime_at_exit") or regime_at_entry)
        what_went_right, what_went_wrong, improvement = _heuristic_notes(
            net_pnl_pct=net_pnl_pct,
            max_favorable_excursion=max_favorable_excursion,
            max_adverse_excursion=max_adverse_excursion,
            regime_at_entry=regime_at_entry,
            regime_at_exit=regime_at_exit,
            confidence_at_entry=confidence_at_entry,
            volume_ratio_at_entry=volume_ratio_at_entry,
            trailing_activated=trailing_activated,
        )

        return {
            "trade_id": str(row.get("trade_id")),
            "symbol": str(row.get("symbol") or "UNKNOWN"),
            "side": str(row.get("side") or "long"),
            "engine": str(row.get("engine") or "ROUTER"),
            "entry_time": entry_dt.isoformat(),
            "exit_time": exit_dt.isoformat(),
            "hold_minutes": int(hold_minutes),
            "leverage": float(leverage),
            "position_size_pct": float(position_size_pct),
            "entry_price": float(_safe_float(row.get("entry_price"), 0.0)),
            "exit_price": float(_safe_float(row.get("exit_price"), 0.0)),
            "pnl_pct": float(pnl_pct),
            "net_pnl_pct": float(net_pnl_pct),
            "max_favorable_excursion": float(max_favorable_excursion),
            "max_adverse_excursion": float(max_adverse_excursion),
            "drawdown_during_trade": float(drawdown_during_trade),
            "regime_at_entry": regime_at_entry,
            "regime_at_exit": regime_at_exit,
            "confidence_at_entry": float(confidence_at_entry),
            "atr_at_entry": float(atr_at_entry),
            "volatility_at_entry": float(volatility_at_entry),
            "volume_ratio_at_entry": float(volume_ratio_at_entry),
            "trailing_activated": bool(trailing_activated),
            "trailing_exit": bool(trailing_exit),
            "what_went_right": what_went_right,
            "what_went_wrong": what_went_wrong,
            "improvement_suggestion": improvement,
        }

    def _write_trade_json(self, payload: dict[str, Any]) -> None:
        trade_id = str(payload.get("trade_id") or "unknown_trade").replace("/", "_").replace("\\", "_")
        target = self._trades_dir / f"{trade_id}.json"
        target.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    def _append_index_row(self, payload: dict[str, Any]) -> None:
        header = [
            "trade_id",
            "symbol",
            "engine",
            "side",
            "entry_time",
            "exit_time",
            "net_pnl_pct",
            "max_drawdown",
            "regime",
        ]
        row = {
            "trade_id": str(payload.get("trade_id") or ""),
            "symbol": str(payload.get("symbol") or ""),
            "engine": str(payload.get("engine") or ""),
            "side": str(payload.get("side") or ""),
            "entry_time": str(payload.get("entry_time") or ""),
            "exit_time": str(payload.get("exit_time") or ""),
            "net_pnl_pct": f"{_safe_float(payload.get('net_pnl_pct')):.10f}",
            "max_drawdown": f"{_safe_float(payload.get('drawdown_during_trade')):.10f}",
            "regime": str(payload.get("regime_at_entry") or "UNKNOWN"),
        }
        write_header = not self._index_path.exists()
        with self._index_path.open("a", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=header)
            if write_header:
                writer.writeheader()
            writer.writerow(row)

    def _load_trade_payloads(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for path in sorted(self._trades_dir.glob("*.json")):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            if isinstance(payload, dict):
                rows.append(payload)
        return rows

    def _records_for_period(self, records: Iterable[dict[str, Any]], prefix: str) -> list[dict[str, Any]]:
        return [rec for rec in records if str(rec.get("exit_time") or "").startswith(prefix)]

    def _write_daily_report(self, day: str) -> None:
        all_records = self._load_trade_payloads()
        day_records = self._records_for_period(all_records, f"{day}")
        report = _markdown_report(f"Daily Report — {day}", day_records)
        (self._daily_dir / f"{day}.md").write_text(report, encoding="utf-8")

    def _write_monthly_report(self, month: str) -> None:
        all_records = self._load_trade_payloads()
        month_records = self._records_for_period(all_records, f"{month}")
        report = _markdown_report(f"Monthly Report — {month}", month_records)
        (self._monthly_dir / f"{month}.md").write_text(report, encoding="utf-8")
