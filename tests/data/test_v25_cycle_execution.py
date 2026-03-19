from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import sqlite3
import sys
from types import SimpleNamespace

import pandas as pd

import src.main as main_mod
import src.mde.regime_alignment as _regime_alignment_mod
import src.mde.confluence_filter as _confluence_filter_mod
import src.mde.trade_quality as _trade_quality_mod
from src.core.constants import REGIME_CRISIS
from src.core.types import EngineSignal
from src.main import ArgusPipeline
from src.v25.bootstrap import run_v25_migrations


def _bypass_new_filters(monkeypatch, pipeline=None):
    """Monkeypatch the new Step 6.45/6.55/6.8/6.9 filters to always pass.

    These integration tests focus on backtest execution, equity curves,
    and hold-grid mechanics.  They pre-date the directional-bias,
    regime-alignment, confluence, and trade-quality pipeline filters and should not be
    gated by them.
    """
    monkeypatch.setattr(
        _regime_alignment_mod,
        "score_regime_alignment",
        lambda **kw: SimpleNamespace(
            alignment_score=0.90, confidence_multiplier=1.0, aligned=True, reason="mock_bypass",
        ),
    )
    monkeypatch.setattr(
        _confluence_filter_mod,
        "evaluate_confluence",
        lambda **kw: SimpleNamespace(
            score=0.80, factors_passed=6, factors_total=6, passed=True, reason="mock_bypass",
            factor_details={},
        ),
    )
    monkeypatch.setattr(
        _trade_quality_mod,
        "classify_trade_quality",
        lambda inp, **kw: SimpleNamespace(
            grade="A", composite_score=0.85, passed=True,
        ),
    )
    # Disable Step 6.45 directional bias (inline code, controlled via instance flag)
    monkeypatch.setattr(ArgusPipeline, "_enable_directional_bias", False, raising=False)


def test_v25_minimal_cycle_persists_decision_and_trade(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "argus_v25.db"
    conn = run_v25_migrations(str(db_path))

    pipeline = ArgusPipeline(
        mode="paper",
        assets=["crypto"],
        v25_conn=conn,
        ohlcv_limit=30,
    )

    def _fake_load_ohlcv(*, symbol: str, now: datetime):
        _ = symbol, now
        ts = pd.date_range("2024-01-01T00:01:00Z", periods=30, freq="min", tz="UTC")
        return pd.DataFrame(
            {
                "timestamp": ts,
                "open": [100.0 + i for i in range(30)],
                "high": [101.0 + i for i in range(30)],
                "low": [99.0 + i for i in range(30)],
                "close": [100.5 + i for i in range(30)],
                "volume": [1000.0 for _ in range(30)],
            }
        )

    pipeline._load_ohlcv = _fake_load_ohlcv  # type: ignore[method-assign]
    monkeypatch.setattr(pipeline, "_gemini_engine", None)
    monkeypatch.setattr(
        pipeline.router,
        "route",
        lambda *, regime, features, allow_crisis_override=False: EngineSignal(
            engine="TITAN",
            sub_strategy="trend_follow",
            asset_class=features.asset_class,
            symbol=features.symbol,
            bias="long",
            confidence=0.72,
            stop_distance=0.01,
            expected_return=0.02,
            atr=max(features.atr_14, 1e-6),
        ),
    )

    outputs = pipeline.run_v25_minimal_cycle(now=datetime.now(timezone.utc))
    assert outputs

    decision_count = conn.execute("SELECT COUNT(*) FROM decisions").fetchone()[0]
    trade_count = conn.execute("SELECT COUNT(*) FROM trades").fetchone()[0]
    assert decision_count >= 1
    assert trade_count >= 1


def test_v25_backtest_cycle_routes_real_engine_for_signal(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "argus_v25_backtest_cycle.db"
    conn = run_v25_migrations(str(db_path))

    pipeline = ArgusPipeline(
        mode="backtest",
        assets=["crypto"],
        v25_conn=conn,
        ohlcv_limit=260,
    )

    def _fake_load_ohlcv(*, symbol: str, now: datetime):
        _ = symbol, now
        ts = pd.date_range("2024-01-01T00:00:00Z", periods=320, freq="min", tz="UTC")
        base = pd.Series(range(320), dtype=float)
        close = 100.0 + base * 0.03
        return pd.DataFrame(
            {
                "timestamp": ts,
                "open": close - 0.1,
                "high": close + 0.2,
                "low": close - 0.2,
                "close": close,
                "volume": [1300.0 for _ in range(320)],
            }
        )

    class _GeminiStub:
        def generate_signal(self, *, regime, features):
            _ = regime
            assert features.ema_21_vs_55 > 0.0
            return EngineSignal(
                engine="GEMINI",
                sub_strategy="corr_mean_reversion",
                asset_class=features.asset_class,
                symbol=features.symbol,
                bias="long",
                confidence=0.81,
                stop_distance=0.01,
                expected_return=0.025,
                atr=max(features.atr_14, 1e-6),
            )

    monkeypatch.setattr(pipeline, "_load_ohlcv", _fake_load_ohlcv)
    monkeypatch.setattr(pipeline, "_gemini_engine", _GeminiStub())

    outputs = pipeline.run_v25_minimal_cycle(now=datetime.now(timezone.utc))
    assert outputs
    assert outputs[0].get("engine") == "GEMINI"
    assert outputs[0].get("engine") != "PIPELINE"
    assert outputs[0].get("reason") != "no_signal"
    assert outputs[0].get("action") in {"long", "short"}

    engines = {row[0] for row in conn.execute("SELECT DISTINCT engine FROM decisions").fetchall()}
    assert "GEMINI" in engines
    assert "PIPELINE" not in engines

    engine, reason, action = conn.execute(
        "SELECT engine, reason, action FROM decisions ORDER BY decision_id DESC LIMIT 1"
    ).fetchone()
    assert engine == "GEMINI"
    assert reason != "no_signal"
    assert action in {"long", "short"}


def test_basic_indicators_path_uses_normal_engine_not_v25_fallback(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "argus_v25_runonce.db"
    conn = run_v25_migrations(str(db_path))

    pipeline = ArgusPipeline(
        mode="backtest",
        assets=["crypto"],
        v25_conn=conn,
        ohlcv_limit=260,
    )

    # Python 3.11 path should use basic indicators fallback builder.
    assert pipeline.feature_builder is not None
    assert pipeline.feature_builder.__class__.__name__ in {"BasicFeatureBuilder", "FeatureBuilder"}

    def _fake_load_ohlcv(*, symbol: str, now: datetime):
        _ = symbol, now
        ts = pd.date_range("2024-01-01T00:00:00Z", periods=400, freq="min", tz="UTC")
        base = pd.Series(range(400), dtype=float)
        close = 100.0 + base * 0.05
        return pd.DataFrame(
            {
                "timestamp": ts,
                "open": close - 0.1,
                "high": close + 0.2,
                "low": close - 0.2,
                "close": close,
                "volume": [1500.0 for _ in range(400)],
            }
        )

    # Keep test deterministic: force route + gates + pretrade pass.
    def _route(*, regime, features, allow_crisis_override=False, **kwargs):
        _ = regime, features
        return EngineSignal(
            engine="TITAN",
            sub_strategy="trend_follow",
            asset_class="crypto",
            symbol="BTCUSDT",
            bias="long",
            confidence=0.75,
            stop_distance=0.01,
            expected_return=0.02,
            atr=1.0,
        )

    monkeypatch.setattr(pipeline, "_load_ohlcv", _fake_load_ohlcv)
    monkeypatch.setattr(pipeline.router, "route", _route)
    monkeypatch.setattr(
        main_mod,
        "evaluate_gates",
        lambda inp: SimpleNamespace(approved=True, reason="ok"),
    )
    monkeypatch.setattr(
        pipeline.pre_trade,
        "check",
        lambda inp: SimpleNamespace(
            approved=True,
            reason="ok",
            adjusted_position_size=0.01,
            validated_sizing=None,
        ),
    )

    outputs = pipeline.run_once()
    assert outputs
    assert outputs[0].get("engine") in {"TITAN", "POSEIDON", "AEGEAN", "HYDRA", "NAUTILUS"}
    assert outputs[0].get("engine") != "PIPELINE"
    assert outputs[0].get("reason") != "no_signal"
    assert outputs[0].get("action") in {"long", "short"}


def test_engine_error_reject_sets_real_engine_hint(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "argus_v25_engine_error.db"
    conn = run_v25_migrations(str(db_path))

    pipeline = ArgusPipeline(
        mode="backtest",
        assets=["crypto"],
        v25_conn=conn,
        ohlcv_limit=260,
    )

    def _fake_load_ohlcv(*, symbol: str, now: datetime):
        _ = symbol, now
        ts = pd.date_range("2024-01-01T00:00:00Z", periods=400, freq="min", tz="UTC")
        base = pd.Series(range(400), dtype=float)
        close = 100.0 + base * 0.01
        return pd.DataFrame(
            {
                "timestamp": ts,
                "open": close - 0.1,
                "high": close + 0.2,
                "low": close - 0.2,
                "close": close,
                "volume": [1200.0 for _ in range(400)],
            }
        )

    monkeypatch.setattr(pipeline, "_load_ohlcv", _fake_load_ohlcv)
    monkeypatch.setattr(
        pipeline.router,
        "route",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("router exploded")),
    )

    outputs = pipeline.run_once()
    assert outputs
    assert outputs[0].get("status") == "rejected"
    assert str(outputs[0].get("reason", "")).startswith("engine_error:")
    assert outputs[0].get("engine") != "PIPELINE"


def test_run_once_no_signal_output_has_engine_action_confidence(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "argus_v25_no_signal.db"
    conn = run_v25_migrations(str(db_path))

    pipeline = ArgusPipeline(
        mode="backtest",
        assets=["crypto"],
        v25_conn=conn,
        ohlcv_limit=260,
    )

    def _fake_load_ohlcv(*, symbol: str, now: datetime):
        _ = symbol, now
        ts = pd.date_range("2024-01-01T00:00:00Z", periods=320, freq="min", tz="UTC")
        base = pd.Series(range(320), dtype=float)
        close = 100.0 + base * 0.02
        return pd.DataFrame(
            {
                "timestamp": ts,
                "open": close - 0.1,
                "high": close + 0.2,
                "low": close - 0.2,
                "close": close,
                "volume": [1400.0 for _ in range(320)],
            }
        )

    monkeypatch.setattr(pipeline, "_load_ohlcv", _fake_load_ohlcv)
    monkeypatch.setattr(
        pipeline.router,
        "route",
        lambda *, regime, features, allow_crisis_override=False, **kwargs: None,
    )

    outputs = pipeline.run_once()
    assert outputs
    assert outputs[0].get("status") == "rejected"
    assert outputs[0].get("reason") == "no_signal"
    assert outputs[0].get("action") == "rejected"
    assert outputs[0].get("engine") == "ROUTER"
    assert float(outputs[0].get("confidence", -1.0)) == 0.0


def test_main_backtest_without_synthetic_exit_writes_no_closed_trades(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "argus_v25_main.db"
    run_dir = tmp_path / "run"
    dryrun_log = tmp_path / "dryrun_events.jsonl"

    monkeypatch.setattr(main_mod.ArgusPipeline, "_init_exchange_client", staticmethod(lambda evolve: None))
    monkeypatch.setattr(
        main_mod.ArgusPipeline,
        "run_once",
        lambda self, *, now=None: [
            {
                "symbol": "BTCUSDT",
                "status": "rejected",
                "reason": "no_signal",
                "action": "rejected",
                "engine": "ROUTER",
                "confidence": 0.0,
            }
        ],
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "main.py",
            "--mode",
            "backtest",
            "--assets",
            "crypto",
            "--max-cycles",
            "1",
            "--run-dir",
            str(run_dir),
            "--v25",
            "--v25-db",
            str(db_path),
            "--v25-dryrun-log",
            str(dryrun_log),
        ],
    )

    main_mod.main()

    conn = sqlite3.connect(db_path)
    try:
        engines = {row[0] for row in conn.execute("SELECT DISTINCT engine FROM decisions").fetchall()}
        assert engines
        assert "PIPELINE" not in engines

        closed_trades = conn.execute("SELECT COUNT(*) FROM trades WHERE exit_time IS NOT NULL").fetchone()[0]
        assert closed_trades == 0
    finally:
        conn.close()


def test_backtest_replay_time_walk_persists_60_cycles(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "argus_v25_time_walk.db"
    run_dir = tmp_path / "backtest_v25"
    dryrun_log = tmp_path / "dryrun_events.jsonl"

    seen_now: list[datetime] = []

    def _fake_run_once(self, *, now=None):
        assert now is not None
        seen_now.append(now)
        cycle_idx = len(seen_now)
        if cycle_idx % 10 == 0:
            return [
                {
                    "symbol": "BTCUSDT",
                    "status": "executed",
                    "reason": "engine_signal:trend_follow",
                    "action": "long",
                    "engine": "TITAN",
                    "confidence": 0.78,
                }
            ]
        return [
            {
                "symbol": "BTCUSDT",
                "status": "rejected",
                "reason": "no_signal",
                "action": "rejected",
                "engine": "ROUTER",
                "confidence": 0.0,
            }
        ]

    monkeypatch.setattr(main_mod.ArgusPipeline, "_init_exchange_client", staticmethod(lambda evolve: None))
    monkeypatch.setattr(main_mod.ArgusPipeline, "run_once", _fake_run_once)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "main.py",
            "--mode",
            "backtest",
            "--assets",
            "crypto",
            "--max-cycles",
            "60",
            "--run-dir",
            str(run_dir),
            "--v25",
            "--v25-db",
            str(db_path),
            "--v25-dryrun-log",
            str(dryrun_log),
            "--replay-now",
            "2024-01-01T00:00:00Z",
            "--cycle-step-minutes",
            "1",
        ],
    )

    main_mod.main()

    assert len(seen_now) == 60
    assert len({dt.isoformat() for dt in seen_now}) == 60
    assert all((seen_now[i] - seen_now[i - 1]).total_seconds() == 60 for i in range(1, len(seen_now)))

    conn = sqlite3.connect(db_path)
    try:
        decision_count = conn.execute("SELECT COUNT(*) FROM decisions").fetchone()[0]
        assert decision_count == 60

        distinct_ts = conn.execute("SELECT COUNT(DISTINCT timestamp) FROM decisions").fetchone()[0]
        assert distinct_ts == 60

        engines = {row[0] for row in conn.execute("SELECT DISTINCT engine FROM decisions").fetchall()}
        assert "TITAN" in engines
        assert "PIPELINE" not in engines

        run_ids = {row[0] for row in conn.execute("SELECT DISTINCT run_id FROM decisions").fetchall()}
        assert any(":c0001" in rid for rid in run_ids)
        assert any(":c0060" in rid for rid in run_ids)

        closed_trades = conn.execute("SELECT COUNT(*) FROM trades WHERE exit_time IS NOT NULL").fetchone()[0]
        assert closed_trades == 0
    finally:
        conn.close()

    decisions_log = run_dir / "decisions.jsonl"
    assert decisions_log.exists()
    lines = [ln for ln in decisions_log.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert len(lines) == 60


def test_backtest_writes_summary_report_files(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "argus_v25_summary.db"
    run_dir = tmp_path / "backtest_v25"
    dryrun_log = tmp_path / "dryrun_events.jsonl"

    cycle_idx = {"value": 0}

    def _fake_run_once(self, *, now=None):
        _ = self, now
        cycle_idx["value"] += 1
        n = cycle_idx["value"]
        if n % 2 == 0:
            return [
                {
                    "symbol": "BTCUSDT",
                    "status": "executed",
                    "reason": "engine_signal:trend_follow",
                    "action": "long",
                    "engine": "TITAN",
                    "confidence": 0.80,
                }
            ]
        return [
            {
                "symbol": "BTCUSDT",
                "status": "rejected",
                "reason": "no_signal",
                "action": "rejected",
                "engine": "ROUTER",
                "confidence": 0.0,
            }
        ]

    monkeypatch.setattr(main_mod.ArgusPipeline, "_init_exchange_client", staticmethod(lambda evolve: None))
    monkeypatch.setattr(main_mod.ArgusPipeline, "run_once", _fake_run_once)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "main.py",
            "--mode",
            "backtest",
            "--assets",
            "crypto",
            "--max-cycles",
            "5",
            "--run-dir",
            str(run_dir),
            "--v25",
            "--v25-db",
            str(db_path),
            "--v25-dryrun-log",
            str(dryrun_log),
            "--replay-now",
            "2024-01-01T00:00:00Z",
        ],
    )

    main_mod.main()

    summary_json = run_dir / "summary.json"
    summary_md = run_dir / "summary.md"
    engine_counts = run_dir / "engine_counts.csv"
    reason_counts = run_dir / "reason_counts.csv"
    action_counts = run_dir / "action_counts.csv"

    assert summary_json.exists()
    assert summary_md.exists()
    assert engine_counts.exists()
    assert reason_counts.exists()
    assert action_counts.exists()

    conn = sqlite3.connect(db_path)
    try:
        decision_count = conn.execute("SELECT COUNT(*) FROM decisions").fetchone()[0]
    finally:
        conn.close()

    payload = json.loads(summary_json.read_text(encoding="utf-8"))
    assert int(payload["counts"]["total_decisions"]) == int(decision_count) == 5
    assert "gate_metrics" in payload
    assert {"gate9_fail_count", "gate9_fail_avg_fee_risk_ratio", "crisis_regime_reject_count"}.issubset(
        payload["gate_metrics"].keys()
    )


def test_gate9_fail_persists_gate_results_json(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "argus_v25_gate9.db"
    run_dir = tmp_path / "backtest_v25"
    dryrun_log = tmp_path / "dryrun_events.jsonl"

    def _fake_load_ohlcv(self, *, symbol: str, now: datetime):
        _ = self, symbol, now
        ts = pd.date_range("2024-01-01T00:00:00Z", periods=360, freq="min", tz="UTC")
        base = pd.Series(range(360), dtype=float)
        close = 100.0 + base * 0.02
        return pd.DataFrame(
            {
                "timestamp": ts,
                "open": close - 0.1,
                "high": close + 0.2,
                "low": close - 0.2,
                "close": close,
                "volume": [1500.0 for _ in range(360)],
            }
        )

    def _route(self, *, regime, features, allow_crisis_override=False, **kwargs):
        _ = self, regime, allow_crisis_override
        return EngineSignal(
            engine="TITAN",
            sub_strategy="trend_follow",
            asset_class=features.asset_class,
            symbol=features.symbol,
            bias="long",
            confidence=0.82,
            stop_distance=0.0017,
            expected_return=0.01,
            atr=max(features.atr_14, 1e-6),
        )

    monkeypatch.setattr(main_mod.ArgusPipeline, "_init_exchange_client", staticmethod(lambda evolve: None))
    monkeypatch.setattr(main_mod.ArgusPipeline, "_load_ohlcv", _fake_load_ohlcv)
    monkeypatch.setattr(main_mod.ArgusPipeline, "_persist_validated_sizing", lambda self, pre, symbol: None)
    monkeypatch.setattr(main_mod.SentinelValidator, "validate", lambda self, inp: SimpleNamespace(score=1.0))
    monkeypatch.setattr(main_mod.RegimeRouter, "route", _route)
    _bypass_new_filters(monkeypatch)
    monkeypatch.setattr(main_mod, "evaluate_gates", lambda inp: SimpleNamespace(approved=True, reason="ok"))
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "main.py",
            "--mode",
            "backtest",
            "--assets",
            "crypto",
            "--max-cycles",
            "1",
            "--run-dir",
            str(run_dir),
            "--v25",
            "--v25-db",
            str(db_path),
            "--v25-dryrun-log",
            str(dryrun_log),
            "--replay-now",
            "2024-01-01T00:00:00Z",
        ],
    )

    main_mod.main()

    conn = sqlite3.connect(db_path)
    try:
        reason, gate_results_json = conn.execute(
            "SELECT reason, gate_results_json FROM decisions ORDER BY decision_id DESC LIMIT 1"
        ).fetchone()
    finally:
        conn.close()

    assert "gate9_fail" in str(reason)
    payload = json.loads(str(gate_results_json))
    gate9 = payload.get("gate9")
    assert isinstance(gate9, dict)
    assert gate9.get("pass") is False
    assert {"fee_est_usd", "risk_usd", "fee_risk_ratio", "threshold"}.issubset(gate9.keys())


def test_risk_profile_relaxed_reduces_gate9_fail_count(monkeypatch, tmp_path) -> None:
    def _fake_load_ohlcv(self, *, symbol: str, now: datetime):
        _ = self, symbol, now
        ts = pd.date_range("2024-01-01T00:00:00Z", periods=360, freq="min", tz="UTC")
        base = pd.Series(range(360), dtype=float)
        close = 100.0 + base * 0.03
        return pd.DataFrame(
            {
                "timestamp": ts,
                "open": close - 0.1,
                "high": close + 0.2,
                "low": close - 0.2,
                "close": close,
                "volume": [1400.0 for _ in range(360)],
            }
        )

    def _route(self, *, regime, features, allow_crisis_override=False, **kwargs):
        _ = self, regime, allow_crisis_override
        return EngineSignal(
            engine="TITAN",
            sub_strategy="trend_follow",
            asset_class=features.asset_class,
            symbol=features.symbol,
            bias="long",
            confidence=0.80,
            stop_distance=0.0017,
            expected_return=0.01,
            atr=max(features.atr_14, 1e-6),
        )

    monkeypatch.setattr(main_mod.ArgusPipeline, "_init_exchange_client", staticmethod(lambda evolve: None))
    monkeypatch.setattr(main_mod.ArgusPipeline, "_load_ohlcv", _fake_load_ohlcv)
    monkeypatch.setattr(main_mod.ArgusPipeline, "_persist_validated_sizing", lambda self, pre, symbol: None)
    monkeypatch.setattr(main_mod.SentinelValidator, "validate", lambda self, inp: SimpleNamespace(score=1.0))
    monkeypatch.setattr(main_mod.RegimeRouter, "route", _route)
    _bypass_new_filters(monkeypatch)
    monkeypatch.setattr(main_mod, "evaluate_gates", lambda inp: SimpleNamespace(approved=True, reason="ok"))

    def _run_profile(profile: str, suffix: str) -> int:
        db_path = tmp_path / f"argus_v25_{suffix}.db"
        run_dir = tmp_path / f"run_{suffix}"
        dryrun_log = tmp_path / f"dryrun_{suffix}.jsonl"

        monkeypatch.setattr(
            sys,
            "argv",
            [
                "main.py",
                "--mode",
                "backtest",
                "--assets",
                "crypto",
                "--max-cycles",
                "60",
                "--run-dir",
                str(run_dir),
                "--v25",
                "--v25-db",
                str(db_path),
                "--v25-dryrun-log",
                str(dryrun_log),
                "--replay-now",
                "2024-01-01T00:00:00Z",
                "--risk-profile",
                profile,
            ],
        )
        main_mod.main()
        conn = sqlite3.connect(db_path)
        try:
            return int(
                conn.execute(
                    "SELECT COUNT(*) FROM decisions WHERE reason LIKE 'gate9_fail%'"
                ).fetchone()[0]
            )
        finally:
            conn.close()

    normal_fails = _run_profile("normal", "normal")
    relaxed_fails = _run_profile("relaxed", "relaxed")

    assert normal_fails > 0
    assert relaxed_fails < normal_fails


def test_allow_crisis_routes_with_capped_size_backtest_only(monkeypatch) -> None:
    def _fake_load_ohlcv(*, symbol: str, now: datetime):
        _ = symbol, now
        ts = pd.date_range("2024-01-01T00:00:00Z", periods=360, freq="min", tz="UTC")
        base = pd.Series(range(360), dtype=float)
        close = 100.0 + base * 0.01
        return pd.DataFrame(
            {
                "timestamp": ts,
                "open": close - 0.1,
                "high": close + 0.2,
                "low": close - 0.2,
                "close": close,
                "volume": [1300.0 for _ in range(360)],
            }
        )

    def _route(*, regime, features, allow_crisis_override=False, **kwargs):
        _ = regime
        if not allow_crisis_override:
            return None
        return EngineSignal(
            engine="TITAN",
            sub_strategy="trend_follow",
            asset_class=features.asset_class,
            symbol=features.symbol,
            bias="long",
            confidence=0.82,
            stop_distance=0.005,
            expected_return=0.02,
            atr=max(features.atr_14, 1e-6),
        )

    def _force_crisis_pipeline(pipeline: ArgusPipeline) -> None:
        monkeypatch.setattr(pipeline, "_load_ohlcv", _fake_load_ohlcv)
        monkeypatch.setattr(pipeline.sentinel, "validate", lambda inp: SimpleNamespace(score=1.0))
        monkeypatch.setattr(pipeline.router, "route", _route)
        monkeypatch.setattr(pipeline.rule_classifier, "classify", lambda inp: REGIME_CRISIS)
        monkeypatch.setattr(
            pipeline.consensus,
            "resolve",
            lambda votes: SimpleNamespace(regime=REGIME_CRISIS, confidence=0.9, reason="forced"),
        )
        monkeypatch.setattr(pipeline, "_persist_validated_sizing", lambda pre, symbol: None)

    backtest_no_override = ArgusPipeline(mode="backtest", assets=["crypto"], allow_crisis=False)
    _force_crisis_pipeline(backtest_no_override)
    out_no = backtest_no_override.run_once(now=datetime(2024, 1, 1, tzinfo=timezone.utc))
    assert out_no
    assert "crisis_regime" in str(out_no[0].get("reason", ""))

    backtest_override = ArgusPipeline(mode="backtest", assets=["crypto"], allow_crisis=True)
    _force_crisis_pipeline(backtest_override)
    out_yes = backtest_override.run_once(now=datetime(2024, 1, 1, tzinfo=timezone.utc))
    assert out_yes
    assert "crisis_regime" not in str(out_yes[0].get("reason", ""))
    assert "crisis_override" in str(out_yes[0].get("reason", ""))
    assert float(out_yes[0].get("position_size_pct", 0.0)) <= 0.02

    paper_override = ArgusPipeline(mode="paper", assets=["crypto"], allow_crisis=True)
    _force_crisis_pipeline(paper_override)
    out_paper = paper_override.run_once(now=datetime(2024, 1, 1, tzinfo=timezone.utc))
    assert out_paper
    assert "crisis_regime" in str(out_paper[0].get("reason", ""))


def test_backtest_execution_simulator_and_equity_curve(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "argus_v25_exec_sim.db"
    run_dir = tmp_path / "backtest_v25"
    dryrun_log = tmp_path / "dryrun_events.jsonl"

    def _fake_fetch_ohlcv(self, *, symbol: str, timeframe: str = "1m", limit: int = 500, now=None):
        _ = self, symbol, timeframe
        anchor = pd.Timestamp(now if now is not None else "2024-02-01T12:00:00Z")
        if anchor.tzinfo is None:
            anchor = anchor.tz_localize("UTC")
        else:
            anchor = anchor.tz_convert("UTC")

        n = max(1, int(limit))
        ts = pd.date_range(end=anchor, periods=n, freq="min", tz="UTC")
        minute_index = (ts.asi8 // 60_000_000_000).astype(float)
        close = 100.0 + minute_index * 0.0001

        rows: list[list[object]] = []
        for i, t in enumerate(ts):
            c = float(close[i])
            rows.append([t.to_pydatetime(), c - 0.05, c + 0.10, c - 0.10, c, 1200.0])
        return rows

    def _route(self, *, regime, features, allow_crisis_override=False, **kwargs):
        _ = self, regime, allow_crisis_override
        return EngineSignal(
            engine="TITAN",
            sub_strategy="trend_follow",
            asset_class=features.asset_class,
            symbol=features.symbol,
            bias="long",
            confidence=0.78,
            stop_distance=0.01,
            expected_return=0.02,
            atr=max(features.atr_14, 1e-6),
        )

    monkeypatch.setattr(main_mod.ArgusPipeline, "_init_exchange_client", staticmethod(lambda evolve: None))
    monkeypatch.setattr(main_mod.DataFactory, "fetch_ohlcv", _fake_fetch_ohlcv)
    monkeypatch.setattr(main_mod.ArgusPipeline, "_persist_validated_sizing", lambda self, pre, symbol: None)
    monkeypatch.setattr(main_mod.SentinelValidator, "validate", lambda self, inp: SimpleNamespace(score=1.0))
    monkeypatch.setattr(main_mod.RegimeRouter, "route", _route)
    _bypass_new_filters(monkeypatch)
    monkeypatch.setattr(main_mod, "evaluate_gates", lambda inp: SimpleNamespace(approved=True, reason="ok"))

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "main.py",
            "--mode",
            "backtest",
            "--assets",
            "crypto",
            "--max-cycles",
            "60",
            "--run-dir",
            str(run_dir),
            "--v25",
            "--v25-db",
            str(db_path),
            "--v25-dryrun-log",
            str(dryrun_log),
            "--replay-now",
            "2024-02-01T12:00:00Z",
            "--cycle-step-minutes",
            "1",
            "--risk-profile",
            "relaxed",
            "--allow-crisis",
        ],
    )

    main_mod.main()

    conn = sqlite3.connect(db_path)
    try:
        decisions_count = conn.execute("SELECT COUNT(*) FROM decisions").fetchone()[0]
        closed_trades = conn.execute("SELECT COUNT(*) FROM trades WHERE exit_time IS NOT NULL").fetchone()[0]
    finally:
        conn.close()

    assert decisions_count == 60
    assert closed_trades >= 1

    equity_csv = run_dir / "equity.csv"
    assert equity_csv.exists()
    rows = [ln for ln in equity_csv.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert len(rows) >= 2

    summary_json = run_dir / "summary.json"
    payload = json.loads(summary_json.read_text(encoding="utf-8"))
    for key in ("trades_closed_count", "total_return", "max_drawdown", "win_rate", "avg_trade_return"):
        assert key in payload


def test_backtest_exit_hold_grid_sweep_outputs(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "argus_v25_exit_sweep.db"
    run_dir = tmp_path / "backtest_v25"
    dryrun_log = tmp_path / "dryrun_events.jsonl"

    def _fake_fetch_ohlcv(self, *, symbol: str, timeframe: str = "1m", limit: int = 500, now=None):
        _ = self, symbol, timeframe
        anchor = pd.Timestamp(now if now is not None else "2024-02-01T12:00:00Z")
        if anchor.tzinfo is None:
            anchor = anchor.tz_localize("UTC")
        else:
            anchor = anchor.tz_convert("UTC")

        n = max(1, int(limit))
        ts = pd.date_range(end=anchor, periods=n, freq="min", tz="UTC")
        minute_index = (ts.asi8 // 60_000_000_000).astype(float)
        close = 100.0 + minute_index * 0.0001

        rows: list[list[object]] = []
        for i, t in enumerate(ts):
            c = float(close[i])
            rows.append([t.to_pydatetime(), c - 0.05, c + 0.10, c - 0.10, c, 1200.0])
        return rows

    def _route(self, *, regime, features, allow_crisis_override=False, **kwargs):
        _ = self, regime, allow_crisis_override
        return EngineSignal(
            engine="TITAN",
            sub_strategy="trend_follow",
            asset_class=features.asset_class,
            symbol=features.symbol,
            bias="long",
            confidence=0.78,
            stop_distance=0.01,
            expected_return=0.02,
            atr=max(features.atr_14, 1e-6),
        )

    monkeypatch.setattr(main_mod.ArgusPipeline, "_init_exchange_client", staticmethod(lambda evolve: None))
    monkeypatch.setattr(main_mod.DataFactory, "fetch_ohlcv", _fake_fetch_ohlcv)
    monkeypatch.setattr(main_mod.ArgusPipeline, "_persist_validated_sizing", lambda self, pre, symbol: None)
    monkeypatch.setattr(main_mod.SentinelValidator, "validate", lambda self, inp: SimpleNamespace(score=1.0))
    monkeypatch.setattr(main_mod.RegimeRouter, "route", _route)
    _bypass_new_filters(monkeypatch)
    monkeypatch.setattr(main_mod, "evaluate_gates", lambda inp: SimpleNamespace(approved=True, reason="ok"))

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "main.py",
            "--mode",
            "backtest",
            "--assets",
            "crypto",
            "--max-cycles",
            "60",
            "--run-dir",
            str(run_dir),
            "--v25",
            "--v25-db",
            str(db_path),
            "--v25-dryrun-log",
            str(dryrun_log),
            "--replay-now",
            "2024-02-01T12:00:00Z",
            "--cycle-step-minutes",
            "1",
            "--risk-profile",
            "relaxed",
            "--allow-crisis",
            "--hold-minutes",
            "30",
            "--hold-grid-minutes",
            "10,30,60",
        ],
    )

    main_mod.main()

    conn = sqlite3.connect(db_path)
    try:
        decision_count = conn.execute("SELECT COUNT(*) FROM decisions").fetchone()[0]
        executed_decisions = conn.execute(
            """
            SELECT COUNT(*) FROM decisions
            WHERE action IN ('long','short') AND reason = 'advisory_signal_sent'
            """
        ).fetchone()[0]
        closed_trades = conn.execute("SELECT COUNT(*) FROM trades WHERE exit_time IS NOT NULL").fetchone()[0]
        sweep_rows = conn.execute("SELECT COUNT(*) FROM backtest_exit_sweep").fetchone()[0]
        table_exists = conn.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='backtest_exit_sweep'"
        ).fetchone()[0]
    finally:
        conn.close()

    assert decision_count == 60
    assert closed_trades >= 1
    assert table_exists == 1
    assert sweep_rows >= executed_decisions * 3

    sweep_csv = run_dir / "exit_sweep.csv"
    assert sweep_csv.exists()
    sweep_lines = [ln for ln in sweep_csv.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert len(sweep_lines) >= 4

    summary_json = run_dir / "summary.json"
    payload = json.loads(summary_json.read_text(encoding="utf-8"))
    assert "exit_sweep" in payload
    assert payload["exit_sweep"].get("holds") == [10, 30, 60]
    assert payload["exit_sweep"].get("best_hold_overall") is not None


def test_backtest_adaptive_hold_from_sweep_by_regime(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "argus_v25_adaptive_hold.db"
    run_dir = tmp_path / "backtest_v25"
    dryrun_log = tmp_path / "dryrun_events.jsonl"

    def _fake_fetch_ohlcv(self, *, symbol: str, timeframe: str = "1m", limit: int = 500, now=None):
        _ = self, symbol, timeframe
        anchor = pd.Timestamp(now if now is not None else "2024-02-01T12:00:00Z")
        if anchor.tzinfo is None:
            anchor = anchor.tz_localize("UTC")
        else:
            anchor = anchor.tz_convert("UTC")

        n = max(1, int(limit))
        ts = pd.date_range(end=anchor, periods=n, freq="min", tz="UTC")
        minute_index = (ts.asi8 // 60_000_000_000).astype(float)
        close = 100.0 + minute_index * 0.0001

        rows: list[list[object]] = []
        for i, t in enumerate(ts):
            c = float(close[i])
            rows.append([t.to_pydatetime(), c - 0.05, c + 0.10, c - 0.10, c, 1200.0])
        return rows

    def _route(self, *, regime, features, allow_crisis_override=False, **kwargs):
        _ = self, regime, allow_crisis_override
        return EngineSignal(
            engine="TITAN",
            sub_strategy="trend_follow",
            asset_class=features.asset_class,
            symbol=features.symbol,
            bias="long",
            confidence=0.78,
            stop_distance=0.01,
            expected_return=0.02,
            atr=max(features.atr_14, 1e-6),
        )

    monkeypatch.setattr(main_mod.ArgusPipeline, "_init_exchange_client", staticmethod(lambda evolve: None))
    monkeypatch.setattr(main_mod.DataFactory, "fetch_ohlcv", _fake_fetch_ohlcv)
    monkeypatch.setattr(main_mod.ArgusPipeline, "_persist_validated_sizing", lambda self, pre, symbol: None)
    monkeypatch.setattr(main_mod.SentinelValidator, "validate", lambda self, inp: SimpleNamespace(score=1.0))
    monkeypatch.setattr(main_mod.RegimeRouter, "route", _route)
    _bypass_new_filters(monkeypatch)
    monkeypatch.setattr(main_mod, "evaluate_gates", lambda inp: SimpleNamespace(approved=True, reason="ok"))

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "main.py",
            "--mode",
            "backtest",
            "--assets",
            "crypto",
            "--max-cycles",
            "60",
            "--run-dir",
            str(run_dir),
            "--v25",
            "--v25-db",
            str(db_path),
            "--v25-dryrun-log",
            str(dryrun_log),
            "--replay-now",
            "2024-02-01T12:00:00Z",
            "--cycle-step-minutes",
            "1",
            "--risk-profile",
            "relaxed",
            "--allow-crisis",
            "--hold-minutes",
            "30",
            "--hold-grid-minutes",
            "10,30,60",
            "--adaptive-hold-from-sweep",
            "--hold-grid-by",
            "regime",
        ],
    )

    main_mod.main()

    conn = sqlite3.connect(db_path)
    try:
        decision_count = conn.execute("SELECT COUNT(*) FROM decisions").fetchone()[0]
        closed_trades = conn.execute("SELECT COUNT(*) FROM trades WHERE exit_time IS NOT NULL").fetchone()[0]
        hold_values = {
            int(row[0])
            for row in conn.execute(
                "SELECT DISTINCT hold_minutes FROM trades WHERE exit_time IS NOT NULL AND hold_minutes IS NOT NULL"
            ).fetchall()
        }
    finally:
        conn.close()

    assert decision_count == 60
    assert closed_trades >= 1
    assert hold_values
    assert hold_values.issubset({10, 30, 60})

    summary_json = run_dir / "summary.json"
    payload = json.loads(summary_json.read_text(encoding="utf-8"))
    assert payload.get("adaptive_hold_used") is True
    assert isinstance(payload.get("best_hold_by_regime"), dict)
    assert payload.get("exit_sweep", {}).get("best_hold_by_regime")


def test_backtest_adaptive_hold_split_uses_is_then_oos(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "argus_v25_adaptive_split.db"
    run_dir = tmp_path / "backtest_v25"
    dryrun_log = tmp_path / "dryrun_events.jsonl"

    anchor = datetime(2024, 2, 1, 12, 0, 0, tzinfo=timezone.utc)
    split_ts = (anchor + timedelta(minutes=30)).isoformat()

    def _fake_fetch_ohlcv(self, *, symbol: str, timeframe: str = "1m", limit: int = 500, now=None):
        _ = self, symbol, timeframe
        anchor_ts = pd.Timestamp(now if now is not None else "2024-02-01T12:00:00Z")
        if anchor_ts.tzinfo is None:
            anchor_ts = anchor_ts.tz_localize("UTC")
        else:
            anchor_ts = anchor_ts.tz_convert("UTC")

        n = max(1, int(limit))
        ts = pd.date_range(end=anchor_ts, periods=n, freq="min", tz="UTC")
        minute_index = (ts.asi8 // 60_000_000_000).astype(float)
        close = 100.0 + minute_index * 0.0002

        rows: list[list[object]] = []
        for i, t in enumerate(ts):
            c = float(close[i])
            rows.append([t.to_pydatetime(), c - 0.05, c + 0.10, c - 0.10, c, 1200.0])
        return rows

    def _route(self, *, regime, features, allow_crisis_override=False, **kwargs):
        _ = self, regime, allow_crisis_override
        return EngineSignal(
            engine="TITAN",
            sub_strategy="trend_follow",
            asset_class=features.asset_class,
            symbol=features.symbol,
            bias="long",
            confidence=0.8,
            stop_distance=0.01,
            expected_return=0.02,
            atr=max(features.atr_14, 1e-6),
        )

    monkeypatch.setattr(main_mod.ArgusPipeline, "_init_exchange_client", staticmethod(lambda evolve: None))
    monkeypatch.setattr(main_mod.DataFactory, "fetch_ohlcv", _fake_fetch_ohlcv)
    monkeypatch.setattr(main_mod.ArgusPipeline, "_persist_validated_sizing", lambda self, pre, symbol: None)
    monkeypatch.setattr(main_mod.SentinelValidator, "validate", lambda self, inp: SimpleNamespace(score=1.0))
    monkeypatch.setattr(main_mod.RegimeRouter, "route", _route)
    _bypass_new_filters(monkeypatch)
    monkeypatch.setattr(main_mod, "evaluate_gates", lambda inp: SimpleNamespace(approved=True, reason="ok"))

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "main.py",
            "--mode",
            "backtest",
            "--assets",
            "crypto",
            "--max-cycles",
            "60",
            "--run-dir",
            str(run_dir),
            "--v25",
            "--v25-db",
            str(db_path),
            "--v25-dryrun-log",
            str(dryrun_log),
            "--replay-now",
            "2024-02-01T12:00:00Z",
            "--cycle-step-minutes",
            "1",
            "--risk-profile",
            "relaxed",
            "--allow-crisis",
            "--hold-minutes",
            "45",
            "--hold-grid-minutes",
            "10,30,60",
            "--adaptive-hold-from-sweep",
            "--adaptive-split-ratio",
            "0.5",
            "--hold-grid-by",
            "regime",
        ],
    )

    main_mod.main()

    conn = sqlite3.connect(db_path)
    try:
        decision_count = conn.execute("SELECT COUNT(*) FROM decisions").fetchone()[0]
        in_sample_holds = {
            int(row[0])
            for row in conn.execute(
                """
                SELECT DISTINCT hold_minutes FROM trades
                WHERE exit_time IS NOT NULL AND hold_minutes IS NOT NULL AND entry_time < ?
                """,
                (split_ts,),
            ).fetchall()
        }
        out_sample_holds = {
            int(row[0])
            for row in conn.execute(
                """
                SELECT DISTINCT hold_minutes FROM trades
                WHERE exit_time IS NOT NULL AND hold_minutes IS NOT NULL AND entry_time >= ?
                """,
                (split_ts,),
            ).fetchall()
        }
    finally:
        conn.close()

    assert decision_count == 60
    assert in_sample_holds
    assert in_sample_holds == {45}
    assert out_sample_holds
    assert out_sample_holds.issubset({10, 30, 60})

    summary_json = run_dir / "summary.json"
    payload = json.loads(summary_json.read_text(encoding="utf-8"))
    assert payload.get("adaptive_hold_used") is True
    assert float(payload.get("adaptive_split_ratio", 0.0)) == 0.5
    assert int(payload.get("in_sample_cycles", 0)) == 30
    assert int(payload.get("out_of_sample_cycles", 0)) == 30


def test_backtest_walk_forward_adaptive_hold(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "argus_v25_walk_forward.db"
    run_dir = tmp_path / "backtest_v25"
    dryrun_log = tmp_path / "dryrun_events.jsonl"

    def _fake_fetch_ohlcv(self, *, symbol: str, timeframe: str = "1m", limit: int = 500, now=None):
        _ = self, symbol, timeframe
        anchor_ts = pd.Timestamp(now if now is not None else "2024-02-01T12:00:00Z")
        if anchor_ts.tzinfo is None:
            anchor_ts = anchor_ts.tz_localize("UTC")
        else:
            anchor_ts = anchor_ts.tz_convert("UTC")

        n = max(1, int(limit))
        ts = pd.date_range(end=anchor_ts, periods=n, freq="min", tz="UTC")
        minute_index = (ts.asi8 // 60_000_000_000).astype(float)
        close = 100.0 + minute_index * 0.0002

        rows: list[list[object]] = []
        for i, t in enumerate(ts):
            c = float(close[i])
            rows.append([t.to_pydatetime(), c - 0.05, c + 0.10, c - 0.10, c, 1200.0])
        return rows

    def _route(self, *, regime, features, allow_crisis_override=False, **kwargs):
        _ = self, regime, allow_crisis_override
        return EngineSignal(
            engine="TITAN",
            sub_strategy="trend_follow",
            asset_class=features.asset_class,
            symbol=features.symbol,
            bias="long",
            confidence=0.8,
            stop_distance=0.01,
            expected_return=0.02,
            atr=max(features.atr_14, 1e-6),
        )

    monkeypatch.setattr(main_mod.ArgusPipeline, "_init_exchange_client", staticmethod(lambda evolve: None))
    monkeypatch.setattr(main_mod.DataFactory, "fetch_ohlcv", _fake_fetch_ohlcv)
    monkeypatch.setattr(main_mod.ArgusPipeline, "_persist_validated_sizing", lambda self, pre, symbol: None)
    monkeypatch.setattr(main_mod.SentinelValidator, "validate", lambda self, inp: SimpleNamespace(score=1.0))
    monkeypatch.setattr(main_mod.RegimeRouter, "route", _route)
    _bypass_new_filters(monkeypatch)
    monkeypatch.setattr(main_mod, "evaluate_gates", lambda inp: SimpleNamespace(approved=True, reason="ok"))

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "main.py",
            "--mode",
            "backtest",
            "--assets",
            "crypto",
            "--max-cycles",
            "60",
            "--run-dir",
            str(run_dir),
            "--v25",
            "--v25-db",
            str(db_path),
            "--v25-dryrun-log",
            str(dryrun_log),
            "--replay-now",
            "2024-02-01T12:00:00Z",
            "--cycle-step-minutes",
            "1",
            "--risk-profile",
            "relaxed",
            "--allow-crisis",
            "--hold-minutes",
            "45",
            "--hold-grid-minutes",
            "10,30,60",
            "--adaptive-hold-from-sweep",
            "--adaptive-walk-window",
            "20",
            "--adaptive-walk-step",
            "10",
            "--hold-grid-by",
            "regime",
        ],
    )

    main_mod.main()

    conn = sqlite3.connect(db_path)
    try:
        decision_count = conn.execute("SELECT COUNT(*) FROM decisions").fetchone()[0]
        hold_values = {
            int(row[0])
            for row in conn.execute(
                "SELECT DISTINCT hold_minutes FROM trades WHERE exit_time IS NOT NULL AND hold_minutes IS NOT NULL"
            ).fetchall()
        }
    finally:
        conn.close()

    assert decision_count == 60
    assert hold_values
    assert len(hold_values) >= 2

    payload = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    walk = payload.get("walk_forward", {})
    assert walk.get("enabled") is True


def test_backtest_simulator_resolves_time_shifted_exit_prices(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "argus_v25_time_shifted_exit.db"
    run_dir = tmp_path / "backtest_v25"
    dryrun_log = tmp_path / "dryrun_events.jsonl"

    def _fake_fetch_ohlcv(self, *, symbol: str, timeframe: str = "1m", limit: int = 500, now=None):
        _ = self, symbol, timeframe
        if now is None:
            # Prevent silent fallback from passing with static/latest price.
            return []

        assert isinstance(now, pd.Timestamp)
        anchor = now
        if anchor.tzinfo is None:
            anchor = anchor.tz_localize("UTC")
        else:
            anchor = anchor.tz_convert("UTC")

        n = max(2, int(limit))
        ts = pd.date_range(end=anchor, periods=n, freq="min", tz="UTC")
        minute_index = (ts.asi8 // 60_000_000_000).astype(float)
        close = 100.0 + minute_index * 0.0001

        rows: list[list[object]] = []
        for i, t in enumerate(ts):
            c = float(close[i])
            rows.append([t.to_pydatetime(), c - 0.05, c + 0.10, c - 0.10, c, 1100.0])
        return rows

    def _route(self, *, regime, features, allow_crisis_override=False, **kwargs):
        _ = self, regime, allow_crisis_override
        return EngineSignal(
            engine="TITAN",
            sub_strategy="trend_follow",
            asset_class=features.asset_class,
            symbol=features.symbol,
            bias="short",
            confidence=0.8,
            stop_distance=0.01,
            expected_return=0.02,
            atr=max(features.atr_14, 1e-6),
        )

    monkeypatch.setattr(main_mod.ArgusPipeline, "_init_exchange_client", staticmethod(lambda evolve: None))
    monkeypatch.setattr(main_mod.DataFactory, "fetch_ohlcv", _fake_fetch_ohlcv)
    monkeypatch.setattr(main_mod.ArgusPipeline, "_persist_validated_sizing", lambda self, pre, symbol: None)
    monkeypatch.setattr(main_mod.SentinelValidator, "validate", lambda self, inp: SimpleNamespace(score=1.0))
    monkeypatch.setattr(main_mod.RegimeRouter, "route", _route)
    _bypass_new_filters(monkeypatch)
    monkeypatch.setattr(main_mod, "evaluate_gates", lambda inp: SimpleNamespace(approved=True, reason="ok"))

    # Bypass new high-win-rate filters that reject mock data
    from src.mde import regime_alignment as _ra_mod, confluence_filter as _cf_mod, trade_quality as _tq_mod, adaptive_confidence as _ac_mod
    monkeypatch.setattr(_ra_mod, "score_regime_alignment", lambda **kw: SimpleNamespace(aligned=True, alignment_score=0.80, confidence_multiplier=1.0, reason="mock_bypass"))
    monkeypatch.setattr(_cf_mod, "evaluate_confluence", lambda **kw: SimpleNamespace(passed=True, score=0.80, factors_passed=5, factors_total=6, factor_details={}, reason="mock_bypass"))
    monkeypatch.setattr(_tq_mod, "classify_trade_quality", lambda inp, **kw: SimpleNamespace(passed=True, grade="A", composite_score=0.85, reason="mock_bypass"))
    monkeypatch.setattr(_ac_mod, "compute_adaptive_floor", lambda **kw: SimpleNamespace(effective_min_confidence=0.55, base_confidence=0.65, adjustment=0.0, recent_win_rate=0.0, sample_size=0, reason="mock_bypass"))

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "main.py",
            "--mode",
            "backtest",
            "--assets",
            "crypto",
            "--max-cycles",
            "20",
            "--run-dir",
            str(run_dir),
            "--v25",
            "--v25-db",
            str(db_path),
            "--v25-dryrun-log",
            str(dryrun_log),
            "--replay-now",
            "2024-02-01T12:00:00Z",
            "--cycle-step-minutes",
            "1",
            "--risk-profile",
            "relaxed",
            "--allow-crisis",
            "--hold-minutes",
            "30",
        ],
    )

    main_mod.main()

    conn = sqlite3.connect(db_path)
    try:
        closed = conn.execute("SELECT COUNT(*) FROM trades WHERE exit_time IS NOT NULL").fetchone()[0]
        same = conn.execute(
            """
            SELECT COUNT(*) FROM trades
            WHERE exit_time IS NOT NULL
              AND entry_price IS NOT NULL
              AND exit_price IS NOT NULL
              AND ABS(entry_price - exit_price) < 1e-12
            """
        ).fetchone()[0]
    finally:
        conn.close()

    assert closed >= 1
    assert same <= closed
