from typing import Final, Tuple

DECISION_VERDICTS: Final[set[str]] = {"GO", "WAIT", "EXIT", "SKIP"}
DECISION_DIRECTIONS: Final[set[str]] = {"LONG", "SHORT", "FLAT"}
DECISION_REGIMES: Final[set[str]] = {"TREND", "CHOP", "UNCERTAIN"}

TRADE_EVENTS: Final[set[str]] = {"OPEN", "CLOSE", "REJECTED"}

DECISION_HEADERS: Final[Tuple[str, ...]] = (
    "timestamp",
    "bar_ts",
    "symbol",
    "verdict",
    "direction",
    "score",
    "adx",
    "exp_move",
    "regime",
    "position_state",
)

TRADE_HEADERS: Final[Tuple[str, ...]] = (
    "timestamp",
    "symbol",
    "event",
    "side",
    "price",
    "quantity",
    "commission",
    "pnl",
    "position_id",
    "reject_reason",
)

REJECT_HEADERS: Final[Tuple[str, ...]] = (
    "timestamp",
    "bar_ts",
    "symbol",
    "code",
    "detail",
    "position_state",
    "risk_level",
)
