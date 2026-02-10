from __future__ import annotations

import asyncio
import json
import sqlite3
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from argus_py.core.event_bus import EventBus, EventType
from argus_py.data.market_state import Bar
from argus_py.execution import (
    ExecutionEngineV2,
    ExecutionIntent,
    ExchangeOrder,
    ExecutionRealismModel,
    OrderSide,
    UrgencyLevel,
)
from argus_py.learning.chiron import ChironLearningEngine, LearningSample
from argus_py.models.aether.aether_c import AetherCEngine, AetherCInputs
from argus_py.models.atlas.atlas_c import AtlasCEngine, AtlasCInputs
from argus_py.models.hermes.hermes_c import HermesCEngine
from argus_py.ops.incident_manager import IncidentManager, IncidentSeverity
from argus_py.regime.classifier import MarketRegime, MarketRegimeClassifier
from argus_py.risk.correlation import CorrelationRiskMonitor
from argus_py.strategy.lifecycle import StrategyLifecycleManager, StrategyPerformanceSnapshot, StrategyState
from argus_py.telemetry.metrics_warehouse import MetricsWarehouse, make_metric_point


@dataclass(frozen=True)
class V2MarketSnapshot:
    regime_v2: str
    regime_legacy: str
    regime_confidence: float
    regime_reason: str
    atlas_score: float
    aether_score: float
    hermes_score: float


class _PaperBrokerGateway:
    """Adapter to reuse PaperBroker through ExecutionEngineV2 contract."""

    def __init__(self, broker):
        self.broker = broker

    def place_order(self, intent: ExecutionIntent) -> ExchangeOrder:
        market_price = float(intent.metadata.get("market_price") or intent.limit_price or 0.0)
        timestamp = float(intent.metadata.get("timestamp") or time.time())
        risk_pct = float(intent.metadata.get("risk_pct") or 0.0)
        direction = "BUY" if intent.side == OrderSide.BUY else "SELL"

        success, _reason = self.broker.execute_strategy(
            symbol=intent.symbol,
            decision="GO",
            direction=direction,
            price=market_price,
            timestamp=timestamp,
            risk_pct=risk_pct,
            leverage=1.0,
            custom_sl_price=intent.stop_loss,
            custom_tp_price=intent.take_profit,
        )

        if not success:
            return ExchangeOrder(
                order_id=f"paper_rej_{uuid.uuid4().hex[:10]}",
                status="REJECTED",
                filled_qty=0.0,
                avg_price=market_price,
                side=intent.side,
                symbol=intent.symbol,
            )

        pos = self.broker.details.get(intent.symbol)
        if pos is None:
            return ExchangeOrder(
                order_id=f"paper_missing_{uuid.uuid4().hex[:10]}",
                status="REJECTED",
                filled_qty=0.0,
                avg_price=market_price,
                side=intent.side,
                symbol=intent.symbol,
            )

        return ExchangeOrder(
            order_id=f"paper_{pos.position_id}",
            status="FILLED",
            filled_qty=float(pos.quantity),
            avg_price=float(pos.entry_price),
            side=intent.side,
            symbol=intent.symbol,
        )

    def place_stop_loss(self, symbol: str, side: OrderSide, qty: float, stop_price: float) -> str:
        # Paper broker already stores bracket SL when opening position.
        return f"paper_sl_{symbol}_{side.value}_{qty:.6f}_{stop_price:.4f}"

    def get_position_qty(self, symbol: str) -> float:
        pos = self.broker.details.get(symbol)
        if pos is None:
            return 0.0
        qty = float(pos.quantity)
        return qty if str(pos.side).upper() == "BUY" else -qty


class V2RuntimeBridge:
    """Incremental runtime bridge for MODE=v2 without breaking legacy path."""

    def __init__(self, cfg: Dict[str, Any], run_dir: Path, broker) -> None:
        self.cfg = dict(cfg)
        self.run_dir = Path(run_dir)
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.events_path = self.run_dir / "events_v2.jsonl"
        self.runbook_path = self.run_dir / "v2_runtime_state.json"

        self.bus = EventBus()
        self.event_counts: Dict[str, int] = {}
        self.last_market: Optional[V2MarketSnapshot] = None
        self.last_lifecycle_action: str = "KEEP"
        self.last_lifecycle_reason: str = "N/A"
        self.lifecycle_state: StrategyState = StrategyState.PAPER
        self.last_execution_profile: Dict[str, Any] = {}

        self.regime_classifier = MarketRegimeClassifier()
        self.atlas_engine = AtlasCEngine()
        self.aether_engine = AetherCEngine()
        self.hermes_engine = HermesCEngine()
        self.chiron = ChironLearningEngine()
        self.lifecycle = StrategyLifecycleManager()
        self.correlation = CorrelationRiskMonitor()
        self.incidents = IncidentManager(self.run_dir / "incidents")
        self.warehouse = MetricsWarehouse(
            redis_url=self.cfg.get("redis_url"),
            warm_dir=self.run_dir / "warehouse" / "warm",
            cold_db=self.run_dir / "warehouse" / "cold" / "metrics.sqlite3",
        )

        self._exec_gateway = _PaperBrokerGateway(broker)
        self.execution = ExecutionEngineV2(
            self._exec_gateway,
            realism_model=ExecutionRealismModel(),
        )
        self.metric_tags_base = {
            "mode": "v2",
            "asset_class": str(self.cfg.get("asset_class", "crypto")),
            "venue_id": str(self.cfg.get("venue_id", "auto")),
        }

        # Subscribe one wildcard writer so every event is persisted.
        asyncio.run(self.bus.subscribe(self._persist_event, None))

    def compute_market_snapshot(self, history: List[Bar]) -> Optional[V2MarketSnapshot]:
        if len(history) < 30:
            return None

        regime = self.regime_classifier.classify(history)
        legacy_regime = self._map_regime(regime.regime)

        closes = np.array([float(b.close) for b in history[-240:]], dtype=float)
        vols = np.array([float(b.volume) for b in history[-240:]], dtype=float)
        highs = np.array([float(b.high) for b in history[-240:]], dtype=float)
        lows = np.array([float(b.low) for b in history[-240:]], dtype=float)

        atlas_inputs = self._atlas_inputs(closes, vols)
        atlas = self.atlas_engine.evaluate(atlas_inputs)

        aether_inputs = self._aether_inputs(closes)
        aether = self.aether_engine.evaluate(aether_inputs)

        hermes_score, _conf = self.hermes_engine._score_headline_keyword(self._synthetic_headline(closes))

        snapshot = V2MarketSnapshot(
            regime_v2=regime.regime.value,
            regime_legacy=legacy_regime,
            regime_confidence=float(regime.confidence),
            regime_reason=regime.reason,
            atlas_score=float(atlas.score),
            aether_score=float(aether.score),
            hermes_score=float(hermes_score),
        )
        self.last_market = snapshot

        self.emit(
            EventType.STRATEGY_SIGNAL,
            {
                "regime_v2": snapshot.regime_v2,
                "regime_legacy": snapshot.regime_legacy,
                "regime_confidence": snapshot.regime_confidence,
                "atlas_score": snapshot.atlas_score,
                "aether_score": snapshot.aether_score,
                "hermes_score": snapshot.hermes_score,
            },
            source="v2_runtime.market",
        )

        self._write_metric("atlas_score", snapshot.atlas_score, {})
        self._write_metric("aether_score", snapshot.aether_score, {})
        self._write_metric("hermes_score", snapshot.hermes_score, {})

        return snapshot

    def evaluate_lifecycle(
        self,
        *,
        strategy_id: str,
        trades: int,
        expectancy: float,
        sharpe: float,
        max_dd_pct: float,
        error_rate_pct: float,
        telemetry_stale_sec: float,
        hard_risk_violations: int,
        consecutive_loss_days: int,
    ) -> None:
        snap = StrategyPerformanceSnapshot(
            strategy_id=strategy_id,
            trades=int(trades),
            expectancy=float(expectancy),
            sharpe=float(sharpe),
            max_dd_pct=float(max_dd_pct),
            error_rate_pct=float(error_rate_pct),
            telemetry_stale_sec=float(telemetry_stale_sec),
            hard_risk_violations=int(hard_risk_violations),
            consecutive_loss_days=int(consecutive_loss_days),
        )

        decision = self.lifecycle.evaluate(self.lifecycle_state, snap)
        self.last_lifecycle_action = decision.action
        self.last_lifecycle_reason = decision.reason

        if decision.next_state != self.lifecycle_state:
            old_state = self.lifecycle_state
            self.lifecycle_state = decision.next_state
            self.emit(
                EventType.MODE_CHANGE,
                {
                    "strategy_id": strategy_id,
                    "from": old_state.value,
                    "to": self.lifecycle_state.value,
                    "action": decision.action,
                    "reason": decision.reason,
                },
                source="v2_runtime.lifecycle",
            )

    def observe_trade(self, *, regime: str, engine_signals: Dict[str, float], pnl: float, timestamp: float) -> None:
        sample = LearningSample(
            regime=str(regime),
            pnl=float(pnl),
            engine_signals={k: float(v) for k, v in engine_signals.items()},
            timestamp=float(timestamp),
        )
        self.chiron.add_sample(sample)
        # keep incremental and cheap
        self.chiron.optimize_regime(str(regime), min_samples=40)

    def execute_with_v2(
        self,
        *,
        symbol: str,
        direction: str,
        market_price: float,
        timestamp: float,
        risk_pct: float,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        urgency: UrgencyLevel = UrgencyLevel.NORMAL,
        expected_post_qty: float = 0.0,
    ) -> tuple[bool, str, Dict[str, Any]]:
        side = OrderSide.BUY if str(direction).upper() == "BUY" else OrderSide.SELL
        intent = ExecutionIntent(
            symbol=symbol,
            side=side,
            qty=max(1e-9, float(risk_pct)),
            order_type="MARKET",
            limit_price=float(market_price),
            stop_loss=stop_loss,
            take_profit=take_profit,
            urgency=urgency,
            metadata={
                "market_price": float(market_price),
                "timestamp": float(timestamp),
                "risk_pct": float(risk_pct),
                "asset_class": str(self.cfg.get("asset_class", "crypto")),
                "venue_id": str(self.cfg.get("venue_id", "auto")),
                "regime": self.last_market.regime_v2 if self.last_market is not None else "RANGE",
            },
        )

        result = self.execution.execute(intent, expected_post_qty=float(expected_post_qty))

        payload = {
            "accepted": bool(result.accepted),
            "order_id": result.order_id,
            "status": result.status,
            "reason": result.reason,
            "stop_loss_enforced": bool(result.stop_loss_enforced),
            "reconciliation_delta": float(result.reconciliation_delta),
            "requested_qty": float(result.requested_qty),
            "filled_qty": float(result.filled_qty),
            "avg_price": float(result.avg_price),
            "metadata": dict(result.metadata or {}),
        }
        self.last_execution_profile = dict(result.metadata or {})
        self.emit(EventType.EXECUTION_ACK if result.accepted else EventType.EXECUTION_ERROR, payload, source="v2_runtime.exec")
        self._write_metric("execution_reconciliation_delta", float(result.reconciliation_delta), {})
        if result.metadata:
            fill_ratio = result.metadata.get("fill_ratio")
            slippage_bps = result.metadata.get("slippage_bps")
            latency_ms = result.metadata.get("latency_ms")
            if fill_ratio is not None:
                self._write_metric("execution_fill_ratio", float(fill_ratio), {})
            if slippage_bps is not None:
                self._write_metric("execution_slippage_bps", float(slippage_bps), {})
            if latency_ms is not None:
                self._write_metric("execution_latency_ms", float(latency_ms), {})

        return bool(result.accepted), str(result.reason), payload

    def on_decision(self, payload: Dict[str, Any]) -> None:
        self.emit(EventType.DECISION, payload, source="paper_daemon")

    def on_reject(self, payload: Dict[str, Any]) -> None:
        self.emit(EventType.REJECT, payload, source="paper_daemon")

    def on_trade(self, payload: Dict[str, Any]) -> None:
        evt = EventType.TRADE_CLOSE if str(payload.get("event", "")).upper() not in {"OPEN", "ENTRY"} else EventType.TRADE_OPEN
        self.emit(evt, payload, source="paper_daemon")

    def on_bar_close(
        self,
        *,
        equity: float,
        drawdown_pct: float,
        bars_seen: int,
        decisions_total: int,
        rejects_total: int,
        trades_total: int,
        errors_total: int,
    ) -> None:
        self._write_metric("equity", float(equity), {})
        self._write_metric("drawdown_pct", float(drawdown_pct), {})
        self._write_metric("bars_seen", float(bars_seen), {})
        self._write_metric("decisions_total", float(decisions_total), {})
        self._write_metric("rejects_total", float(rejects_total), {})
        self._write_metric("trades_total", float(trades_total), {})
        self._write_metric("errors_total", float(errors_total), {})

        self.emit(
            EventType.METRICS,
            {
                "equity": float(equity),
                "drawdown_pct": float(drawdown_pct),
                "bars_seen": int(bars_seen),
                "decisions_total": int(decisions_total),
                "rejects_total": int(rejects_total),
                "trades_total": int(trades_total),
                "errors_total": int(errors_total),
            },
            source="v2_runtime.metrics",
        )

        self._persist_runtime_state()

    def open_incident(self, title: str, context: Optional[Dict[str, Any]] = None) -> None:
        incident = self.incidents.open_incident(
            title=title,
            severity=IncidentSeverity.WARN,
            context=context or {},
            recovery_checklist=["heartbeat_ok", "metrics_ok"],
        )
        self.emit(
            EventType.INCIDENT_OPEN,
            {"incident_id": incident.incident_id, "title": incident.title},
            source="v2_runtime.incident",
        )

    def metrics_payload(self) -> Dict[str, Any]:
        return {
            "regime_v2": self.last_market.regime_v2 if self.last_market else None,
            "regime_legacy": self.last_market.regime_legacy if self.last_market else None,
            "regime_confidence": self.last_market.regime_confidence if self.last_market else None,
            "atlas_score": self.last_market.atlas_score if self.last_market else None,
            "aether_score": self.last_market.aether_score if self.last_market else None,
            "hermes_score": self.last_market.hermes_score if self.last_market else None,
            "lifecycle_state": self.lifecycle_state.value,
            "lifecycle_action": self.last_lifecycle_action,
            "lifecycle_reason": self.last_lifecycle_reason,
            "event_counts": dict(self.event_counts),
            "asset_class": str(self.cfg.get("asset_class", "crypto")),
            "venue_id": str(self.cfg.get("venue_id", "auto")),
            "last_execution_profile": dict(self.last_execution_profile),
        }

    def emit(self, event_type: EventType, payload: Dict[str, Any], source: str) -> None:
        asyncio.run(self.bus.emit(event_type, payload, source=source))

    def _persist_event(self, event) -> None:
        row = {
            "event_id": event.event_id,
            "ts_utc": event.ts_utc,
            "event_type": event.event_type.value,
            "source": event.source,
            "correlation_id": event.correlation_id,
            "payload": event.payload,
        }
        with self.events_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=True) + "\n")
        key = event.event_type.value
        self.event_counts[key] = int(self.event_counts.get(key, 0)) + 1

    def _persist_runtime_state(self) -> None:
        payload = {
            "ts_utc": time.time(),
            "metrics": self.metrics_payload(),
        }
        self.runbook_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")

    def _write_metric(self, key: str, value: float, tags: Dict[str, Any]) -> None:
        merged_tags = dict(self.metric_tags_base)
        merged_tags.update(tags)
        point = make_metric_point(key=key, value=float(value), source="v2_runtime", tags=merged_tags)
        self.warehouse.write(point)

    def _map_regime(self, regime: MarketRegime) -> str:
        if regime in {MarketRegime.BULL_TREND, MarketRegime.BEAR_TREND}:
            return "TREND"
        if regime == MarketRegime.HIGH_VOL_CHOP:
            return "CHOP"
        return "RANGE"

    def _atlas_inputs(self, closes: np.ndarray, volumes: np.ndarray) -> AtlasCInputs:
        c = closes[-1]
        mean_c = float(np.mean(closes[-30:])) if closes.size >= 30 else float(c)
        mean_v = float(np.mean(volumes[-30:])) if volumes.size >= 30 else float(np.mean(volumes))
        nvt_ratio = float(c / max(mean_v, 1e-6)) * 1000.0
        mvrv_ratio = float(c / max(mean_c, 1e-6))
        reserve_change = float(((volumes[-1] - mean_v) / max(mean_v, 1e-6)) * -10.0)
        active_change = float(((closes[-1] - closes[-8]) / max(abs(closes[-8]), 1e-6)) * 100.0) if closes.size >= 8 else 0.0
        funding = float(((closes[-1] - closes[-2]) / max(abs(closes[-2]), 1e-6)) * 0.0005) if closes.size >= 2 else 0.0
        return AtlasCInputs(
            nvt_ratio=nvt_ratio,
            mvrv_ratio=mvrv_ratio,
            exchange_reserve_change_7d=reserve_change,
            active_address_change_7d=active_change,
            funding_rate=funding,
        )

    def _aether_inputs(self, closes: np.ndarray) -> AetherCInputs:
        if closes.size >= 24:
            ch24 = float((closes[-1] - closes[-24]) / max(abs(closes[-24]), 1e-6) * 100.0)
        else:
            ch24 = 0.0

        if closes.size >= 120:
            trend = float(np.polyfit(np.arange(60), closes[-60:], 1)[0])
        else:
            trend = 0.0

        dxy_trend = "DOWN" if trend > 0 else "UP" if trend < 0 else "FLAT"
        fg = float(np.clip(50.0 + ch24 * 2.5, 0.0, 100.0))
        dominance = float(np.clip(48.0 - ch24 * 0.4, 35.0, 60.0))
        return AetherCInputs(
            fear_greed=fg,
            btc_dominance=dominance,
            total_market_cap_change_24h=ch24,
            dxy_trend=dxy_trend,
        )

    @staticmethod
    def _synthetic_headline(closes: np.ndarray) -> str:
        if closes.size < 3:
            return "Crypto market mixed signals"
        ret = (closes[-1] - closes[-3]) / max(abs(closes[-3]), 1e-6)
        if ret > 0.01:
            return "BTC sees breakout rally with strong inflow"
        if ret < -0.01:
            return "BTC hit by crash fears and liquidation pressure"
        return "BTC trades flat as market waits for catalyst"


def count_warehouse_rows(cold_db: Path) -> int:
    if not Path(cold_db).exists():
        return 0
    with sqlite3.connect(cold_db) as conn:
        row = conn.execute("SELECT COUNT(*) FROM metrics").fetchone()
    return int(row[0]) if row else 0


__all__ = ["V2RuntimeBridge", "V2MarketSnapshot", "count_warehouse_rows"]
