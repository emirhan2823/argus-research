from __future__ import annotations

import csv
import json
import re
from dataclasses import asdict, dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Dict, List, Tuple


_WEEK_RE = re.compile(r"^(\d{4})-W(\d{2})$")


@dataclass
class RejectionBreakdown:
    total_rejects: int
    by_code: Dict[str, int]
    by_regime: Dict[str, int]
    top_5_codes: List[tuple]


@dataclass
class ConversionMetrics:
    total_signals: int
    total_opens: int
    total_rejects: int
    conversion_rate: float
    by_regime: Dict[str, float]


@dataclass
class WeeklyAuditReport:
    week: str
    period_start: date
    period_end: date
    rejection_breakdown: RejectionBreakdown
    conversion_metrics: ConversionMetrics
    kill_switch_activations: int
    recommendations: List[str]


class AuditPipeline:
    def __init__(self, run_dir: Path) -> None:
        self.run_dir = Path(run_dir)

    def generate_weekly_report(self, week: str) -> WeeklyAuditReport:
        period_start, period_end = self._parse_week(week)

        decisions = self._load_csv_rows(self.run_dir / "decisions.csv", period_start, period_end)
        trades = self._load_csv_rows(self.run_dir / "trades.csv", period_start, period_end)
        rejects = self._load_csv_rows(self.run_dir / "rejects.csv", period_start, period_end)

        rejection_breakdown = self._build_rejection_breakdown(decisions, rejects)
        conversion_metrics = self._build_conversion_metrics(decisions, trades)
        kill_switch_activations = self._count_kill_switch_activations(rejects)
        recommendations = self._build_recommendations(
            rejection_breakdown=rejection_breakdown,
            conversion_metrics=conversion_metrics,
            kill_switch_activations=kill_switch_activations,
        )

        return WeeklyAuditReport(
            week=week,
            period_start=period_start,
            period_end=period_end,
            rejection_breakdown=rejection_breakdown,
            conversion_metrics=conversion_metrics,
            kill_switch_activations=kill_switch_activations,
            recommendations=recommendations,
        )

    def to_markdown(self, report: WeeklyAuditReport) -> str:
        rb = report.rejection_breakdown
        cm = report.conversion_metrics

        lines: List[str] = []
        lines.append(f"# Weekly Audit Report - {report.week}")
        lines.append("")
        lines.append(f"Period: {report.period_start.isoformat()} -> {report.period_end.isoformat()}")
        lines.append("")

        lines.append("## Conversion Metrics")
        lines.append("| Metric | Value |")
        lines.append("|---|---:|")
        lines.append(f"| GO Signals | {cm.total_signals} |")
        lines.append(f"| OPEN Events | {cm.total_opens} |")
        lines.append(f"| REJECTED Events | {cm.total_rejects} |")
        lines.append(f"| Conversion Rate | {cm.conversion_rate:.2%} |")
        lines.append("")

        lines.append("### Conversion By Regime")
        if cm.by_regime:
            lines.append("| Regime | Rate |")
            lines.append("|---|---:|")
            for regime, rate in sorted(cm.by_regime.items()):
                lines.append(f"| {regime} | {rate:.2%} |")
        else:
            lines.append("- No regime-level conversion data available.")
        lines.append("")

        lines.append("## Rejection Breakdown")
        lines.append(f"Total Rejects: **{rb.total_rejects}**")
        lines.append("")

        lines.append("### Top 5 Codes")
        if rb.top_5_codes:
            lines.append("| Code | Count |")
            lines.append("|---|---:|")
            for code, count in rb.top_5_codes:
                lines.append(f"| {code} | {count} |")
        else:
            lines.append("- No rejections this week.")
        lines.append("")

        lines.append("### By Regime")
        if rb.by_regime:
            lines.append("| Regime | Rejects |")
            lines.append("|---|---:|")
            for regime, count in sorted(rb.by_regime.items()):
                lines.append(f"| {regime} | {count} |")
        else:
            lines.append("- No regime mapping for rejections.")
        lines.append("")

        lines.append("## Risk Events")
        lines.append(f"- Kill-switch activations: {report.kill_switch_activations}")
        lines.append("")

        lines.append("## Recommendations")
        for rec in report.recommendations:
            lines.append(f"- {rec}")

        return "\n".join(lines)

    def to_json(self, report: WeeklyAuditReport) -> str:
        payload = {
            "week": report.week,
            "period_start": report.period_start.isoformat(),
            "period_end": report.period_end.isoformat(),
            "rejection_breakdown": {
                "total_rejects": report.rejection_breakdown.total_rejects,
                "by_code": report.rejection_breakdown.by_code,
                "by_regime": report.rejection_breakdown.by_regime,
                "top_5_codes": [list(item) for item in report.rejection_breakdown.top_5_codes],
            },
            "conversion_metrics": asdict(report.conversion_metrics),
            "kill_switch_activations": report.kill_switch_activations,
            "recommendations": report.recommendations,
        }
        return json.dumps(payload, ensure_ascii=True, indent=2)

    def _parse_week(self, week: str) -> Tuple[date, date]:
        m = _WEEK_RE.match(week)
        if not m:
            raise ValueError(f"Invalid week format: {week}. Expected YYYY-Www")
        year = int(m.group(1))
        iso_week = int(m.group(2))
        start = date.fromisocalendar(year, iso_week, 1)
        end = date.fromisocalendar(year, iso_week, 7)
        return start, end

    def _load_csv_rows(self, path: Path, period_start: date, period_end: date) -> List[Dict[str, str]]:
        if not path.exists():
            return []
        try:
            with path.open("r", newline="", encoding="utf-8") as f:
                rows = list(csv.DictReader(f))
        except Exception:
            return []

        filtered: List[Dict[str, str]] = []
        for row in rows:
            row_date = self._extract_row_date(row)
            if row_date is None:
                continue
            if period_start <= row_date <= period_end:
                filtered.append(row)
        return filtered

    def _extract_row_date(self, row: Dict[str, str]) -> date | None:
        candidates = ["ts_iso", "bar_ts_iso", "timestamp", "bar_ts"]
        for key in candidates:
            value = row.get(key)
            if not value:
                continue

            if key.endswith("_iso"):
                ts = self._parse_iso_datetime(value)
                if ts is not None:
                    return ts.date()
            else:
                try:
                    ts = float(value)
                except Exception:
                    continue
                return datetime.fromtimestamp(ts).date()
        return None

    def _parse_iso_datetime(self, value: str) -> datetime | None:
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except Exception:
            return None

    def _build_rejection_breakdown(
        self,
        decisions: List[Dict[str, str]],
        rejects: List[Dict[str, str]],
    ) -> RejectionBreakdown:
        by_code: Dict[str, int] = {}
        by_regime: Dict[str, int] = {}

        regime_by_bar_ts: Dict[str, str] = {}
        for row in decisions:
            bar_ts_iso = row.get("bar_ts_iso", "")
            regime = row.get("regime", "UNKNOWN") or "UNKNOWN"
            if bar_ts_iso:
                regime_by_bar_ts[bar_ts_iso] = regime

        for row in rejects:
            code = (row.get("code") or row.get("reason") or "UNKNOWN").strip() or "UNKNOWN"
            by_code[code] = by_code.get(code, 0) + 1

            regime = (row.get("regime") or "").strip()
            if not regime:
                regime = regime_by_bar_ts.get(row.get("bar_ts_iso", ""), "UNKNOWN")
            by_regime[regime] = by_regime.get(regime, 0) + 1

        top_5_codes = sorted(by_code.items(), key=lambda item: (-item[1], item[0]))[:5]
        total_rejects = sum(by_code.values())

        return RejectionBreakdown(
            total_rejects=total_rejects,
            by_code=by_code,
            by_regime=by_regime,
            top_5_codes=top_5_codes,
        )

    def _build_conversion_metrics(
        self,
        decisions: List[Dict[str, str]],
        trades: List[Dict[str, str]],
    ) -> ConversionMetrics:
        go_rows = [
            row for row in decisions
            if (row.get("decision") or row.get("verdict") or "").strip().upper() == "GO"
        ]

        open_rows = [
            row for row in trades
            if (row.get("event") or "").strip().upper() in {"OPEN", "ENTRY"}
        ]

        rejected_rows = [
            row for row in trades
            if (row.get("event") or "").strip().upper() == "REJECTED"
        ]

        total_signals = len(go_rows)
        total_opens = len(open_rows)
        total_rejects = len(rejected_rows)
        conversion_rate = (total_opens / total_signals) if total_signals > 0 else 0.0

        signals_by_regime: Dict[str, int] = {}
        for row in go_rows:
            regime = (row.get("regime") or "UNKNOWN").strip() or "UNKNOWN"
            signals_by_regime[regime] = signals_by_regime.get(regime, 0) + 1

        opens_by_regime: Dict[str, int] = {k: 0 for k in signals_by_regime}
        converted_count = min(total_opens, total_signals)
        ordered_go = sorted(go_rows, key=lambda r: r.get("ts_iso", ""))
        for row in ordered_go[:converted_count]:
            regime = (row.get("regime") or "UNKNOWN").strip() or "UNKNOWN"
            opens_by_regime[regime] = opens_by_regime.get(regime, 0) + 1

        by_regime: Dict[str, float] = {}
        for regime, signal_count in signals_by_regime.items():
            if signal_count <= 0:
                by_regime[regime] = 0.0
            else:
                by_regime[regime] = opens_by_regime.get(regime, 0) / signal_count

        return ConversionMetrics(
            total_signals=total_signals,
            total_opens=total_opens,
            total_rejects=total_rejects,
            conversion_rate=conversion_rate,
            by_regime=by_regime,
        )

    def _count_kill_switch_activations(self, rejects: List[Dict[str, str]]) -> int:
        count = 0
        for row in rejects:
            code = (row.get("code") or row.get("reason") or "").upper()
            if "KILL_SWITCH" in code:
                count += 1
        return count

    def _build_recommendations(
        self,
        rejection_breakdown: RejectionBreakdown,
        conversion_metrics: ConversionMetrics,
        kill_switch_activations: int,
    ) -> List[str]:
        recs: List[str] = []

        if conversion_metrics.total_signals == 0:
            recs.append("No GO signals this week; verify model thresholds and data quality.")
        elif conversion_metrics.conversion_rate < 0.20:
            recs.append("Conversion is low; review dominant reject codes before relaxing gates.")

        if rejection_breakdown.total_rejects > conversion_metrics.total_signals:
            recs.append("Reject volume exceeds GO signals; prioritize gate calibration.")

        if rejection_breakdown.top_5_codes:
            top_code, top_count = rejection_breakdown.top_5_codes[0]
            recs.append(f"Top reject code is {top_code} ({top_count}); audit this gate first.")

        if kill_switch_activations > 0:
            recs.append(
                f"Kill-switch activated {kill_switch_activations} times; reduce risk and inspect drawdown triggers."
            )

        if not recs:
            recs.append("Pipeline looks stable; continue monitoring conversion and reject drift weekly.")

        return recs
