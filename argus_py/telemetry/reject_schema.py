from __future__ import annotations

import re
from typing import Tuple


_CODE_RE = re.compile(r"^[A-Z][A-Z0-9_]{2,63}$")


def normalize_reject(code: str | None, detail: str | None) -> Tuple[str, str]:
    raw_code = (code or "").strip().upper()
    raw_code = re.sub(r"[^A-Z0-9_]+", "_", raw_code).strip("_")
    if not raw_code:
        raw_code = "REJECT_UNKNOWN"

    raw_detail = (detail or "").strip()
    if not raw_detail:
        raw_detail = "No detail provided"

    return raw_code, raw_detail


def validate_reject(code: str, detail: str) -> None:
    if not _CODE_RE.match(code):
        raise ValueError(f"invalid reject code format: {code}")
    if not detail or not str(detail).strip():
        raise ValueError("reject detail must be non-empty")
