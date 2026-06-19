"""Payable schemas — money the user borrowed and owes."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import ImportanceLevel, PayableStatus, ReturnExpectation

Money = Annotated[Decimal, Field(gt=0, max_digits=18, decimal_places=4)]


class PayableCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_name: str = Field(min_length=1, max_length=200)  # who you owe
    original_amount: Money
    original_currency: str = Field(min_length=3, max_length=3)
    return_expectation: ReturnExpectation = ReturnExpectation.required
    due_date: date | None = None
    reason: str | None = Field(default=None, max_length=2000)
    person_id: uuid.UUID | None = None
    importance: ImportanceLevel = ImportanceLevel.medium
    ai_metadata: dict[str, Any] | None = None

    @field_validator("original_currency")
    @classmethod
    def _upper(cls, value: str) -> str:
        return value.upper()


class PayableUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_name: str | None = Field(default=None, min_length=1, max_length=200)
    original_amount: Money | None = None
    original_currency: str | None = Field(default=None, min_length=3, max_length=3)
    return_expectation: ReturnExpectation | None = None
    due_date: date | None = None
    reason: str | None = Field(default=None, max_length=2000)
    status: PayableStatus | None = None
    person_id: uuid.UUID | None = None
    importance: ImportanceLevel | None = None
    ai_metadata: dict[str, Any] | None = None

    @field_validator("original_currency")
    @classmethod
    def _upper(cls, value: str | None) -> str | None:
        return value.upper() if value is not None else value


class RepaymentPlanRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_date: date
    preference: str = "auto"  # all_at_once | gradual | auto


class PayableRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    source_name: str
    person_id: uuid.UUID | None
    original_amount: Decimal
    original_currency: str
    exchange_rate: Decimal
    converted_amount: Decimal
    base_currency: str
    return_expectation: ReturnExpectation
    due_date: date | None
    reason: str | None
    status: PayableStatus
    days_overdue: int  # derived: open + past due_date
    settled_at: datetime | None
    importance: ImportanceLevel
    ai_metadata: dict[str, Any] | None
    created_at: datetime
    updated_at: datetime
