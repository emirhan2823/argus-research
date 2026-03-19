from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence

from argus_py.data.market_state import Bar

STRATEGY_ID = "TOPHUNTER_SHORT_V1"
TRIGGER_TYPE = "SWING_LOW_BREAK"
REGIME_FILTER = "ADX_LT_20"


@dataclass
class TopHunterSignal:
    decision: str
    direction: str
    reason_code: str
    reason: str
    tags: Dict[str, str]
    entry_price: Optional[float] = None
    stop_price: Optional[float] = None
    tp1_price: Optional[float] = None
    tp2_price: Optional[float] = None
    pivot_low: Optional[float] = None
    pivot_high: Optional[float] = None
    atr: Optional[float] = None


def _is_pivot_low(lows: Sequence[float], i: int, left: int, right: int) -> bool:
    base = lows[i]
    for k in range(1, left + 1):
        if base >= lows[i - k]:
            return False
    for k in range(1, right + 1):
        if base >= lows[i + k]:
            return False
    return True


def _is_pivot_high(highs: Sequence[float], i: int, left: int, right: int) -> bool:
    base = highs[i]
    for k in range(1, left + 1):
        if base <= highs[i - k]:
            return False
    for k in range(1, right + 1):
        if base <= highs[i + k]:
            return False
    return True


def detect_pivot_low_indices(bars: Sequence[Bar], left: int = 2, right: int = 2) -> List[int]:
    if len(bars) < left + right + 1:
        return []
    lows = [b.low for b in bars]
    out: List[int] = []
    for i in range(left, len(bars) - right):
        if _is_pivot_low(lows, i, left, right):
            out.append(i)
    return out


def detect_pivot_high_indices(bars: Sequence[Bar], left: int = 2, right: int = 2) -> List[int]:
    if len(bars) < left + right + 1:
        return []
    highs = [b.high for b in bars]
    out: List[int] = []
    for i in range(left, len(bars) - right):
        if _is_pivot_high(highs, i, left, right):
            out.append(i)
    return out


def latest_confirmed_pivot_low(
    bars: Sequence[Bar], left: int = 2, right: int = 2
) -> Optional[float]:
    idxs = detect_pivot_low_indices(bars, left=left, right=right)
    if not idxs:
        return None
    # We only trade on the latest closed bar; pivot must be behind it.
    latest = idxs[-1]
    return bars[latest].low


def latest_confirmed_pivot_high(
    bars: Sequence[Bar], left: int = 2, right: int = 2
) -> Optional[float]:
    idxs = detect_pivot_high_indices(bars, left=left, right=right)
    if not idxs:
        return None
    latest = idxs[-1]
    return bars[latest].high


def _atr14(bars: Sequence[Bar], period: int = 14) -> Optional[float]:
    if len(bars) < period + 1:
        return None
    tr_values: List[float] = []
    for i in range(1, len(bars)):
        cur = bars[i]
        prev = bars[i - 1]
        tr = max(cur.high - cur.low, abs(cur.high - prev.close), abs(cur.low - prev.close))
        tr_values.append(tr)
    tail = tr_values[-period:]
    if not tail:
        return None
    return sum(tail) / float(len(tail))


def evaluate_tophunter_short_v1(
    bars: Sequence[Bar],
    adx_value: float,
    max_adx: float = 20.0,
    left: int = 2,
    right: int = 2,
) -> TopHunterSignal:
    tags = {
        "strategy_id": STRATEGY_ID,
        "trigger_type": TRIGGER_TYPE,
        "regime_filter": REGIME_FILTER,
    }
    if len(bars) < left + right + 2:
        return TopHunterSignal(
            decision="NO_GO",
            direction="HOLD",
            reason_code="REJECT_INSUFFICIENT_DATA",
            reason="Not enough bars for pivot detection.",
            tags=tags,
        )
    if adx_value >= max_adx:
        return TopHunterSignal(
            decision="NO_GO",
            direction="HOLD",
            reason_code="REJECT_REGIME_ADX",
            reason=f"ADX {adx_value:.2f} >= {max_adx:.2f}",
            tags=tags,
        )

    pivot_low = latest_confirmed_pivot_low(bars, left=left, right=right)
    if pivot_low is None:
        return TopHunterSignal(
            decision="NO_GO",
            direction="HOLD",
            reason_code="REJECT_TRIGGER_NOT_MET",
            reason="No confirmed pivot low.",
            tags=tags,
        )

    entry = bars[-1].close
    if entry >= pivot_low:
        return TopHunterSignal(
            decision="NO_GO",
            direction="HOLD",
            reason_code="REJECT_TRIGGER_NOT_MET",
            reason=f"Close {entry:.2f} is not below pivot low {pivot_low:.2f}.",
            tags=tags,
            pivot_low=pivot_low,
        )

    pivot_high = latest_confirmed_pivot_high(bars, left=left, right=right)
    atr = _atr14(bars)
    atr_stop = (entry + 1.2 * atr) if atr is not None else (entry * 1.005)
    pivot_stop = pivot_high if pivot_high is not None else atr_stop
    stop = max(pivot_stop, atr_stop)
    if stop <= entry:
        stop = entry * 1.005
    r = stop - entry
    tp1 = entry - r
    tp2 = entry - (2.0 * r)

    return TopHunterSignal(
        decision="GO",
        direction="SELL",
        reason_code="OK",
        reason=f"1h pivot swing-low break confirmed ({entry:.2f} < {pivot_low:.2f}).",
        tags=tags,
        entry_price=entry,
        stop_price=stop,
        tp1_price=tp1,
        tp2_price=tp2,
        pivot_low=pivot_low,
        pivot_high=pivot_high,
        atr=atr,
    )

