"""Universe pair classifier — CORE vs MOVER classification.

Two pair classes:
    CORE   — high-liquidity majors: BTC, ETH, XRP, SOL, BNB and similar.
             These pairs have deep order books, tight spreads, and lower
             relative volatility. MR strategies work well here.

    MOVER  — high-activity, high-volatility altcoins: HYPE, PEPE, WIF, etc.
             These pairs can produce large directional moves. Trend strategies
             are preferred. Not every volatile pair qualifies — liquidity must
             still be adequate.

Classification is explicit and config-driven. The vol_ratio_mover_threshold
allows a CORE pair to be "upgraded" to MOVER if its realized vol dwarfs BTC.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class PairClass(str, Enum):
    CORE = "CORE"
    MOVER = "MOVER"


# ── Static classification table ──────────────────────────────────────────────

# Tier-1 majors: always CORE unless vol blows out
CORE_TIER1: frozenset[str] = frozenset({
    "BTCUSDT", "ETHUSDT", "XRPUSDT", "SOLUSDT",
    "BNBUSDT", "USDCUSDT", "BUSDUSDT", "USDTUSDT",
})

# Tier-2 majors: CORE by default, but easier to upgrade to MOVER
CORE_TIER2: frozenset[str] = frozenset({
    "ADAUSDT", "AVAXUSDT", "DOTUSDT", "LINKUSDT",
    "LTCUSDT", "BCHUSDT", "ATOMUSDT", "TRXUSDT",
    "NEARUSDT", "MATICUSDT", "UNIUSDT", "AAVEUSDT",
})

CORE_SYMBOLS: frozenset[str] = CORE_TIER1 | CORE_TIER2

# Default MOVER list (known high-beta expansion pairs)
DEFAULT_MOVERS: frozenset[str] = frozenset({
    "HYPESIMUSDT", "HYPEUSDT", "WIFUSDT", "PEPEUSDT",
    "BONKUSDT", "JUPUSDT", "TIAUSDT", "INJUSDT",
    "SUIUSDT", "APTUSDT", "SEIUSDT",
})


# ── Classifier ───────────────────────────────────────────────────────────────

@dataclass
class PairClassifier:
    """Classify a symbol as CORE or MOVER.

    Classification priority:
        1. If in DEFAULT_MOVERS → MOVER
        2. If vol_ratio_vs_btc > tier1_vol_upgrade_threshold → MOVER (even for CORE_TIER1)
        3. If in CORE_TIER1 → CORE
        4. If vol_ratio_vs_btc > tier2_vol_upgrade_threshold → MOVER
        5. If in CORE_TIER2 → CORE
        6. Default: MOVER (unknown pairs assumed volatile)
    """

    # A CORE_TIER1 pair must have vol > this multiple of BTC vol to become MOVER
    tier1_vol_upgrade_threshold: float = 3.0
    # A CORE_TIER2 pair needs less extreme vol to become MOVER
    tier2_vol_upgrade_threshold: float = 1.8

    def classify(self, symbol: str, vol_ratio_vs_btc: float = 1.0) -> PairClass:
        """Return CORE or MOVER for a symbol.

        Args:
            symbol: trading pair (e.g. "BTCUSDT")
            vol_ratio_vs_btc: realized_vol(symbol) / realized_vol(BTC).
                              Default 1.0 = same vol as BTC.
        """
        sym = symbol.upper().strip()

        if sym in DEFAULT_MOVERS:
            return PairClass.MOVER

        if sym in CORE_TIER1:
            if vol_ratio_vs_btc >= self.tier1_vol_upgrade_threshold:
                return PairClass.MOVER
            return PairClass.CORE

        if sym in CORE_TIER2:
            if vol_ratio_vs_btc >= self.tier2_vol_upgrade_threshold:
                return PairClass.MOVER
            return PairClass.CORE

        # Unknown symbol: classify as MOVER (conservative — assume volatile)
        if vol_ratio_vs_btc < 0.8:
            return PairClass.CORE  # Very calm unknown pair → treat as CORE
        return PairClass.MOVER

    def classify_batch(
        self,
        symbols: list[str],
        vol_ratios: dict[str, float] | None = None,
    ) -> dict[str, PairClass]:
        """Classify multiple symbols at once."""
        result: dict[str, PairClass] = {}
        vols = vol_ratios or {}
        for sym in symbols:
            result[sym] = self.classify(sym, vols.get(sym, 1.0))
        return result
