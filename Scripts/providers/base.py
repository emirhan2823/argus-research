"""Provider abstractions for historical OHLCV backfill tooling."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
import logging
import time
from typing import Any

import requests

LOG = logging.getLogger(__name__)

INTERVAL_MS: dict[str, int] = {
    "1m": 60_000,
    "3m": 180_000,
    "5m": 300_000,
    "15m": 900_000,
    "30m": 1_800_000,
    "1h": 3_600_000,
    "2h": 7_200_000,
    "4h": 14_400_000,
    "6h": 21_600_000,
    "8h": 28_800_000,
    "12h": 43_200_000,
    "1d": 86_400_000,
}


class ProviderError(RuntimeError):
    """Base exception for provider failures."""


class ProviderCircuitOpenError(ProviderError):
    """Raised when provider circuit breaker is open."""


@dataclass(frozen=True)
class OHLCVRow:
    """Normalized OHLCV row in milliseconds UTC."""

    timestamp_ms: int
    open: float
    high: float
    low: float
    close: float
    volume: float
    close_time_ms: int | None = None
    quote_volume: float | None = None
    num_trades: int | None = None
    taker_buy_volume: float | None = None
    taker_buy_quote_volume: float | None = None


class OHLCVProvider(ABC):
    """Base provider with deterministic retry/backoff and circuit breaker."""

    name: str = "base"
    max_limit: int = 1000

    def __init__(
        self,
        *,
        timeout: float = 20.0,
        max_retries: int = 5,
        backoff_base: float = 1.0,
        max_backoff: float = 30.0,
        rate_limit_sleep: float = 0.2,
        breaker_failures: int = 5,
        breaker_cooldown_seconds: float = 60.0,
    ) -> None:
        self.timeout = float(timeout)
        self.max_retries = max(1, int(max_retries))
        self.backoff_base = float(backoff_base)
        self.max_backoff = float(max_backoff)
        self.rate_limit_sleep = max(0.0, float(rate_limit_sleep))
        self.breaker_failures = max(1, int(breaker_failures))
        self.breaker_cooldown_seconds = max(1.0, float(breaker_cooldown_seconds))
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "ArgusV2.5-Backfill/StageB"})

        self._consecutive_failures = 0
        self._breaker_open_until = 0.0

    @abstractmethod
    def fetch_ohlcv(
        self,
        *,
        symbol: str,
        timeframe: str,
        start_ts: int,
        end_ts: int,
        limit: int,
    ) -> list[OHLCVRow]:
        """Fetch normalized OHLCV rows in [start_ts, end_ts)."""

    def _refresh_session(self, *, reason: str) -> None:
        try:
            self.session.close()
        except Exception:
            pass
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "ArgusV2.5-Backfill/StageB"})
        LOG.debug("[%s] session refreshed reason=%s", self.name, reason)

    def _deterministic_jitter(self, attempt: int) -> float:
        # Deterministic jitter in [0.0, 0.249] to keep retries reproducible.
        seed = (attempt * 7919 + len(self.name) * 101) % 250
        return seed / 1000.0

    def _backoff_delay(self, attempt: int) -> float:
        return min(self.max_backoff, self.backoff_base * (2 ** (attempt - 1)) + self._deterministic_jitter(attempt))

    def _record_failure(self, *, attempt: int, error: Exception) -> None:
        self._consecutive_failures += 1
        if self._consecutive_failures >= self.breaker_failures:
            self._breaker_open_until = time.monotonic() + self.breaker_cooldown_seconds
            LOG.error(
                "[%s] circuit opened failures=%d cooldown=%.2fs",
                self.name,
                self._consecutive_failures,
                self.breaker_cooldown_seconds,
            )
        LOG.warning(
            "[%s] request failed attempt=%d/%d failures=%d error=%s",
            self.name,
            attempt,
            self.max_retries,
            self._consecutive_failures,
            error,
        )
        self._refresh_session(reason="request_error")

    def _record_success(self) -> None:
        if self._consecutive_failures > 0:
            LOG.info("[%s] recovered after %d failure(s)", self.name, self._consecutive_failures)
        self._consecutive_failures = 0
        self._breaker_open_until = 0.0

    def _request_json(self, *, url: str, params: dict[str, Any]) -> Any:
        now = time.monotonic()
        if now < self._breaker_open_until:
            remaining = self._breaker_open_until - now
            raise ProviderCircuitOpenError(
                f"[{self.name}] circuit breaker open for {remaining:.2f}s"
            )

        for attempt in range(1, self.max_retries + 1):
            try:
                response = self.session.get(url, params=params, timeout=self.timeout)
                if response.status_code in (429, 418):
                    retry_after_raw = response.headers.get("Retry-After", "1")
                    try:
                        retry_after = float(retry_after_raw)
                    except ValueError:
                        retry_after = 1.0
                    sleep_s = max(retry_after, self._backoff_delay(attempt))
                    LOG.warning(
                        "[%s] rate-limit status=%d sleep=%.2fs attempt=%d/%d",
                        self.name,
                        response.status_code,
                        sleep_s,
                        attempt,
                        self.max_retries,
                    )
                    time.sleep(sleep_s)
                    continue

                if response.status_code >= 500:
                    raise requests.HTTPError(
                        f"server_error_{response.status_code}",
                        response=response,
                    )

                response.raise_for_status()
                payload = response.json()
                self._record_success()
                if self.rate_limit_sleep > 0:
                    time.sleep(self.rate_limit_sleep)
                return payload

            except (requests.RequestException, ValueError) as exc:
                self._record_failure(attempt=attempt, error=exc)
                if attempt >= self.max_retries:
                    raise ProviderError(f"[{self.name}] request failed: {exc}") from exc
                time.sleep(self._backoff_delay(attempt))

        raise ProviderError(f"[{self.name}] exhausted retries")
