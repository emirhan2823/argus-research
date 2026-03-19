from __future__ import annotations

from src.mde.trade_quality import TradeQualityConfig, TradeQualityInput, classify_trade_quality


def _inp(confidence: float = 0.82) -> TradeQualityInput:
    return TradeQualityInput(
        signal_quality_score=0.56,
        precision_grade_score=0.56,
        confluence_score=0.56,
        regime_alignment_score=0.56,
        final_confidence=confidence,
        reward_risk_ratio=2.0,
    )


def test_trade_quality_uses_custom_c_confidence_floor() -> None:
    res_default = classify_trade_quality(_inp(confidence=0.82))
    assert res_default.grade == "C"
    assert res_default.passed is False

    res_custom = classify_trade_quality(
        _inp(confidence=0.82),
        config=TradeQualityConfig(grade_c_min_confidence=0.80),
    )
    assert res_custom.grade == "C"
    assert res_custom.passed is True


def test_trade_quality_allows_grade_c_in_crypto_when_enabled() -> None:
    res_reject = classify_trade_quality(_inp(confidence=0.90), crypto_fee_mode=True)
    assert res_reject.grade == "C"
    assert res_reject.passed is False

    res_allow = classify_trade_quality(
        _inp(confidence=0.90),
        crypto_fee_mode=True,
        config=TradeQualityConfig(
            grade_c_min_confidence=0.85,
            allow_grade_c_in_crypto=True,
        ),
    )
    assert res_allow.grade == "C"
    assert res_allow.passed is True
    assert "exception_crypto" in res_allow.reason

