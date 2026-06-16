"""Income-source schemas (expected income feeding the projection)."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator, model_validator

from app.models.enums import ExpectedTimeWindow, IncomeKind, IncomeSourceType

Money = Annotated[Decimal, Field(gt=0, max_digits=18, decimal_places=4)]
Reliability = Annotated[Decimal, Field(ge=0, le=1, max_digits=4, decimal_places=3)]


def confidence_label_for(reliability: Decimal) -> str:
    """Map a stored reliability value to a human label."""
    if reliability >= Decimal("0.85"):
        return "High"
    if reliability >= Decimal("0.60"):
        return "Medium"
    return "Low"


class IncomeSourceCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str = Field(min_length=1, max_length=255)
    source_type: IncomeSourceType
    kind: IncomeKind
    original_amount: Money
    original_currency: str = Field(min_length=3, max_length=3)
    reliability: Reliability = Decimal("0.5")
    is_active: bool = True
    recurrence_day: int | None = Field(default=None, ge=1, le=31)
    expected_date: date | None = None
    expected_time_window: ExpectedTimeWindow | None = None

    @field_validator("original_currency")
    @classmethod
    def _upper(cls, value: str) -> str:
        return value.upper()

    @model_validator(mode="after")
    def _validate_kind(self) -> IncomeSourceCreate:
        if self.kind == IncomeKind.recurring:
            if self.recurrence_day is None:
                raise ValueError("recurrence_day is required for recurring income sources")
            self.expected_date = None
        else:  # one_time
            if self.expected_date is None:
                raise ValueError("expected_date is required for one-time income sources")
            self.recurrence_day = None
        return self


class IncomeSourceUpdate(BaseModel):
    """Partial update. Kind/recurrence/date consistency is enforced server-side
    after merging with the existing row."""

    model_config = ConfigDict(extra="forbid")

    label: str | None = Field(default=None, min_length=1, max_length=255)
    source_type: IncomeSourceType | None = None
    kind: IncomeKind | None = None
    original_amount: Money | None = None
    original_currency: str | None = Field(default=None, min_length=3, max_length=3)
    reliability: Reliability | None = None
    is_active: bool | None = None
    recurrence_day: int | None = Field(default=None, ge=1, le=31)
    expected_date: date | None = None
    expected_time_window: ExpectedTimeWindow | None = None

    @field_validator("original_currency")
    @classmethod
    def _upper(cls, value: str | None) -> str | None:
        return value.upper() if value is not None else value


class IncomeSourceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    label: str
    source_type: IncomeSourceType
    kind: IncomeKind
    original_amount: Decimal
    original_currency: str
    exchange_rate: Decimal
    converted_amount: Decimal
    base_currency: str
    recurrence_day: int | None
    expected_date: date | None
    reliability: Decimal
    is_active: bool
    expected_time_window: ExpectedTimeWindow | None
    created_at: datetime
    updated_at: datetime

    @computed_field  # type: ignore[prop-decorator]
    @property
    def confidence_label(self) -> str:
        return confidence_label_for(self.reliability)
