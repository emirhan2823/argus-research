from __future__ import annotations

from pathlib import Path
import sys

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from argus_py.telemetry.reject_schema import normalize_reject, validate_reject


def test_normalize_reject_fills_defaults_for_empty_payload():
    code, detail = normalize_reject("", "")
    assert code == "REJECT_UNKNOWN"
    assert detail == "No detail provided"


def test_normalize_reject_uppercases_and_sanitizes_code():
    code, detail = normalize_reject("reject-risk cap", "  blocked by guard  ")
    assert code == "REJECT_RISK_CAP"
    assert detail == "blocked by guard"


def test_validate_reject_accepts_stable_schema():
    validate_reject("REJECT_RISK_CAP", "Daily cap reached")


@pytest.mark.parametrize("bad_code", ["", "bad", "REJECT-RISK", "??"])
def test_validate_reject_rejects_invalid_codes(bad_code: str):
    with pytest.raises(ValueError):
        validate_reject(bad_code, "detail")


def test_validate_reject_requires_non_empty_detail():
    with pytest.raises(ValueError):
        validate_reject("REJECT_COOLDOWN", "")
