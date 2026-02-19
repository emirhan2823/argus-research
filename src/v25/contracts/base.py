"""Core contract primitives for ARGUS v2.5."""

from __future__ import annotations

import math
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Annotated, Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator


DecimalValue = Annotated[
    Decimal,
    Field(max_digits=38, decimal_places=18),
]

PositiveDecimal = Annotated[
    Decimal,
    Field(gt=Decimal("0"), max_digits=38, decimal_places=18),
]

NonNegativeDecimal = Annotated[
    Decimal,
    Field(ge=Decimal("0"), max_digits=38, decimal_places=18),
]

RatioDecimal = Annotated[
    Decimal,
    Field(ge=Decimal("0"), le=Decimal("1"), max_digits=20, decimal_places=10),
]

SignedUnitDecimal = Annotated[
    Decimal,
    Field(ge=Decimal("-1"), le=Decimal("1"), max_digits=20, decimal_places=10),
]


class AuditSeverity(str, Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class ArgusModel(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")

    @model_validator(mode="after")
    def _validate_scalar_values(self) -> "ArgusModel":
        for field_name in self.__class__.model_fields:
            value = getattr(self, field_name)

            if isinstance(value, float):
                if math.isnan(value) or math.isinf(value):
                    raise ValueError(f"Invalid float for field '{field_name}'")

            if isinstance(value, Decimal):
                if not value.is_finite():
                    raise ValueError(f"Invalid Decimal for field '{field_name}'")

            if isinstance(value, datetime):
                if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
                    raise ValueError(f"Datetime must be timezone-aware for '{field_name}'")

        return self


class TimestampedModel(ArgusModel):
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AuditLog(TimestampedModel):
    audit_id: UUID = Field(default_factory=uuid4)
    module: str = Field(min_length=1, max_length=128)
    event: str = Field(min_length=1, max_length=128)
    severity: AuditSeverity = AuditSeverity.INFO
    message: str = Field(min_length=1, max_length=4096)
    run_id: str | None = Field(default=None, min_length=1, max_length=128)
    correlation_id: str | None = Field(default=None, min_length=1, max_length=128)
    symbol: str | None = Field(default=None, min_length=1, max_length=64)
    asset_class: str | None = Field(default=None, min_length=1, max_length=32)
    actor: str | None = Field(default=None, min_length=1, max_length=128)
    payload: dict[str, Any] = Field(default_factory=dict)
    tags: tuple[str, ...] = ()
