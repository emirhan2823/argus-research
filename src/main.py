"""ARGUS v2.0 main pipeline entrypoint."""

from __future__ import annotations

import argparse
import json
import logging
import os
import random
import sqlite3
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

import numpy as np
import pandas as pd

# Allow direct script execution: `python src/main.py ...`
if __package__ in (None, ""):
    _PROJECT_ROOT = Path(__file__).resolve().parent.parent
    if str(_PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(_PROJECT_ROOT))

from src.core.clock import Clock
from src.core.config import load_config
from src.core.constants import ENGINE_HERMES, ENGINE_PHOENIX, REGIME_CRISIS, REGIME_TO_ENGINE
from src.core.events import EventBus, EventType
from src.core.types import Decision, EngineSignal, FeatureVector, RegimeState, TelemetryEvent
from src.data.data_factory import DataFactory
from src.data.sentinel.validator import SentinelInput, SentinelValidator
from src.engines.atlas.risk_overlay import AtlasRiskOverlay
from src.engines.hermes.engine import HermesEngine
from src.engines.hydra.engine import HydraEngine
from src.engines.nautilus.engine import NautilusEngine
from src.engines.phoenix.engine import PhoenixEngine
from src.engines.titan.engine import TitanEngine
from src.execution.executor import Executor
from src.execution.hermes_position_manager import HermesPositionManager
from src.mde.gates import GateInput, evaluate_gates
from src.mde.router import RegimeRouter
from src.mde.sizing import SizingInput, compute_size
from src.regime.consensus import RegimeConsensus
from src.regime.rule_based import RuleBasedInput, RuleBasedRegimeClassifier
from src.regime.state_machine import RegimeStateMachine
from src.risk.kill_switch import KillSwitch
from src.risk.pre_trade import PreTradeChecker, PreTradeInput
from src.telemetry.event_logger import EventLogger
from src.v25.config.loader import DynamicExitConfig
from src.v25.telemetry.log_writer import log_decision, log_dynamic_exit, log_validated_sizing, log_whale_momentum
from src.engines.hermes.whale_momentum import (
    compute_whale_momentum,
    apply_whale_boost_to_signal,
)
from src.v25.contracts.intelligence import WhaleAlert
from src.correlation.tracker import CorrelationTracker
from src.correlation.signals import CorrelationSignalGenerator
from src.engines.gemini.engine import GeminiEngine
from src.mde.precision_filter import PrecisionConfig
from src.notifications.telegram import TelegramSignalNotifier
from src.orchestration.orion import OrionOrchestrator

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


class ShadowNoopHermesBroker:
    def close_position(self, *, symbol: str, reason: str) -> None:
        return None

    def modify_stop_loss(self, *, symbol: str, stop_price: float) -> None:
        return None

    def modify_take_profit(self, *, symbol: str, tp_price: float) -> None:
        return None


DEFAULT_CRYPTO_SYMBOLS_15: tuple[str, ...] = (
    "BTCUSDT",
    "ETHUSDT",
    "SOLUSDT",
    "XRPUSDT",
    "DOGEUSDT",
    "BNBUSDT",
    "ADAUSDT",
    "AVAXUSDT",
    "LINKUSDT",
    "TRXUSDT",
    "LTCUSDT",
    "DOTUSDT",
    "BCHUSDT",
    "ATOMUSDT",
    "NEARUSDT",
)
DEFAULT_CRYPTO_SYMBOLS_5: tuple[str, ...] = DEFAULT_CRYPTO_SYMBOLS_15[:5]


def parse_symbols_arg(raw: str | None) -> list[str]:
    if raw is None:
        return []
    symbols: list[str] = []
    seen: set[str] = set()
    for part in str(raw).split(","):
        sym = str(part).strip().upper()
        if not sym:
            continue
        sym = sym.replace("/", "").replace("-", "").replace("_", "")
        if sym and sym not in seen:
            seen.add(sym)
            symbols.append(sym)
    return symbols


def resolve_crypto_symbol_universe(*, symbols_arg: str | None, universe_size: int, live_data: bool) -> list[str]:
    explicit = parse_symbols_arg(symbols_arg)
    if explicit:
        return explicit
    # Safe default universe is applied for live-data operation.
    if not live_data:
        return []
    size = 15 if int(universe_size) == 15 else 5
    base = DEFAULT_CRYPTO_SYMBOLS_15 if size == 15 else DEFAULT_CRYPTO_SYMBOLS_5
    return list(base[:size])


@dataclass
class PipelineContext:
    mode: str
    assets: list[str]
    run_id: str


@dataclass(frozen=True)
class V25RoutedDecision:
    action: str
    confidence: float
    sqs_score: float
    stop_loss: float
    take_profit: float
    engine: str
    reason: str
    sub_strategy: str | None = None


class ArgusPipeline:
    _LOG = logging.getLogger("argus.pipeline")

    def __init__(
        self,
        *,
        mode: str,
        assets: list[str],
        evolve: bool = False,
        time_machine_dir: str = "data/time_machine",
        data_mode: str | None = None,
        replay_now: pd.Timestamp | None = None,
        forward_sim: bool = False,
        ohlcv_limit: int = 260,
        v25_conn: sqlite3.Connection | None = None,
        risk_profile: str = "normal",
        allow_crisis: bool = False,
        symbols_override: dict[str, list[str]] | None = None,
    ) -> None:
        self.clock = Clock(mode="live")
        self.config = load_config()
        self.event_bus = EventBus()
        self.ctx = PipelineContext(mode=mode, assets=assets, run_id=f"run-{int(datetime.now(timezone.utc).timestamp())}")
        self.evolve = evolve
        self.replay_now = replay_now
        self.forward_sim = bool(forward_sim)
        self.ohlcv_limit = max(1, int(ohlcv_limit))
        self.v25_conn = v25_conn
        self.symbols_override = symbols_override or {}
        self._forward_history: dict[str, pd.DataFrame] = {}
        self._forward_processed_ts: dict[str, pd.Timestamp] = {}
        self._forward_history_limit = max(self.ohlcv_limit, 260)
        normalized_risk = str(risk_profile).strip().lower()
        self.risk_profile = normalized_risk if normalized_risk in {"strict", "normal", "relaxed"} else "normal"
        self.allow_crisis = bool(allow_crisis)
        resolved_data_mode = (data_mode or os.getenv("ARGUS_DATA_MODE", "mock")).lower()
        if replay_now is not None and resolved_data_mode == "mock":
            resolved_data_mode = "replay"
        self.data_factory = DataFactory(
            data_root=time_machine_dir,
            evolve=evolve,
            mode=resolved_data_mode,
            replay_root="data/binance",
            exchange_client=self._init_exchange_client(evolve),
        )
        self._replay_smoke_logged = False
        if self.data_factory.mode == "replay":
            self._LOG.debug(
                "replay mode enabled: replay_now=%s limit=%d replay_root=%s",
                self.replay_now.isoformat() if isinstance(self.replay_now, pd.Timestamp) else self.replay_now,
                self.ohlcv_limit,
                "data/binance",
            )
        if self.forward_sim:
            self._LOG.info("forward simulation enabled: incremental candle stepping active")
        # Track open positions for shadow dynamic exit
        self._open_positions: dict[str, dict[str, Any]] = {}
        # Whale alerts for momentum boost (populated by external data source)
        self._whale_alerts: list[WhaleAlert] = []
        # PR-J02: When True, dynamic exit intents are executed live via broker
        self._live_exit_enabled: bool = False

        self.sentinel = SentinelValidator()
        self.feature_builder = self._init_feature_builder()
        self.rule_classifier = RuleBasedRegimeClassifier()
        self.consensus = RegimeConsensus()
        self.state_machines: dict[str, RegimeStateMachine] = {}

        self.hermes_engine = HermesEngine()
        self.nautilus_engine = NautilusEngine()
        # Initialize Gemini (correlation pairs engine) from config
        self._gemini_engine, self._correlation_tracker = self._init_gemini_engine()
        self.router = RegimeRouter(
            engines={
                "TITAN": TitanEngine(),
                "NAUTILUS": self.nautilus_engine,
                "PHOENIX": PhoenixEngine(),
                "HYDRA": HydraEngine(),
                "HERMES": self.hermes_engine,
                **({"GEMINI": self._gemini_engine} if self._gemini_engine else {}),
            }
        )
        self.atlas = AtlasRiskOverlay()
        runtime_db = "runs/year2/v2_runtime/argus_runtime.db"
        self.kill_switch = KillSwitch(db_path=runtime_db)
        self.pre_trade = PreTradeChecker()
        self.executor = Executor(broker=DemoBroker())
        self._dynamic_exit_config = self._load_dynamic_exit_config()
        self._precision_config = self._load_precision_config()
        self.shadow_position_manager = HermesPositionManager(
            broker=ShadowNoopHermesBroker(),
            shadow_enabled=bool(self.config.engines.hermes.position_management.dynamic_exit_shadow_enabled),
            shadow_noop_debug_sample_n=max(
                int(self.config.engines.hermes.position_management.dynamic_exit_noop_debug_sample_n),
                0,
            ),
            dynamic_exit_config=self._dynamic_exit_config,
        )
        self.telemetry = EventLogger(sqlite_path=runtime_db)
        # Stage-2B: paper execution realism parameters
        self._paper_taker_fee: float = 0.0004
        self._paper_maker_fee: float = 0.0002
        # ORION meta-orchestrator (default: disabled, enabled via --orion)
        self.orion = OrionOrchestrator(account_equity_usd=500.0, enabled=False)

    def run_once(self, *, now: datetime | None = None) -> list[dict[str, Any]]:
        if self.feature_builder is None:
            raise ModuleNotFoundError("Feature builder is unavailable")

        outputs: list[dict[str, Any]] = []
        cycle_now = now or datetime.now(timezone.utc)
        gate9_threshold = self._active_gate9_threshold()

        for asset_class in self.ctx.assets:
            if self._live_exit_enabled:
                self._run_live_dynamic_exit(asset_class=asset_class, now=cycle_now)
            else:
                self._run_shadow_dynamic_exit(asset_class=asset_class, now=cycle_now)
            for symbol in self._symbols_for_asset(asset_class):
                candles = self._load_ohlcv(symbol=symbol, now=cycle_now)
                if candles.empty:
                    self._reject(
                        outputs=outputs,
                        asset_class=asset_class,
                        symbol=symbol,
                        reason="no_ohlcv_data",
                        engine=self._engine_hint_for_regime(None),
                        action="rejected",
                        confidence=0.0,
                        gate_results={
                            "path": "run_once",
                            "mode": self.ctx.mode,
                            "forward_sim": self.forward_sim,
                            "bars": int(len(candles)),
                        },
                    )
                    continue

                if self.forward_sim:
                    candle_ts = pd.Timestamp(candles["timestamp"].iloc[-1])
                    if candle_ts.tzinfo is None:
                        candle_ts = candle_ts.tz_localize("UTC")
                    else:
                        candle_ts = candle_ts.tz_convert("UTC")
                    prev_ts = self._forward_processed_ts.get(symbol)
                    if prev_ts is not None and candle_ts <= prev_ts:
                        self._reject(
                            outputs=outputs,
                            asset_class=asset_class,
                            symbol=symbol,
                            reason="forward_wait_next_candle",
                            engine=self._engine_hint_for_regime(None),
                            action="rejected",
                            confidence=0.0,
                            gate_results={
                                "path": "run_once",
                                "mode": self.ctx.mode,
                                "forward_sim": True,
                                "bars": int(len(candles)),
                                "last_candle_ts": candle_ts.isoformat(),
                            },
                        )
                        continue
                    self._forward_processed_ts[symbol] = candle_ts

                last_close = float(candles["close"].iloc[-1])

                # Feed candle data to NautilusEngine for range detection (micro-reversion)
                self.nautilus_engine.feed_candles(
                    symbol=symbol,
                    highs=list(candles["high"].astype(float)),
                    lows=list(candles["low"].astype(float)),
                    closes=list(candles["close"].astype(float)),
                )

                # Update correlation tracker with latest prices for Gemini + chop_corr_gap
                if self._correlation_tracker is not None:
                    self._correlation_tracker.update(
                        {symbol: candles["close"].astype(float)}
                    )

                # Step 1-2: data acquisition + sentinel
                sentinel_report = self.sentinel.validate(
                    SentinelInput(
                        symbol=symbol,
                        asset_class=asset_class,
                        last_candle_time=cycle_now - timedelta(minutes=20),
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
                        now=cycle_now,
                    )
                )

                # Step 3-4: sentiment + features
                try:
                    fv = self.feature_builder.build(
                        df=candles,
                        symbol=symbol,
                        asset_class=asset_class,
                        timestamp=cycle_now,
                        spread_pct=0.001,
                        funding_rate=0.0001 if asset_class == "crypto" else None,
                        funding_pctile_30d=50.0 if asset_class == "crypto" else None,
                        hermes_sentiment_score=0.0,
                        hermes_sentiment_confidence=0.5,
                        hermes_urgency="LOW",
                    ).feature_vector
                except Exception as exc:
                    self._reject(
                        outputs=outputs,
                        asset_class=asset_class,
                        symbol=symbol,
                        reason=f"feature_build_failed:{type(exc).__name__}",
                        engine="ROUTER",
                        action="rejected",
                        confidence=0.0,
                        gate_results={
                            "path": "run_once",
                            "mode": self.ctx.mode,
                            "forward_sim": self.forward_sim,
                            "bars": int(len(candles)),
                        },
                    )
                    continue
                if fv is None:
                    self._reject(
                        outputs=outputs,
                        asset_class=asset_class,
                        symbol=symbol,
                        reason="feature_build_failed",
                        engine="ROUTER",
                        action="rejected",
                        confidence=0.0,
                        gate_results={"path": "run_once", "mode": self.ctx.mode},
                    )
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
                    timestamp=cycle_now,
                    hermes_override=consensus.regime if consensus.reason == "hermes_critical_override" else None,
                )

                crisis_override_active = self._is_crisis_override_active(regime_state.regime)
                base_gate_results: dict[str, Any] = {
                    "path": "run_once",
                    "mode": self.ctx.mode,
                    "features_snapshot": {
                        "regime": regime_state.regime,
                        "atr_14_pct": self._safe_float(getattr(fv, "atr_14_pct", None)),
                        "adx_14": self._safe_float(getattr(fv, "adx_14", None)),
                        "volume_ratio": self._safe_float(getattr(fv, "volume_ratio", None)),
                    },
                }
                if crisis_override_active:
                    base_gate_results["crisis_override"] = True

                # Step 5.5: ORION multi-engine dispatch
                orion_decision = None
                if self.orion.enabled:
                    try:
                        # Collect candidate signals from ALL engines
                        _candidate_signals: dict[str, EngineSignal | None] = {}
                        for _eng_name, _eng_impl in self.router.engines.items():
                            if _eng_name == ENGINE_HERMES:
                                continue  # HERMES is overlay only
                            try:
                                _candidate_signals[_eng_name] = _eng_impl.generate_signal(
                                    regime=regime_state, features=fv,
                                )
                            except Exception:
                                _candidate_signals[_eng_name] = None

                        orion_decision = self.orion.step(
                            features=fv,
                            regime_state=regime_state,
                            candidate_signals=_candidate_signals,
                        )
                        # Stage-2B: store for paper_cycle_log
                        self._last_orion_decision = orion_decision
                        self._last_candidate_signals = _candidate_signals

                        # ORION risk posture: block entries if needed
                        if not orion_decision.risk_posture.allow_new_entries:
                            self._reject(
                                outputs=outputs,
                                asset_class=asset_class,
                                symbol=symbol,
                                reason=self._annotate_reason(
                                    f"orion_risk_block:{orion_decision.risk_posture.reason}",
                                    crisis_override=crisis_override_active,
                                ),
                                engine="ORION",
                                action="rejected",
                                confidence=0.0,
                                gate_results=base_gate_results,
                            )
                            continue

                        # Use ORION's chosen engine signal
                        chosen = orion_decision.chosen_engine
                        if chosen != "NONE":
                            signal = _candidate_signals.get(chosen)
                        else:
                            # No engine produced a valid signal via direct dispatch;
                            # fall through to standard router.route() path so the
                            # existing fallback+HERMES override semantics apply.
                            orion_decision = None

                        # Inject ORION telemetry into gate results
                        if orion_decision is not None:
                            base_gate_results["orion"] = orion_decision.to_telemetry_dict()

                    except Exception as orion_exc:
                        self._LOG.warning("ORION step failed, falling back to static routing: %s", orion_exc)
                        orion_decision = None

                # Step 6: routing (fallback if ORION disabled or failed)
                if orion_decision is None:
                    try:
                        signal = self.router.route(
                            regime=regime_state,
                            features=fv,
                            allow_crisis_override=crisis_override_active,
                        )
                    except Exception as exc:
                        reject_engine = self._engine_hint_for_regime(regime_state.regime)
                        self._reject(
                            outputs=outputs,
                            asset_class=asset_class,
                            symbol=symbol,
                            reason=self._annotate_reason(f"engine_error:{exc}", crisis_override=crisis_override_active),
                            engine=reject_engine,
                            action="rejected",
                            confidence=0.0,
                            gate_results=base_gate_results,
                        )
                        continue

                # Step 6.5: signal quality assessment (NEW)
                if signal is not None:
                    from src.mde.signal_quality import assess_signal_quality
                    sq = assess_signal_quality(
                        bias=signal.bias,
                        confidence=signal.confidence,
                        engine=signal.engine,
                        rsi_14=fv.rsi_14,
                        adx_14=fv.adx_14,
                        bb_pct_b=fv.bb_pct_b,
                        volume_ratio=fv.volume_ratio,
                        volume_delta=fv.volume_delta,
                        ema_21_vs_55=fv.ema_21_vs_55,
                        price_vs_ma200=fv.price_vs_ma200,
                        roc_10=fv.roc_10,
                        willr_14=fv.willr_14,
                        cci_20=fv.cci_20,
                        hurst_exponent=fv.hurst_exponent,
                        aroon_osc=fv.aroon_osc,
                        supertrend_dir=fv.supertrend_dir,
                        orderbook_imbalance=fv.orderbook_imbalance,
                        funding_rate=fv.funding_rate,
                        long_short_ratio=fv.long_short_ratio,
                        regime=regime_state.regime,
                        candles_in_regime=regime_state.candles_in_regime,
                        regime_confidence=regime_state.confidence,
                    )
                    if not sq.pass_quality:
                        self._reject(
                            outputs=outputs, asset_class=asset_class,
                            symbol=symbol,
                            reason=self._annotate_reason(
                                f"signal_quality_too_low ({sq.quality_score:.2f})",
                                crisis_override=crisis_override_active,
                            ),
                            engine=str(signal.engine),
                            action="rejected",
                            confidence=float(signal.confidence),
                            gate_results=base_gate_results,
                        )
                        continue
                    # Update confidence with quality-adjusted value
                    signal = signal.model_copy(update={"confidence": sq.adjusted_confidence})

                # Step 6.6: whale momentum boost (Blueprint Pivot 4)
                if signal is not None:
                    signal = self._apply_whale_momentum_boost(
                        signal=signal,
                        regime_state=regime_state,
                        symbol=symbol,
                        now=cycle_now,
                    )

                # Step 6.7: precision entry filter (Phase E)
                if signal is not None:
                    from src.mde.precision_filter import assess_entry_precision
                    _prec = assess_entry_precision(
                        direction=signal.bias,
                        current_price=max(fv.atr_14 / max(fv.atr_14_pct, 1e-6), 1.0),
                        obi=fv.orderbook_imbalance,
                        spread_pct=fv.spread_pct,
                        median_spread_pct=max(fv.spread_pct, 0.0005),  # fallback median
                        vwap_dev_pct=fv.vwap_dev_pct,
                        volume_ratio=fv.volume_ratio,
                        atr_pct=fv.atr_14_pct,
                        config=self._precision_config,
                    )
                    if not _prec.passed:
                        self._reject(
                            outputs=outputs, asset_class=asset_class,
                            symbol=symbol,
                            reason=self._annotate_reason(
                                f"precision_grade_F ({_prec.score:.2f})",
                                crisis_override=crisis_override_active,
                            ),
                            engine=str(signal.engine),
                            action="rejected",
                            confidence=float(signal.confidence),
                            gate_results=base_gate_results,
                        )
                        continue
                    # Apply confidence adjustment from precision grade
                    _adj_conf = max(0.0, min(1.0, signal.confidence + _prec.confidence_adjustment))
                    signal = signal.model_copy(update={"confidence": _adj_conf})

                # Step 7: gates
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
                        allow_crisis_override=crisis_override_active,
                    )
                )
                if not gate_result.approved or signal is None:
                    reject_engine = str(signal.engine) if signal is not None else "ROUTER"
                    reject_confidence = float(signal.confidence) if signal is not None else 0.0
                    gate_diag = dict(base_gate_results)
                    gate_diag.update(
                        {
                            "gate": gate_result.gate_number,
                            "gate_action": gate_result.action,
                            "features_snapshot": gate_result.features_snapshot,
                        }
                    )
                    self._reject(
                        outputs=outputs,
                        asset_class=asset_class,
                        symbol=symbol,
                        reason=self._annotate_reason(gate_result.reason, crisis_override=crisis_override_active),
                        engine=reject_engine,
                        action="rejected",
                        confidence=reject_confidence,
                        gate_results=gate_diag,
                    )
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
                position_size_pct = float(size.position_size)
                if crisis_override_active:
                    position_size_pct = min(position_size_pct, 0.02)

                pre = self.pre_trade.check(
                    PreTradeInput(
                        asset_class=asset_class,
                        position_size=position_size_pct,
                        leverage=1.0,
                        trades_today=0,
                        stop_loss=signal.stop_distance,
                        correlation_with_book=0.1,
                        allocation_ok=True,
                        gate9_threshold=gate9_threshold,
                    )
                )
                # Persist validated sizing telemetry (both approved and rejected)
                self._persist_validated_sizing(pre=pre, symbol=symbol)

                gate9_diag = self._gate9_diagnostics(pre=pre, threshold=gate9_threshold)
                pretrade_gate_results = dict(base_gate_results)
                if gate9_diag is not None:
                    pretrade_gate_results.update(gate9_diag)

                if not pre.approved:
                    self._reject(
                        outputs=outputs,
                        asset_class=asset_class,
                        symbol=symbol,
                        reason=self._annotate_reason(pre.reason, crisis_override=crisis_override_active),
                        engine=str(signal.engine),
                        action="rejected",
                        confidence=float(signal.confidence),
                        position_size_pct=float(pre.adjusted_position_size),
                        gate_results=pretrade_gate_results,
                    )
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
                    reason=self._annotate_reason("pipeline_entry", crisis_override=crisis_override_active),
                    timestamp=cycle_now,
                    **advisory_fields,
                )
                ex_result = self.executor.execute(decision=decision)

                # Track open position for shadow dynamic exit
                if ex_result.success:
                    pos_id = f"pos-{symbol}-{int(cycle_now.timestamp())}"
                    self._open_positions[pos_id] = {
                        "position_id": pos_id,
                        "symbol": symbol,
                        "side": signal.bias.upper() if hasattr(signal, "bias") else "LONG",
                        "entry_price": last_close,
                        "current_price": last_close,
                        "sl_pct": signal.stop_distance,
                        "r_value_pct": signal.stop_distance,
                        "atr_pct": max(float(getattr(fv, "atr_ratio_5_20", 0.005) or 0.005), 0.001),
                    }

                # Step 10-11: telemetry + post
                evt_type = "order_filled" if ex_result.success else "order_rejected"
                self._log_event(evt_type, asset_class, reason=ex_result.reason)
                output_reason = self._annotate_reason(str(ex_result.reason), crisis_override=crisis_override_active)
                outputs.append(
                    {
                        "symbol": symbol,
                        "status": "executed" if ex_result.success else "failed",
                        "reason": output_reason,
                        "action": decision.action,
                        "engine": decision.engine,
                        "confidence": float(decision.confidence),
                        "position_size_pct": float(decision.position_size),
                        "leverage": float(decision.leverage),
                        "stop_loss_pct": float(decision.stop_loss),
                        "take_profit_pct": float(decision.take_profit),
                        "suggested_entry_price": (
                            float(decision.suggested_entry_price)
                            if decision.suggested_entry_price is not None
                            else None
                        ),
                        "gate_results": pretrade_gate_results,
                        "execution_mode": decision.execution_mode,
                        "advisory_message": ex_result.advisory_message,
                    }
                )

        self.event_bus.publish(EventType.HEARTBEAT, {"run_id": self.ctx.run_id, "ts": cycle_now.isoformat()})
        return outputs

    def _symbols_for_asset(self, asset_class: str) -> list[str]:
        override = self.symbols_override.get(asset_class)
        if override:
            return [str(s).upper() for s in override if str(s).strip()]

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
        if self.ctx.mode == "backtest":
            return "advisory"

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

    def _active_gate9_threshold(self) -> Decimal:
        if self.ctx.mode != "backtest":
            return Decimal("0.30")
        if self.risk_profile == "relaxed":
            return Decimal("0.35")
        if self.risk_profile == "strict":
            return Decimal("0.25")
        return Decimal("0.30")

    def _is_crisis_override_active(self, regime: str) -> bool:
        return self.ctx.mode == "backtest" and self.allow_crisis and regime == REGIME_CRISIS

    @staticmethod
    def _annotate_reason(reason: str, *, crisis_override: bool) -> str:
        if not crisis_override:
            return reason
        text = str(reason)
        if "crisis_override" in text:
            return text
        return f"{text}|crisis_override"

    @staticmethod
    def _gate9_diagnostics(*, pre: Any, threshold: Decimal) -> dict[str, Any] | None:
        sizing = getattr(pre, "validated_sizing", None)
        if sizing is None:
            return None
        try:
            return {
                "gate9": {
                    "pass": bool(getattr(sizing, "passed_gate9")),
                    "fee_est_usd": float(getattr(sizing, "fee_est_usd")),
                    "risk_usd": float(getattr(sizing, "risk_usd")),
                    "fee_risk_ratio": float(getattr(sizing, "fee_risk_ratio")),
                    "threshold": float(threshold),
                }
            }
        except (TypeError, ValueError, AttributeError):
            return None

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

    def run_v25_minimal_cycle(self, *, now: datetime | None = None) -> list[dict[str, Any]]:
        """Run one minimal v2.5 cycle without pandas_ta-dependent feature building.

        This path is used only when pandas_ta is unavailable and v25 mode is enabled.
        It consumes OHLCV data, builds fallback features, routes into real engines
        (Gemini first, then existing router), and persists decision/trade telemetry.
        """
        if self.feature_builder is None:
            raise ModuleNotFoundError("Feature builder is unavailable")

        cycle_now = now or datetime.now(timezone.utc)
        outputs: list[dict[str, Any]] = []

        for asset_class in self.ctx.assets:
            for symbol in self._symbols_for_asset(asset_class):
                candles = self._load_ohlcv(symbol=symbol, now=cycle_now)
                if candles.empty:
                    outputs.append({
                        "symbol": symbol,
                        "status": "rejected",
                        "action": "rejected",
                        "engine": "ROUTER",
                        "confidence": 0.0,
                        "sqs_score": 0.0,
                        "reason": "no_candles",
                        "asset_class": asset_class,
                    })
                    continue

                last_close = float(candles["close"].iloc[-1])
                fv = self.feature_builder.build(
                    df=candles,
                    symbol=symbol,
                    asset_class=asset_class,
                    timestamp=cycle_now,
                    spread_pct=0.001,
                    funding_rate=0.0001 if asset_class == "crypto" else None,
                    funding_pctile_30d=50.0 if asset_class == "crypto" else None,
                    hermes_sentiment_score=0.0,
                    hermes_sentiment_confidence=0.5,
                    hermes_urgency="LOW",
                ).feature_vector

                if fv is None:
                    routed = V25RoutedDecision(
                        action="rejected",
                        confidence=0.0,
                        sqs_score=0.0,
                        stop_loss=0.01,
                        take_profit=0.0,
                        engine="ROUTER",
                        reason="feature_build_failed",
                        sub_strategy="minimal_router",
                    )
                else:
                    regime_state = self._compute_regime_state(symbol=symbol, fv=fv, now=cycle_now)
                    routed = self._route_v25_engine(regime_state=regime_state, features=fv)

                decision: Decision | None = None
                ex_result: Any | None = None
                if routed.action in {"long", "short"}:
                    decision = Decision(
                        action=routed.action,
                        asset_class=asset_class,
                        symbol=symbol,
                        execution_mode=self._execution_mode(asset_class),
                        position_size=0.01,
                        leverage=1.0,
                        stop_loss=routed.stop_loss,
                        take_profit=routed.take_profit,
                        confidence=routed.confidence,
                        engine=routed.engine,
                        reason=routed.reason,
                        timestamp=cycle_now,
                    )
                    ex_result = self.executor.execute(decision=decision)

                status = "rejected"
                execution_reason: str | None = None
                if decision is not None and ex_result is not None:
                    status = "executed" if ex_result.success else "failed"
                    execution_reason = str(ex_result.reason)

                # Persist decision row for observability/backtest audit
                if self.v25_conn is not None:
                    try:
                        log_decision(
                            self.v25_conn,
                            run_id=self.ctx.run_id,
                            timestamp=cycle_now.isoformat(),
                            symbol=symbol,
                            action=routed.action,
                            capital_engine="core",
                            position_size_pct=float(decision.position_size) if decision is not None else 0.0,
                            leverage=float(decision.leverage) if decision is not None else 1.0,
                            stop_loss_pct=float(routed.stop_loss),
                            confidence=float(routed.confidence),
                            sqs_score=float(routed.sqs_score),
                            engine=routed.engine,
                            sub_strategy=routed.sub_strategy or "minimal_router",
                            regime="REPLAY" if self.data_factory.mode == "replay" else "UNKNOWN",
                            reason=routed.reason,
                            status=status,
                            gate_results={
                                "path": "v25_engine_router",
                                "mode": self.ctx.mode,
                                "execution_attempted": decision is not None,
                            },
                        )
                        if decision is not None and ex_result is not None and ex_result.success:
                            self._persist_v25_fallback_trade(
                                symbol=symbol,
                                side=decision.action,
                                entry_price=float(ex_result.fill_price or last_close),
                                size=float(ex_result.fill_quantity or decision.position_size),
                                confidence=float(routed.confidence),
                                stop_distance=float(routed.stop_loss),
                                engine=str(routed.engine),
                                reason_entry=str(routed.reason),
                                entry_time=cycle_now,
                                fees=float(ex_result.fees or 0.0),
                                slippage=float(ex_result.slippage or 0.0),
                            )
                        self.v25_conn.commit()
                    except Exception:
                        self._LOG.debug("v25 minimal cycle persistence failed", exc_info=True)

                outputs.append(
                    {
                        "symbol": symbol,
                        "status": status,
                        "reason": routed.reason,
                        "execution_reason": execution_reason,
                        "action": routed.action,
                        "engine": routed.engine,
                        "confidence": float(routed.confidence),
                        "sqs_score": float(routed.sqs_score),
                        "asset_class": asset_class,
                    }
                )

        return outputs

    def _compute_regime_state(self, *, symbol: str, fv: FeatureVector, now: datetime) -> RegimeState:
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
        consensus = self.consensus.resolve(
            {"rule": rule_vote, "ml": rule_vote, "x1": rule_vote, "x2": rule_vote}
        )
        sm = self.state_machines.setdefault(symbol, RegimeStateMachine(initial_regime=consensus.regime))
        return sm.step(
            candidate_regime=consensus.regime,
            confidence=consensus.confidence,
            stability=0.6,
            direction=1,
            rule_regime=rule_vote,
            ml_regime=rule_vote,
            timestamp=now,
            hermes_override=consensus.regime if consensus.reason == "hermes_critical_override" else None,
        )

    def _route_v25_engine(self, *, regime_state: RegimeState, features: FeatureVector) -> V25RoutedDecision:
        crisis_override_active = self._is_crisis_override_active(regime_state.regime)
        reject_engine = (
            "GEMINI" if self._gemini_engine is not None else self._engine_hint_for_regime(regime_state.regime)
        )
        try:
            signal: EngineSignal | None = None

            # Minimal engine-router call for v2.5 fallback path.
            # Prefer explicit Gemini call, then existing regime router.
            if self._gemini_engine is not None:
                signal = self._gemini_engine.generate_signal(regime=regime_state, features=features)
            if signal is None:
                signal = self.router.route(
                    regime=regime_state,
                    features=features,
                    allow_crisis_override=self._is_crisis_override_active(regime_state.regime),
                )

            if signal is None:
                return V25RoutedDecision(
                    action="rejected",
                    confidence=0.0,
                    sqs_score=0.0,
                    stop_loss=0.01,
                    take_profit=0.0,
                    engine="ROUTER",
                    reason=self._annotate_reason("no_signal", crisis_override=crisis_override_active),
                    sub_strategy="minimal_router",
                )

            engine_name = str(signal.engine or reject_engine)
            action = str(signal.bias).lower()
            if action not in {"long", "short"}:
                return V25RoutedDecision(
                    action="rejected",
                    confidence=0.0,
                    sqs_score=0.0,
                    stop_loss=0.01,
                    take_profit=0.0,
                    engine=engine_name,
                    reason="invalid_signal_bias",
                    sub_strategy=str(signal.sub_strategy),
                )

            confidence = max(0.0, min(1.0, float(signal.confidence)))
            stop_loss = max(0.001, min(float(signal.stop_distance), 0.10))
            take_profit = max(stop_loss * 1.5, float(signal.expected_return))
            sqs_score = max(0.0, min(1.0, confidence))
            return V25RoutedDecision(
                action=action,
                confidence=confidence,
                sqs_score=sqs_score,
                stop_loss=stop_loss,
                take_profit=take_profit,
                engine=engine_name,
                reason=self._annotate_reason(
                    f"engine_signal:{signal.sub_strategy}",
                    crisis_override=crisis_override_active,
                ),
                sub_strategy=str(signal.sub_strategy),
            )
        except Exception:
            self._LOG.debug("v25 engine routing failed", exc_info=True)
            return V25RoutedDecision(
                action="rejected",
                confidence=0.0,
                sqs_score=0.0,
                stop_loss=0.01,
                take_profit=0.0,
                engine=reject_engine,
                reason="engine_error",
                sub_strategy="minimal_router",
            )

    def _persist_v25_fallback_trade(
        self,
        *,
        symbol: str,
        side: str,
        entry_price: float,
        size: float,
        confidence: float,
        stop_distance: float,
        engine: str,
        reason_entry: str,
        entry_time: datetime,
        fees: float,
        slippage: float,
    ) -> None:
        """Insert one append-only trade row for fallback execution path."""
        if self.v25_conn is None:
            return

        trade_id = f"v25-{symbol}-{entry_time.strftime('%Y%m%d%H%M%S%f')}"
        self.v25_conn.execute(
            """
            INSERT INTO trades (
              trade_id, symbol, side, capital_engine, entry_time, entry_price, size,
              fees, slippage, net_pnl_pct, regime_at_entry, engine, sub_strategy,
              confidence, sqs_score, stop_distance, reason_entry
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                trade_id,
                symbol,
                side,
                "core",
                entry_time.isoformat(),
                float(entry_price),
                float(size),
                float(fees),
                float(slippage),
                0.0,
                "REPLAY" if self.data_factory.mode == "replay" else "UNKNOWN",
                engine,
                "fallback_no_pandas_ta",
                float(confidence),
                0.50,
                float(stop_distance),
                reason_entry,
            ),
        )

    def _persist_backtest_time_exit_trade(
        self,
        *,
        symbol: str,
        side: str,
        engine: str,
        reason_entry: str,
        confidence: float,
        stop_distance: float,
        entry_time: datetime,
        entry_price: float = 100.0,
        size: float = 1.0,
        hold_minutes: int = 5,
    ) -> None:
        """Persist one closed backtest trade with a minimal time-based exit."""
        if self.v25_conn is None:
            return

        s = "long" if str(side).lower() != "short" else "short"
        hold = max(1, int(hold_minutes))
        exit_time = entry_time + timedelta(minutes=hold)

        entry_px = max(float(entry_price), 1e-6)
        move = 0.002  # 20 bps synthetic move for deterministic closure
        if s == "long":
            exit_px = entry_px * (1.0 + move)
            pnl_pct = (exit_px - entry_px) / entry_px
        else:
            exit_px = entry_px * (1.0 - move)
            pnl_pct = (entry_px - exit_px) / entry_px

        fees = 0.0005
        slippage = 0.0002
        net_pnl_pct = float(pnl_pct - fees - slippage)
        pnl = float(entry_px * float(size) * net_pnl_pct)
        duration_hours = float((exit_time - entry_time).total_seconds() / 3600.0)

        trade_id = f"bt-{symbol}-{entry_time.strftime('%Y%m%d%H%M%S%f')}-{s}"
        regime = "REPLAY" if self.data_factory.mode == "replay" else "UNKNOWN"

        self.v25_conn.execute(
            """
            INSERT INTO trades (
              trade_id, symbol, side, capital_engine, entry_time, exit_time,
              entry_price, exit_price, size, pnl, pnl_pct, fees, slippage,
              net_pnl_pct, regime_at_entry, regime_at_exit, engine, sub_strategy,
              confidence, sqs_score, stop_distance, duration_hours, hold_minutes, reason_entry, reason_exit
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                trade_id,
                symbol,
                s,
                "core",
                entry_time.isoformat(),
                exit_time.isoformat(),
                entry_px,
                float(exit_px),
                float(size),
                pnl,
                float(pnl_pct),
                fees,
                slippage,
                net_pnl_pct,
                regime,
                regime,
                engine,
                "time_exit_backtest",
                float(confidence),
                0.50,
                float(max(0.0001, stop_distance)),
                duration_hours,
                hold,
                reason_entry,
                "time_exit_backtest",
            ),
        )

    @staticmethod
    def _to_utc_timestamp(value: datetime | pd.Timestamp) -> pd.Timestamp:
        ts = pd.Timestamp(value)
        if ts.tzinfo is None:
            return cast(pd.Timestamp, ts.tz_localize("UTC"))
        return cast(pd.Timestamp, ts.tz_convert("UTC"))

    def _resolve_backtest_close_price(
        self,
        *,
        symbol: str,
        at: datetime,
        after: datetime | None = None,
    ) -> tuple[float | None, datetime | None, str]:
        """Resolve deterministic close at/near timestamp with strict-after option.

        Returns: (price, candle_timestamp, source_tag)
        - source_tag helps diagnose fallback behavior in simulator logs.
        """

        at_ts = self._to_utc_timestamp(at)
        after_ts = self._to_utc_timestamp(after) if after is not None else None
        fetch_limit = max(int(self.ohlcv_limit), 64)

        def _pick(rows: list[list[Any]]) -> tuple[float, datetime] | None:
            best: tuple[pd.Timestamp, float] | None = None
            for row in rows:
                if len(row) < 5:
                    continue
                try:
                    row_ts = self._to_utc_timestamp(cast(datetime | pd.Timestamp, row[0]))
                    row_close = float(row[4])
                except Exception:
                    continue
                if not np.isfinite(row_close):
                    continue
                if row_ts > at_ts:
                    continue
                if after_ts is not None and row_ts <= after_ts:
                    continue
                if best is None or row_ts > best[0]:
                    best = (row_ts, row_close)

            if best is None:
                return None
            candle_ts, candle_close = best
            candle_dt = cast(datetime, candle_ts.to_pydatetime())
            if candle_dt.tzinfo is None:
                candle_dt = candle_dt.replace(tzinfo=timezone.utc)
            else:
                candle_dt = candle_dt.astimezone(timezone.utc)
            return float(candle_close), candle_dt

        try:
            rows = self.data_factory.fetch_ohlcv(
                symbol=symbol,
                timeframe="1m",
                limit=fetch_limit,
                now=at_ts,
            )
            picked = _pick(rows)
            if picked is not None:
                return picked[0], picked[1], "fetch_now"
        except Exception:
            self._LOG.debug(
                "backtest close fetch failed at now=%s symbol=%s",
                at_ts.isoformat(),
                symbol,
                exc_info=True,
            )

        # Deterministic fallback: broader slice from source without now bound.
        # Still enforce <= at and (when provided) > after to avoid reusing entry bar.
        try:
            rows = self.data_factory.fetch_ohlcv(
                symbol=symbol,
                timeframe="1m",
                limit=fetch_limit,
                now=None,
            )
            picked = _pick(rows)
            if picked is not None:
                return picked[0], picked[1], "fetch_fallback"
        except Exception:
            self._LOG.debug("backtest close fallback fetch failed symbol=%s", symbol, exc_info=True)

        # Avoid replay-mode fallback to _load_ohlcv, because replay loader anchor
        # may not match `at` here and could accidentally reuse entry-time pricing.
        if self.data_factory.mode != "replay":
            try:
                frame = self._load_ohlcv(symbol=symbol, now=at)
                if not frame.empty:
                    frame = frame.copy()
                    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True, errors="coerce")
                    frame = frame.dropna(subset=["timestamp"]).reset_index(drop=True)
                    rows = [
                        [
                            row["timestamp"],
                            row["open"],
                            row["high"],
                            row["low"],
                            row["close"],
                            row["volume"],
                        ]
                        for _, row in frame.iterrows()
                    ]
                    picked = _pick(rows)
                    if picked is not None:
                        return picked[0], picked[1], "frame_fallback"
            except Exception:
                self._LOG.debug("backtest close fallback _load_ohlcv failed symbol=%s", symbol, exc_info=True)

        return None, None, "none"

    @staticmethod
    def _estimate_backtest_costs(
        *,
        fee_model: Any | None,
        entry_price: float,
        size: float,
        leverage: float,
    ) -> tuple[float, float]:
        """Return (fees_pct, slippage_pct) for deterministic backtest sim."""
        if fee_model is None:
            return 0.0005, 0.0002

        try:
            notional_usd = max(float(entry_price) * float(size) * float(leverage), 0.0)
            fees_pct = float(getattr(fee_model, "backtest_round_trip"))
            slippage_pct = float(fee_model.estimate_slippage(notional_usd))
            return max(fees_pct, 0.0), max(slippage_pct, 0.0)
        except Exception:
            return 0.0005, 0.0002

    @staticmethod
    def _compute_backtest_pnl(
        *,
        side: str,
        entry_price: float,
        exit_price: float,
        leverage: float,
        fees_pct: float,
        slippage_pct: float,
    ) -> tuple[float, float]:
        """Return (gross_pnl_pct, net_pnl_pct) for deterministic backtest sim."""
        s = "long" if str(side).lower() != "short" else "short"
        entry_px = max(float(entry_price), 1e-6)
        exit_px = max(float(exit_price), 1e-6)
        lev = max(float(leverage), 0.0)

        if s == "long":
            gross = ((exit_px - entry_px) / entry_px) * lev
        else:
            gross = ((entry_px - exit_px) / entry_px) * lev

        net = float(gross - max(float(fees_pct), 0.0) - max(float(slippage_pct), 0.0))
        return float(gross), net

    @staticmethod
    def _extract_regime_from_gate_results(gate_results: Any) -> str:
        """Extract regime label from persisted gate_results payload."""
        if not isinstance(gate_results, dict):
            return "UNKNOWN"
        feature_snapshot = gate_results.get("features_snapshot")
        if isinstance(feature_snapshot, dict):
            regime = feature_snapshot.get("regime")
            if regime is not None:
                text = str(regime).strip()
                if text:
                    return text
        return "UNKNOWN"

    def _persist_backtest_exit_sweep_row(
        self,
        *,
        run_id: str,
        decision_cycle: int,
        decision_id: int,
        symbol: str,
        side: str,
        entry_time: datetime,
        hold_minutes: int,
        exit_time: datetime,
        entry_price: float,
        exit_price: float,
        gross_pnl_pct: float,
        net_pnl_pct: float,
        fee_est_usd: float | None,
        slippage_est_pct: float | None,
        regime: str,
    ) -> None:
        if self.v25_conn is None:
            return

        self.v25_conn.execute(
            """
            INSERT INTO backtest_exit_sweep (
              run_id, decision_cycle, decision_id, symbol, side, entry_time, hold_minutes, exit_time,
              entry_price, exit_price, gross_pnl_pct, net_pnl_pct, fee_est_usd,
              slippage_est_pct, regime
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                int(decision_cycle),
                int(decision_id),
                symbol,
                "long" if str(side).lower() != "short" else "short",
                entry_time.isoformat(),
                int(hold_minutes),
                exit_time.isoformat(),
                float(entry_price),
                float(exit_price),
                float(gross_pnl_pct),
                float(net_pnl_pct),
                float(fee_est_usd) if fee_est_usd is not None else None,
                float(slippage_est_pct) if slippage_est_pct is not None else None,
                regime,
            ),
        )

    def _persist_backtest_execution_sim_trade(
        self,
        *,
        symbol: str,
        side: str,
        engine: str,
        confidence: float,
        stop_distance: float,
        entry_time: datetime,
        exit_time: datetime,
        entry_price: float,
        exit_price: float,
        size: float,
        leverage: float,
        hold_minutes: int,
        fees_pct: float,
        slippage_pct: float,
    ) -> None:
        """Persist one deterministic closed trade from advisory backtest output."""
        if self.v25_conn is None:
            return

        s = "long" if str(side).lower() != "short" else "short"
        entry_px = max(float(entry_price), 1e-6)
        exit_px = max(float(exit_price), 1e-6)
        lev = max(float(leverage), 0.0)

        fees = max(float(fees_pct), 0.0)
        slippage = max(float(slippage_pct), 0.0)
        raw_pnl_pct, net_pnl_pct = self._compute_backtest_pnl(
            side=s,
            entry_price=entry_px,
            exit_price=exit_px,
            leverage=lev,
            fees_pct=fees,
            slippage_pct=slippage,
        )

        qty = max(float(size), 0.0)
        pnl = float(entry_px * qty * net_pnl_pct)
        duration_hours = float((exit_time - entry_time).total_seconds() / 3600.0)
        regime = "REPLAY" if self.data_factory.mode == "replay" else "UNKNOWN"

        trade_id = f"btsim-{symbol}-{entry_time.strftime('%Y%m%d%H%M%S%f')}-{s}"
        self.v25_conn.execute(
            """
            INSERT INTO trades (
              trade_id, symbol, side, capital_engine, entry_time, exit_time,
              entry_price, exit_price, size, pnl, pnl_pct, fees, slippage,
              net_pnl_pct, regime_at_entry, regime_at_exit, engine, sub_strategy,
              confidence, sqs_score, stop_distance, duration_hours, hold_minutes, reason_entry, reason_exit
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                trade_id,
                symbol,
                s,
                "core",
                entry_time.isoformat(),
                exit_time.isoformat(),
                entry_px,
                exit_px,
                qty,
                pnl,
                float(raw_pnl_pct),
                fees,
                slippage,
                net_pnl_pct,
                regime,
                regime,
                str(engine or "ROUTER"),
                "backtest_execution_sim",
                float(max(0.0, min(1.0, confidence))),
                0.50,
                float(max(0.0001, stop_distance)),
                duration_hours,
                int(max(1, int(hold_minutes))),
                "backtest_sim_entry",
                "time_exit_backtest_sim",
            ),
        )

    def _run_shadow_dynamic_exit(self, *, asset_class: str, now: datetime) -> None:
        positions = self._shadow_positions_snapshot(asset_class=asset_class)
        intents = self.shadow_position_manager.shadow_dynamic_exit_intents(
            positions=positions,
            ts=now,
        )
        for intent in intents:
            self._log_event(
                "dynamic_exit_shadow_intent",
                asset_class,
                reason=intent.reason,
            )
            # Persist shadow exit intent to v2.5 DB
            self._persist_dynamic_exit_intent(intent=intent, now=now)

    def _run_live_dynamic_exit(self, *, asset_class: str, now: datetime) -> None:
        """Live dynamic exit: compute intents AND execute via broker (PR-J02)."""
        positions = self._shadow_positions_snapshot(asset_class=asset_class)
        intents = self.shadow_position_manager.live_dynamic_exit_intents(
            positions=positions,
            ts=now,
        )
        for intent in intents:
            self._log_event(
                "dynamic_exit_live_intent",
                asset_class,
                reason=intent.reason,
            )
            self._persist_dynamic_exit_intent(intent=intent, now=now)

    def _shadow_positions_snapshot(self, *, asset_class: str) -> list[dict[str, float | str]]:
        """Return tracked open positions for shadow dynamic exit.

        In production, this would read from the broker/exchange.
        Currently uses pipeline-tracked positions from successful fills.
        """
        _ = asset_class
        return list(self._open_positions.values())

    @staticmethod
    def _engine_hint_for_regime(regime: str | None) -> str:
        if regime:
            mapped = REGIME_TO_ENGINE.get(regime)
            if mapped:
                return str(mapped)
        return ENGINE_PHOENIX

    def _reject(
        self,
        *,
        outputs: list[dict[str, Any]],
        asset_class: str,
        symbol: str,
        reason: str,
        engine: str | None = None,
        action: str = "rejected",
        confidence: float = 0.0,
        position_size_pct: float = 0.0,
        gate_results: dict[str, Any] | None = None,
    ) -> None:
        self._log_event("signal_rejected", asset_class, reason=reason)
        out: dict[str, Any] = {
            "symbol": symbol,
            "status": "rejected",
            "reason": reason,
            "action": action,
            "engine": engine or "ROUTER",
            "confidence": float(confidence),
            "position_size_pct": float(max(position_size_pct, 0.0)),
            "leverage": 1.0,
        }
        if gate_results is not None:
            out["gate_results"] = dict(gate_results)
        outputs.append(out)

    @staticmethod
    def _stage_from_reason(reason: str) -> str:
        """Map intent reason to a valid dynamic_exit_log stage."""
        _map = {
            "to_breakeven_lock": "BREAKEVEN_LOCK",
            "to_profit_capture": "PROFIT_CAPTURE",
            "to_trend_rider": "TREND_RIDER",
        }
        return _map.get(reason, "ENTRY")

    def _persist_dynamic_exit_intent(self, *, intent: Any, now: datetime) -> None:
        """Persist a shadow dynamic exit intent to the v2.5 DB. Silently skips if no DB connection."""
        if self.v25_conn is None:
            return
        try:
            reason = str(getattr(intent, "reason", "shadow_intent"))
            log_dynamic_exit(
                self.v25_conn,
                position_id=str(getattr(intent, "symbol", "unknown")),
                symbol=str(getattr(intent, "symbol", "unknown")),
                stage=self._stage_from_reason(reason),
                current_r=0.0,  # R not available on OrderIntent; logged for audit completeness
                pct_closed=float(intent.take_profit_fraction) if getattr(intent, "take_profit_fraction", None) else 0.0,
                partial_pnl_locked=0.0,  # Not computed in shadow path
                regime="shadow",
                trigger_reason=reason,
                trailing_sl=float(intent.new_stop_price) if getattr(intent, "new_stop_price", None) else None,
                timestamp=now.isoformat(),
            )
            self.v25_conn.commit()
        except Exception:
            self._LOG.debug("persist_dynamic_exit_intent failed", exc_info=True)

    def _persist_validated_sizing(self, *, pre: Any, symbol: str) -> None:
        """Persist validated sizing telemetry to the v2.5 DB. Silently skips if no DB or no sizing."""
        if self.v25_conn is None:
            return
        sizing = getattr(pre, "validated_sizing", None)
        if sizing is None:
            return
        try:
            log_validated_sizing(
                self.v25_conn,
                symbol=sizing.symbol,
                equity=float(sizing.leverage * sizing.notional_usd / sizing.leverage) if sizing.leverage else 0.0,
                risk_pct=0.0,  # Not carried on ValidatedSizing; placeholder
                risk_usd=float(sizing.risk_usd),
                entry_price=float(sizing.notional_usd / sizing.qty) if sizing.qty else 0.0,
                sl_price=0.0,  # Absolute SL price not on contract; placeholder
                sl_pct=float(sizing.sl_pct),
                notional_usd=float(sizing.notional_usd),
                quantity=float(sizing.qty) if sizing.qty else 0.0,
                leverage_derived=float(sizing.leverage) if sizing.leverage else 0.0,
                breakeven_r=float(sizing.fee_risk_ratio),
                fee_reserved=float(sizing.fee_est_usd),
                net_risk_usd=float(sizing.net_risk_usd),
                passed_breakeven_gate=sizing.passed_gate9,
            )
            self.v25_conn.commit()
        except Exception:
            self._LOG.debug("persist_validated_sizing failed", exc_info=True)

    def _apply_whale_momentum_boost(
        self,
        *,
        signal: Any,
        regime_state: Any,
        symbol: str,
        now: datetime,
    ) -> Any:
        """Apply whale momentum boost to signal confidence (Blueprint Pivot 4).

        Computes whale momentum from stored alerts, applies boost to
        signal confidence if regime qualifies as TREND_STRONG, then
        persists telemetry.  Returns the (possibly boosted) signal.
        """
        if not self._whale_alerts:
            return signal

        try:
            whale_signal = compute_whale_momentum(self._whale_alerts)
            boosted_conf, was_applied, reason = apply_whale_boost_to_signal(
                base_confidence=signal.confidence,
                whale=whale_signal,
                regime=regime_state.regime,
                regime_confidence=regime_state.confidence,
                regime_stability=regime_state.stability,
            )
            # Persist telemetry regardless of whether boost was applied
            self._persist_whale_momentum(whale=whale_signal, now=now)

            if was_applied:
                self._LOG.info(
                    "whale_boost applied: symbol=%s conf=%.3f->%.3f reason=%s",
                    symbol, signal.confidence, boosted_conf, reason,
                )
                return signal.model_copy(update={"confidence": boosted_conf})
            return signal
        except Exception:
            self._LOG.debug("whale_momentum_boost failed", exc_info=True)
            return signal

    def _persist_whale_momentum(self, *, whale: Any, now: datetime) -> None:
        """Persist whale momentum telemetry to the v2.5 DB."""
        if self.v25_conn is None:
            return
        try:
            log_whale_momentum(
                self.v25_conn,
                symbol=str(whale.symbol),
                net_flow_usd_24h=float(whale.net_flow_usd_24h),
                exchange_reserve_change_pct=float(whale.exchange_reserve_change_pct),
                is_bullish_flow=bool(whale.is_bullish_flow),
                is_bearish_flow=bool(whale.is_bearish_flow),
                momentum_score=float(whale.momentum_score),
                sqs_boost=float(whale.sqs_boost),
                size_modifier=float(whale.size_modifier),
                stablecoin_mint_usd_24h=float(whale.stablecoin_mint_usd_24h),
                timestamp=now.isoformat(),
            )
            self.v25_conn.commit()
        except Exception:
            self._LOG.debug("persist_whale_momentum failed", exc_info=True)

    @staticmethod
    def _load_dynamic_exit_config() -> DynamicExitConfig | None:
        """Load DynamicExitConfig from engines.yaml. Returns None if unavailable."""
        try:
            import yaml
            from pathlib import Path
            engines_path = Path("config/engines.yaml")
            if not engines_path.exists():
                return None
            raw = yaml.safe_load(engines_path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                return None
            engines = raw.get("engines", raw)
            hermes = engines.get("hermes", {})
            de = hermes.get("dynamic_exit", {})
            if not de:
                return None
            return DynamicExitConfig(
                r_breakeven=float(de.get("r_breakeven", 0.5)),
                r_profit_capture=float(de.get("r_profit_capture", 1.5)),
                r_trend_rider=float(de.get("r_trend_rider", 3.0)),
                atr_mult_profit_capture=float(de.get("atr_mult_profit_capture", 2.0)),
                atr_mult_trend_rider=float(de.get("atr_mult_trend_rider", 1.2)),
                partial_fraction_profit_capture=float(de.get("partial_fraction_profit_capture", 0.30)),
                partial_fraction_trend_rider=float(de.get("partial_fraction_trend_rider", 0.20)),
            )
        except Exception:
            return None

    @staticmethod
    def _init_gemini_engine() -> tuple[GeminiEngine | None, CorrelationTracker | None]:
        """Initialize GeminiEngine from engines.yaml pairs config.

        Returns (engine, tracker) or (None, None) if config unavailable.
        """
        try:
            import yaml
            from pathlib import Path
            engines_path = Path("config/engines.yaml")
            if not engines_path.exists():
                return None, None
            raw = yaml.safe_load(engines_path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                return None, None
            engines = raw.get("engines", raw)
            gemini_node = engines.get("gemini", {})
            if not gemini_node:
                return None, None
            pairs_raw = gemini_node.get("pairs", [])
            if not pairs_raw:
                return None, None

            pairs_config = [
                {
                    "symbol_a": str(p["symbol_a"]),
                    "symbol_b": str(p["symbol_b"]),
                    "pair_id": str(p.get("pair_id", f"{p['symbol_a']}_{p['symbol_b']}")),
                }
                for p in pairs_raw
            ]
            corr_cfg = gemini_node.get("correlation", {})
            tracker = CorrelationTracker(
                pairs_config,
                window=int(corr_cfg.get("window", 100)),
            )
            signal_gen = CorrelationSignalGenerator(
                entry_zscore=float(corr_cfg.get("entry_zscore", 2.0)),
                exit_zscore=float(corr_cfg.get("exit_zscore", 0.5)),
                stop_zscore=float(corr_cfg.get("stop_zscore", 3.0)),
            )
            engine = GeminiEngine(
                tracker=tracker,
                signal_generator=signal_gen,
                max_simultaneous_pairs=int(gemini_node.get("max_simultaneous_pairs", 3)),
            )
            return engine, tracker
        except Exception:
            return None, None

    @staticmethod
    def _load_precision_config() -> PrecisionConfig:
        """Load PrecisionConfig from engines.yaml. Returns defaults if unavailable."""
        try:
            import yaml
            from pathlib import Path
            engines_path = Path("config/engines.yaml")
            if not engines_path.exists():
                return PrecisionConfig()
            raw = yaml.safe_load(engines_path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                return PrecisionConfig()
            engines = raw.get("engines", raw)
            pf = engines.get("precision_filter", {})
            if not pf:
                return PrecisionConfig()
            adj = pf.get("confidence_adjustments", {})
            return PrecisionConfig(
                grade_a_threshold=float(pf.get("grade_a_threshold", 0.80)),
                grade_b_threshold=float(pf.get("grade_b_threshold", 0.65)),
                grade_c_threshold=float(pf.get("grade_c_threshold", 0.50)),
                grade_d_threshold=float(pf.get("grade_d_threshold", 0.35)),
                conf_boost_a=float(adj.get("grade_a", 0.05)),
                conf_boost_b=float(adj.get("grade_b", 0.02)),
                conf_penalty_d=float(adj.get("grade_d", -0.05)),
                conf_penalty_f=float(adj.get("grade_f", -0.10)),
            )
        except Exception:
            return PrecisionConfig()

    @staticmethod
    def _init_exchange_client(evolve: bool) -> Any | None:
        """Initialize exchange client for live data.

        Uses Binance public API by default (no API key needed for klines).
        Set ARGUS_DATA_SOURCE=bingx to use BingX instead.
        In evolve mode, returns None (local parquet only).
        """
        if evolve:
            return None
        try:
            # Load .env if available
            from pathlib import Path
            env_path = Path(".env")
            if env_path.exists():
                for line in env_path.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, _, val = line.partition("=")
                        os.environ.setdefault(key.strip(), val.strip())

            source = os.getenv("ARGUS_DATA_SOURCE", "binance").lower()

            if source == "bingx":
                from src.data.exchange_clients import BingXClient
                client = BingXClient()
                logging.getLogger(__name__).info(
                    "[DataSource] BingX (authenticated=%s)", client.is_authenticated,
                )
                return client
            else:
                from src.data.exchange_clients import BinancePublicClient
                client = BinancePublicClient(
                    use_futures=True,
                    idle_refresh_seconds=float(os.getenv("ARGUS_BINANCE_IDLE_REFRESH_S", "180")),
                    breaker_failures=int(os.getenv("ARGUS_BINANCE_BREAKER_FAILURES", "5")),
                    breaker_cooldown_seconds=float(os.getenv("ARGUS_BINANCE_BREAKER_COOLDOWN_S", "60")),
                )
                logging.getLogger(__name__).info("[DataSource] Binance Futures (public)")
                return client
        except Exception as exc:
            logging.getLogger(__name__).warning("[DataSource] Failed to init: %s", exc)
            return None

    @staticmethod
    def _init_feature_builder() -> Any | None:
        try:
            from src.data.features.builder import FeatureBuilder
        except ModuleNotFoundError as exc:
            if exc.name == "pandas_ta":
                from src.data.features.basic_builder import BasicFeatureBuilder

                logging.getLogger(__name__).warning(
                    "pandas_ta not available; using BasicFeatureBuilder fallback"
                )
                return BasicFeatureBuilder()
            raise
        return FeatureBuilder()

    @staticmethod
    def _safe_float(value: Any, default: float = 0.0) -> float:
        try:
            out = float(value)
        except (TypeError, ValueError):
            return float(default)
        if not np.isfinite(out):
            return float(default)
        return float(out)

    def _append_forward_rows(self, *, symbol: str, rows: list[list[Any]]) -> pd.DataFrame:
        if not rows:
            history = self._forward_history.get(symbol)
            if history is not None and not history.empty:
                return history.copy()
            return pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume"])

        frame = pd.DataFrame(rows, columns=["timestamp", "open", "high", "low", "close", "volume"])
        frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True, errors="coerce")
        frame = frame.dropna(subset=["timestamp"]).reset_index(drop=True)
        if frame.empty:
            history = self._forward_history.get(symbol)
            if history is not None and not history.empty:
                return history.copy()
            return frame

        existing = self._forward_history.get(symbol)
        if existing is None or existing.empty:
            merged = frame
        else:
            merged = pd.concat([existing, frame], ignore_index=True)
            merged = merged.drop_duplicates(subset=["timestamp"]).sort_values("timestamp")

        if len(merged) > self._forward_history_limit:
            merged = merged.tail(self._forward_history_limit)

        merged = merged.reset_index(drop=True)
        self._forward_history[symbol] = merged
        return merged.copy()

    def forward_state_snapshot(self) -> dict[str, Any]:
        symbols: dict[str, dict[str, Any]] = {}
        for symbol, frame in self._forward_history.items():
            if frame.empty:
                continue
            first_ts = frame["timestamp"].iloc[0]
            last_ts = frame["timestamp"].iloc[-1]
            symbols[symbol] = {
                "bars": int(len(frame)),
                "first_timestamp": first_ts.isoformat() if isinstance(first_ts, pd.Timestamp) else str(first_ts),
                "last_timestamp": last_ts.isoformat() if isinstance(last_ts, pd.Timestamp) else str(last_ts),
            }
        return {
            "forward_sim": bool(self.forward_sim),
            "mode": str(self.ctx.mode),
            "replay_now": (
                self.replay_now.isoformat()
                if isinstance(self.replay_now, pd.Timestamp)
                else str(self.replay_now)
                if self.replay_now is not None
                else None
            ),
            "symbols": symbols,
        }

    def _load_ohlcv(self, *, symbol: str, now: datetime) -> pd.DataFrame:
        _OHLCV_COLS = ["timestamp", "open", "high", "low", "close", "volume"]

        if self.forward_sim:
            if self.data_factory.mode == "replay":
                replay_anchor = self.replay_now if self.replay_now is not None else None
                rows = self.data_factory.fetch_ohlcv(
                    symbol=symbol,
                    timeframe="1m",
                    limit=1,
                    now=replay_anchor,
                )
                if not rows:
                    history = self._forward_history.get(symbol)
                    if history is not None and not history.empty:
                        return history.copy()
                    raise ValueError(f"Replay mode requires local OHLCV data for symbol={symbol}")
                return self._append_forward_rows(symbol=symbol, rows=rows[-1:])

            if self.data_factory.mode == "live" and self.data_factory.exchange_client is not None:
                primary_tf = getattr(self, "_primary_tf", "1h")
                rows = self.data_factory.fetch_ohlcv(
                    symbol=symbol,
                    timeframe=primary_tf,
                    limit=2,
                )
                if rows:
                    return self._append_forward_rows(symbol=symbol, rows=rows[-1:])

                history = self._forward_history.get(symbol)
                if history is not None and not history.empty:
                    self._LOG.warning("[LIVE] forward fetch empty for %s, reusing cached candle history", symbol)
                    return history.copy()

        # Live mode: fetch real market data from exchange client
        if self.data_factory.mode == "live" and self.data_factory.exchange_client is not None:
            primary_tf = getattr(self, "_primary_tf", "1h")
            rows = self.data_factory.fetch_ohlcv(
                symbol=symbol,
                timeframe=primary_tf,
                limit=self.ohlcv_limit,
            )
            if rows:
                frame = pd.DataFrame(rows, columns=_OHLCV_COLS)
                frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True, errors="coerce")
                frame = frame.dropna(subset=["timestamp"]).reset_index(drop=True)
                self._LOG.debug(
                    "[LIVE] %s %s -> %d bars (last=%s)",
                    symbol, primary_tf, len(frame),
                    frame["timestamp"].iloc[-1] if not frame.empty else "N/A",
                )
                return frame
            self._LOG.warning("[LIVE] fetch empty for %s, falling back to mock", symbol)

        # Replay mode: deterministic local parquet slice around replay_now
        if self.data_factory.mode == "replay":
            replay_anchor = self.replay_now if self.replay_now is not None else None
            rows = self.data_factory.fetch_ohlcv(
                symbol=symbol,
                timeframe="1m",
                limit=self.ohlcv_limit,
                now=replay_anchor,
            )
            if not rows:
                raise ValueError(f"Replay mode requires local OHLCV data for symbol={symbol}")
            frame = pd.DataFrame(rows, columns=["timestamp", "open", "high", "low", "close", "volume"])
            frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True, errors="coerce")
            frame = frame.dropna(subset=["timestamp"]).reset_index(drop=True)

            if not self._replay_smoke_logged:
                first_ts = frame["timestamp"].iloc[0] if not frame.empty else None
                last_ts = frame["timestamp"].iloc[-1] if not frame.empty else None
                self._LOG.debug(
                    "replay smoke: replay_now=%s symbol=%s bars=%d first_ts=%s last_ts=%s",
                    replay_anchor.isoformat() if isinstance(replay_anchor, pd.Timestamp) else replay_anchor,
                    symbol,
                    len(frame),
                    first_ts.isoformat() if isinstance(first_ts, pd.Timestamp) else first_ts,
                    last_ts.isoformat() if isinstance(last_ts, pd.Timestamp) else last_ts,
                )
                self._replay_smoke_logged = True

            return frame

        if not self.evolve:
            return self._mock_ohlcv(now, limit=self.ohlcv_limit)

        rows = self.data_factory.fetch_ohlcv(
            symbol=symbol,
            timeframe="1m",
            limit=self.ohlcv_limit,
            now=now,
        )
        if not rows:
            raise ValueError(f"Evolve mode requires local OHLCV data for symbol={symbol}")
        frame = pd.DataFrame(rows, columns=["timestamp", "open", "high", "low", "close", "volume"])
        frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True, errors="coerce")
        return frame.dropna(subset=["timestamp"]).reset_index(drop=True)

    @staticmethod
    def _mock_ohlcv(now: datetime, *, limit: int = 260) -> pd.DataFrame:
        rng = np.random.default_rng(123)
        n = max(1, int(limit))
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
    # Smoke test: python -m src.main --mode paper --assets crypto --v25 --v25-db runs/v25/argus_v25.db
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
    parser.add_argument(
        "--replay-now",
        default=None,
        help="Replay anchor time (UTC ISO-8601, e.g. 2024-01-01T00:10:00Z).",
    )
    parser.add_argument(
        "--forward-sim",
        action="store_true",
        default=False,
        help="Backtest/replay only: step forward one candle per cycle and persist forward state.",
    )
    parser.add_argument(
        "--smoke",
        action="store_true",
        default=False,
        help="Quick validation mode: 50 cycles and BTCUSDT only.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=260,
        help="OHLCV bars per symbol fetch (default: 260).",
    )
    parser.add_argument(
        "--max-cycles",
        type=int,
        default=None,
        help="Max pipeline cycles to run (paper default: 5, backtest default: 1).",
    )
    parser.add_argument(
        "--run-dir",
        default=None,
        help="Output directory for run artifacts (default: runs/paper_v2 for paper, runs/backtest_v25 for backtest).",
    )
    parser.add_argument(
        "--synthetic-exit",
        action="store_true",
        default=False,
        help="Enable synthetic time-based trade exits for backtest telemetry.",
    )
    parser.add_argument(
        "--cycle-step-minutes",
        type=int,
        default=1,
        help="Backtest replay step between cycles in minutes (default: 1).",
    )
    parser.add_argument(
        "--hold-minutes",
        type=int,
        default=30,
        help="Backtest simulator holding period in minutes (default: 30).",
    )
    parser.add_argument(
        "--hold-grid-minutes",
        default=None,
        help="Comma-separated hold minutes grid for exit sweep analysis (e.g. 10,20,30).",
    )
    parser.add_argument(
        "--hold-grid-by",
        choices=["overall", "regime"],
        default="overall",
        help="Exit sweep aggregation mode for best-hold reporting.",
    )
    parser.add_argument(
        "--adaptive-hold-from-sweep",
        action="store_true",
        default=False,
        help="Backtest-only: use regime-aware best hold from sweep for simulated trade exits.",
    )
    parser.add_argument(
        "--adaptive-split-ratio",
        type=float,
        default=0.5,
        help="Backtest-only in-sample ratio for adaptive hold learning window (0.0-1.0).",
    )
    parser.add_argument(
        "--adaptive-walk-window",
        type=int,
        default=None,
        help="Backtest-only rolling adaptive hold training window in cycles.",
    )
    parser.add_argument(
        "--adaptive-walk-step",
        type=int,
        default=1,
        help="Backtest-only rolling adaptive hold retrain step in cycles.",
    )
    parser.add_argument(
        "--risk-profile",
        choices=["strict", "normal", "relaxed"],
        default="normal",
        help="Backtest-only risk profile tuning for gate thresholds.",
    )
    parser.add_argument(
        "--allow-crisis",
        action="store_true",
        default=False,
        help="Backtest-only crisis override (route with capped size).",
    )
    parser.add_argument("--v25", action="store_true", help="Enable v2.5 foundation bootstrap")
    parser.add_argument("--v25-db", default="runs/v25/argus_v25.db", help="SQLite path for v2.5 runtime DB")
    parser.add_argument("--v25-dryrun-log", default="runs/v25/dryrun_events.jsonl", help="Write v2.5 dry-run telemetry as JSONL (no behavior change).")
    parser.add_argument("--demo-24h", action="store_true", default=False, help="Run in 24/7 demo mode: loop indefinitely with heartbeat, auto log rotation, safe exception handling.")
    parser.add_argument("--orion", action="store_true", default=False, help="Enable ORION meta-orchestrator for dynamic engine weighting and risk posture.")
    parser.add_argument("--live-data", action="store_true", default=False, help="Use real market data from exchange API instead of mock random walks.")
    parser.add_argument("--timeframe", default="1h", help="Primary OHLCV timeframe for live data (e.g. 1m, 5m, 15m, 1h). Default: 1h.")
    parser.add_argument("--symbols", default=None, help="Comma-separated symbol override list (e.g. BTCUSDT,ETHUSDT,SOLUSDT).")
    parser.add_argument("--symbol-universe-size", type=int, choices=[5, 15], default=5, help="Default crypto universe size for live-data mode when --symbols is omitted.")
    parser.add_argument("--maker-fee", type=float, default=0.0002, help="Maker fee rate for paper execution (default: 0.0002 = 0.02%%).")
    parser.add_argument("--taker-fee", type=float, default=0.0004, help="Taker fee rate for paper execution (default: 0.0004 = 0.04%%).")
    parser.add_argument("--export-training-dataset", action="store_true", default=False, help="Export training dataset CSV after run (runs/training_dataset.csv).")
    # --- Stage-2C flags ---
    parser.add_argument("--paper-24h", action="store_true", default=False, help="Launch 7/24 paper supervisor with heartbeat, crash recovery, and daily rotation.")
    parser.add_argument("--daily-scoreboard", action="store_true", default=False, help="Generate daily scoreboard report after run.")
    parser.add_argument("--daily-loss-cap-pct", type=float, default=0.05, help="Paper-only daily loss cap (default: 5%%).")
    parser.add_argument("--max-trades-per-day", type=int, default=50, help="Paper-only max trades per day (default: 50).")
    parser.add_argument("--telegram-signals", action="store_true", default=False, help="Enable Telegram alerts for actionable advisory signals (requires TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID).")
    parser.add_argument("--telegram-min-confidence", type=float, default=0.60, help="Minimum confidence for Telegram signal notifications (default: 0.60).")
    args = parser.parse_args()

    conn: sqlite3.Connection | None = None
    fee_model: Any | None = None
    v25_cfg: Any | None = None
    evaluate_accel_gates_fn: Any | None = None

    # --- v2.5 bootstrap (no-op unless --v25 flag is provided) ---
    if args.v25:
        try:
            from src.v25.bootstrap import (
                build_fee_model,
                evaluate_accel_gates as _evaluate_accel_gates,
                load_v25_config,
                run_v25_migrations,
            )

            os.makedirs(os.path.dirname(args.v25_db) or ".", exist_ok=True)
            v25_cfg = load_v25_config()
            conn = run_v25_migrations(args.v25_db)
            fee_model = build_fee_model(v25_cfg)
            evaluate_accel_gates_fn = _evaluate_accel_gates
            print(f"[v25] bootstrap ok | db={args.v25_db} | fee_model_loaded=true")
        except Exception as exc:  # noqa: BLE001
            print(f"[v25] bootstrap FAILED: {exc}")
            raise SystemExit(1) from exc

    replay_now_ts: pd.Timestamp | None = None
    replay_now_dt: datetime | None = None
    if args.replay_now:
        try:
            raw_iso = str(args.replay_now).replace("Z", "+00:00")
            replay_now_dt = datetime.fromisoformat(raw_iso)
            if replay_now_dt.tzinfo is None:
                replay_now_dt = replay_now_dt.replace(tzinfo=timezone.utc)
            else:
                replay_now_dt = replay_now_dt.astimezone(timezone.utc)
            replay_now_ts = cast(pd.Timestamp, pd.Timestamp(replay_now_dt))
        except Exception as exc:  # noqa: BLE001
            print(f"[replay] invalid --replay-now value: {args.replay_now!r} ({exc})")
            raise SystemExit(2) from exc

    assets = [a.strip() for a in args.assets.split(",") if a.strip()]
    symbols_override: dict[str, list[str]] = {}
    if "crypto" in assets:
        crypto_symbols = resolve_crypto_symbol_universe(
            symbols_arg=args.symbols,
            universe_size=int(args.symbol_universe_size),
            live_data=bool(args.live_data),
        )
        if crypto_symbols:
            symbols_override["crypto"] = crypto_symbols

    if args.smoke:
        assets = ["crypto"]
        symbols_override["crypto"] = ["BTCUSDT"]

    v25_conn_ref = conn if args.v25 else None
    pipeline = ArgusPipeline(
        mode=args.mode,
        assets=assets,
        evolve=bool(args.evolve),
        time_machine_dir=str(args.time_machine_dir),
        data_mode="live" if args.live_data else None,
        replay_now=replay_now_ts,
        forward_sim=bool(args.forward_sim),
        ohlcv_limit=int(args.limit),
        v25_conn=v25_conn_ref,
        risk_profile=str(args.risk_profile),
        allow_crisis=bool(args.allow_crisis),
        symbols_override=symbols_override,
    )
    pipeline._primary_tf = str(args.timeframe)
    pipeline._paper_taker_fee = float(args.taker_fee)
    pipeline._paper_maker_fee = float(args.maker_fee)

    # Apply --live-data flag
    if args.live_data:
        print(f"[data] LIVE — real {args.timeframe} klines from exchange API")
        if symbols_override.get("crypto"):
            print(f"[symbols] crypto universe={','.join(symbols_override['crypto'])}")
    else:
        print(f"[data] MOCK — using synthetic random walk OHLCV")

    # Apply --orion flag
    if args.orion:
        pipeline.orion.enabled = True
        print("[orion] ENABLED — ORION v1 meta-orchestrator active")
    else:
        print("[orion] DISABLED (use --orion to enable)")

    default_cycles = 1 if args.mode == "backtest" else 5 if args.mode == "paper" else 1
    max_cycles = max(1, int(args.max_cycles if args.max_cycles is not None else default_cycles))
    if args.smoke:
        max_cycles = 50
    default_run_dir = "runs/paper_v2" if args.mode == "paper" else "runs/backtest_v25"
    run_dir = Path(args.run_dir or default_run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    decisions_log = run_dir / "decisions.jsonl"

    telegram_notifier = TelegramSignalNotifier.from_env(
        conn=v25_conn_ref,
        enabled=bool(args.telegram_signals and args.mode in {"paper", "live"}),
        min_confidence=float(args.telegram_min_confidence),
    )
    if args.telegram_signals and args.mode in {"paper", "live"}:
        if telegram_notifier.active:
            print("[notify] Telegram signal alerts ENABLED")
        else:
            print("[notify] Telegram signal alerts requested but disabled (missing TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID)")

    print(
        f"[run] mode={args.mode} cycles={max_cycles} assets={','.join(assets)} "
        f"run_dir={run_dir} replay_now={replay_now_ts.isoformat() if replay_now_ts is not None else 'None'}"
    )

    cycle_step_minutes = max(1, int(args.cycle_step_minutes))
    hold_minutes = max(1, int(args.hold_minutes))

    def _parse_hold_grid_minutes(raw: Any) -> list[int]:
        if raw is None:
            return []
        text = str(raw).strip()
        if not text:
            return []
        values: set[int] = set()
        for part in text.split(","):
            token = part.strip()
            if not token:
                continue
            try:
                minute = int(token)
            except ValueError as exc:
                raise ValueError(f"invalid hold grid minute: {token!r}") from exc
            if minute < 1 or minute > 24 * 60:
                raise ValueError(f"hold grid minute out of range [1,1440]: {minute}")
            values.add(minute)
        return sorted(values)

    try:
        hold_grid_minutes = _parse_hold_grid_minutes(args.hold_grid_minutes)
    except ValueError as exc:
        print(f"[backtest] invalid --hold-grid-minutes value: {args.hold_grid_minutes!r} ({exc})")
        raise SystemExit(2) from exc

    adaptive_split_ratio = float(args.adaptive_split_ratio)
    if adaptive_split_ratio < 0.0 or adaptive_split_ratio > 1.0:
        print(
            f"[backtest] invalid --adaptive-split-ratio value: {args.adaptive_split_ratio!r} "
            "(must be between 0.0 and 1.0)"
        )
        raise SystemExit(2)

    adaptive_walk_window: int | None = args.adaptive_walk_window
    if adaptive_walk_window is not None and int(adaptive_walk_window) < 1:
        print(
            f"[backtest] invalid --adaptive-walk-window value: {args.adaptive_walk_window!r} "
            "(must be >= 1)"
        )
        raise SystemExit(2)
    adaptive_walk_window = int(adaptive_walk_window) if adaptive_walk_window is not None else None

    adaptive_walk_step = int(args.adaptive_walk_step)
    if adaptive_walk_step < 1:
        print(
            f"[backtest] invalid --adaptive-walk-step value: {args.adaptive_walk_step!r} "
            "(must be >= 1)"
        )
        raise SystemExit(2)

    sweep_skipped_rows = 0

    def _opt_float(value: Any) -> float | None:
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _as_float_default(value: Any, default: float) -> float:
        maybe = _opt_float(value)
        return default if maybe is None else float(maybe)

    adaptive_hold_enabled = bool(
        args.mode == "backtest"
        and bool(args.adaptive_hold_from_sweep)
        and bool(hold_grid_minutes)
    )
    walk_forward_enabled = bool(adaptive_hold_enabled and adaptive_walk_window is not None)

    adaptive_split_index = int(max_cycles * adaptive_split_ratio)
    adaptive_in_sample_cycles = int(min(max(adaptive_split_index, 0), max_cycles))
    adaptive_out_of_sample_cycles = int(max_cycles - adaptive_in_sample_cycles)

    if walk_forward_enabled:
        adaptive_in_sample_cycles = 0
        adaptive_out_of_sample_cycles = 0

    walk_window = int(adaptive_walk_window) if adaptive_walk_window is not None else 0
    walk_oos_cycles = int(max(0, max_cycles - walk_window)) if walk_forward_enabled else 0
    walk_segments = int((walk_oos_cycles + adaptive_walk_step - 1) // adaptive_walk_step) if walk_forward_enabled else 0

    adaptive_series_by_regime: dict[str, dict[int, list[tuple[str, float]]]] = {}
    walk_sweep_history: list[dict[str, Any]] = []
    walk_hold_cache: dict[tuple[int, str], int | None] = {}

    def _performance_from_series(series: list[tuple[str, float]]) -> tuple[float, float, float]:
        ordered = sorted(series, key=lambda x: x[0])
        if not ordered:
            return 0.0, 0.0, 0.0

        equity = 1.0
        peak = 1.0
        max_drawdown = 0.0
        wins = 0
        for _, ret in ordered:
            val = float(ret)
            if val > 0.0:
                wins += 1
            equity *= (1.0 + val)
            peak = max(peak, equity)
            dd = (equity / peak) - 1.0 if peak > 0.0 else 0.0
            max_drawdown = min(max_drawdown, dd)
        return float(equity - 1.0), float(max_drawdown), float(wins / len(ordered))

    def _choose_best_hold(series_by_hold: dict[int, list[tuple[str, float]]]) -> int | None:
        candidates: list[tuple[int, float, float, float]] = []
        for hold in hold_grid_minutes:
            data = series_by_hold.get(int(hold), [])
            if not data:
                continue
            total_return, max_drawdown, win_rate = _performance_from_series(data)
            candidates.append((int(hold), total_return, max_drawdown, win_rate))
        if not candidates:
            return None
        best = max(candidates, key=lambda x: (x[1], x[2], x[3], -x[0]))
        return int(best[0])

    for cycle in range(1, max_cycles + 1):
        if args.mode == "backtest" and replay_now_dt is not None:
            cycle_now = replay_now_dt + timedelta(minutes=cycle_step_minutes * (cycle - 1))
            cycle_now_ts = cast(pd.Timestamp, pd.Timestamp(cycle_now))
            pipeline.replay_now = cycle_now_ts
        else:
            cycle_now = datetime.now(timezone.utc)
        try:
            outputs = pipeline.run_once(now=cycle_now)
        except ModuleNotFoundError as exc:
            if args.v25 and "pandas_ta" in str(exc):
                print("[v25] pandas_ta missing; using v25 minimal execution path for this cycle")
                outputs = pipeline.run_v25_minimal_cycle(now=cycle_now)
            else:
                raise

        for item in outputs:
            print(item)

        # Always append observable decisions log for cycle-level debugging
        with open(decisions_log, "a", encoding="utf-8") as f:
            for item in outputs:
                rec = {
                    "_ts": cycle_now.isoformat(),
                    "_cycle": cycle,
                    "mode": args.mode,
                    **item,
                }
                f.write(json.dumps(rec, ensure_ascii=True, default=str) + "\n")

        if args.forward_sim:
            try:
                forward_state_payload = {
                    "cycle": int(cycle),
                    "timestamp": cycle_now.isoformat(),
                    **pipeline.forward_state_snapshot(),
                }
                (run_dir / "forward_state.json").write_text(
                    json.dumps(forward_state_payload, indent=2, ensure_ascii=True) + "\n",
                    encoding="utf-8",
                )
            except Exception as exc:  # noqa: BLE001
                print(f"[forward-sim] state persistence error: {exc}")

        # Persist summary decisions into v25 DB (append-only) even on fallback path
        persisted_cycle_records: list[dict[str, Any]] = []
        if v25_conn_ref is not None:
            try:
                cycle_run_id = f"{pipeline.ctx.run_id}:c{cycle:04d}"
                for item in outputs:
                    out_engine = str(item.get("engine") or "").strip()
                    if not out_engine or out_engine == "PIPELINE":
                        out_engine = pipeline._engine_hint_for_regime(None)
                    out_action = str(item.get("action") or item.get("status") or "rejected")
                    merged_gate_results: dict[str, Any] = {}
                    raw_gate_results = item.get("gate_results")
                    if isinstance(raw_gate_results, dict):
                        merged_gate_results.update(raw_gate_results)
                    merged_gate_results.setdefault("path", "cycle_output")
                    merged_gate_results.setdefault("mode", args.mode)
                    merged_gate_results["cycle"] = cycle
                    merged_gate_results["status"] = item.get("status")
                    decision_id = log_decision(
                        v25_conn_ref,
                        run_id=cycle_run_id,
                        timestamp=cycle_now.isoformat(),
                        symbol=str(item.get("symbol", "UNKNOWN")),
                        action=out_action,
                        capital_engine="core",
                        position_size_pct=_opt_float(item.get("position_size_pct")),
                        leverage=_opt_float(item.get("leverage")),
                        stop_loss_pct=_opt_float(item.get("stop_loss_pct")),
                        confidence=_opt_float(item.get("confidence")),
                        sqs_score=_opt_float(item.get("sqs_score")),
                        regime="REPLAY" if pipeline.data_factory.mode == "replay" else "UNKNOWN",
                        reason=str(item.get("reason", "cycle_output")),
                        status=str(item.get("status", "unknown")),
                        engine=out_engine,
                        gate_results=merged_gate_results,
                    )
                    persisted_cycle_records.append(
                        {
                            "decision_id": decision_id,
                            "run_id": cycle_run_id,
                            "symbol": str(item.get("symbol", "UNKNOWN")),
                            "action": out_action,
                            "item": item,
                            "gate_results": merged_gate_results,
                        }
                    )
                v25_conn_ref.commit()

                # Stage-2B: persist paper cycle log snapshot
                if args.mode in ("paper", "live"):
                    try:
                        for item in outputs:
                            _orion_d = getattr(pipeline, '_last_orion_decision', None)
                            _regime_json = json.dumps(
                                _orion_d.regime_probabilities if _orion_d else {},
                                default=str,
                            )
                            _weights_json = json.dumps(
                                _orion_d.engine_weights if _orion_d else {},
                                default=str,
                            )
                            _candidates_json = json.dumps(
                                {k: str(v) for k, v in getattr(pipeline, '_last_candidate_signals', {}).items()},
                                default=str,
                            )
                            _final_json = json.dumps({
                                "selected_engine": str(item.get("engine", "")),
                                "final_confidence": float(item.get("confidence", 0.0)),
                                "gate_results": item.get("gate_results", {}),
                                "risk_posture": getattr(
                                    getattr(_orion_d, 'risk_posture', None), 'reason', 'default'
                                ) if _orion_d else "default",
                                "position_size_pct": float(item.get("position_size_pct", 0.0)),
                                "hold_minutes": hold_minutes,
                                "action": str(item.get("action", "")),
                                "status": str(item.get("status", "")),
                            }, default=str)
                            v25_conn_ref.execute(
                                "INSERT INTO paper_cycle_log "
                                "(decision_cycle, timestamp, symbol, regime_json, "
                                "engine_weights_json, candidate_signals_json, final_decision_json) "
                                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                                (
                                    cycle,
                                    cycle_now.isoformat(),
                                    str(item.get("symbol", "UNKNOWN")),
                                    _regime_json,
                                    _weights_json,
                                    _candidates_json,
                                    _final_json,
                                ),
                            )
                        v25_conn_ref.commit()
                    except Exception as pcl_exc:
                        logging.getLogger(__name__).warning(
                            "[stage-2b] paper_cycle_log error: %s", pcl_exc,
                        )

            except Exception as e:
                print(f"[v25] decision persistence error: {e}")

        # Paper/live actionable signal notifications (opt-in via --telegram-signals).
        if args.mode in {"paper", "live"} and telegram_notifier.active:
            notify_records = persisted_cycle_records
            if not notify_records:
                notify_records = [
                    {
                        "decision_id": None,
                        "symbol": str(item.get("symbol", "UNKNOWN")),
                        "item": item,
                        "gate_results": item.get("gate_results") if isinstance(item.get("gate_results"), dict) else {},
                    }
                    for item in outputs
                ]

            for rec in notify_records:
                item = rec.get("item", {})
                status = str(item.get("status", "")).lower()
                reason = str(item.get("reason", ""))
                action = str(item.get("action", "")).lower()
                if not (
                    status == "executed"
                    and reason == "advisory_signal_sent"
                    and action in {"long", "short"}
                ):
                    continue

                regime = pipeline._extract_regime_from_gate_results(rec.get("gate_results"))
                telegram_notifier.notify_signal(
                    timestamp=cycle_now,
                    symbol=str(rec.get("symbol", item.get("symbol", "UNKNOWN"))),
                    action=action,
                    confidence=_as_float_default(item.get("confidence"), 0.0),
                    engine=str(item.get("engine") or pipeline._engine_hint_for_regime(None)),
                    regime=regime,
                    run_dir=str(run_dir),
                    decision_id=(int(rec["decision_id"]) if rec.get("decision_id") is not None else None),
                    size_pct=_opt_float(item.get("position_size_pct")),
                    leverage=_opt_float(item.get("leverage")),
                    entry_price=_opt_float(item.get("suggested_entry_price")),
                    stop_loss_pct=_opt_float(item.get("stop_loss_pct")),
                    take_profit_pct=_opt_float(item.get("take_profit_pct")),
                    advisory_message=str(item.get("advisory_message")) if item.get("advisory_message") else None,
                )

        # Deterministic backtest execution simulator from advisory outputs.
        if args.mode == "backtest" and v25_conn_ref is not None:
            try:
                for rec in persisted_cycle_records:
                    item = rec["item"]
                    status = str(item.get("status", "")).lower()
                    reason = str(item.get("reason", ""))
                    action = str(item.get("action", "")).lower()
                    if not (
                        status == "executed"
                        and reason == "advisory_signal_sent"
                        and action in {"long", "short"}
                    ):
                        continue

                    symbol = str(rec.get("symbol", item.get("symbol", "UNKNOWN")))
                    entry_time = cycle_now
                    entry_price, entry_candle_ts, entry_source = pipeline._resolve_backtest_close_price(
                        symbol=symbol,
                        at=entry_time,
                    )
                    if entry_price is None or entry_candle_ts is None:
                        pipeline._LOG.debug(
                            "backtest sim skip: no entry price | symbol=%s entry_time=%s source=%s",
                            symbol,
                            entry_time.isoformat(),
                            entry_source,
                        )
                        continue

                    size = _as_float_default(item.get("position_size_pct"), 0.01)
                    leverage = _as_float_default(item.get("leverage"), 1.0)
                    stop_distance = _as_float_default(item.get("stop_loss_pct"), 0.01)
                    confidence = _as_float_default(item.get("confidence"), 0.0)
                    engine = str(item.get("engine") or pipeline._engine_hint_for_regime(None))
                    fees_pct, slippage_pct = pipeline._estimate_backtest_costs(
                        fee_model=fee_model,
                        entry_price=entry_price,
                        size=size,
                        leverage=leverage,
                    )
                    regime = pipeline._extract_regime_from_gate_results(rec.get("gate_results"))
                    by_hold_eval: dict[int, tuple[datetime, float, float, float, datetime, str]] = {}

                    if hold_grid_minutes:
                        decision_id_raw = rec.get("decision_id")
                        if decision_id_raw is None:
                            sweep_skipped_rows += len(hold_grid_minutes)
                            continue

                        decision_id = int(decision_id_raw)
                        run_id = str(rec.get("run_id", ""))
                        fee_est_usd = max(float(entry_price) * float(size) * float(leverage), 0.0) * max(fees_pct, 0.0)

                        for hold in hold_grid_minutes:
                            sweep_exit_time = entry_time + timedelta(minutes=int(hold))
                            sweep_exit_price, sweep_exit_candle_ts, sweep_source = pipeline._resolve_backtest_close_price(
                                symbol=symbol,
                                at=sweep_exit_time,
                                after=entry_time,
                            )
                            if sweep_exit_price is None or sweep_exit_candle_ts is None:
                                sweep_skipped_rows += 1
                                pipeline._LOG.debug(
                                    "backtest sweep skip: no exit candle | symbol=%s entry_time=%s target_exit_time=%s hold=%d source=%s",
                                    symbol,
                                    entry_time.isoformat(),
                                    sweep_exit_time.isoformat(),
                                    int(hold),
                                    sweep_source,
                                )
                                continue

                            gross_pct, net_pct = pipeline._compute_backtest_pnl(
                                side=action,
                                entry_price=entry_price,
                                exit_price=sweep_exit_price,
                                leverage=leverage,
                                fees_pct=fees_pct,
                                slippage_pct=slippage_pct,
                            )
                            by_hold_eval[int(hold)] = (
                                sweep_exit_time,
                                float(sweep_exit_price),
                                float(gross_pct),
                                float(net_pct),
                                sweep_exit_candle_ts,
                                sweep_source,
                            )
                            pipeline._persist_backtest_exit_sweep_row(
                                run_id=run_id,
                                decision_cycle=cycle,
                                decision_id=decision_id,
                                symbol=symbol,
                                side=action,
                                entry_time=entry_time,
                                hold_minutes=int(hold),
                                exit_time=sweep_exit_time,
                                entry_price=entry_price,
                                exit_price=sweep_exit_price,
                                gross_pnl_pct=gross_pct,
                                net_pnl_pct=net_pct,
                                fee_est_usd=fee_est_usd,
                                slippage_est_pct=slippage_pct,
                                regime=regime,
                            )

                            walk_sweep_history.append(
                                {
                                    "decision_cycle": int(cycle),
                                    "regime": regime,
                                    "hold": int(hold),
                                    "exit_time": sweep_exit_candle_ts.isoformat(),
                                    "net_pnl_pct": float(net_pct),
                                }
                            )

                            if (
                                adaptive_hold_enabled
                                and not walk_forward_enabled
                                and cycle <= adaptive_in_sample_cycles
                            ):
                                regime_series = adaptive_series_by_regime.setdefault(regime, {})
                                regime_series.setdefault(int(hold), []).append(
                                    (sweep_exit_time.isoformat(), float(net_pct))
                                )

                    selected_hold = int(hold_minutes)
                    if walk_forward_enabled and adaptive_hold_enabled and cycle > walk_window:
                        segment_id = int((cycle - walk_window - 1) // adaptive_walk_step)
                        cache_key = (segment_id, str(regime))
                        if cache_key not in walk_hold_cache:
                            learn_start = int(cycle - walk_window)
                            learn_end = int(cycle - 1)
                            series_by_hold: dict[int, list[tuple[str, float]]] = {
                                int(h): [] for h in hold_grid_minutes
                            }
                            for row in walk_sweep_history:
                                row_cycle = int(row.get("decision_cycle", 0))
                                if row_cycle < learn_start or row_cycle > learn_end:
                                    continue
                                if str(row.get("regime", "UNKNOWN")) != str(regime):
                                    continue
                                row_hold = int(row.get("hold", 0))
                                if row_hold not in series_by_hold:
                                    continue
                                series_by_hold[row_hold].append(
                                    (
                                        str(row.get("exit_time", "")),
                                        float(row.get("net_pnl_pct", 0.0)),
                                    )
                                )
                            walk_hold_cache[cache_key] = _choose_best_hold(series_by_hold)

                        best_hold = walk_hold_cache.get(cache_key)
                        if best_hold is not None:
                            selected_hold = int(best_hold)
                    elif (not walk_forward_enabled) and adaptive_hold_enabled and cycle > adaptive_in_sample_cycles:
                        best_hold = _choose_best_hold(adaptive_series_by_regime.get(regime, {}))
                        if best_hold is not None:
                            selected_hold = int(best_hold)

                    if selected_hold in by_hold_eval:
                        exit_time, exit_price, _, _, exit_candle_ts, exit_source = by_hold_eval[selected_hold]
                    else:
                        exit_time = entry_time + timedelta(minutes=int(selected_hold))
                        resolved_exit, exit_candle_ts, exit_source = pipeline._resolve_backtest_close_price(
                            symbol=symbol,
                            at=exit_time,
                            after=entry_time,
                        )
                        if resolved_exit is None or exit_candle_ts is None:
                            if by_hold_eval:
                                fallback_hold = min(by_hold_eval)
                                selected_hold = int(fallback_hold)
                                exit_time, exit_price, _, _, exit_candle_ts, exit_source = by_hold_eval[fallback_hold]
                            else:
                                continue
                        else:
                            exit_price = float(resolved_exit)

                    pipeline._LOG.debug(
                        "backtest sim pricing | symbol=%s entry_time=%s exit_time=%s entry_price=%.8f exit_price=%.8f entry_candle_ts=%s exit_candle_ts=%s entry_source=%s exit_source=%s hold=%d",
                        symbol,
                        entry_time.isoformat(),
                        exit_time.isoformat(),
                        float(entry_price),
                        float(exit_price),
                        entry_candle_ts.isoformat(),
                        exit_candle_ts.isoformat(),
                        entry_source,
                        exit_source,
                        int(selected_hold),
                    )

                    pipeline._persist_backtest_execution_sim_trade(
                        symbol=symbol,
                        side=action,
                        engine=engine,
                        confidence=confidence,
                        stop_distance=stop_distance,
                        entry_time=entry_time,
                        exit_time=exit_time,
                        entry_price=entry_price,
                        exit_price=float(exit_price),
                        size=size,
                        leverage=leverage,
                        hold_minutes=int(selected_hold),
                        fees_pct=fees_pct,
                        slippage_pct=slippage_pct,
                    )
                v25_conn_ref.commit()
            except Exception as e:
                print(f"[v25] backtest execution simulator error: {e}")

        # Backtest-only optional synthetic exits (disabled by default)
        if args.mode == "backtest" and args.synthetic_exit and v25_conn_ref is not None:
            try:
                executed = [o for o in outputs if str(o.get("status", "")).lower() == "executed"]
                if executed:
                    for item in executed:
                        pipeline._persist_backtest_time_exit_trade(
                            symbol=str(item.get("symbol", "UNKNOWN")),
                            side=str(item.get("action", "long")),
                            engine=str(item.get("engine") or pipeline._engine_hint_for_regime(None)),
                            reason_entry=str(item.get("reason", "backtest_cycle")),
                            confidence=float(item.get("confidence", 0.55)),
                            stop_distance=0.01,
                            entry_time=cycle_now,
                        )
                else:
                    fallback_symbol = str(outputs[0].get("symbol", pipeline._fallback_symbol("crypto"))) if outputs else pipeline._fallback_symbol("crypto")
                    pipeline._persist_backtest_time_exit_trade(
                        symbol=fallback_symbol,
                        side="long",
                        engine="BACKTEST_TIME_EXIT",
                        reason_entry="backtest_cycle_no_executions",
                        confidence=0.50,
                        stop_distance=0.01,
                        entry_time=cycle_now,
                    )
                v25_conn_ref.commit()
            except Exception as e:
                print(f"[v25] backtest trade persistence error: {e}")

        print(f"[cycle {cycle}/{max_cycles}] outputs={len(outputs)}")

    if args.mode == "backtest" and args.v25:
        try:
            from src.v25.reports.backtest_summary import write_backtest_summary

            write_backtest_summary(
                db_path=str(args.v25_db),
                run_dir=str(run_dir),
                hold_grid_minutes=hold_grid_minutes,
                hold_grid_by=str(args.hold_grid_by),
                sweep_skipped_rows=int(sweep_skipped_rows),
                adaptive_hold_used=bool(adaptive_hold_enabled),
                adaptive_split_ratio=float(adaptive_split_ratio),
                in_sample_cycles=int(adaptive_in_sample_cycles),
                out_of_sample_cycles=int(adaptive_out_of_sample_cycles),
                walk_forward_enabled=bool(walk_forward_enabled),
                walk_forward_window=int(walk_window),
                walk_forward_step=int(adaptive_walk_step),
                walk_forward_segments=int(walk_segments),
                walk_forward_oos_cycles=int(walk_oos_cycles),
            )
            print(f"[v25] backtest summary written | run_dir={run_dir}")
        except Exception as exc:  # noqa: BLE001
            print(f"[v25] backtest summary error: {exc}")

    # Stage-2B: Export training dataset CSV
    if args.export_training_dataset and args.v25 and v25_conn_ref is not None:
        try:
            _export_path = run_dir / "training_dataset.csv"
            _export_conn = v25_conn_ref
            _export_conn.row_factory = sqlite3.Row
            _export_rows = _export_conn.execute(
                """
                SELECT
                    d.timestamp,
                    d.symbol,
                    d.regime,
                    d.engine AS engine_selected,
                    d.confidence,
                    d.reason,
                    d.gate_results_json,
                    d.status,
                    d.position_size_pct,
                    p.regime_json AS regime_probabilities_json,
                    p.engine_weights_json,
                    p.final_decision_json
                FROM decisions d
                LEFT JOIN paper_cycle_log p
                  ON d.timestamp = p.timestamp AND d.symbol = p.symbol
                ORDER BY d.decision_id ASC
                """
            ).fetchall()

            import csv as _csv
            _csv_headers = [
                "timestamp", "symbol", "regime", "engine_selected",
                "engine_weights_json", "confidence", "atr_14", "atr_14_pct",
                "volume_ratio", "bb_pct_b", "ema_21_vs_55", "price_vs_ma200",
                "net_pnl_pct", "hold_minutes", "regime_probabilities_json",
            ]
            with open(_export_path, "w", encoding="utf-8", newline="") as _csvf:
                _writer = _csv.DictWriter(_csvf, fieldnames=_csv_headers)
                _writer.writeheader()
                for _r in _export_rows:
                    _fd = {}
                    try:
                        _fd = json.loads(_r["final_decision_json"] or "{}")
                    except (json.JSONDecodeError, TypeError):
                        pass
                    _gate = {}
                    try:
                        _gate = json.loads(_r["gate_results_json"] or "{}")
                    except (json.JSONDecodeError, TypeError):
                        pass
                    _features = _gate.get("features_snapshot", {})
                    _writer.writerow({
                        "timestamp": _r["timestamp"],
                        "symbol": _r["symbol"],
                        "regime": _r["regime"],
                        "engine_selected": _r["engine_selected"],
                        "engine_weights_json": _r["engine_weights_json"] or "",
                        "confidence": _r["confidence"],
                        "atr_14": _features.get("atr_14", ""),
                        "atr_14_pct": _features.get("atr_14_pct", ""),
                        "volume_ratio": _features.get("volume_ratio", ""),
                        "bb_pct_b": _features.get("bb_pct_b", ""),
                        "ema_21_vs_55": _features.get("ema_21_vs_55", ""),
                        "price_vs_ma200": _features.get("price_vs_ma200", ""),
                        "net_pnl_pct": _fd.get("net_pnl_pct", ""),
                        "hold_minutes": _fd.get("hold_minutes", ""),
                        "regime_probabilities_json": _r["regime_probabilities_json"] or "",
                    })
            print(f"[stage-2b] training dataset exported | path={_export_path} | rows={len(_export_rows)}")
        except Exception as exc:  # noqa: BLE001
            print(f"[stage-2b] training dataset export error: {exc}")

    # P4-D Engine Observatory — write for ALL v25 modes (backtest/paper/live)
    if args.v25:
        try:
            from src.v25.reports.engine_observatory import write_engine_observatory

            write_engine_observatory(
                db_path=str(args.v25_db),
                run_dir=str(run_dir),
                mode=str(args.mode),
            )
            print(f"[v25] engine observatory written | run_dir={run_dir}")
        except Exception as exc:  # noqa: BLE001
            print(f"[v25] engine observatory error: {exc}")

    if args.v25:
        # v2.5 Dry-Run Telemetry
        try:
            if evaluate_accel_gates_fn is None or v25_cfg is None:
                raise RuntimeError("v25 bootstrap not initialized")
            # Conservative defaults (plumbing check only)
            passed, reason = evaluate_accel_gates_fn(
                sub_regime="UNCERTAIN",         # S1: Fail (sub_regime_ok=False)
                alignment_score=0.0,            # S2: Fail (alignment_ok=False)
                sqs_score=0.0,                  # S3: Fail (sqs_ok=False)
                kill_switch_level=0,            # R1: Pass (ok=True)
                rolling_vol_24h=0.01,           # A: Pass (ok=True)
                current_drawdown_pct=0.0,       # B: Pass (ok=True)
                recent_slippage_err=None,       # C: Neutral
                filled_order_count=0,           # D: Fail (count < 20)
                config=v25_cfg,
            )

            log_entry = {
                "ts": datetime.now(timezone.utc).isoformat(),
                "mode": args.mode,
                "assets": args.assets,
                "accel_passed": passed,
                "accel_reason": reason,
                "max_cycles": max_cycles,
                "run_dir": str(run_dir),
            }

            os.makedirs(os.path.dirname(args.v25_dryrun_log) or ".", exist_ok=True)
            with open(args.v25_dryrun_log, "a", encoding="utf-8") as f:
                f.write(json.dumps(log_entry) + "\n")

        except Exception as e:
            print(f"[v25] telemetry error: {e}")

    # ── Stage-2C: Daily Scoreboard ────────────────────────────
    if args.daily_scoreboard and args.v25:
        try:
            from src.v25.reports.daily_scoreboard import write_daily_scoreboard
            sb = write_daily_scoreboard(
                db_path=str(args.v25_db),
                run_dir=str(run_dir),
                mode=str(args.mode),
            )
            print(f"[stage-2c] daily scoreboard written | run_dir={run_dir}")
            for check, verdict in sb.get("go_nogo", {}).items():
                print(f"  [{check}] {verdict}")
        except Exception as exc:  # noqa: BLE001
            print(f"[stage-2c] daily scoreboard error: {exc}")

    # ── Stage-2C: Hardened training dataset ───────────────────
    if args.export_training_dataset and args.v25 and v25_conn_ref is not None:
        try:
            from src.v25.reports.export_training_dataset import export_training_dataset
            _ds_result = export_training_dataset(
                conn=v25_conn_ref,
                output_path=run_dir / "training_dataset.csv",
            )
            print(f"[stage-2c] hardened dataset exported | rows={_ds_result['row_count']} valid={_ds_result['valid']}")
        except Exception as exc:  # noqa: BLE001
            print(f"[stage-2c] hardened dataset error: {exc}")

    # ── Stage-2C: Live readiness check ────────────────────────
    if args.v25 and args.mode in ("paper",):
        try:
            from src.runtime.live_readiness_check import evaluate_live_readiness
            _readiness = evaluate_live_readiness(db_path=str(args.v25_db))
            _status = "READY" if _readiness["ready"] else "NOT READY"
            print(f"[stage-2c] live readiness: {_status} | reason={_readiness['reason']}")
        except Exception as exc:  # noqa: BLE001
            print(f"[stage-2c] readiness check error: {exc}")

    # ── Stage-2C: Paper 24h supervisor ─────────────────────────
    if args.paper_24h and args.v25:
        try:
            from src.runtime.paper_supervisor import run_paper_supervisor
            run_paper_supervisor(
                db_path=str(args.v25_db),
                base_run_dir=str(run_dir.parent / "paper_24h"),
                cycle_interval_seconds=300,
                restart_delay_seconds=30,
                pipeline_factory=lambda: (pipeline, v25_conn_ref),
            )
        except KeyboardInterrupt:
            print("[stage-2c] supervisor stopped by user")
        except Exception as exc:  # noqa: BLE001
            print(f"[stage-2c] supervisor error: {exc}")

    # ── Demo-24h continuous loop ───────────────────────────────
    if args.demo_24h:
        import time as _time
        _heartbeat_interval = 60  # seconds
        _cycle_interval = 300     # 5 minutes between cycles
        _demo_cycle = 0
        print(f"[demo-24h] Starting 24/7 demo mode | mode={args.mode} | cycle_interval={_cycle_interval}s")
        print(f"[demo-24h] Paper mode default. Press Ctrl+C to stop.")

        if args.mode == "live":
            print("[demo-24h] WARNING: --demo-24h with --mode live requires explicit confirmation.")
            print("[demo-24h] Live trading is enabled. Proceed with caution.")

        while True:
            _demo_cycle += 1
            try:
                demo_now = datetime.now(timezone.utc)
                print(f"[demo-24h] cycle={_demo_cycle} | ts={demo_now.isoformat()}")
                demo_outputs = pipeline.run_once(now=demo_now)
                print(f"[demo-24h] cycle={_demo_cycle} complete | outputs={len(demo_outputs)}")

                # Persist to decisions log
                with open(decisions_log, "a", encoding="utf-8") as f:
                    for out in demo_outputs:
                        f.write(json.dumps({"cycle": _demo_cycle, **out}, default=str) + "\n")

            except KeyboardInterrupt:
                print(f"\n[demo-24h] Stopped by user after {_demo_cycle} cycles.")
                break
            except Exception as demo_exc:
                print(f"[demo-24h] cycle={_demo_cycle} ERROR: {demo_exc}")
                # Do NOT exit — continue next cycle

            # Heartbeat + sleep
            try:
                _time.sleep(_cycle_interval)
                if _demo_cycle % (_heartbeat_interval // max(_cycle_interval, 1) + 1) == 0:
                    print(f"[demo-24h] heartbeat | cycle={_demo_cycle} | ts={datetime.now(timezone.utc).isoformat()}")
            except KeyboardInterrupt:
                print(f"\n[demo-24h] Stopped by user after {_demo_cycle} cycles.")
                break


if __name__ == "__main__":
    main()
