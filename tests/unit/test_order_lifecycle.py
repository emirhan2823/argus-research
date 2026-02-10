from __future__ import annotations

from pathlib import Path
import sys

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from argus_py.execution.order_lifecycle import (
    OrderLifecycleState,
    OrderLifecycleStateMachine,
)


def test_order_lifecycle_happy_path_and_terminal_behavior() -> None:
    sm = OrderLifecycleStateMachine()
    rec = sm.ensure("oid-1", "BTCUSDT", 1.0)
    assert rec.state == OrderLifecycleState.ROUTED
    assert len(rec.events) == 2

    rec = sm.transition("oid-1", exchange_status="ACCEPTED", filled_qty=0.0, avg_price=0.0)
    assert rec.state == OrderLifecycleState.ACCEPTED

    rec = sm.transition("oid-1", exchange_status="PARTIAL", filled_qty=0.4, avg_price=101.0)
    assert rec.state == OrderLifecycleState.PARTIAL
    assert rec.filled_qty == 0.4

    rec = sm.transition("oid-1", exchange_status="FILLED", filled_qty=1.0, avg_price=102.0)
    assert rec.state == OrderLifecycleState.FILLED
    assert sm.is_terminal(rec.state) is True
    event_count = len(rec.events)

    rec2 = sm.transition("oid-1", exchange_status="CANCELED", filled_qty=1.0, avg_price=102.0)
    assert rec2.state == OrderLifecycleState.FILLED
    assert len(rec2.events) == event_count


def test_order_lifecycle_rejected_stays_terminal_and_unknown_raises() -> None:
    sm = OrderLifecycleStateMachine()
    sm.ensure("oid-2", "ETHUSDT", 2.0)
    rec = sm.transition("oid-2", exchange_status="REJECTED", filled_qty=0.0, avg_price=0.0, reason="venue reject")
    assert rec.state == OrderLifecycleState.REJECTED
    assert sm.is_terminal(rec.state) is True

    rec2 = sm.transition("oid-2", exchange_status="ACCEPTED", filled_qty=0.0, avg_price=0.0)
    assert rec2.state == OrderLifecycleState.REJECTED

    with pytest.raises(KeyError):
        sm.transition("unknown", exchange_status="FILLED", filled_qty=1.0, avg_price=100.0)

