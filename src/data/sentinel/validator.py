"""ARGUS v2.0 — Sentinel data quality validator.

6 checks (asset-class aware):
1. Data staleness: any source > 2x expected interval
2. Price anomaly: price move > 3 sigma without volume confirmation
3. Spread blowout: spread > 5x normal
4. Exchange latency: response time > 2s
5. Orderbook depth: depth < 30% normal within 5% of mid (crypto only)
6. Funding flash spike: funding > 10x normal (crypto only)

For non-crypto assets, checks 5 and 6 are skipped.
Score = checks_passed / total_applicable_checks.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

from src.core.constants import (
    AC_CRYPTO,
    SENTINEL_DEGRADED,
    SENTINEL_EMERGENCY,
    SENTINEL_HALT,
    SENTINEL_PROCEED,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SentinelCheckResult:
    """Result of a single sentinel check."""

    check_name: str
    passed: bool
    detail: str


@dataclass(frozen=True)
class SentinelReport:
    """Aggregated sentinel validation report."""

    asset_class: str
    symbol: str
    score: float  # 0.0 to 1.0
    checks: tuple[SentinelCheckResult, ...]
    action: str  # "PROCEED" | "DEGRADED" | "HALT" | "EMERGENCY"
    confidence_penalty: float  # 0.0 or 0.3 for degraded
    timestamp: datetime


@dataclass
class SentinelInput:
    """Input data bundle for sentinel validation."""

    symbol: str
    asset_class: str
    last_candle_time: datetime
    expected_interval: timedelta  # e.g. timedelta(hours=1) for 1h candles
    current_price: float
    previous_prices: list[float]  # last N prices for sigma calculation
    current_volume: float
    avg_volume: float  # rolling average volume
    spread_pct: float  # current bid-ask spread as %
    normal_spread_pct: float  # historical average spread
    exchange_latency_ms: float  # last API response time in ms
    # Crypto-only fields (None for non-crypto)
    orderbook_depth_pct: Optional[float] = None  # depth as % of normal
    funding_rate: Optional[float] = None
    normal_funding_rate: Optional[float] = None
    now: Optional[datetime] = None  # injectable for testing


class SentinelValidator:
    """Data quality gate — runs 6 checks before pipeline proceeds.

    For non-crypto assets, checks 5 (orderbook depth) and 6 (funding spike)
    are skipped. Score is checks_passed / total_applicable_checks.
    """

    # Configurable thresholds
    STALENESS_FACTOR: float = 2.0
    PRICE_ANOMALY_SIGMA: float = 3.0
    VOLUME_CONFIRMATION_RATIO: float = 1.5
    SPREAD_BLOWOUT_FACTOR: float = 5.0
    LATENCY_THRESHOLD_MS: float = 2000.0
    DEPTH_COLLAPSE_PCT: float = 0.30
    FUNDING_SPIKE_FACTOR: float = 10.0

    def validate(self, inp: SentinelInput) -> SentinelReport:
        """Run all applicable checks and return a scored report."""
        now = inp.now or datetime.utcnow()
        checks: list[SentinelCheckResult] = []

        # Check 1: Data staleness
        checks.append(self._check_staleness(inp, now))

        # Check 2: Price anomaly
        checks.append(self._check_price_anomaly(inp))

        # Check 3: Spread blowout
        checks.append(self._check_spread(inp))

        # Check 4: Exchange latency
        checks.append(self._check_latency(inp))

        # Check 5: Orderbook depth (crypto only)
        if inp.asset_class == AC_CRYPTO:
            checks.append(self._check_orderbook_depth(inp))

        # Check 6: Funding flash spike (crypto only)
        if inp.asset_class == AC_CRYPTO:
            checks.append(self._check_funding_spike(inp))

        # Calculate score
        total = len(checks)
        passed = sum(1 for c in checks if c.passed)
        score = passed / total if total > 0 else 0.0

        # Determine action and confidence penalty
        action, penalty = self._score_to_action(score)

        report = SentinelReport(
            asset_class=inp.asset_class,
            symbol=inp.symbol,
            score=score,
            checks=tuple(checks),
            action=action,
            confidence_penalty=penalty,
            timestamp=now,
        )

        if action != "PROCEED":
            logger.warning(
                "Sentinel %s for %s %s: score=%.2f, failed=[%s]",
                action,
                inp.asset_class,
                inp.symbol,
                score,
                ", ".join(c.check_name for c in checks if not c.passed),
            )

        return report

    # ── Individual Checks ──────────────────────────────────────────

    def _check_staleness(self, inp: SentinelInput, now: datetime) -> SentinelCheckResult:
        """Check 1: Data staleness — any source > 2x expected interval."""
        elapsed = now - inp.last_candle_time
        threshold = inp.expected_interval * self.STALENESS_FACTOR
        passed = elapsed <= threshold
        detail = f"elapsed={elapsed}, threshold={threshold}"
        return SentinelCheckResult(check_name="staleness", passed=passed, detail=detail)

    def _check_price_anomaly(self, inp: SentinelInput) -> SentinelCheckResult:
        """Check 2: Price move > 3 sigma without volume confirmation."""
        if len(inp.previous_prices) < 2:
            return SentinelCheckResult(
                check_name="price_anomaly",
                passed=True,
                detail="insufficient history",
            )

        mean = sum(inp.previous_prices) / len(inp.previous_prices)
        variance = sum((p - mean) ** 2 for p in inp.previous_prices) / len(
            inp.previous_prices
        )
        std = variance**0.5

        if std == 0:
            return SentinelCheckResult(
                check_name="price_anomaly", passed=True, detail="zero std"
            )

        z_score = abs(inp.current_price - mean) / std
        volume_confirmed = inp.current_volume > (
            inp.avg_volume * self.VOLUME_CONFIRMATION_RATIO
        )

        # Anomaly = large move WITHOUT volume confirmation
        is_anomaly = z_score > self.PRICE_ANOMALY_SIGMA and not volume_confirmed
        passed = not is_anomaly
        detail = f"z={z_score:.2f}, vol_confirmed={volume_confirmed}"
        return SentinelCheckResult(
            check_name="price_anomaly", passed=passed, detail=detail
        )

    def _check_spread(self, inp: SentinelInput) -> SentinelCheckResult:
        """Check 3: Spread > 5x normal."""
        if inp.normal_spread_pct <= 0:
            return SentinelCheckResult(
                check_name="spread_blowout", passed=True, detail="no baseline"
            )

        ratio = inp.spread_pct / inp.normal_spread_pct
        passed = ratio <= self.SPREAD_BLOWOUT_FACTOR
        detail = f"ratio={ratio:.2f}x"
        return SentinelCheckResult(
            check_name="spread_blowout", passed=passed, detail=detail
        )

    def _check_latency(self, inp: SentinelInput) -> SentinelCheckResult:
        """Check 4: Exchange latency > 2s."""
        passed = inp.exchange_latency_ms <= self.LATENCY_THRESHOLD_MS
        detail = f"latency={inp.exchange_latency_ms:.0f}ms"
        return SentinelCheckResult(
            check_name="exchange_latency", passed=passed, detail=detail
        )

    def _check_orderbook_depth(self, inp: SentinelInput) -> SentinelCheckResult:
        """Check 5: Orderbook depth < 30% normal (crypto only)."""
        if inp.orderbook_depth_pct is None:
            return SentinelCheckResult(
                check_name="orderbook_depth", passed=True, detail="no data"
            )

        passed = inp.orderbook_depth_pct >= self.DEPTH_COLLAPSE_PCT
        detail = f"depth={inp.orderbook_depth_pct:.2%}"
        return SentinelCheckResult(
            check_name="orderbook_depth", passed=passed, detail=detail
        )

    def _check_funding_spike(self, inp: SentinelInput) -> SentinelCheckResult:
        """Check 6: Funding rate > 10x normal (crypto only)."""
        if inp.funding_rate is None or inp.normal_funding_rate is None:
            return SentinelCheckResult(
                check_name="funding_spike", passed=True, detail="no data"
            )

        if inp.normal_funding_rate == 0:
            return SentinelCheckResult(
                check_name="funding_spike", passed=True, detail="zero baseline"
            )

        ratio = abs(inp.funding_rate) / abs(inp.normal_funding_rate)
        passed = ratio <= self.FUNDING_SPIKE_FACTOR
        detail = f"ratio={ratio:.1f}x"
        return SentinelCheckResult(
            check_name="funding_spike", passed=passed, detail=detail
        )

    # ── Scoring ────────────────────────────────────────────────────

    @staticmethod
    def _score_to_action(score: float) -> tuple[str, float]:
        """Map sentinel score to action and confidence penalty.

        Returns:
            (action, confidence_penalty)
        """
        if score < SENTINEL_EMERGENCY:
            return "EMERGENCY", 1.0  # close all
        if score < SENTINEL_HALT:
            return "HALT", 1.0  # no new trades
        if score < SENTINEL_PROCEED:
            return "DEGRADED", 0.30  # reduce confidence by 30%
        return "PROCEED", 0.0
