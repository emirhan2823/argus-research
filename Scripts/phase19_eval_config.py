
# Canonical Evaluation Config for Phase 19.7

# Cost Model (Basis Points)
# Used to calculate Net Returns from raw price moves.
COST_MODEL = {
    "fee_bps": 4.0,       # Exchange Fee (Taker)
    "slippage_bps": 2.0,  # Estimated Slippage
    "spread_bps": 1.0     # Bid-Ask Spread
}

# Evaluation Horizons (Minutes)
# H5: Scalp reaction
# H15: Standard trade duration
# H60: Trend continuation / structural validation
HORIZONS = [5, 15, 60]

DEFAULT_H = 15

# Gate Definitions for Attribution
GATES = ["MIN_ADX", "ROUTER_DEFENSE", "MAX_EXP", "OTHER"]
