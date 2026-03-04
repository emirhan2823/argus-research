"""SONAR v1 — Multi-asset universe trend scanner.

Scans top USDT perpetual pairs by volume, computes TrendScore (0-100),
and produces a ranked watchlist with capital allocation weights.

Flow:
    1. discover_universe() — merge Binance + BingX symbols, filter by volume
    2. scan(universe) — fetch OHLCV for top 30, compute TrendScore, rank
    3. Output: SonarWatchlist with top 5 watchlist, top 2 allocated
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import numpy as np

from src.features.market_structure import detect_swing_levels

LOG = logging.getLogger(__name__)


# ── Data contracts ────────────────────────────────────────────────────


@dataclass(frozen=True)
class SonarScore:
    """Trend score for a single symbol."""

    symbol: str
    trend_score: float          # 0-100
    adx_norm: float             # ADX normalized 0-100
    ema_slope_score: float      # EMA slope normalized 0-100
    structure_strength: float   # HH/HL or LL/LH count normalized 0-100
    atr_percentile: float       # ATR percentile 0-100
    volume_expansion: float     # Volume expansion normalized 0-100
    bias: str                   # "long" | "short" | "neutral"
    rank: int = 0


@dataclass(frozen=True)
class SonarWatchlist:
    """Scanner output: ranked watchlist with capital allocation."""

    watchlist: list[SonarScore]         # top N ranked
    allocated: list[str]                # symbols receiving capital
    allocations: dict[str, float]       # symbol -> weight (sums <= 1.0)
    scan_timestamp: datetime
    universe_size: int = 0
    flat_reason: str | None = None      # set when all below threshold


# ── Inline indicator helpers ──────────────────────────────────────────


def _ema(values: list[float], period: int) -> list[float]:
    """Compute EMA series from a list of floats."""
    if not values or period < 1:
        return []
    alpha = 2.0 / (period + 1)
    result = [values[0]]
    for i in range(1, len(values)):
        result.append(result[-1] * (1 - alpha) + values[i] * alpha)
    return result


def _atr_series(
    highs: list[float], lows: list[float], closes: list[float], period: int = 14,
) -> list[float]:
    """Compute ATR series using Wilder smoothing."""
    n = len(closes)
    if n < 2:
        return []
    tr = [highs[0] - lows[0]]
    for i in range(1, n):
        tr.append(max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1]),
        ))
    alpha = 1.0 / period
    atr = [tr[0]]
    for i in range(1, len(tr)):
        atr.append(atr[-1] * (1 - alpha) + tr[i] * alpha)
    return atr


def _compute_adx(
    highs: list[float], lows: list[float], closes: list[float], length: int = 14,
) -> float:
    """Compute latest ADX value from OHLC. Returns 0.0 if insufficient data."""
    n = len(closes)
    if n < length + 1:
        return 0.0

    h = np.array(highs, dtype=float)
    l = np.array(lows, dtype=float)
    c = np.array(closes, dtype=float)

    up_move = np.diff(h)
    down_move = -np.diff(l)

    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)

    tr = np.maximum(
        h[1:] - l[1:],
        np.maximum(np.abs(h[1:] - c[:-1]), np.abs(l[1:] - c[:-1])),
    )

    alpha = 1.0 / length
    atr_v = np.zeros(len(tr))
    plus_di_s = np.zeros(len(tr))
    minus_di_s = np.zeros(len(tr))
    atr_v[0], plus_di_s[0], minus_di_s[0] = tr[0], plus_dm[0], minus_dm[0]

    for i in range(1, len(tr)):
        atr_v[i] = atr_v[i - 1] * (1 - alpha) + tr[i] * alpha
        plus_di_s[i] = plus_di_s[i - 1] * (1 - alpha) + plus_dm[i] * alpha
        minus_di_s[i] = minus_di_s[i - 1] * (1 - alpha) + minus_dm[i] * alpha

    atr_safe = np.where(atr_v > 0, atr_v, 1e-10)
    plus_di = 100.0 * plus_di_s / atr_safe
    minus_di = 100.0 * minus_di_s / atr_safe
    di_sum = plus_di + minus_di
    di_sum_safe = np.where(di_sum > 0, di_sum, 1e-10)
    dx = 100.0 * np.abs(plus_di - minus_di) / di_sum_safe

    adx = np.zeros(len(dx))
    adx[0] = dx[0]
    for i in range(1, len(dx)):
        adx[i] = adx[i - 1] * (1 - alpha) + dx[i] * alpha

    return float(adx[-1])


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


# ── SONAR Scanner ─────────────────────────────────────────────────────


@dataclass
class SonarScanner:
    """Multi-asset trend scanner.

    Discovers top USDT perpetual pairs, scores them by trend strength,
    and produces a watchlist with capital allocation weights.
    """

    # Exchange clients (injected)
    binance_client: Any = None   # BinancePublicClient
    bingx_client: Any = None     # BingXPublicClient | None

    # Universe config
    universe_size: int = 100
    ohlcv_fetch_limit: int = 30     # fetch OHLCV for top 30 by volume only
    watchlist_size: int = 5
    allocate_top_n: int = 2
    min_trend_score: float = 30.0
    min_volume_usdt_24h: float = 50_000_000.0  # $50M

    # Timing
    scan_interval_seconds: int = 900  # 15 min

    # Scoring weights
    w_adx: float = 0.25
    w_ema_slope: float = 0.20
    w_structure: float = 0.25
    w_atr_pctl: float = 0.15
    w_volume: float = 0.15

    # OHLCV cache: symbol -> (monotonic_ts, highs, lows, closes, volumes)
    _ohlcv_cache: dict[str, tuple[float, list[float], list[float], list[float], list[float]]] = field(
        default_factory=dict, repr=False,
    )

    # ── Universe discovery ────────────────────────────────────────────

    def discover_universe(self) -> list[str]:
        """Fetch and merge perpetual symbols from Binance + BingX, ranked by volume.

        Returns top `universe_size` symbols sorted by 24h USDT volume descending.
        """
        volume_map: dict[str, float] = {}

        # Binance
        if self.binance_client is not None:
            try:
                tickers = self.binance_client.fetch_24h_tickers()
                info = self.binance_client.fetch_exchange_info()
                valid_symbols = {s["symbol"] for s in info}
                for t in tickers:
                    sym = t["symbol"]
                    if sym in valid_symbols:
                        volume_map[sym] = max(volume_map.get(sym, 0.0), t["volume_usdt"])
            except Exception as exc:
                LOG.warning("SONAR Binance discovery failed: %s", exc)

        # BingX
        if self.bingx_client is not None:
            try:
                bx_tickers = self.bingx_client.fetch_all_tickers()
                bx_symbols = {s["symbol"] for s in self.bingx_client.fetch_all_symbols()}
                for t in bx_tickers:
                    sym = t["symbol"]
                    if sym in bx_symbols and sym.endswith("USDT"):
                        volume_map[sym] = max(volume_map.get(sym, 0.0), t["volume_usdt"])
            except Exception as exc:
                LOG.warning("SONAR BingX discovery failed: %s", exc)

        # Filter and sort
        qualified = [
            (sym, vol) for sym, vol in volume_map.items()
            if vol >= self.min_volume_usdt_24h
        ]
        qualified.sort(key=lambda x: x[1], reverse=True)

        universe = [sym for sym, _ in qualified[:self.universe_size]]
        LOG.info("SONAR universe: %d qualified out of %d total", len(universe), len(volume_map))
        return universe

    # ── Scanning ──────────────────────────────────────────────────────

    def scan(self, universe: list[str]) -> SonarWatchlist:
        """Score top symbols and produce ranked watchlist.

        Only fetches OHLCV for top `ohlcv_fetch_limit` symbols (by position
        in universe, which is already volume-sorted). Uses cache to avoid
        duplicate fetches within scan interval.
        """
        now = time.monotonic()
        candidates_to_score = universe[:self.ohlcv_fetch_limit]

        scores: list[SonarScore] = []
        for symbol in candidates_to_score:
            ohlcv = self._fetch_ohlcv_cached(symbol, now)
            if ohlcv is None:
                continue
            highs, lows, closes, volumes = ohlcv
            if len(closes) < 30:
                continue
            score = self._score_symbol(symbol, highs, lows, closes, volumes)
            scores.append(score)

        # Rank by trend_score descending
        scores.sort(key=lambda s: s.trend_score, reverse=True)
        ranked = [
            SonarScore(
                symbol=s.symbol,
                trend_score=s.trend_score,
                adx_norm=s.adx_norm,
                ema_slope_score=s.ema_slope_score,
                structure_strength=s.structure_strength,
                atr_percentile=s.atr_percentile,
                volume_expansion=s.volume_expansion,
                bias=s.bias,
                rank=i + 1,
            )
            for i, s in enumerate(scores)
        ]

        watchlist = ranked[:self.watchlist_size]

        # Allocate capital to top N that exceed threshold
        eligible = [s for s in ranked[:self.allocate_top_n] if s.trend_score >= self.min_trend_score]

        if not eligible:
            return SonarWatchlist(
                watchlist=watchlist,
                allocated=[],
                allocations={s.symbol: 0.0 for s in watchlist},
                scan_timestamp=datetime.now(timezone.utc),
                universe_size=len(universe),
                flat_reason="all_below_threshold",
            )

        total_score = sum(s.trend_score for s in eligible)
        allocations: dict[str, float] = {}
        for s in eligible:
            allocations[s.symbol] = s.trend_score / total_score if total_score > 0 else 0.0

        return SonarWatchlist(
            watchlist=watchlist,
            allocated=[s.symbol for s in eligible],
            allocations=allocations,
            scan_timestamp=datetime.now(timezone.utc),
            universe_size=len(universe),
        )

    # ── Scoring ───────────────────────────────────────────────────────

    def _score_symbol(
        self,
        symbol: str,
        highs: list[float],
        lows: list[float],
        closes: list[float],
        volumes: list[float],
    ) -> SonarScore:
        """Compute TrendScore (0-100) for a single symbol."""

        # ADX normalized (0-100)
        adx = _compute_adx(highs, lows, closes, length=14)
        adx_norm = _clamp(adx / 60.0, 0.0, 1.0) * 100.0

        # EMA slope score (0-100)
        ema21 = _ema(closes, 21)
        ema55 = _ema(closes, 55)
        if len(ema21) >= 5 and len(ema55) >= 5:
            ema21_slope = (ema21[-1] - ema21[-5]) / max(abs(ema21[-5]), 1e-10)
            ema55_slope = (ema55[-1] - ema55[-5]) / max(abs(ema55[-5]), 1e-10)
            # Combined slope strength
            slope_mag = abs(ema21_slope) + abs(ema55_slope)
            ema_slope_score = _clamp(slope_mag / 0.05, 0.0, 1.0) * 100.0
        else:
            ema_slope_score = 0.0

        # Structure strength (0-100): count consecutive HH/HL or LL/LH
        structure_strength, detected_bias = self._compute_structure_score(highs, lows)

        # ATR percentile (0-100)
        atr_vals = _atr_series(highs, lows, closes, period=14)
        if len(atr_vals) >= 20:
            tail = atr_vals[-100:] if len(atr_vals) >= 100 else atr_vals
            current_atr = tail[-1]
            pctl = sum(1 for v in tail if v < current_atr) / len(tail)
            atr_percentile = pctl * 100.0
        else:
            atr_percentile = 50.0

        # Volume expansion (0-100)
        if len(volumes) >= 20:
            vol_sma = sum(volumes[-20:]) / 20.0
            vol_ratio = volumes[-1] / max(vol_sma, 1e-10)
            volume_expansion = _clamp(vol_ratio / 3.0, 0.0, 1.0) * 100.0
        else:
            volume_expansion = 50.0

        # Determine bias
        ema_bias = "neutral"
        if len(ema21) > 0 and len(ema55) > 0:
            if ema21[-1] > ema55[-1]:
                ema_bias = "long"
            elif ema21[-1] < ema55[-1]:
                ema_bias = "short"

        if ema_bias == "long" and detected_bias == "long":
            bias = "long"
        elif ema_bias == "short" and detected_bias == "short":
            bias = "short"
        else:
            bias = "neutral"

        # Weighted composite
        trend_score = (
            self.w_adx * adx_norm
            + self.w_ema_slope * ema_slope_score
            + self.w_structure * structure_strength
            + self.w_atr_pctl * atr_percentile
            + self.w_volume * volume_expansion
        )
        trend_score = _clamp(trend_score, 0.0, 100.0)

        return SonarScore(
            symbol=symbol,
            trend_score=trend_score,
            adx_norm=adx_norm,
            ema_slope_score=ema_slope_score,
            structure_strength=structure_strength,
            atr_percentile=atr_percentile,
            volume_expansion=volume_expansion,
            bias=bias,
        )

    def _compute_structure_score(
        self, highs: list[float], lows: list[float],
    ) -> tuple[float, str]:
        """Count consecutive HH/HL or LL/LH patterns. Returns (score 0-100, bias)."""
        levels = detect_swing_levels(highs=highs, lows=lows, window=5)

        swing_highs = sorted(
            [lv for lv in levels if lv.level_type == "resistance"],
            key=lambda lv: lv.bar_index,
        )
        swing_lows = sorted(
            [lv for lv in levels if lv.level_type == "support"],
            key=lambda lv: lv.bar_index,
        )

        if len(swing_highs) < 2 or len(swing_lows) < 2:
            return 0.0, "neutral"

        # Count consecutive HH/HL (long) and LL/LH (short)
        hh_count = 0
        for i in range(1, len(swing_highs)):
            if swing_highs[i].price > swing_highs[i - 1].price:
                hh_count += 1
            else:
                hh_count = 0

        hl_count = 0
        for i in range(1, len(swing_lows)):
            if swing_lows[i].price > swing_lows[i - 1].price:
                hl_count += 1
            else:
                hl_count = 0

        ll_count = 0
        for i in range(1, len(swing_lows)):
            if swing_lows[i].price < swing_lows[i - 1].price:
                ll_count += 1
            else:
                ll_count = 0

        lh_count = 0
        for i in range(1, len(swing_highs)):
            if swing_highs[i].price < swing_highs[i - 1].price:
                lh_count += 1
            else:
                lh_count = 0

        long_str = min(hh_count, hl_count)   # Both needed for uptrend
        short_str = min(ll_count, lh_count)   # Both needed for downtrend

        if long_str >= short_str and long_str > 0:
            # Normalize: 4+ consecutive = 100
            score = _clamp(long_str / 4.0, 0.0, 1.0) * 100.0
            return score, "long"
        elif short_str > 0:
            score = _clamp(short_str / 4.0, 0.0, 1.0) * 100.0
            return score, "short"
        return 0.0, "neutral"

    # ── OHLCV fetching with cache ─────────────────────────────────────

    def _fetch_ohlcv_cached(
        self, symbol: str, now_mono: float,
    ) -> tuple[list[float], list[float], list[float], list[float]] | None:
        """Fetch 100-bar 1h OHLCV with simple TTL cache."""
        cached = self._ohlcv_cache.get(symbol)
        if cached is not None:
            cached_at, h, l, c, v = cached
            if (now_mono - cached_at) < self.scan_interval_seconds:
                return h, l, c, v

        # Try Binance first, fallback to BingX
        rows = self._fetch_ohlcv_raw(symbol)
        if not rows:
            return None

        highs = [float(r[2]) for r in rows]
        lows = [float(r[3]) for r in rows]
        closes = [float(r[4]) for r in rows]
        volumes = [float(r[5]) for r in rows]

        self._ohlcv_cache[symbol] = (now_mono, highs, lows, closes, volumes)
        return highs, lows, closes, volumes

    def _fetch_ohlcv_raw(self, symbol: str) -> list[list[Any]]:
        """Fetch raw OHLCV from best available exchange."""
        if self.binance_client is not None:
            try:
                rows = self.binance_client.fetch_ohlcv(
                    symbol=symbol, timeframe="1h", limit=100,
                )
                if rows:
                    return rows
            except Exception:
                pass

        if self.bingx_client is not None:
            try:
                rows = self.bingx_client.fetch_ohlcv(
                    symbol=symbol, timeframe="1h", limit=100,
                )
                if rows:
                    return rows
            except Exception:
                pass

        return []
