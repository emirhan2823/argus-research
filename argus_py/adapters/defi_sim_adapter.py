from __future__ import annotations

import hashlib
import math
import time
from typing import List

from argus_py.adapters.contracts import (
    MarketRequest,
    OrderRequest,
    OrderResult,
    PositionSnapshot,
)
from argus_py.data.market_state import Bar


def _interval_to_sec(interval: str) -> int:
    text = str(interval or "1m").strip().lower()
    if text.endswith("m"):
        return max(60, int(float(text[:-1]) * 60))
    if text.endswith("h"):
        return max(3600, int(float(text[:-1]) * 3600))
    if text.endswith("d"):
        return max(86400, int(float(text[:-1]) * 86400))
    return 60


def _seed(key: str) -> int:
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]
    return int(digest, 16)


class DefiSimAdapter:
    """
    Deterministic DeFi simulator backend.
    Produces higher-volatility synthetic bars.
    Orders/positions still flow through paper broker.
    """

    adapter_id = "defi_sim_adapter_v2"
    asset_class = "defi"

    def __init__(self, broker, venue_id: str = "defi_sim_paper") -> None:
        self.broker = broker
        self.venue_id = str(venue_id or "defi_sim_paper")

    def fetch_klines(self, request: MarketRequest) -> List[Bar]:
        symbol = str(request.symbol).upper()
        interval_sec = _interval_to_sec(request.interval)
        limit = max(1, int(request.limit))
        now_ts = float(request.now_ts) if request.now_ts is not None else time.time()
        end_ts = int(now_ts // interval_sec) * interval_sec

        seed = _seed(f"defi:{symbol}:{request.interval}")
        base = 1.0 + ((seed % 1900) / 120.0)
        drift = ((seed % 19) - 9) * 0.0009
        amp_1 = 0.015 + ((seed % 13) * 0.0010)
        amp_2 = 0.010 + ((seed % 11) * 0.0008)

        bars: List[Bar] = []
        for idx in range(limit):
            ts = float(end_ts - (limit - idx) * interval_sec)
            step = int(ts // interval_sec)
            series_idx = idx - (limit - 1)
            pulse = 1.0 + (((step + seed) % 37) == 0) * 0.025

            wave = (amp_1 * math.sin((step + (seed % 101)) / 7.0)) + (amp_2 * math.cos((step + (seed % 83)) / 13.0))
            trend = drift * series_idx
            close = max(0.01, base * (1.0 + trend + wave) * pulse)

            prev_step = step - 1
            prev_series_idx = series_idx - 1
            prev_pulse = 1.0 + (((prev_step + seed) % 37) == 0) * 0.025
            prev_wave = (amp_1 * math.sin((prev_step + (seed % 101)) / 7.0)) + (
                amp_2 * math.cos((prev_step + (seed % 83)) / 13.0)
            )
            prev_close = max(0.01, base * (1.0 + (drift * prev_series_idx) + prev_wave) * prev_pulse)
            spread = max(0.001, close * (0.003 + ((seed % 7) * 0.0005)))

            bars.append(
                Bar(
                    timestamp=ts,
                    open=prev_close,
                    high=max(close, prev_close) + spread,
                    low=max(0.001, min(close, prev_close) - spread),
                    close=close,
                    volume=12000.0 + float(((seed // 17) + step * 89) % 9000),
                )
            )
        return bars

    def submit_order(self, request: OrderRequest) -> OrderResult:
        accepted, reason = self.broker.execute_strategy(
            symbol=request.symbol,
            decision=request.decision,
            direction=request.direction,
            price=float(request.price),
            timestamp=float(request.timestamp),
            risk_pct=float(request.risk_pct),
            leverage=float(request.leverage),
            custom_sl_price=request.custom_sl_price,
            custom_tp_price=request.custom_tp_price,
        )
        oid = None
        if accepted and getattr(self.broker, "trades", None):
            oid = f"defisim:{int(time.time() * 1000)}:{len(self.broker.trades)}"
        return OrderResult(accepted=bool(accepted), reason=str(reason), venue_order_id=oid)

    def get_position(self, symbol: str) -> PositionSnapshot:
        pos = getattr(self.broker, "details", {}).get(symbol)
        if pos is None:
            return PositionSnapshot(symbol=symbol, qty=0.0, side="FLAT", entry_price=0.0)
        return PositionSnapshot(
            symbol=symbol,
            qty=float(getattr(pos, "quantity", 0.0)),
            side=str(getattr(pos, "side", "FLAT")).upper(),
            entry_price=float(getattr(pos, "entry_price", 0.0)),
        )
