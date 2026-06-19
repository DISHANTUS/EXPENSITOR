"""Planned-expense schemas."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import OccasionType, PlannedExpensePriority, PlannedExpenseStatus

Money = Annotated[Decimal, Field(gt=0, max_digits=18, decimal_places=4)]
# Events double as notes/reminders (a birthday, an exam, "call parents"), so an
# event can carry no money — amount defaults to 0 and the UI hides a zero amount.
OptionalMoney = Annotated[Decimal, Field(ge=0, max_digits=18, decimal_places=4)]


class PlannedExpenseCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=255)
    planned_date: date
    original_amount: OptionalMoney = Decimal("0")
    original_currency: str = Field(min_length=3, max_length=3)
    priority: PlannedExpensePriority = PlannedExpensePriority.medium
    notes: str | None = Field(default=None, max_length=2000)
    category_id: uuid.UUID | None = None
    is_recurring: bool = False
    occasion_type: OccasionType | None = None

    @field_validator("original_currency")
    @classmethod
    def _upper(cls, value: str) -> str:
        return value.upper()


class PlannedExpenseUpdate(BaseModel):
    """Partial update. ``status`` is settable here (create always starts 'planned')."""

    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=255)
    planned_date: date | None = None
    original_amount: OptionalMoney | None = None
    original_currency: str | None = Field(default=None, min_length=3, max_length=3)
    priority: PlannedExpensePriority | None = None
    status: PlannedExpenseStatus | None = None
    notes: str | None = Field(default=None, max_length=2000)
    category_id: uuid.UUID | None = None
    is_recurring: bool | None = None
    occasion_type: OccasionType | None = None

    @field_validator("original_currency")
    @classmethod
    def _upper(cls, value: str | None) -> str | None:
        return value.upper() if value is not None else value


class PlannedExpenseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    category_id: uuid.UUID | None
    title: str
    planned_date: date
    original_amount: Decimal
    original_currency: str
    exchange_rate: Decimal
    converted_amount: Decimal
    base_currency: str
    priority: PlannedExpensePriority
    status: PlannedExpenseStatus
    notes: str | None
    is_recurring: bool
    occasion_type: OccasionType | None
    created_at: datetime
    updated_at: datetime
