from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

try:
    from flask import Flask, jsonify, render_template
except ModuleNotFoundError:  # pragma: no cover
    Flask = None
    jsonify = None
    render_template = None


class DashboardData:
    """Data provider for dashboard."""

    def __init__(self, run_dir: Path):
        self.run_dir = Path(run_dir)

    def get_heartbeat(self) -> dict:
        """Get latest heartbeat data."""
        path = self.run_dir / "heartbeat.json"
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                return {"error": "Invalid heartbeat"}
        return {"error": "No heartbeat"}

    def get_state(self) -> dict:
        """Get daemon state."""
        path = self.run_dir / "daemon_state.json"
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                return {"error": "Invalid state"}
        return {"error": "No state"}

    def get_recent_trades(self, limit: int = 20) -> list:
        """Get recent trades from CSV."""
        path = self.run_dir / "trades.csv"
        if not path.exists():
            return []

        trades: List[Dict[str, Any]] = []
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                row["_ts"] = self._row_ts(row)
                trades.append(row)

        trades.sort(key=lambda r: r.get("_ts", 0))
        return trades[-limit:]

    def get_recent_decisions(self, limit: int = 50) -> list:
        """Get recent decisions."""
        path = self.run_dir / "decisions.csv"
        if not path.exists():
            return []

        decisions: List[Dict[str, Any]] = []
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                row["_ts"] = self._row_ts(row)
                decisions.append(row)

        decisions.sort(key=lambda r: r.get("_ts", 0))
        return decisions[-limit:]

    def get_equity_curve(self) -> list:
        """Calculate equity curve from trades."""
        trades = self.get_recent_trades(1000)
        curve = []
        equity = float(self.get_state().get("equity", 1000.0))

        close_rows = [t for t in trades if str(t.get("event", "")).upper() == "CLOSE"]
        total_realized = sum(float(t.get("pnl", 0.0) or 0.0) for t in close_rows)
        start_equity = equity - total_realized

        rolling = start_equity
        for trade in close_rows:
            pnl = float(trade.get("pnl", 0.0) or 0.0)
            rolling += pnl
            curve.append(
                {
                    "timestamp": trade.get("timestamp") or trade.get("ts_iso") or "",
                    "equity": round(rolling, 6),
                }
            )

        return curve

    def get_rejection_summary(self) -> dict:
        """Summarize rejections by code."""
        path = self.run_dir / "rejects.csv"
        if not path.exists():
            return {}

        summary: Dict[str, int] = {}
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                code = str(row.get("code", "UNKNOWN") or "UNKNOWN")
                summary[code] = summary.get(code, 0) + 1

        return summary

    @staticmethod
    def _row_ts(row: Dict[str, Any]) -> float:
        for key in ("timestamp", "Timestamp", "bar_ts", "ts"):
            value = row.get(key)
            if value not in (None, ""):
                try:
                    return float(value)
                except (TypeError, ValueError):
                    pass
        for key in ("ts_iso", "bar_ts_iso"):
            value = row.get(key)
            if value:
                try:
                    return datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp()
                except ValueError:
                    pass
        return 0.0


def create_app(run_dir: str):
    if Flask is None:  # pragma: no cover
        raise RuntimeError("Flask is not installed. Install with: pip install flask")

    app = Flask(__name__, template_folder="templates")
    app.config["RUN_DIR"] = run_dir

    @app.route("/")
    def index():
        return render_template("index.html")

    @app.route("/api/status")
    def api_status():
        data = DashboardData(Path(app.config["RUN_DIR"]))
        return jsonify({"heartbeat": data.get_heartbeat(), "state": data.get_state()})

    @app.route("/api/trades")
    def api_trades():
        data = DashboardData(Path(app.config["RUN_DIR"]))
        return jsonify(data.get_recent_trades(50))

    @app.route("/api/equity")
    def api_equity():
        data = DashboardData(Path(app.config["RUN_DIR"]))
        return jsonify(data.get_equity_curve())

    @app.route("/api/rejections")
    def api_rejections():
        data = DashboardData(Path(app.config["RUN_DIR"]))
        return jsonify(data.get_rejection_summary())

    return app
