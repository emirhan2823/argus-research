from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple


class CorrelationBucket(Enum):
    BTC_ECOSYSTEM = "BTC_ECOSYSTEM"
    ETH_ECOSYSTEM = "ETH_ECOSYSTEM"
    ALTCOIN_MAJOR = "ALTCOIN_MAJOR"
    ALTCOIN_MID = "ALTCOIN_MID"
    STABLECOIN = "STABLECOIN"


@dataclass
class SymbolConfig:
    symbol: str
    enabled: bool = True
    max_position_pct: float = 20.0
    bucket: CorrelationBucket = CorrelationBucket.ALTCOIN_MID
    min_score_for_entry: float = 65.0
    priority: int = 1


@dataclass
class PortfolioLimits:
    max_total_exposure_pct: float = 100.0
    max_correlated_exposure_pct: float = 40.0
    max_open_positions: int = 5
    max_daily_trades: int = 10
    min_cash_reserve_pct: float = 10.0


@dataclass
class PortfolioState:
    positions: Dict[str, float] = field(default_factory=dict)
    cash: float = 0.0
    total_equity: float = 0.0
    exposure_by_bucket: Dict[str, float] = field(default_factory=dict)
    daily_trades: int = 0
    daily_pnl: float = 0.0


@dataclass
class AllocationDecision:
    symbol: str
    action: str
    target_allocation_pct: float
    current_allocation_pct: float
    reason: str
    blocked_by: Optional[str] = None


class PortfolioManager:
    """
    Multi-symbol portfolio manager with correlation awareness.

    Responsibilities:
    - Track positions across multiple symbols
    - Enforce portfolio-level limits
    - Rebalance based on signals
    - Prevent over-concentration in correlated assets
    """

    def __init__(self, symbols: List[SymbolConfig], limits: PortfolioLimits = None):
        self.symbols = {s.symbol: s for s in symbols}
        self.limits = limits or PortfolioLimits()
        self.state = PortfolioState()

    def update_state(self, positions: Dict[str, float], cash: float) -> None:
        self.state.positions = dict(positions)
        self.state.cash = float(cash)
        self.state.total_equity = float(sum(positions.values()) + cash)

        self.state.exposure_by_bucket = {}
        for symbol, value in positions.items():
            if symbol in self.symbols:
                bucket = self.symbols[symbol].bucket.value
                self.state.exposure_by_bucket[bucket] = self.state.exposure_by_bucket.get(bucket, 0.0) + float(value)

    def can_open_position(self, symbol: str, value: float) -> Tuple[bool, str]:
        if symbol not in self.symbols:
            return False, "Symbol not configured"

        config = self.symbols[symbol]

        if symbol in self.state.positions:
            return False, "Already in position"

        if len(self.state.positions) >= self.limits.max_open_positions:
            return False, f"Max positions ({self.limits.max_open_positions}) reached"

        if self.state.daily_trades >= self.limits.max_daily_trades:
            return False, "Max daily trades reached"

        min_cash = self.state.total_equity * (self.limits.min_cash_reserve_pct / 100.0)
        if self.state.cash - value < min_cash:
            return False, "Would violate cash reserve"

        max_position = self.state.total_equity * (config.max_position_pct / 100.0)
        if value > max_position:
            return False, f"Exceeds max position size ({config.max_position_pct}%)"

        new_exposure = sum(self.state.positions.values()) + value
        max_exposure = self.state.total_equity * (self.limits.max_total_exposure_pct / 100.0)
        if new_exposure > max_exposure:
            return False, "Would exceed total exposure limit"

        bucket = config.bucket.value
        current_bucket = self.state.exposure_by_bucket.get(bucket, 0.0)
        max_bucket = self.state.total_equity * (self.limits.max_correlated_exposure_pct / 100.0)
        if current_bucket + value > max_bucket:
            return False, f"Would exceed {bucket} correlation limit"

        return True, "OK"

    def rank_opportunities(self, signals: Dict[str, float]) -> List[AllocationDecision]:
        decisions: List[AllocationDecision] = []

        for symbol, score in signals.items():
            if symbol not in self.symbols:
                continue

            config = self.symbols[symbol]
            if not config.enabled:
                continue

            if score < config.min_score_for_entry:
                decisions.append(
                    AllocationDecision(
                        symbol=symbol,
                        action="SKIP",
                        target_allocation_pct=0.0,
                        current_allocation_pct=0.0,
                        reason=f"Score {score:.0f} < {config.min_score_for_entry}",
                    )
                )
                continue

            target_pct = min(config.max_position_pct, score / 5.0)
            current_pct = (
                (self.state.positions.get(symbol, 0.0) / self.state.total_equity) * 100.0
                if self.state.total_equity > 0
                else 0.0
            )

            allowed, reason = self.can_open_position(symbol, self.state.total_equity * target_pct / 100.0)

            decisions.append(
                AllocationDecision(
                    symbol=symbol,
                    action="BUY" if allowed else "HOLD",
                    target_allocation_pct=target_pct,
                    current_allocation_pct=current_pct,
                    reason=f"Score: {score:.0f}",
                    blocked_by=None if allowed else reason,
                )
            )

        decisions.sort(
            key=lambda d: (
                self.symbols.get(d.symbol, SymbolConfig(d.symbol)).priority,
                -signals.get(d.symbol, 0.0),
            )
        )

        return decisions
