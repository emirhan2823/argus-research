from __future__ import annotations

from dataclasses import dataclass
from typing import List, Sequence
import math
import time

from argus_py.data.market_state import Bar


def _interval_to_seconds(interval: str) -> int:
    raw = str(interval or "1m").strip().lower()
    if raw.endswith("m"):
        return max(60, int(float(raw[:-1]) * 60))
    if raw.endswith("h"):
        return max(3600, int(float(raw[:-1]) * 3600))
    if raw.endswith("d"):
        return max(86400, int(float(raw[:-1]) * 86400))
    return 60


@dataclass(frozen=True)
class SentinelCheck:
    name: str
    passed: bool
    detail: str
    penalty: float


@dataclass(frozen=True)
class SentinelResult:
    score: float
    band: str
    reason: str
    checks: List[SentinelCheck]
    halt_new_entries: bool


class DataQualitySentinel:
    """
    Runtime data quality checker.

    Bands:
    - OK: score >= degraded_threshold
    - DEGRADED: halt threshold <= score < degraded threshold
    - HALT: score < halt threshold
    """

    def __init__(
        self,
        *,
        interval: str = "1m",
        max_staleness_mult: float = 4.0,
        max_gap_bps: float = 250.0,
        max_range_bps: float = 450.0,
        degraded_threshold: float = 0.70,
        halt_threshold: float = 0.40,
    ) -> None:
        self.interval_sec = _interval_to_seconds(interval)
        self.max_staleness_mult = max(1.0, float(max_staleness_mult))
        self.max_gap_bps = max(10.0, float(max_gap_bps))
        self.max_range_bps = max(10.0, float(max_range_bps))
        self.degraded_threshold = max(0.0, min(1.0, float(degraded_threshold)))
        self.halt_threshold = max(0.0, min(self.degraded_threshold, float(halt_threshold)))

    def evaluate(self, history: Sequence[Bar], *, now_ts: float | None = None) -> SentinelResult:
        if not history:
            return SentinelResult(
                score=0.0,
                band="HALT",
                reason="NO_BARS",
                checks=[SentinelCheck(name="history_non_empty", passed=False, detail="history is empty", penalty=1.0)],
                halt_new_entries=True,
            )
        now = float(now_ts if now_ts is not None else time.time())
        checks: List[SentinelCheck] = []
        bar = history[-1]

        checks.append(self._finite_ohlcv(bar))
        checks.append(self._ohlc_consistency(bar))
        checks.append(self._freshness(bar, now))
        checks.append(self._range_spike(bar))
        checks.append(self._gap_check(history))

        score = 1.0 - sum(c.penalty for c in checks if not c.passed)
        score = max(0.0, min(1.0, score))
        if score < self.halt_threshold:
            band = "HALT"
            halt = True
        elif score < self.degraded_threshold:
            band = "DEGRADED"
            halt = False
        else:
            band = "OK"
            halt = False

        failed = [c.name for c in checks if not c.passed]
        reason = "OK" if not failed else ",".join(failed)
        return SentinelResult(score=score, band=band, reason=reason, checks=checks, halt_new_entries=halt)

    def _finite_ohlcv(self, bar: Bar) -> SentinelCheck:
        values = [bar.open, bar.high, bar.low, bar.close, bar.volume]
        is_ok = all(math.isfinite(float(v)) for v in values)
        return SentinelCheck(
            name="finite_ohlcv",
            passed=is_ok,
            detail="all finite" if is_ok else "contains NaN/inf",
            penalty=0.65 if not is_ok else 0.0,
        )

    def _ohlc_consistency(self, bar: Bar) -> SentinelCheck:
        is_ok = (
            float(bar.high) >= max(float(bar.open), float(bar.close))
            and float(bar.low) <= min(float(bar.open), float(bar.close))
            and float(bar.high) >= float(bar.low)
        )
        return SentinelCheck(
            name="ohlc_consistency",
            passed=is_ok,
            detail="high/low envelope valid" if is_ok else "invalid high/low envelope",
            penalty=0.25 if not is_ok else 0.0,
        )

    def _freshness(self, bar: Bar, now_ts: float) -> SentinelCheck:
        age_sec = max(0.0, float(now_ts) - float(bar.timestamp))
        max_age = float(self.interval_sec) * self.max_staleness_mult
        is_ok = age_sec <= max_age
        return SentinelCheck(
            name="freshness",
            passed=is_ok,
            detail=f"age={age_sec:.1f}s max={max_age:.1f}s",
            penalty=0.35 if not is_ok else 0.0,
        )

    def _range_spike(self, bar: Bar) -> SentinelCheck:
        close = max(1e-9, abs(float(bar.close)))
        range_bps = ((float(bar.high) - float(bar.low)) / close) * 10000.0
        is_ok = range_bps <= self.max_range_bps
        return SentinelCheck(
            name="range_spike",
            passed=is_ok,
            detail=f"range_bps={range_bps:.2f} limit={self.max_range_bps:.2f}",
            penalty=0.10 if not is_ok else 0.0,
        )

    def _gap_check(self, history: Sequence[Bar]) -> SentinelCheck:
        if len(history) < 2:
            return SentinelCheck(name="gap_check", passed=True, detail="insufficient history", penalty=0.0)
        prev = history[-2]
        curr = history[-1]
        prev_close = max(1e-9, abs(float(prev.close)))
        gap_bps = abs(float(curr.close) - float(prev.close)) / prev_close * 10000.0
        is_ok = gap_bps <= self.max_gap_bps
        return SentinelCheck(
            name="gap_check",
            passed=is_ok,
            detail=f"gap_bps={gap_bps:.2f} limit={self.max_gap_bps:.2f}",
            penalty=0.20 if not is_ok else 0.0,
        )


__all__ = ["DataQualitySentinel", "SentinelCheck", "SentinelResult"]
