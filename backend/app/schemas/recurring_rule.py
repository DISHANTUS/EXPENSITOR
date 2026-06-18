"""Recurring-rule schemas (subscriptions / EMI / bills / insurance / borrowed)."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import ImportanceLevel, RecurringRuleType

Money = Annotated[Decimal, Field(gt=0, max_digits=18, decimal_places=4)]


class RecurringRuleCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rule_type: RecurringRuleType
    label: str = Field(min_length=1, max_length=255)
    original_amount: Money
    original_currency: str = Field(min_length=3, max_length=3)
    recurrence_day: int = Field(ge=1, le=31)
    start_date: date
    category_id: uuid.UUID | None = None
    person_id: uuid.UUID | None = None
    reason: str | None = None
    importance: ImportanceLevel = ImportanceLevel.medium
    is_active: bool = True
    ai_metadata: dict[str, Any] | None = None

    @field_validator("original_currency")
    @classmethod
    def _upper(cls, value: str) -> str:
        return value.upper()


class RecurringRuleUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rule_type: RecurringRuleType | None = None
    label: str | None = Field(default=None, min_length=1, max_length=255)
    original_amount: Money | None = None
    original_currency: str | None = Field(default=None, min_length=3, max_length=3)
    recurrence_day: int | None = Field(default=None, ge=1, le=31)
    start_date: date | None = None
    category_id: uuid.UUID | None = None
    person_id: uuid.UUID | None = None
    reason: str | None = None
    importance: ImportanceLevel | None = None
    is_active: bool | None = None
    ai_metadata: dict[str, Any] | None = None

    @field_validator("original_currency")
    @classmethod
    def _upper(cls, value: str | None) -> str | None:
        return value.upper() if value is not None else value


class RecurringRuleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    rule_type: RecurringRuleType
    label: str
    original_amount: Decimal
    original_currency: str
    exchange_rate: Decimal
    converted_amount: Decimal
    base_currency: str
    recurrence_day: int
    start_date: date
    category_id: uuid.UUID | None
    person_id: uuid.UUID | None
    reason: str | None
    importance: ImportanceLevel
    is_active: bool
    ai_metadata: dict[str, Any] | None
    created_at: datetime
    updated_at: datetime
