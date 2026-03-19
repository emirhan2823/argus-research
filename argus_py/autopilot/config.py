from __future__ import annotations

from dataclasses import dataclass


@dataclass
class AutoPilotConfig:
    # Risk limits
    max_risk_per_trade_pct: float = 1.0
    max_equity_exposure: float = 1.0

    # Corse (Swing) settings
    corse_stop_pct: float = 8.0
    corse_trim_threshold_pct: float = 20.0
    corse_trailing_activation_pct: float = 5.0
    corse_trailing_distance_pct: float = 2.5

    # Pulse (Scalp) settings
    pulse_stop_pct: float = 5.0
    pulse_trim_threshold_pct: float = 10.0
    pulse_trailing_activation_pct: float = 3.0
    pulse_trailing_distance_pct: float = 1.5

    # Entry
    min_score_for_entry: float = 65.0
    min_confidence_pct: float = 40.0
