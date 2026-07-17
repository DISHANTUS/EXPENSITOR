"""Expense schemas."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator

Money = Annotated[Decimal, Field(gt=0, max_digits=18, decimal_places=4)]


class ExpenseCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    original_amount: Money
    original_currency: str = Field(min_length=3, max_length=3)
    expense_date: date
    category_id: uuid.UUID | None = None
    description: str | None = Field(default=None, max_length=500)

    @field_validator("original_currency")
    @classmethod
    def _upper(cls, value: str) -> str:
        return value.upper()


class ExpenseUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    original_amount: Money | None = None
    original_currency: str | None = Field(default=None, min_length=3, max_length=3)
    expense_date: date | None = None
    category_id: uuid.UUID | None = None
    description: str | None = Field(default=None, max_length=500)

    @field_validator("original_currency")
    @classmethod
    def _upper(cls, value: str | None) -> str | None:
        return value.upper() if value is not None else value


class ExpenseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    category_id: uuid.UUID | None
    original_amount: Decimal
    original_currency: str
    exchange_rate: Decimal
    converted_amount: Decimal
    base_currency: str
    description: str | None
    expense_date: date
    created_at: datetime
    updated_at: datetime


class PredictedExpense(BaseModel):
    """A learned daily habit the compact Home offers to log in one tap
    ("is the ₹200 for travel over?"). Never written server-side — confirming
    is an ordinary POST /expenses from the client."""

    category_id: uuid.UUID
    label: str
    amount: float
    occurrences: int
    day_type: str        # weekday | weekend
    confidence: str      # medium | high


class ReasonSuggestion(BaseModel):
    """A reason the user has given before, offered as a one-tap chip. `reason`
    is their own past wording, never generated."""

    reason: str
    uses: int
    last_used: str | None = None
