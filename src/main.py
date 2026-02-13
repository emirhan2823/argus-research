"""ARGUS v2.0 main pipeline entrypoint."""

from __future__ import annotations

import argparse
import os
import random
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any

import numpy as np
import pandas as pd

from src.core.clock import Clock
from src.core.config import load_config
from src.core.events import EventBus, EventType
from src.core.types import Decision, TelemetryEvent
from src.data.data_factory import DataFactory
from src.data.sentinel.validator import SentinelInput, SentinelValidator
from src.engines.atlas.risk_overlay import AtlasRiskOverlay
from src.engines.hermes.engine import HermesEngine
from src.engines.nautilus.engine import NautilusEngine
from src.engines.phoenix.engine import PhoenixEngine
from src.engines.titan.engine import TitanEngine
from src.execution.executor import Executor
from src.mde.gates import GateInput, evaluate_gates
from src.mde.router import RegimeRouter
from src.mde.sizing import SizingInput, compute_size
from src.regime.consensus import RegimeConsensus
from src.regime.rule_based import RuleBasedInput, RuleBasedRegimeClassifier
from src.regime.state_machine import RegimeStateMachine
from src.risk.kill_switch import KillSwitch
from src.risk.pre_trade import PreTradeChecker, PreTradeInput
from src.telemetry.event_logger import EventLogger

if TYPE_CHECKING:
    from src.data.features.builder import FeatureBuilder


class DemoBroker:
    def place_order(self, *, symbol: str, side: str, size: float, order_type: str, urgency: str) -> dict[str, Any]:
        px = 100.0 + random.random()
        return {
            "order_id": f"ord-{symbol}-{int(datetime.now(timezone.utc).timestamp())}",
            "fill_price": px,
            "fill_quantity": size,
            "slippage": 0.0004,
            "fees": size * px * 0.0005,
            "order_type": order_type,
            "urgency": urgency,
        }


@dataclass
class PipelineContext:
    mode: str
    assets: list[str]
    run_id: str


class ArgusPipeline:
    def __init__(
        self,
        *,
        mode: str,
        assets: list[str],
        evolve: bool = False,
        time_machine_dir: str = "data/time_machine",
    ) -> None:
        self.clock = Clock(mode="live")
        self.config = load_config()
        self.event_bus = EventBus()
        self.ctx = PipelineContext(mode=mode, assets=assets, run_id=f"run-{int(datetime.now(timezone.utc).timestamp())}")
        self.evolve = evolve
        self.data_factory = DataFactory(
            data_root=time_machine_dir,
            evolve=evolve,
            exchange_client=None,
        )

        self.sentinel = SentinelValidator()
        self.feature_builder = self._init_feature_builder()
        self.rule_classifier = RuleBasedRegimeClassifier()
        self.consensus = RegimeConsensus()
        self.state_machines: dict[str, RegimeStateMachine] = {}

        self.hermes_engine = HermesEngine()
        self.router = RegimeRouter(
            engines={
                "TITAN": TitanEngine(),
                "NAUTILUS": NautilusEngine(),
                "PHOENIX": PhoenixEngine(),
                "HERMES": self.hermes_engine,
            }
        )
        self.atlas = AtlasRiskOverlay()
        runtime_db = "runs/year2/v2_runtime/argus_runtime.db"
        self.kill_switch = KillSwitch(db_path=runtime_db)
        self.pre_trade = PreTradeChecker()
        self.executor = Executor(broker=DemoBroker())
        self.telemetry = EventLogger(sqlite_path=runtime_db)

    def run_once(self) -> list[dict[str, Any]]:
        if self.feature_builder is None:
            raise ModuleNotFoundError(
                "pandas_ta is required for run_once() feature computation. "
                "Install pandas_ta or skip integration tests with importorskip."
            )

        outputs: list[dict[str, Any]] = []
        now = datetime.now(timezone.utc)

        for asset_class in self.ctx.assets:
            for symbol in self._symbols_for_asset(asset_class):
                candles = self._load_ohlcv(symbol=symbol, now=now)
                last_close = float(candles["close"].iloc[-1])

                # Step 1-2: data acquisition + sentinel
                sentinel_report = self.sentinel.validate(
                    SentinelInput(
                        symbol=symbol,
                        asset_class=asset_class,
                        last_candle_time=now - timedelta(minutes=20),
                        expected_interval=timedelta(hours=1),
                        current_price=last_close,
                        previous_prices=list(candles["close"].tail(30).values),
                        current_volume=float(candles["volume"].iloc[-1]),
                        avg_volume=float(candles["volume"].tail(20).mean()),
                        spread_pct=0.001,
                        normal_spread_pct=0.001,
                        exchange_latency_ms=300.0,
                        orderbook_depth_pct=0.7 if asset_class == "crypto" else None,
                        funding_rate=0.0001 if asset_class == "crypto" else None,
                        normal_funding_rate=0.0001 if asset_class == "crypto" else None,
                        now=now,
                    )
                )

                # Step 3-4: sentiment + features
                fv = self.feature_builder.build(
                    df=candles,
                    symbol=symbol,
                    asset_class=asset_class,
                    timestamp=now,
                    spread_pct=0.001,
                    funding_rate=0.0001 if asset_class == "crypto" else None,
                    funding_pctile_30d=50.0 if asset_class == "crypto" else None,
                    hermes_sentiment_score=0.0,
                    hermes_sentiment_confidence=0.5,
                    hermes_urgency="LOW",
                ).feature_vector
                if fv is None:
                    continue

                # Step 5: regime
                rule_vote = self.rule_classifier.classify(
                    RuleBasedInput(
                        adx_14=fv.adx_14,
                        price_vs_ma200=fv.price_vs_ma200,
                        ema_21_vs_55=fv.ema_21_vs_55,
                        hurst_exponent=fv.hurst_exponent,
                        atr_ratio_5_20=fv.atr_ratio_5_20,
                        vol_multiple_60d=max(fv.volume_ratio, 0.0),
                        directional_alignment_candles=24,
                        hermes_urgency=fv.hermes_urgency,
                        hermes_sentiment_score=fv.hermes_sentiment_score,
                    )
                )
                consensus = self.consensus.resolve({"rule": rule_vote, "ml": rule_vote, "x1": rule_vote, "x2": rule_vote})
                sm = self.state_machines.setdefault(symbol, RegimeStateMachine(initial_regime=consensus.regime))
                regime_state = sm.step(
                    candidate_regime=consensus.regime,
                    confidence=consensus.confidence,
                    stability=0.6,
                    direction=1,
                    rule_regime=rule_vote,
                    ml_regime=rule_vote,
                    timestamp=now,
                    hermes_override=consensus.regime if consensus.reason == "hermes_critical_override" else None,
                )

                # Step 6-7: routing + gates
                signal = self.router.route(regime=regime_state, features=fv)
                gate_result = evaluate_gates(
                    GateInput(
                        sentinel_score=sentinel_report.score,
                        regime=regime_state,
                        rsl_level=int(self.kill_switch.level),
                        signal=signal,
                        features=fv,
                        hermes_block_active=self.hermes_engine.is_entry_blocked(
                            sentiment_score=fv.hermes_sentiment_score,
                            urgency=fv.hermes_urgency,
                        ),
                    )
                )
                if not gate_result.approved or signal is None:
                    self._reject(outputs=outputs, asset_class=asset_class, symbol=symbol, reason=gate_result.reason)
                    continue

                # Step 8: risk + sizing
                atlas_mult = self.atlas.compute_multiplier(
                    regime=regime_state.regime,
                    asset_class=asset_class,
                    btc_dominance_delta_24h=fv.btc_dominance_delta_24h,
                    total_mcap_momentum=fv.total_mcap_momentum,
                    stablecoin_flow=fv.stablecoin_flow,
                )
                dd = 0.0
                rsl_level = self.kill_switch.update_from_drawdown(drawdown=dd, hermes_critical=False)
                size = compute_size(
                    SizingInput(
                        stop_distance=signal.stop_distance,
                        atlas_mult=atlas_mult,
                        sentinel_mult=max(sentinel_report.score, 0.2),
                        regime_conf=regime_state.confidence,
                        dd_mult=1.0,
                        rsl_mult=1.0 if rsl_level < 2 else 0.5,
                        hermes_mult=1.0,
                    )
                )
                pre = self.pre_trade.check(
                    PreTradeInput(
                        asset_class=asset_class,
                        position_size=size.position_size,
                        leverage=1.0,
                        trades_today=0,
                        stop_loss=signal.stop_distance,
                        correlation_with_book=0.1,
                        allocation_ok=True,
                    )
                )
                if not pre.approved:
                    self._reject(outputs=outputs, asset_class=asset_class, symbol=symbol, reason=pre.reason)
                    continue

                # Step 9: execution
                execution_mode = self._execution_mode(asset_class)
                advisory_fields: dict[str, Any] = {}
                if execution_mode == "advisory":
                    advisory_fields = self._build_advisory_fields(
                        signal=signal,
                        last_price=last_close,
                    )

                decision = Decision(
                    action=signal.bias,
                    asset_class=asset_class,
                    symbol=symbol,
                    execution_mode=execution_mode,
                    position_size=pre.adjusted_position_size,
                    leverage=1.0,
                    stop_loss=signal.stop_distance,
                    take_profit=signal.expected_return,
                    confidence=signal.confidence,
                    engine=signal.engine,
                    reason="pipeline_entry",
                    timestamp=now,
                    **advisory_fields,
                )
                ex_result = self.executor.execute(decision=decision)

                # Step 10-11: telemetry + post
                evt_type = "order_filled" if ex_result.success else "order_rejected"
                self._log_event(evt_type, asset_class, reason=ex_result.reason)
                outputs.append(
                    {
                        "symbol": symbol,
                        "status": "executed" if ex_result.success else "failed",
                        "reason": ex_result.reason,
                        "execution_mode": decision.execution_mode,
                        "advisory_message": ex_result.advisory_message,
                    }
                )

        self.event_bus.publish(EventType.HEARTBEAT, {"run_id": self.ctx.run_id, "ts": now.isoformat()})
        return outputs

    def _symbols_for_asset(self, asset_class: str) -> list[str]:
        configured = self.config.base.asset_classes.get(asset_class)
        if configured and configured.enabled and configured.symbols:
            return configured.symbols[:1]
        return [self._fallback_symbol(asset_class)]

    @staticmethod
    def _fallback_symbol(asset_class: str) -> str:
        return {
            "crypto": "BTCUSDT",
            "us_equity": "AAPL",
            "commodity": "XAUUSD",
            "index": "NAS100",
            "bist": "THYAO",
        }.get(asset_class, "BTCUSDT")

    def _execution_mode(self, asset_class: str) -> str:
        cfg = self.config.base.asset_classes.get(asset_class)
        if not cfg:
            return "advisory"
        requested = str(cfg.execution_mode).lower()
        if requested != "auto":
            return requested

        # Safety fallback: if API keys are not available, move to advisory mode
        # rather than attempting blind auto execution.
        exchange = str(cfg.exchange or "").lower()
        if exchange == "bingx":
            if os.getenv("BINGX_API_KEY") and os.getenv("BINGX_API_SECRET"):
                return "auto"
            return "advisory"
        return requested

    @staticmethod
    def _build_advisory_fields(*, signal: Any, last_price: float) -> dict[str, Any]:
        expected = abs(float(getattr(signal, "expected_return", 0.01) or 0.01))
        expected = max(0.005, min(expected, 0.10))
        stop_dist = max(0.001, float(getattr(signal, "stop_distance", 0.01) or 0.01))
        is_long = str(getattr(signal, "bias", "long")).lower() == "long"

        if is_long:
            tp1 = last_price * (1.0 + expected * 0.5)
            tp2 = last_price * (1.0 + expected)
            stop_hint = last_price * (1.0 - stop_dist)
            conditional = [
                f"If price reaches {tp1:.4f}, consider partial take profit.",
                f"If price falls below {stop_hint:.4f}, close position.",
            ]
        else:
            tp1 = last_price * (1.0 - expected * 0.5)
            tp2 = last_price * (1.0 - expected)
            stop_hint = last_price * (1.0 + stop_dist)
            conditional = [
                f"If price reaches {tp1:.4f}, consider partial take profit.",
                f"If price rises above {stop_hint:.4f}, close position.",
            ]

        return {
            "suggested_entry_price": float(last_price),
            "tp_levels": [float(tp1), float(tp2)],
            "conditional_alerts": conditional,
        }

    def _log_event(self, event_type: str, asset_class: str, *, reason: str) -> None:
        evt = TelemetryEvent(
            event_type=event_type,
            timestamp=datetime.now(timezone.utc),
            run_id=self.ctx.run_id,
            inputs_hash=None,
        )
        self.telemetry.log(evt, asset_class=asset_class, reason=reason, payload={"reason": reason})

    def _reject(self, *, outputs: list[dict[str, Any]], asset_class: str, symbol: str, reason: str) -> None:
        self._log_event("signal_rejected", asset_class, reason=reason)
        outputs.append({"symbol": symbol, "status": "rejected", "reason": reason})

    @staticmethod
    def _init_feature_builder() -> Any | None:
        try:
            from src.data.features.builder import FeatureBuilder
        except ModuleNotFoundError as exc:
            if exc.name == "pandas_ta":
                return None
            raise
        return FeatureBuilder()

    def _load_ohlcv(self, *, symbol: str, now: datetime) -> pd.DataFrame:
        if not self.evolve:
            return self._mock_ohlcv(now)

        rows = self.data_factory.fetch_ohlcv(
            symbol=symbol,
            timeframe="1m",
            limit=260,
            now=now,
        )
        if not rows:
            raise ValueError(f"Evolve mode requires local OHLCV data for symbol={symbol}")
        frame = pd.DataFrame(rows, columns=["timestamp", "open", "high", "low", "close", "volume"])
        frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True, errors="coerce")
        return frame.dropna(subset=["timestamp"]).reset_index(drop=True)

    @staticmethod
    def _mock_ohlcv(now: datetime) -> pd.DataFrame:
        rng = np.random.default_rng(123)
        n = 260
        close = 100 + np.cumsum(rng.normal(0.0, 0.8, n))
        high = close + np.abs(rng.normal(0.4, 0.1, n))
        low = close - np.abs(rng.normal(0.4, 0.1, n))
        open_ = close + rng.normal(0.0, 0.1, n)
        volume = rng.uniform(1_000, 10_000, n)
        ts = [now - timedelta(hours=n - i) for i in range(n)]
        return pd.DataFrame(
            {
                "timestamp": ts,
                "open": open_,
                "high": high,
                "low": low,
                "close": close,
                "volume": volume,
            }
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="ARGUS v2.0 pipeline")
    parser.add_argument("--mode", choices=["paper", "live", "backtest"], default="paper")
    parser.add_argument("--assets", default="crypto", help="Comma-separated asset classes")
    parser.add_argument(
        "--evolve",
        action="store_true",
        help="Use local time_machine parquet data (exchange bypass) for deterministic evolution runs.",
    )
    parser.add_argument(
        "--time-machine-dir",
        default="data/time_machine",
        help="Parquet directory for local evolve runs.",
    )
    args = parser.parse_args()

    assets = [a.strip() for a in args.assets.split(",") if a.strip()]
    pipeline = ArgusPipeline(
        mode=args.mode,
        assets=assets,
        evolve=bool(args.evolve),
        time_machine_dir=str(args.time_machine_dir),
    )
    outputs = pipeline.run_once()
    for item in outputs:
        print(item)


if __name__ == "__main__":
    main()
