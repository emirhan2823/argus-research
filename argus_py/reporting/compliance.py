from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional
import csv


@dataclass
class TaxLot:
    symbol: str
    buy_date: date
    buy_price: float
    sell_date: date
    sell_price: float
    quantity: float
    pnl: float
    hold_days: int
    short_term: bool  # <1 year


@dataclass
class _Trade:
    symbol: str
    action: str  # BUY | SELL
    trade_date: date
    price: float
    quantity: float
    commission: float


class ComplianceReporter:
    def __init__(self, trades_csv: Path):
        self.trades_csv = Path(trades_csv)
        self._cached_lots: Optional[List[TaxLot]] = None

    def generate_8949(self, year: int) -> List[TaxLot]:
        """Generate IRS Form 8949 compatible report."""
        lots = self._build_tax_lots()
        return [lot for lot in lots if lot.sell_date.year == year]

    def generate_pnl_statement(self, start: date, end: date) -> dict:
        """Generate P&L statement for period."""
        lots = self._get_lots_in_range(start, end)
        return {
            "period_start": start.isoformat(),
            "period_end": end.isoformat(),
            "total_trades": len(lots),
            "realized_pnl": sum(l.pnl for l in lots),
            "short_term_pnl": sum(l.pnl for l in lots if l.short_term),
            "long_term_pnl": sum(l.pnl for l in lots if not l.short_term),
            "win_rate": sum(1 for l in lots if l.pnl > 0) / len(lots) if lots else 0,
        }

    def export_csv(self, lots: List[TaxLot], output: Path):
        output = Path(output)
        output.parent.mkdir(parents=True, exist_ok=True)

        with output.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(
                [
                    "Symbol",
                    "Buy Date",
                    "Buy Price",
                    "Sell Date",
                    "Sell Price",
                    "Quantity",
                    "P&L",
                    "Term",
                ]
            )
            for lot in lots:
                writer.writerow(
                    [
                        lot.symbol,
                        lot.buy_date.isoformat(),
                        lot.buy_price,
                        lot.sell_date.isoformat(),
                        lot.sell_price,
                        lot.quantity,
                        lot.pnl,
                        "Short" if lot.short_term else "Long",
                    ]
                )

    def _build_tax_lots(self) -> List[TaxLot]:
        if self._cached_lots is not None:
            return list(self._cached_lots)

        inventory: Dict[str, List[dict]] = {}
        lots: List[TaxLot] = []

        for trade in self._iter_trades():
            queue = inventory.setdefault(trade.symbol, [])
            if trade.action == "BUY":
                buy_unit_cost = trade.price + (trade.commission / trade.quantity if trade.quantity > 0 else 0.0)
                queue.append(
                    {
                        "buy_date": trade.trade_date,
                        "buy_price": buy_unit_cost,
                        "qty": trade.quantity,
                    }
                )
                continue

            remaining = trade.quantity
            sell_unit_proceeds = trade.price - (trade.commission / trade.quantity if trade.quantity > 0 else 0.0)
            while remaining > 0 and queue:
                head = queue[0]
                matched_qty = min(remaining, float(head["qty"]))
                buy_date = head["buy_date"]
                buy_price = float(head["buy_price"])
                sell_date = trade.trade_date
                pnl = (sell_unit_proceeds - buy_price) * matched_qty
                hold_days = max(0, (sell_date - buy_date).days)

                lots.append(
                    TaxLot(
                        symbol=trade.symbol,
                        buy_date=buy_date,
                        buy_price=buy_price,
                        sell_date=sell_date,
                        sell_price=sell_unit_proceeds,
                        quantity=matched_qty,
                        pnl=pnl,
                        hold_days=hold_days,
                        short_term=hold_days < 365,
                    )
                )

                head["qty"] = float(head["qty"]) - matched_qty
                remaining -= matched_qty

                if head["qty"] <= 1e-12:
                    queue.pop(0)

        self._cached_lots = list(lots)
        return list(lots)

    def _get_lots_in_range(self, start: date, end: date) -> List[TaxLot]:
        lots = self._build_tax_lots()
        return [lot for lot in lots if start <= lot.sell_date <= end]

    def _iter_trades(self):
        if not self.trades_csv.exists():
            return

        with self.trades_csv.open("r", newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                action = self._resolve_action(row)
                if action is None:
                    continue

                symbol = self._row_get(row, ["symbol", "Symbol"])
                if not symbol:
                    continue

                price = self._to_float(self._row_get(row, ["price", "Price"]))
                quantity = self._to_float(self._row_get(row, ["quantity", "qty", "Qty"]))
                commission = self._to_float(
                    self._row_get(row, ["commission", "comm", "Comm", "fee", "Fee"])
                )
                trade_date = self._parse_trade_date(row)

                if price <= 0 or quantity <= 0 or trade_date is None:
                    continue

                yield _Trade(
                    symbol=str(symbol).strip(),
                    action=action,
                    trade_date=trade_date,
                    price=price,
                    quantity=quantity,
                    commission=commission,
                )

    @staticmethod
    def _row_get(row: dict, keys: List[str]):
        lowered = {str(k).lower(): v for k, v in row.items()}
        for key in keys:
            if key in row and row.get(key) not in (None, ""):
                return row.get(key)
            lk = key.lower()
            if lk in lowered and lowered[lk] not in (None, ""):
                return lowered[lk]
        return None

    @staticmethod
    def _to_float(value) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    def _resolve_action(self, row: dict) -> Optional[str]:
        side_raw = self._row_get(row, ["side", "Side"])
        if not side_raw:
            return None

        side = str(side_raw).split("_")[0].strip().upper()
        if side not in {"BUY", "SELL"}:
            return None

        event_raw = self._row_get(row, ["event", "Event"])
        if event_raw:
            event = str(event_raw).strip().upper()
            if event == "REJECTED":
                return None
            if event == "OPEN":
                return "BUY" if side == "BUY" else None
            if event == "CLOSE":
                return "SELL" if side == "SELL" else None

        return side

    def _parse_trade_date(self, row: dict) -> Optional[date]:
        ts_iso = self._row_get(row, ["ts_iso", "bar_ts_iso"])
        if ts_iso:
            try:
                dt = datetime.fromisoformat(str(ts_iso).replace("Z", "+00:00"))
                return dt.date()
            except ValueError:
                pass

        timestamp = self._row_get(row, ["timestamp", "Timestamp", "ts"])
        if timestamp is not None:
            try:
                value = float(timestamp)
                # Handle millisecond timestamps as well.
                if value > 1e11:
                    value = value / 1000.0
                return datetime.fromtimestamp(value, tz=timezone.utc).date()
            except (ValueError, OSError):
                return None

        return None
