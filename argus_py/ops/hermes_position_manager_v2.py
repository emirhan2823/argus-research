from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional


@dataclass(frozen=True)
class HermesPositionOutcome:
    handled: bool
    action: str
    reason: str
    stop_price: Optional[float] = None
    tp_price: Optional[float] = None


class HermesPositionManagerV2:
    """
    Applies HERMES sentiment actions to existing open positions.

    Actions:
    - CLOSE_POSITION when sentiment is critical negative.
    - ADJUST_SL when sentiment is strong negative.
    - ADJUST_TP when sentiment is strong positive.
    """

    def __init__(self, broker: Any) -> None:
        self.broker = broker

    def decide_action(self, sentiment_score: float, urgency: str) -> str:
        score = float(sentiment_score)
        urg = str(urgency or "LOW").upper()
        if score <= -80.0 and urg in {"CRITICAL", "HIGH", "MEDIUM", "LOW"}:
            return "CLOSE_POSITION"
        if score <= -55.0 and urg in {"CRITICAL", "HIGH", "MEDIUM"}:
            return "ADJUST_SL"
        if score >= 65.0 and urg in {"CRITICAL", "HIGH", "MEDIUM"}:
            return "ADJUST_TP"
        return "HOLD"

    def apply(
        self,
        *,
        symbol: str,
        sentiment_score: float,
        urgency: str,
        market_price: float,
        timestamp: float,
    ) -> HermesPositionOutcome:
        action = self.decide_action(sentiment_score=sentiment_score, urgency=urgency)
        if action == "HOLD":
            return HermesPositionOutcome(handled=False, action=action, reason="no_action")

        positions = getattr(self.broker, "details", {})
        pos = positions.get(symbol) if isinstance(positions, dict) else None
        if pos is None:
            return HermesPositionOutcome(handled=False, action=action, reason="position_not_found")

        if action == "CLOSE_POSITION":
            if hasattr(self.broker, "_close_position"):
                self.broker._close_position(symbol, float(market_price), "HERMES", float(timestamp))
                return HermesPositionOutcome(handled=True, action=action, reason="position_closed")
            if hasattr(self.broker, "close_position"):
                self.broker.close_position(symbol=symbol, reason="hermes_close_position")
                return HermesPositionOutcome(handled=True, action=action, reason="position_closed")
            return HermesPositionOutcome(handled=False, action=action, reason="close_not_supported")

        side = str(getattr(pos, "side", "BUY")).upper()
        if action == "ADJUST_SL":
            if side == "BUY":
                stop_price = float(market_price) * 0.997
            else:
                stop_price = float(market_price) * 1.003
            if hasattr(pos, "sl_price"):
                pos.sl_price = stop_price
                return HermesPositionOutcome(
                    handled=True,
                    action=action,
                    reason="stop_adjusted",
                    stop_price=stop_price,
                )
            if hasattr(self.broker, "modify_stop_loss"):
                self.broker.modify_stop_loss(symbol=symbol, stop_price=stop_price)
                return HermesPositionOutcome(
                    handled=True,
                    action=action,
                    reason="stop_adjusted",
                    stop_price=stop_price,
                )
            return HermesPositionOutcome(handled=False, action=action, reason="stop_adjust_not_supported")

        if action == "ADJUST_TP":
            if side == "BUY":
                tp_price = float(market_price) * 1.012
            else:
                tp_price = float(market_price) * 0.988
            if hasattr(pos, "tp_price"):
                pos.tp_price = tp_price
                return HermesPositionOutcome(
                    handled=True,
                    action=action,
                    reason="tp_adjusted",
                    tp_price=tp_price,
                )
            if hasattr(self.broker, "modify_take_profit"):
                self.broker.modify_take_profit(symbol=symbol, tp_price=tp_price)
                return HermesPositionOutcome(
                    handled=True,
                    action=action,
                    reason="tp_adjusted",
                    tp_price=tp_price,
                )
            return HermesPositionOutcome(handled=False, action=action, reason="tp_adjust_not_supported")

        return HermesPositionOutcome(handled=False, action=action, reason="unsupported_action")


def urgency_from_score(sentiment_score: float) -> str:
    score = abs(float(sentiment_score))
    if score >= 80.0:
        return "CRITICAL"
    if score >= 60.0:
        return "HIGH"
    if score >= 40.0:
        return "MEDIUM"
    return "LOW"


__all__ = ["HermesPositionManagerV2", "HermesPositionOutcome", "urgency_from_score"]
