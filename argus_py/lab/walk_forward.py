from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from argus_py.data.loader import DataLoader


@dataclass
class WFWindow:
    start: date
    end: date
    train_start: date
    train_end: date
    test_start: date
    test_end: date


@dataclass
class WFResult:
    window: WFWindow
    train_trades: int
    test_trades: int
    train_sharpe: float
    test_sharpe: float
    test_pnl: float
    test_dd: float
    test_wr: float


@dataclass
class WFReport:
    windows: List[WFResult]
    aggregate_sharpe: float
    aggregate_pnl: float
    aggregate_dd: float
    no_data_windows: List[int]


class WalkForwardEngine:
    """Walk-forward optimization engine with proper error handling."""

    def __init__(self, data_path: Path, output_dir: Path):
        self.data_path = Path(data_path)
        self.output_dir = Path(output_dir)
        self._symbol_data: Dict[str, pd.DataFrame] = {}

    def create_windows(
        self,
        start_date: date,
        end_date: date,
        train_months: int = 6,
        test_months: int = 1,
        step_months: int = 1,
    ) -> List[WFWindow]:
        windows: List[WFWindow] = []
        current_test_start = start_date + timedelta(days=train_months * 30)

        while current_test_start + timedelta(days=test_months * 30) <= end_date:
            train_start = current_test_start - timedelta(days=train_months * 30)
            train_end = current_test_start - timedelta(days=1)
            test_end = current_test_start + timedelta(days=test_months * 30) - timedelta(days=1)

            windows.append(
                WFWindow(
                    start=train_start,
                    end=test_end,
                    train_start=train_start,
                    train_end=train_end,
                    test_start=current_test_start,
                    test_end=test_end,
                )
            )

            current_test_start += timedelta(days=step_months * 30)

        return windows

    def validate_data(self, window: WFWindow) -> Tuple[bool, str]:
        train, test = self._window_frames(window)
        if train.empty:
            return False, "NO_TRAIN_DATA"
        if test.empty:
            return False, "NO_TEST_DATA"
        return True, "OK"

    def run_window(self, window: WFWindow) -> WFResult:
        is_valid, reason = self.validate_data(window)
        if not is_valid:
            raise ValueError(f"Data validation failed: {reason}")

        train, test = self._window_frames(window)

        train_m = self._compute_metrics(train)
        test_m = self._compute_metrics(test)

        return WFResult(
            window=window,
            train_trades=train_m["trades"],
            test_trades=test_m["trades"],
            train_sharpe=train_m["sharpe"],
            test_sharpe=test_m["sharpe"],
            test_pnl=test_m["pnl"],
            test_dd=test_m["dd"],
            test_wr=test_m["wr"],
        )

    def run_full(
        self,
        start_date: date,
        end_date: date,
        symbols: List[str] = ["BTCUSDT"],
        skip_invalid: bool = True,
    ) -> WFReport:
        if not symbols:
            symbols = ["BTCUSDT"]

        # Load preferred symbol order; first available drives run.
        selected_symbol = None
        for sym in symbols:
            df = self._load_symbol_data(sym)
            if not df.empty:
                selected_symbol = sym
                break

        if selected_symbol is None:
            if skip_invalid:
                return WFReport([], 0.0, 0.0, 0.0, [])
            raise ValueError("No data available for requested symbols")

        self._active_symbol = selected_symbol
        windows = self.create_windows(start_date, end_date)

        results: List[WFResult] = []
        no_data_windows: List[int] = []

        for idx, window in enumerate(windows):
            is_valid, _ = self.validate_data(window)
            if not is_valid:
                no_data_windows.append(idx)
                if skip_invalid:
                    continue
                raise ValueError(f"Invalid window index={idx}")

            result = self.run_window(window)
            results.append(result)

        aggregate_sharpe = float(np.mean([r.test_sharpe for r in results])) if results else 0.0
        aggregate_pnl = float(np.sum([r.test_pnl for r in results])) if results else 0.0
        aggregate_dd = float(np.max([r.test_dd for r in results])) if results else 0.0

        return WFReport(
            windows=results,
            aggregate_sharpe=aggregate_sharpe,
            aggregate_pnl=aggregate_pnl,
            aggregate_dd=aggregate_dd,
            no_data_windows=no_data_windows,
        )

    def save_report(self, report: WFReport, filename: str) -> Path:
        self.output_dir.mkdir(parents=True, exist_ok=True)

        stem = Path(filename).stem
        json_path = self.output_dir / f"{stem}.json"
        csv_path = self.output_dir / f"{stem}.csv"

        payload = {
            "windows": [self._result_to_dict(r) for r in report.windows],
            "aggregate_sharpe": report.aggregate_sharpe,
            "aggregate_pnl": report.aggregate_pnl,
            "aggregate_dd": report.aggregate_dd,
            "no_data_windows": report.no_data_windows,
        }
        json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

        rows = []
        for result in report.windows:
            rows.append(
                {
                    "train_start": result.window.train_start.isoformat(),
                    "train_end": result.window.train_end.isoformat(),
                    "test_start": result.window.test_start.isoformat(),
                    "test_end": result.window.test_end.isoformat(),
                    "train_trades": result.train_trades,
                    "test_trades": result.test_trades,
                    "train_sharpe": result.train_sharpe,
                    "test_sharpe": result.test_sharpe,
                    "test_pnl": result.test_pnl,
                    "test_dd": result.test_dd,
                    "test_wr": result.test_wr,
                }
            )

        pd.DataFrame(rows).to_csv(csv_path, index=False)
        return json_path

    def _window_frames(self, window: WFWindow) -> Tuple[pd.DataFrame, pd.DataFrame]:
        data = self._load_symbol_data(getattr(self, "_active_symbol", "BTCUSDT"))
        if data.empty:
            return data, data

        train = data[(data["dt"] >= window.train_start) & (data["dt"] <= window.train_end)]
        test = data[(data["dt"] >= window.test_start) & (data["dt"] <= window.test_end)]
        return train, test

    def _load_symbol_data(self, symbol: str) -> pd.DataFrame:
        if symbol in self._symbol_data:
            return self._symbol_data[symbol]

        path = self.data_path / f"{symbol}.csv"
        if not path.exists():
            matches = list(self.data_path.glob(f"*{symbol}*.csv"))
            if not matches:
                self._symbol_data[symbol] = pd.DataFrame()
                return self._symbol_data[symbol]
            path = matches[0]

        bars = DataLoader.load_csv(str(path))
        if not bars:
            self._symbol_data[symbol] = pd.DataFrame()
            return self._symbol_data[symbol]

        df = pd.DataFrame(
            {
                "timestamp": [b.timestamp for b in bars],
                "close": [b.close for b in bars],
            }
        )
        df["dt"] = pd.to_datetime(df["timestamp"], unit="s").dt.date
        df = df.sort_values("timestamp").reset_index(drop=True)
        self._symbol_data[symbol] = df
        return df

    def _compute_metrics(self, df: pd.DataFrame) -> Dict[str, float]:
        if df.empty or len(df) < 2:
            return {"trades": 0, "sharpe": 0.0, "pnl": 0.0, "dd": 0.0, "wr": 0.0}

        closes = df["close"].astype(float)
        rets = closes.pct_change().dropna()

        trades = self._estimate_trade_count(rets)
        sharpe = self._sharpe(rets)
        pnl = float(closes.iloc[-1] - closes.iloc[0])
        dd = self._max_drawdown_pct(closes)
        wr = float((rets > 0).mean()) if len(rets) > 0 else 0.0

        return {
            "trades": int(trades),
            "sharpe": float(sharpe),
            "pnl": float(pnl),
            "dd": float(dd),
            "wr": float(wr),
        }

    def _estimate_trade_count(self, returns: pd.Series) -> int:
        if returns.empty:
            return 0

        signs = np.sign(returns.values)
        non_zero = signs[signs != 0]
        if len(non_zero) == 0:
            return 0

        changes = np.sum(non_zero[1:] != non_zero[:-1])
        return int(changes + 1)

    def _sharpe(self, returns: pd.Series) -> float:
        if returns.empty:
            return 0.0
        std = float(returns.std(ddof=0))
        if std == 0:
            return 0.0
        return float((returns.mean() / std) * np.sqrt(252.0))

    def _max_drawdown_pct(self, closes: pd.Series) -> float:
        equity = closes / closes.iloc[0]
        peak = equity.cummax()
        dd = (peak - equity) / peak
        return float(dd.max() * 100.0)

    def _result_to_dict(self, result: WFResult) -> Dict[str, object]:
        return {
            "window": {
                "start": result.window.start.isoformat(),
                "end": result.window.end.isoformat(),
                "train_start": result.window.train_start.isoformat(),
                "train_end": result.window.train_end.isoformat(),
                "test_start": result.window.test_start.isoformat(),
                "test_end": result.window.test_end.isoformat(),
            },
            "train_trades": result.train_trades,
            "test_trades": result.test_trades,
            "train_sharpe": result.train_sharpe,
            "test_sharpe": result.test_sharpe,
            "test_pnl": result.test_pnl,
            "test_dd": result.test_dd,
            "test_wr": result.test_wr,
        }
