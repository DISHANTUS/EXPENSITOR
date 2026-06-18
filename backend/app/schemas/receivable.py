"""Receivable request/response schemas."""

from __future__ import annotations

import uuid
from datetime import date, datetime, time
from decimal import Decimal
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.enums import (
    ExpectedTimeWindow,
    ImportanceLevel,
    ReceivableKind,
    ReceivableSourceType,
    ReceivableStatus,
)

Money = Annotated[Decimal, Field(gt=0, max_digits=18, decimal_places=4)]
Reliability = Annotated[Decimal, Field(ge=0, le=1, max_digits=4, decimal_places=3)]


class ReceivableCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=255)
    source_name: str = Field(min_length=1, max_length=200)
    source_type: ReceivableSourceType
    kind: ReceivableKind
    original_amount: Money
    original_currency: str = Field(min_length=3, max_length=3)
    reliability: Reliability | None = None  # defaulted by source_type when omitted
    notes: str | None = Field(default=None, max_length=2000)
    expected_date: date | None = None
    recurrence_day: int | None = Field(default=None, ge=1, le=31)
    expected_time_window: ExpectedTimeWindow | None = None
    expected_time: time | None = None
    person_id: uuid.UUID | None = None
    importance: ImportanceLevel = ImportanceLevel.medium
    ai_metadata: dict[str, Any] | None = None

    @field_validator("original_currency")
    @classmethod
    def _upper(cls, value: str) -> str:
        return value.upper()

    @model_validator(mode="after")
    def _validate_kind(self) -> "ReceivableCreate":
        if self.kind == ReceivableKind.recurring:
            if self.recurrence_day is None:
                raise ValueError("recurrence_day is required for recurring receivables")
            self.expected_date = None
        else:  # one_time
            if self.expected_date is None:
                raise ValueError("expected_date is required for one-time receivables")
            self.recurrence_day = None
        return self


class ReceivableUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=255)
    source_name: str | None = Field(default=None, min_length=1, max_length=200)
    source_type: ReceivableSourceType | None = None
    kind: ReceivableKind | None = None
    original_amount: Money | None = None
    original_currency: str | None = Field(default=None, min_length=3, max_length=3)
    reliability: Reliability | None = None
    notes: str | None = Field(default=None, max_length=2000)
    expected_date: date | None = None
    recurrence_day: int | None = Field(default=None, ge=1, le=31)
    expected_time_window: ExpectedTimeWindow | None = None
    expected_time: time | None = None
    status: ReceivableStatus | None = None
    person_id: uuid.UUID | None = None
    importance: ImportanceLevel | None = None
    ai_metadata: dict[str, Any] | None = None

    @field_validator("original_currency")
    @classmethod
    def _upper(cls, value: str | None) -> str | None:
        return value.upper() if value is not None else value

    @field_validator("status")
    @classmethod
    def _no_overdue(cls, value: ReceivableStatus | None) -> ReceivableStatus | None:
        if value == ReceivableStatus.overdue:
            raise ValueError("status 'overdue' is derived and cannot be set directly")
        return value


class ReceivableRead(BaseModel):
    id: uuid.UUID
    title: str
    source_name: str
    source_type: ReceivableSourceType
    kind: ReceivableKind
    status: ReceivableStatus            # effective status (overdue when derived)
    days_overdue: int
    original_amount: Decimal
    original_currency: str
    exchange_rate: Decimal
    converted_amount: Decimal
    base_currency: str
    expected_date: date | None
    recurrence_day: int | None
    next_expected_date: date | None     # computed, recurring only
    reliability: Decimal
    expected_time_window: ExpectedTimeWindow | None
    expected_time: time | None
    notes: str | None
    received_at: datetime | None
    last_follow_up_at: datetime | None
    follow_up_count: int
    person_id: uuid.UUID | None
    importance: ImportanceLevel
    ai_metadata: dict[str, Any] | None
    created_at: datetime
    updated_at: datetime
