"""ARGUS v2.0 — Named constants. No magic numbers in the codebase."""

# ── System ────────────────────────────────────────────────────────
SYSTEM_NAME = "argus"
SYSTEM_VERSION = "2.5.0"

# ── Asset Classes ─────────────────────────────────────────────────
AC_CRYPTO = "crypto"
AC_US_EQUITY = "us_equity"
AC_COMMODITY = "commodity"
AC_INDEX = "index"
AC_BIST = "bist"
ALL_ASSET_CLASSES = (AC_CRYPTO, AC_US_EQUITY, AC_COMMODITY, AC_INDEX, AC_BIST)

# ── Execution Modes ──────────────────────────────────────────────
EXEC_AUTO = "auto"
EXEC_ADVISORY = "advisory"

# ── Regimes ───────────────────────────────────────────────────────
REGIME_TRENDING = "TRENDING"
REGIME_RANGING = "RANGING"
REGIME_VOLATILE = "VOLATILE"
REGIME_CRISIS = "CRISIS"
REGIME_TRANSITION = "TRANSITION"
ALL_REGIMES = (REGIME_TRENDING, REGIME_RANGING, REGIME_VOLATILE, REGIME_CRISIS, REGIME_TRANSITION)
DEFAULT_REGIME = REGIME_RANGING

# ── Engines ───────────────────────────────────────────────────────
ENGINE_TITAN = "TITAN"
ENGINE_NAUTILUS = "NAUTILUS"
ENGINE_PHOENIX = "PHOENIX"  # DEPRECATED — quarantined, not instantiated in pipeline
ENGINE_HERMES = "HERMES"
ENGINE_HYDRA = "HYDRA"
ENGINE_GEMINI = "GEMINI"
ENGINE_AEGEAN = "AEGEAN"
ENGINE_POSEIDON = "POSEIDON"

# ── Overlays ──────────────────────────────────────────────────────
OVERLAY_ATLAS = "ATLAS"
OVERLAY_SENTINEL = "SENTINEL"

# ── Kill Switch Levels ────────────────────────────────────────────
KS_NORMAL = 0
KS_CAUTION = 1
KS_DEFENSIVE = 2
KS_HALT = 3
KS_LOCKDOWN = 4

KS_LEVEL_NAMES = {
    KS_NORMAL: "NORMAL",
    KS_CAUTION: "CAUTION",
    KS_DEFENSIVE: "DEFENSIVE",
    KS_HALT: "HALT",
    KS_LOCKDOWN: "LOCKDOWN",
}

KS_SIZE_MULTIPLIERS = {
    KS_NORMAL: 1.0,
    KS_CAUTION: 0.75,
    KS_DEFENSIVE: 0.40,
    KS_HALT: 0.0,
    KS_LOCKDOWN: 0.0,
}

# ── HERMES Urgency Levels ────────────────────────────────────────
HERMES_LOW = "LOW"
HERMES_MEDIUM = "MEDIUM"
HERMES_HIGH = "HIGH"
HERMES_CRITICAL = "CRITICAL"

HERMES_ACTIONS = (
    "NONE",
    "BLOCK_ENTRY",
    "CLOSE_POSITION",
    "ADJUST_SL",
    "ADJUST_TP",
    "ALERT_ONLY",
)

# ── Sizing ────────────────────────────────────────────────────────
BASE_RISK_PCT = 0.02
MIN_RISK_PCT = 0.005
MAX_RISK_PCT = 0.03
MAX_POSITION_SIZE = 0.15
MAX_LEVERAGE = 2.0  # Conservative default (config can override up to 3.0)

# ── Stop Loss ─────────────────────────────────────────────────────
MIN_STOP = 0.01
MAX_STOP_CRYPTO = 0.05
MAX_STOP_STOCK = 0.08  # Stocks need wider stops
MAX_STOP_COMMODITY = 0.06

# ── Decision Actions ─────────────────────────────────────────────
ACTION_LONG = "long"
ACTION_SHORT = "short"
ACTION_HOLD = "hold"
ACTION_CLOSE_ALL = "close_all"
ACTION_REDUCE = "reduce"
ACTION_ADJUST_SL = "adjust_sl"
ACTION_ADJUST_TP = "adjust_tp"

# ── Sentinel Thresholds ──────────────────────────────────────────
SENTINEL_PROCEED = 0.7
SENTINEL_DEGRADED = 0.4
SENTINEL_HALT = 0.4
SENTINEL_EMERGENCY = 0.2

# ── MDE Gate Thresholds ──────────────────────────────────────────
MIN_CONFIDENCE = 0.55
MIN_NET_EXPECTED_RETURN = 0.001
MIN_REWARD_RISK_RATIO = 1.5

# ── Daily Limits ──────────────────────────────────────────────────
DAILY_SOFT_CAP = -0.015
DAILY_HARD_CAP = -0.025
MAX_TRADES_PER_DAY = 30

# ── Drawdown Thresholds ──────────────────────────────────────────
DD_CAUTION = 0.02
DD_DEFENSIVE = 0.04
DD_HALT = 0.06
DD_LOCKDOWN = 0.10

# ── Drawdown Multipliers ─────────────────────────────────────────
DD_MULTIPLIERS = {
    0.02: 1.0,   # DD < 2%
    0.04: 0.5,   # DD < 4%
    0.06: 0.25,  # DD < 6%
    1.00: 0.0,   # DD > 6%
}

# ── Portfolio Allocation Limits ───────────────────────────────────
MAX_CRYPTO_PCT = 0.50
MAX_EQUITY_PCT = 0.40
MAX_COMMODITY_PCT = 0.20
MIN_CASH_PCT = 0.10

# ── Pipeline Timing Budgets (ms) ─────────────────────────────────
BUDGET_DATA_ACQUISITION_MS = 500
BUDGET_SENTINEL_MS = 100
BUDGET_HERMES_MS = 2000
BUDGET_FEATURES_MS = 2000
BUDGET_REGIME_MS = 200
BUDGET_ENGINE_MS = 500
BUDGET_MDE_MS = 100
BUDGET_RISK_MS = 50
BUDGET_EXECUTION_MS = 5000
BUDGET_TOTAL_MS = 10000

# ── Regime Routing Map ────────────────────────────────────────────
REGIME_TO_ENGINE = {
    REGIME_TRENDING: ENGINE_TITAN,     # Dual-setup trend engine
    REGIME_RANGING: ENGINE_NAUTILUS,   # MR primary for sideways markets
    REGIME_VOLATILE: ENGINE_POSEIDON,  # MR Consortium for volatile markets
    REGIME_CRISIS: None,
}

# Secondary engines per regime (run after primary)
REGIME_TO_SECONDARY_ENGINES = {
    REGIME_TRENDING: [ENGINE_AEGEAN],  # Confirmation-only in trending
    REGIME_RANGING: [ENGINE_HYDRA],    # Scalper secondary for ranging
    REGIME_VOLATILE: [ENGINE_AEGEAN],
    REGIME_CRISIS: [],
}

# ── Feature Tiers ────────────────────────────────────────────────
TIER1_NAN_HALT_THRESHOLD = 5  # >5 Tier 1 NaN → halt all trading

# ── Guards ────────────────────────────────────────────────────────
CORRELATION_MAX = 0.6
FUNDING_SETTLEMENT_BLACKOUT_MIN = 15
WEEKEND_SIZE_MULT = 0.5
CONSECUTIVE_LOSS_COOLDOWN = 3
EQUITY_CURVE_MA_PERIOD = 20
SINGLE_TRADE_MAX_LOSS = 0.03

# ── Reconciler ────────────────────────────────────────────────────
RECONCILER_INTERVAL_S = 60

# ── Heartbeat ─────────────────────────────────────────────────────
HEARTBEAT_INTERVAL_S = 60

# ── HERMES News Fetch ─────────────────────────────────────────────
HERMES_FETCH_INTERVAL_S = 60
