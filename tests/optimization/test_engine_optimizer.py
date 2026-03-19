from __future__ import annotations

from datetime import date
import sys

import pytest

import src.main as main_mod
from src.optimization.engine_optimizer import (
    AssetEvaluation,
    OptimizationArtifacts,
    RiskOptimizationArtifacts,
    WindowMetrics,
    aggregate_balanced_class_scores,
    asset_class_for_symbol,
    compute_composite_score,
    compute_side_aware_composite_score,
    compute_risk_composite_score,
    detect_overfit,
    detect_overfit_risk,
    generate_walk_forward_splits,
    risk_parameter_sets,
)


def test_generate_walk_forward_splits_is_deterministic() -> None:
    kwargs = {
        "optimize_start": date(2020, 1, 1),
        "optimize_end": date(2021, 1, 1),
        "walk_window_days": 180,
        "walk_step_days": 30,
    }
    splits_a = generate_walk_forward_splits(**kwargs)
    splits_b = generate_walk_forward_splits(**kwargs)

    assert splits_a == splits_b
    assert len(splits_a) > 0
    assert splits_a[0].train_start == date(2020, 1, 1)
    assert splits_a[0].train_end == date(2020, 6, 29)
    assert splits_a[0].test_start == date(2020, 6, 29)
    assert splits_a[0].test_end == date(2020, 7, 29)


def test_detect_overfit_flags_expected_conditions() -> None:
    strong = AssetEvaluation(
        asset="BTCUSDT",
        windows=6,
        train=WindowMetrics(0.20, 3.2, -0.05, 0.70, 0.001),
        test=WindowMetrics(0.08, 0.7, -0.10, 0.50, 0.002),
        drawdown_instability=0.35,
        test_by_regime={},
    )
    weak = AssetEvaluation(
        asset="ETHUSDT",
        windows=6,
        train=WindowMetrics(0.18, 2.8, -0.06, 0.65, 0.0012),
        test=WindowMetrics(-0.04, 0.1, -0.12, 0.38, 0.0023),
        drawdown_instability=0.02,
        test_by_regime={},
    )

    flagged, reasons = detect_overfit(
        avg_train_sharpe=3.0,
        avg_test_sharpe=0.6,
        assets={"BTCUSDT": strong, "ETHUSDT": weak},
    )

    assert flagged is True
    assert "train_sharpe_gt_2x_test_sharpe" in reasons
    assert "performance_concentrated_single_asset" in reasons
    assert "drawdown_instability_excess" in reasons
    assert "test_win_rate_below_45pct" in reasons


def test_composite_score_consistency() -> None:
    score = compute_composite_score(
        avg_sharpe=1.2,
        avg_total_return=0.18,
        max_drawdown=-0.10,
        stability_penalty=0.70,
        cross_asset_consistency=0.85,
    )
    expected = (
        0.35 * 1.2
        + 0.25 * 0.18
        - 0.20 * 0.10
        + 0.10 * 0.70
        + 0.10 * 0.85
    )
    assert score == pytest.approx(expected, rel=1e-12, abs=1e-12)

    score_repeat = compute_composite_score(
        avg_sharpe=1.2,
        avg_total_return=0.18,
        max_drawdown=-0.10,
        stability_penalty=0.70,
        cross_asset_consistency=0.85,
    )
    assert score_repeat == pytest.approx(score, rel=1e-12, abs=1e-12)


def test_side_aware_composite_score_consistency() -> None:
    score = compute_side_aware_composite_score(
        avg_total_return=0.20,
        long_total_return=0.18,
        short_total_return=0.12,
        regime_stability=0.85,
        max_drawdown_penalty=0.90,
        overfit_penalty=1.0,
    )
    expected = (
        0.25 * 0.20
        + 0.20 * 0.18
        + 0.20 * 0.12
        + 0.15 * 0.85
        + 0.10 * 0.90
        + 0.10 * 1.0
    )
    assert score == pytest.approx(expected, rel=1e-12, abs=1e-12)


def test_cli_integration_optimize_engines(monkeypatch, tmp_path) -> None:
    called: dict[str, object] = {}

    def _fake_run(request, *, evaluator=None):  # noqa: ANN001
        _ = evaluator
        called["request"] = request
        summary = tmp_path / "ENGINE_OPTIMIZATION_SUMMARY.md"
        results = tmp_path / "ENGINE_OPTIMIZATION_RESULTS.csv"
        heatmap = tmp_path / "ENGINE_OPTIMIZATION_HEATMAP.csv"
        summary.write_text("# ok\n", encoding="utf-8")
        results.write_text("rank\n1\n", encoding="utf-8")
        heatmap.write_text("engine\nTitan\n", encoding="utf-8")
        return OptimizationArtifacts(
            summary_path=summary,
            results_csv_path=results,
            heatmap_csv_path=heatmap,
            result_count=1,
            overfit_count=0,
            split_count=3,
        )

    monkeypatch.setattr("src.optimization.engine_optimizer.run_engine_optimization", _fake_run)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "main.py",
            "--mode",
            "backtest",
            "--optimize-engines",
            "--optimize-assets",
            "BTCUSDT,ETHUSDT",
            "--optimize-start",
            "2022-01-01",
            "--optimize-end",
            "2023-01-01",
            "--walk-window-days",
            "180",
            "--walk-step-days",
            "30",
        ],
    )

    main_mod.main()

    req = called.get("request")
    assert req is not None
    assert tuple(req.assets) == ("BTCUSDT", "ETHUSDT")
    assert req.optimize_start.isoformat() == "2022-01-01"
    assert req.optimize_end.isoformat() == "2023-01-01"
    assert int(req.walk_window_days) == 180
    assert int(req.walk_step_days) == 30


def test_risk_parameter_sets_are_deterministic() -> None:
    a = risk_parameter_sets()
    b = risk_parameter_sets()
    assert a == b
    assert len(a) > 0
    assert set(a[0].keys()) == {
        "atr_multiplier_long",
        "atr_multiplier_short",
        "rr_ratio_long",
        "rr_ratio_short",
        "leverage_cap_long",
        "leverage_cap_short",
        "trailing_activation_long",
        "trailing_activation_short",
        "volatility_threshold",
        "vol_k",
        "drawdown_sensitivity",
        "confidence_floor",
    }


def test_risk_composite_score_consistency() -> None:
    score = compute_risk_composite_score(
        sharpe=1.2,
        total_return=0.18,
        max_drawdown=-0.10,
        win_rate=0.55,
        volatility_of_returns=0.12,
    )
    expected = 0.35 * 1.2 + 0.25 * 0.18 - 0.20 * 0.10 + 0.10 * 0.55 - 0.10 * 0.12
    assert score == pytest.approx(expected, rel=1e-12, abs=1e-12)


def test_detect_overfit_risk_rejects_expected_conditions() -> None:
    flagged, reasons = detect_overfit_risk(
        avg_train_return=0.30,
        avg_test_return=0.10,
        avg_test_sharpe=-0.1,
        max_drawdown=-0.40,
    )
    assert flagged is True
    assert "train_return_gt_2x_test_return" in reasons
    assert "test_sharpe_negative" in reasons
    assert "max_drawdown_gt_35pct" in reasons


def test_detect_overfit_risk_rejects_cap_saturation_and_short_collapse() -> None:
    flagged, reasons = detect_overfit_risk(
        avg_train_return=0.08,
        avg_test_return=0.04,
        avg_test_sharpe=0.5,
        max_drawdown=-0.12,
        long_trade_count=12,
        short_trade_count=12,
        short_return_bear=-0.01,
        leverage_cap_saturation=0.75,
    )
    assert flagged is True
    assert "short_bear_edge_below_threshold" in reasons
    assert "leverage_cap_saturation_excess" in reasons


def test_detect_overfit_rejects_asymmetric_long_only() -> None:
    strong_long = AssetEvaluation(
        asset="BTCUSDT",
        windows=3,
        train=WindowMetrics(0.15, 1.8, -0.08, 0.62, 0.001, trade_count=12, long_trade_count=12, short_trade_count=0),
        test=WindowMetrics(0.10, 1.2, -0.07, 0.58, 0.001, trade_count=10, long_trade_count=10, short_trade_count=0),
        drawdown_instability=0.02,
        test_by_regime={},
    )
    flagged, reasons = detect_overfit(
        avg_train_sharpe=1.8,
        avg_test_sharpe=1.2,
        assets={"BTCUSDT": strong_long},
        long_trade_count=10,
        short_trade_count=0,
        regime_returns={"TRENDING": 0.12, "CRISIS": -0.03, "RANGING": 0.01},
    )
    assert flagged is True
    assert "short_trade_count_below_threshold" in reasons
    assert "bear_regime_not_profitable" in reasons


def test_walk_forward_overfit_detects_train_test_collapse() -> None:
    strong = AssetEvaluation(
        asset="BTCUSDT",
        windows=4,
        train=WindowMetrics(0.22, 2.5, -0.08, 0.66, 0.001),
        test=WindowMetrics(0.01, 0.4, -0.10, 0.46, 0.002),
        drawdown_instability=0.01,
        test_by_regime={},
    )
    flagged, reasons = detect_overfit(
        avg_train_sharpe=2.5,
        avg_test_sharpe=0.4,
        assets={"BTCUSDT": strong},
    )
    assert flagged is True
    assert "train_sharpe_gt_2x_test_sharpe" in reasons


def test_cli_integration_optimize_risk(monkeypatch, tmp_path) -> None:
    called: dict[str, object] = {}

    def _fake_run(request, *, engine="Titan", engine_parameter_set=None, evaluator=None, risk_mode="normal"):  # noqa: ANN001
        _ = (engine_parameter_set, evaluator, risk_mode)
        called["request"] = request
        called["engine"] = engine
        summary = tmp_path / "RISK_OPTIMIZATION_SUMMARY.md"
        results = tmp_path / "RISK_OPTIMIZATION_RESULTS.csv"
        summary.write_text("# ok\n", encoding="utf-8")
        results.write_text("rank\n1\n", encoding="utf-8")
        return RiskOptimizationArtifacts(
            summary_path=summary,
            results_csv_path=results,
            result_count=1,
            overfit_count=0,
            split_count=3,
            best_parameter_set={
                "atr_multiplier_long": 1.5,
                "atr_multiplier_short": 1.5,
                "rr_ratio_long": 2.0,
                "rr_ratio_short": 2.0,
                "leverage_cap_long": 4.0,
                "leverage_cap_short": 3.5,
                "trailing_activation_long": 1.0,
                "trailing_activation_short": 1.0,
                "volatility_threshold": 0.03,
            },
        )

    monkeypatch.setattr("src.optimization.engine_optimizer.run_risk_optimization", _fake_run)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "main.py",
            "--mode",
            "backtest",
            "--optimize-risk",
            "--risk-optimize-engine",
            "Titan",
            "--optimize-assets",
            "BTCUSDT,ETHUSDT",
            "--optimize-start",
            "2022-01-01",
            "--optimize-end",
            "2023-01-01",
            "--walk-window-days",
            "180",
            "--walk-step-days",
            "30",
        ],
    )

    main_mod.main()

    req = called.get("request")
    assert req is not None
    assert called.get("engine") == "Titan"
    assert tuple(req.assets) == ("BTCUSDT", "ETHUSDT")
    assert req.optimize_start.isoformat() == "2022-01-01"
    assert req.optimize_end.isoformat() == "2023-01-01"


def test_mapping_fallback_unknown() -> None:
    assert asset_class_for_symbol("FOO") == "unknown"
    # Normalization: separators should not break known mappings.
    assert asset_class_for_symbol("btc/usdt") == "crypto"


def test_scoring_balanced_classes() -> None:
    # Two crypto symbols are strong; one equity symbol is weak. Class-balanced scoring
    # should not allow the crypto class (with more symbols) to dominate the final score.
    symbol_segment_scores = {
        "BTCUSDT": [0.90, 0.90],
        "ETHUSDT": [0.90, 0.90],
        "AAPL": [0.10, 0.10],
    }
    symbol_segment_returns = {
        "BTCUSDT": [0.50, 0.50],
        "ETHUSDT": [0.50, 0.50],
        "AAPL": [-0.20, -0.20],
    }
    symbol_segment_trades = {
        "BTCUSDT": [10, 10],
        "ETHUSDT": [10, 10],
        "AAPL": [10, 10],
    }
    symbol_to_class = {sym: asset_class_for_symbol(sym) for sym in symbol_segment_scores.keys()}
    breakdown = aggregate_balanced_class_scores(
        symbol_segment_scores=symbol_segment_scores,
        symbol_segment_returns=symbol_segment_returns,
        symbol_segment_trades=symbol_segment_trades,
        symbol_to_asset_class=symbol_to_class,
    )

    assert breakdown.class_scores["crypto"] == pytest.approx(0.90, abs=1e-12)
    assert breakdown.class_scores["equities"] == pytest.approx(0.10, abs=1e-12)

    # base = mean([0.9, 0.1]) = 0.5
    # class_bonus = 0.05*(1 - pstdev([0.9,0.1])) with pstdev=0.4 => 0.03
    # symbol_bonus = 0.05*(1 - pstdev([0.5,0.5,-0.2])) where pstdev ~ 0.329983...
    expected_symbol_pstdev = ((0.23333333333333334**2 + 0.23333333333333334**2 + (-0.4666666666666667) ** 2) / 3) ** 0.5
    expected = 0.5 + 0.05 * (1.0 - 0.4) + 0.05 * (1.0 - expected_symbol_pstdev)
    assert breakdown.final_score == pytest.approx(expected, rel=1e-12, abs=1e-12)

    # If we had averaged per-symbol scores (0.9,0.9,0.1), we'd get ~0.633.
    # Class-balanced base is 0.5; final score should stay closer to that.
    assert breakdown.final_score < 0.62
