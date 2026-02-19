"""Hyper-Precision entry/exit decision helpers (PR-J01, CAI Pivot 5).

Pure functions only -- NO broker calls, NO side effects.
All inputs are primitives; all outputs are frozen dataclasses.
"""

from __future__ import annotations

from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Module-level tuneable constants
# ---------------------------------------------------------------------------
OBI_THRESHOLD: float = 0.60          # minimum |OBI| to qualify for limit entry
SPREAD_RATIO_LIMIT: float = 2.0     # spread_pct / median_spread_pct ceiling
VWAP_LIMIT_BAND_PCT: float = 0.003  # 0.3 % -- band around VWAP for limit pricing

DEFAULT_TIMEOUT_BARS: int = 3
CRITICAL_TIMEOUT_BARS: int = 1

EXIT_OBI_REVERSAL_THRESHOLD: float = 0.30  # |OBI| reversal threshold for exit


# ---------------------------------------------------------------------------
# Result contracts (GR-6: frozen dataclasses)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class PrecisionEntryResult:
    """Decision produced by :func:`snipe_entry`."""
    order_type: str       # "limit" | "market" | "skip"
    price: float | None   # optimal limit price (None if skip)
    timeout_bars: int     # how many bars to wait
    reason: str


@dataclass(frozen=True)
class PrecisionExitResult:
    """Decision produced by :func:`snipe_partial_exit`."""
    order_type: str       # "limit" | "market"
    price: float | None
    timeout_bars: int
    reason: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _directional_obi_ok(obi: float | None, direction: str) -> bool:
    """Return True when OBI is directionally favourable and above threshold.

    LONG  needs obi > +OBI_THRESHOLD   (buyers dominating)
    SHORT needs obi < -OBI_THRESHOLD   (sellers dominating)
    """
    if obi is None:
        return False
    if direction == "LONG":
        return obi >= OBI_THRESHOLD
    # SHORT
    return obi <= -OBI_THRESHOLD


def _exit_obi_reversal(obi: float | None, direction: str) -> bool:
    """Return True when OBI has reversed against the position direction.

    For exiting a LONG we want sellers dominating  (obi < -threshold).
    For exiting a SHORT we want buyers dominating  (obi > +threshold).
    """
    if obi is None:
        return False
    if direction == "LONG":
        return obi <= -EXIT_OBI_REVERSAL_THRESHOLD
    # SHORT
    return obi >= EXIT_OBI_REVERSAL_THRESHOLD


def _spread_is_wide(spread_pct: float, median_spread_pct: float) -> bool:
    """Return True if the current spread is abnormally wide."""
    if median_spread_pct <= 0:
        return True
    return spread_pct / median_spread_pct > SPREAD_RATIO_LIMIT


def _limit_price_for_entry(
    direction: str,
    current_price: float,
    vwap_dev_pct: float,
) -> float:
    """Compute a favourable limit price at the VWAP band edge.

    The idea: place the limit *inside* the VWAP band on the side that
    favours the direction so we get filled near the mean-reversion edge.

    LONG  -> place limit slightly below current price (VWAP band lower edge)
    SHORT -> place limit slightly above current price (VWAP band upper edge)
    """
    band = VWAP_LIMIT_BAND_PCT
    if direction == "LONG":
        # We want a cheaper fill; offset down by the band width
        return current_price * (1.0 - band)
    # SHORT: we want a higher fill; offset up by the band width
    return current_price * (1.0 + band)


def _timeout_for_urgency(urgency: str) -> int:
    if urgency == "CRITICAL":
        return CRITICAL_TIMEOUT_BARS
    return DEFAULT_TIMEOUT_BARS


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def snipe_entry(
    *,
    direction: str,           # "LONG" | "SHORT"
    target_price: float,
    current_price: float,
    obi: float | None,        # orderbook imbalance [-1, 1]
    vwap_dev_pct: float,      # VWAP deviation %
    spread_pct: float,        # current spread %
    median_spread_pct: float, # median spread for comparison
    atr_pct: float,           # ATR as % of price
    urgency: str = "NORMAL",  # "LOW" | "NORMAL" | "HIGH" | "CRITICAL"
) -> PrecisionEntryResult:
    """Attempt limit-order entry on 1m timeframe.

    Logic:
      1. Check directional OBI >= 0.60 on 1m bar.
      2. Place limit at VWAP band edge if spread is reasonable.
      3. Timeout: 3 bars default, 1 for CRITICAL.
      4. Grade "skip" if OBI insufficient and urgency is LOW/NORMAL.
      5. Fall back to "market" if OBI insufficient but urgency is HIGH/CRITICAL.
    """
    if direction not in ("LONG", "SHORT"):
        raise ValueError(f"direction must be LONG or SHORT, got {direction}")
    if urgency not in ("LOW", "NORMAL", "HIGH", "CRITICAL"):
        raise ValueError(f"urgency must be LOW|NORMAL|HIGH|CRITICAL, got {urgency}")

    timeout = _timeout_for_urgency(urgency)
    obi_ok = _directional_obi_ok(obi, direction)
    wide_spread = _spread_is_wide(spread_pct, median_spread_pct)

    # --- Happy path: OBI is directionally favourable ---
    if obi_ok:
        if wide_spread:
            # OBI good but spread too wide -- still place limit, but note it
            limit_px = _limit_price_for_entry(direction, current_price, vwap_dev_pct)
            return PrecisionEntryResult(
                order_type="limit",
                price=round(limit_px, 8),
                timeout_bars=timeout,
                reason="obi_ok_wide_spread_limit",
            )
        limit_px = _limit_price_for_entry(direction, current_price, vwap_dev_pct)
        return PrecisionEntryResult(
            order_type="limit",
            price=round(limit_px, 8),
            timeout_bars=timeout,
            reason="obi_ok_limit",
        )

    # --- OBI insufficient ---
    if urgency in ("LOW", "NORMAL"):
        return PrecisionEntryResult(
            order_type="skip",
            price=None,
            timeout_bars=0,
            reason="obi_insufficient_low_urgency",
        )

    # HIGH / CRITICAL with bad OBI -> market order fallback
    return PrecisionEntryResult(
        order_type="market",
        price=None,
        timeout_bars=timeout,
        reason="obi_insufficient_high_urgency_market",
    )


def snipe_partial_exit(
    *,
    direction: str,           # "LONG" | "SHORT"
    pct_to_close: float,      # 0.25 typically
    current_price: float,
    obi: float | None,
    vwap_dev_pct: float,
    spread_pct: float,
    median_spread_pct: float,
    urgency: str = "NORMAL",
) -> PrecisionExitResult:
    """Attempt limit partial close.  Wait for OBI reversal.

    When selling a LONG we want sellers appearing (obi goes negative).
    When covering a SHORT we want buyers appearing (obi goes positive).
    If OBI reversal is detected and spread is reasonable, use a limit order.
    Otherwise fall back to market.
    """
    if direction not in ("LONG", "SHORT"):
        raise ValueError(f"direction must be LONG or SHORT, got {direction}")
    if urgency not in ("LOW", "NORMAL", "HIGH", "CRITICAL"):
        raise ValueError(f"urgency must be LOW|NORMAL|HIGH|CRITICAL, got {urgency}")

    timeout = _timeout_for_urgency(urgency)
    reversal = _exit_obi_reversal(obi, direction)
    wide_spread = _spread_is_wide(spread_pct, median_spread_pct)

    if reversal and not wide_spread:
        # Place limit at favourable VWAP band edge for exit
        # Exit direction is opposite of position direction
        exit_dir = "SHORT" if direction == "LONG" else "LONG"
        limit_px = _limit_price_for_entry(exit_dir, current_price, vwap_dev_pct)
        return PrecisionExitResult(
            order_type="limit",
            price=round(limit_px, 8),
            timeout_bars=timeout,
            reason="obi_reversal_limit_exit",
        )

    # Fallback: market order
    return PrecisionExitResult(
        order_type="market",
        price=None,
        timeout_bars=timeout,
        reason="no_reversal_market_exit",
    )


def compute_trailing_sl(
    *,
    direction: str,           # "LONG" | "SHORT"
    current_price: float,
    atr: float,               # ATR in price units (3m ATR)
    trailing_mult: float,     # from DynamicExitState (e.g. 2.0, 1.2)
    current_sl: float | None, # existing SL price
) -> float:
    """Recompute trailing SL using 3m ATR.  Only moves favourably.

    LONG : SL = current_price - atr * trailing_mult  (only moves UP)
    SHORT: SL = current_price + atr * trailing_mult  (only moves DOWN)
    """
    if direction not in ("LONG", "SHORT"):
        raise ValueError(f"direction must be LONG or SHORT, got {direction}")

    if direction == "LONG":
        candidate = current_price - atr * trailing_mult
        if current_sl is None:
            return candidate
        return max(candidate, current_sl)  # only ratchet up
    else:
        candidate = current_price + atr * trailing_mult
        if current_sl is None:
            return candidate
        return min(candidate, current_sl)  # only ratchet down
