"""ARGUS v6 — Engine Role Registry.

Canonical mapping of each engine to its trading ROLE, derived from source code
analysis of every engine's docstring, indicators, and signal logic.

Usage:
    from src.regime.engine_roles import ENGINE_ROLES, ROLE_TREND, is_mr_engine
"""

from __future__ import annotations

from src.core.constants import (
    ENGINE_AEGEAN,
    ENGINE_GEMINI,
    ENGINE_HERMES,
    ENGINE_HYDRA,
    ENGINE_NAUTILUS,
    ENGINE_PHOENIX,
    ENGINE_POSEIDON,
    ENGINE_TITAN,
)

# ── Role constants ──────────────────────────────────────────────────
ROLE_TREND = "TREND"            # Trend-following / breakout
ROLE_MEAN_REVERSION = "MR"      # Mean reversion / oscillator-based
ROLE_SCALP = "SCALP"            # High-frequency scalping
ROLE_CARRY = "CARRY"            # Funding / basis harvest
ROLE_SENTIMENT = "SENTIMENT"    # News / sentiment driven
ROLE_PAIRS = "PAIRS"            # Statistical arbitrage / pairs
ROLE_HYBRID = "HYBRID"          # Multi-regime adaptive

# ── Engine → Role mapping ──────────────────────────────────────────
# Derived from source code analysis:
#
# POSEIDON: docstring = "Mean Reversion Consortium", uses 9 oscillators
#           (BB%B, RSI, CCI, WillR, VWAP dev, CMF, WaveTrend, HARSI,
#            Entropy SuperTrend), produces STRONG/NORMAL/WEAK MR grades.
#           CONCLUSION: Mean Reversion engine.
#
# TITAN:   docstring = "trend-follow and breakout for TRENDING regime",
#           requires ADX≥35, uses EMA21/55 alignment + price_vs_ma200,
#           breakout via BB%B≥0.95 + volume spike.
#           CONCLUSION: Trend engine.
#
# AEGEAN:  docstring = "Exponential RSI + Momentum Linear Regression Channel",
#           regime-switching parameters, works TRENDING/RANGING/VOLATILE,
#           MTF trend filter (EMA-200 on HTF), momentum continuation in
#           TRENDING, mean-reversion in RANGING.
#           CONCLUSION: Hybrid engine.
#
# NAUTILUS: docstring = "mean reversion for RANGING regime",
#           BB reversion + funding reversion + micro reversion,
#           ADX<25 gate, RANGING only.
#           CONCLUSION: Mean Reversion engine (range specialist).
#
# HYDRA:   docstring = "high-frequency scalping for RANGING/low-vol",
#           tight stops (1.5x ATR), quick targets (0.6%), BB + RSI +
#           orderbook imbalance + volume delta, ADX<25.
#           CONCLUSION: Scalp engine.
#
# PHOENIX: docstring = "carry/basis opportunities",
#           funding harvest + basis trade + carry proxy.
#           CONCLUSION: Carry engine.
#
# HERMES:  docstring = "sentiment-driven signals and veto actions",
#           news sentiment score + urgency, veto/override capability.
#           CONCLUSION: Sentiment engine.
#
# GEMINI:  docstring = "correlation-based pairs trading",
#           spread z-score + cointegration, single-leg signals.
#           CONCLUSION: Pairs engine.

ENGINE_ROLES: dict[str, str] = {
    ENGINE_POSEIDON: ROLE_MEAN_REVERSION,
    ENGINE_TITAN:    ROLE_TREND,
    ENGINE_AEGEAN:   ROLE_HYBRID,
    ENGINE_NAUTILUS:  ROLE_MEAN_REVERSION,
    ENGINE_HYDRA:    ROLE_SCALP,
    ENGINE_PHOENIX:  ROLE_CARRY,
    ENGINE_HERMES:   ROLE_SENTIMENT,
    ENGINE_GEMINI:   ROLE_PAIRS,
}


# ── Convenience sets ────────────────────────────────────────────────
TREND_ENGINES = frozenset(
    e for e, r in ENGINE_ROLES.items() if r == ROLE_TREND
)

MR_ENGINES = frozenset(
    e for e, r in ENGINE_ROLES.items() if r == ROLE_MEAN_REVERSION
)

SCALP_ENGINES = frozenset(
    e for e, r in ENGINE_ROLES.items() if r == ROLE_SCALP
)

# MR + Scalp = all "ranging-focused" engines
RANGING_ENGINES = MR_ENGINES | SCALP_ENGINES

# Trend + Hybrid = all "trend-capable" engines
TREND_CAPABLE_ENGINES = TREND_ENGINES | frozenset(
    e for e, r in ENGINE_ROLES.items() if r == ROLE_HYBRID
)


# ── Helpers ─────────────────────────────────────────────────────────
def is_mr_engine(engine: str) -> bool:
    return ENGINE_ROLES.get(engine) in (ROLE_MEAN_REVERSION, ROLE_SCALP)


def is_trend_engine(engine: str) -> bool:
    return ENGINE_ROLES.get(engine) == ROLE_TREND


def is_trend_capable(engine: str) -> bool:
    return engine in TREND_CAPABLE_ENGINES


def get_role(engine: str) -> str:
    return ENGINE_ROLES.get(engine, "UNKNOWN")
