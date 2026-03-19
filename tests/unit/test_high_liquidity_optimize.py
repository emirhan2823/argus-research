from __future__ import annotations

from Scripts.high_liquidity_optimize import Candidate, _apply_candidate, _candidate_grid


def test_candidate_grid_expected_shape() -> None:
    rows = _candidate_grid(None)
    assert len(rows) == 108
    assert rows[0].name.startswith("cand_")


def test_apply_candidate_updates_policy_fields() -> None:
    base = {
        "high_liquidity_filters": {
            "enabled": True,
            "target_symbols": ["BTCUSDT", "ETHUSDT"],
            "policies": {
                "1h": {
                    "defaults": {
                        "precision": {"min_grade": "D"},
                        "confluence": {"min_score": 0.50},
                        "risk": {"min_rr": 2.0, "crypto_min_rr": 2.1},
                        "trade_quality": {"grade_c_min_confidence": 0.85},
                    }
                },
                "15m": {
                    "defaults": {
                        "precision": {"min_grade": "D"},
                        "confluence": {"min_score": 0.55},
                        "risk": {"min_rr": 2.2, "crypto_min_rr": 2.3},
                        "trade_quality": {"grade_c_min_confidence": 0.85},
                    },
                    "engines": {"HYDRA": {"mode": "off"}},
                },
            },
        }
    }
    cand = Candidate(
        name="x",
        hydra_mode_15m="strict",
        confluence_offset=0.05,
        precision_min_grade="C",
        rr_offset=0.20,
        grade_c_min_conf=0.80,
    )
    out = _apply_candidate(base, cand)
    node = out["high_liquidity_filters"]
    assert node["policies"]["15m"]["engines"]["HYDRA"]["mode"] == "strict"
    assert node["policies"]["1h"]["defaults"]["precision"]["min_grade"] == "C"
    assert node["policies"]["15m"]["defaults"]["risk"]["min_rr"] >= 2.4
    assert node["policies"]["1h"]["defaults"]["trade_quality"]["grade_c_min_confidence"] == 0.8

