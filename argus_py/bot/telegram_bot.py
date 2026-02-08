from __future__ import annotations

import csv
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from argus_py.risk.kill_switch import KillSwitch, RiskLevel

try:
    from telegram import Update  # type: ignore
    from telegram.ext import Application, CommandHandler, ContextTypes  # type: ignore
except Exception:  # pragma: no cover
    Update = Any  # type: ignore
    Application = None  # type: ignore
    CommandHandler = None  # type: ignore

    class _ContextTypesFallback:
        DEFAULT_TYPE = Any

    ContextTypes = _ContextTypesFallback  # type: ignore


class ArgusTelegramBot:
    def __init__(self, token: str, run_dir: Path, allowed_users: list):
        self.token = token
        self.run_dir = Path(run_dir)
        self.allowed_users = {int(x) for x in allowed_users}

    async def cmd_status(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if not self._is_allowed(update):
            return
        state = self._load_state()
        msg = "*Argus Status*\n"
        msg += f"Equity: ${float(state.get('equity', 0.0)):.2f}\n"
        msg += f"Drawdown: {float(state.get('current_dd_pct', 0.0)):.2f}%\n"
        msg += f"Kill-Switch: {state.get('kill_switch_level', 'NORMAL')}\n"
        msg += f"Open Positions: {int(state.get('open_positions', 0))}"
        await self._reply(update, msg, parse_mode="Markdown")

    async def cmd_trades(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if not self._is_allowed(update):
            return

        trades = self._load_recent_trades(limit=5)
        if not trades:
            await self._reply(update, "No recent trades found.")
            return

        lines = ["Recent Trades (last 5):"]
        for row in trades:
            ts = row.get("ts", "-")
            side = row.get("side", "-")
            price = row.get("price", 0.0)
            qty = row.get("qty", 0.0)
            pnl = row.get("pnl", 0.0)
            event = row.get("event", "-")
            lines.append(f"{ts} | {side} {qty:.6f} @ {price:.2f} | pnl={pnl:.2f} | {event}")

        await self._reply(update, "\n".join(lines))

    async def cmd_killswitch(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if not self._is_allowed(update):
            return

        args = getattr(ctx, "args", []) or []
        if not args:
            await self._reply(update, "Usage: /killswitch [soft|hard|off]")
            return

        level_raw = str(args[0]).strip().lower()
        if level_raw not in {"soft", "hard", "off"}:
            await self._reply(update, "Invalid level. Use: soft | hard | off")
            return

        new_level = self._set_kill_switch(level_raw)
        await self._reply(update, f"Kill-Switch set to {new_level}")

    async def cmd_report(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if not self._is_allowed(update):
            return

        summary = self._build_report()
        msg = "*Argus Report*\n"
        msg += (
            f"Daily: net {summary['daily_net']:.2f} | +{summary['daily_gross_profit']:.2f}"
            f" / {summary['daily_gross_loss']:.2f} | trades {summary['daily_close_trades']}\n"
        )
        msg += (
            f"Weekly: net {summary['weekly_net']:.2f} | +{summary['weekly_gross_profit']:.2f}"
            f" / {summary['weekly_gross_loss']:.2f} | trades {summary['weekly_close_trades']} | "
            f"WR {summary['weekly_win_rate']:.2%}\n"
        )

        by_symbol = summary.get("weekly_by_symbol", [])
        if by_symbol:
            msg += "Top Symbols:\n"
            for item in by_symbol[:5]:
                msg += (
                    f"- {item['symbol']}: pnl {item['net']:.2f}, "
                    f"trades {item['close_trades']}, WR {item['win_rate']:.2%}\n"
                )
        else:
            msg += "Top Symbols: N/A\n"

        await self._reply(update, msg, parse_mode="Markdown")

    async def cmd_balance(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if not self._is_allowed(update):
            return

        state = self._load_state()
        equity = float(state.get("equity", 0.0))
        balance = float(state.get("balance", equity))
        msg = f"Balance: ${balance:.2f}\nEquity: ${equity:.2f}"
        await self._reply(update, msg)

    def run(self):
        if Application is None or CommandHandler is None:
            raise RuntimeError(
                "python-telegram-bot is not installed. Install with: pip install python-telegram-bot"
            )

        app = Application.builder().token(self.token).build()
        app.add_handler(CommandHandler("status", self.cmd_status))
        app.add_handler(CommandHandler("trades", self.cmd_trades))
        app.add_handler(CommandHandler("killswitch", self.cmd_killswitch))
        app.add_handler(CommandHandler("report", self.cmd_report))
        app.add_handler(CommandHandler("balance", self.cmd_balance))
        app.run_polling()

    def _is_allowed(self, update: Any) -> bool:
        user = getattr(update, "effective_user", None)
        uid = getattr(user, "id", None)
        return uid in self.allowed_users

    async def _reply(self, update: Any, text: str, parse_mode: Optional[str] = None) -> None:
        message = getattr(update, "message", None)
        if message is None:
            return
        kwargs = {"parse_mode": parse_mode} if parse_mode else {}
        await message.reply_text(text, **kwargs)

    def _load_state(self) -> Dict[str, Any]:
        state: Dict[str, Any] = {}

        daemon_state = self._read_json(self.run_dir / "daemon_state.json")
        heartbeat = self._read_json(self.run_dir / "heartbeat.json")
        kill_switch = self._read_json(self.run_dir / "kill_switch_state.json")

        if daemon_state:
            state.update(daemon_state)
        if heartbeat:
            state.update(heartbeat)

        if "current_dd_pct" not in state:
            dd = state.get("dd_pct", 0.0)
            try:
                state["current_dd_pct"] = float(dd)
            except (TypeError, ValueError):
                state["current_dd_pct"] = 0.0

        if "kill_switch_level" not in state:
            state["kill_switch_level"] = kill_switch.get("level", "NORMAL") if kill_switch else "NORMAL"

        state["open_positions"] = self._derive_open_positions(state)
        return state

    def _read_json(self, path: Path) -> Dict[str, Any]:
        if not path.exists():
            return {}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _set_kill_switch(self, level: str) -> str:
        path = self.run_dir / "kill_switch_state.json"
        ks = KillSwitch.load_state(path)

        if level == "soft":
            ks.activate(RiskLevel.SOFT, "Telegram command")
        elif level == "hard":
            ks.activate(RiskLevel.HARD, "Telegram command")
        elif level == "off":
            ks.force_recovery(RiskLevel.NORMAL, "Telegram command")

        ks.save_state(path)
        return ks.get_level().value

    def _load_recent_trades(self, limit: int = 5) -> List[Dict[str, Any]]:
        trades_path = self.run_dir / "trades.csv"
        if not trades_path.exists():
            return []

        rows: List[Dict[str, Any]] = []
        with trades_path.open("r", newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                parsed = self._parse_trade_row(row)
                if parsed is not None:
                    rows.append(parsed)

        rows.sort(key=lambda item: item["timestamp"], reverse=True)
        return rows[:limit]

    def _parse_trade_row(self, row: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        ts_value = self._row_get(row, ["timestamp", "Timestamp", "ts_iso"]) or ""
        ts_num = self._parse_timestamp(ts_value)
        ts_human = self._fmt_timestamp(ts_num, ts_value)

        side = str(self._row_get(row, ["side", "Side"]) or "-")
        symbol = str(self._row_get(row, ["symbol", "Symbol"]) or "-")
        event = str(self._row_get(row, ["event", "Event"]) or "-")
        price = self._to_float(self._row_get(row, ["price", "Price"]))
        qty = self._to_float(self._row_get(row, ["quantity", "qty", "Qty"]))
        pnl = self._to_float(self._row_get(row, ["pnl", "PnL"]))

        return {
            "timestamp": ts_num,
            "ts": ts_human,
            "symbol": symbol,
            "side": side,
            "event": event,
            "price": price,
            "qty": qty,
            "pnl": pnl,
        }

    def _build_report(self) -> Dict[str, Any]:
        now = datetime.now(timezone.utc)
        day_cut = now - timedelta(days=1)
        week_cut = now - timedelta(days=7)

        trades = self._load_recent_trades(limit=100000)
        day_rows = [r for r in trades if datetime.fromtimestamp(r["timestamp"], tz=timezone.utc) >= day_cut]
        week_rows = [r for r in trades if datetime.fromtimestamp(r["timestamp"], tz=timezone.utc) >= week_cut]

        def _close_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
            return [r for r in rows if str(r.get("event", "")).upper() == "CLOSE"]

        def _net(rows: List[Dict[str, Any]]) -> float:
            close_rows = _close_rows(rows)
            return float(sum(float(r.get("pnl", 0.0)) for r in close_rows))

        def _gross_profit(rows: List[Dict[str, Any]]) -> float:
            close_rows = _close_rows(rows)
            return float(sum(float(r.get("pnl", 0.0)) for r in close_rows if float(r.get("pnl", 0.0)) > 0))

        def _gross_loss(rows: List[Dict[str, Any]]) -> float:
            close_rows = _close_rows(rows)
            return float(sum(float(r.get("pnl", 0.0)) for r in close_rows if float(r.get("pnl", 0.0)) < 0))

        def _win_rate(rows: List[Dict[str, Any]]) -> float:
            close_rows = _close_rows(rows)
            if not close_rows:
                return 0.0
            wins = sum(1 for r in close_rows if float(r.get("pnl", 0.0)) > 0)
            return wins / len(close_rows)

        def _symbol_breakdown(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
            close_rows = _close_rows(rows)
            bucket: Dict[str, List[Dict[str, Any]]] = {}
            for row in close_rows:
                symbol = str(row.get("symbol", "-"))
                bucket.setdefault(symbol, []).append(row)

            out: List[Dict[str, Any]] = []
            for symbol, symbol_rows in bucket.items():
                net = float(sum(float(r.get("pnl", 0.0)) for r in symbol_rows))
                wins = sum(1 for r in symbol_rows if float(r.get("pnl", 0.0)) > 0)
                wr = wins / len(symbol_rows) if symbol_rows else 0.0
                out.append(
                    {
                        "symbol": symbol,
                        "net": net,
                        "close_trades": len(symbol_rows),
                        "win_rate": wr,
                    }
                )
            out.sort(key=lambda x: x["net"], reverse=True)
            return out

        return {
            "daily_net": _net(day_rows),
            "daily_gross_profit": _gross_profit(day_rows),
            "daily_gross_loss": _gross_loss(day_rows),
            "daily_trades": len(day_rows),
            "daily_close_trades": len(_close_rows(day_rows)),
            "daily_win_rate": _win_rate(day_rows),
            "weekly_net": _net(week_rows),
            "weekly_gross_profit": _gross_profit(week_rows),
            "weekly_gross_loss": _gross_loss(week_rows),
            "weekly_trades": len(week_rows),
            "weekly_close_trades": len(_close_rows(week_rows)),
            "weekly_win_rate": _win_rate(week_rows),
            "weekly_by_symbol": _symbol_breakdown(week_rows),
        }

    @staticmethod
    def _row_get(row: Dict[str, Any], keys: List[str]) -> Any:
        lowered = {str(k).lower(): v for k, v in row.items()}
        for key in keys:
            if key in row and row.get(key) not in (None, ""):
                return row.get(key)
            lk = key.lower()
            if lk in lowered and lowered[lk] not in (None, ""):
                return lowered[lk]
        return None

    @staticmethod
    def _to_float(value: Any) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _parse_timestamp(value: Any) -> float:
        try:
            raw = float(value)
            if raw > 1e11:
                raw /= 1000.0
            return raw
        except (TypeError, ValueError):
            pass

        if isinstance(value, str) and value:
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
            except ValueError:
                return 0.0

        return 0.0

    @staticmethod
    def _fmt_timestamp(ts_num: float, fallback: Any) -> str:
        if ts_num <= 0:
            return str(fallback)
        return datetime.fromtimestamp(ts_num, tz=timezone.utc).isoformat()

    @staticmethod
    def _derive_open_positions(state: Dict[str, Any]) -> int:
        heartbeat_pos = state.get("position")
        if isinstance(heartbeat_pos, dict) and heartbeat_pos:
            return 1

        positions = state.get("positions")
        if isinstance(positions, list):
            return len(positions)

        if isinstance(positions, dict):
            return len([k for k, v in positions.items() if float(v or 0) != 0.0])

        return 0
