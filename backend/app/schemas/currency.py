"""Currency + conversion schemas."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CurrencyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    code: str
    name: str
    symbol: str
    decimal_digits: int


class ConvertRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    amount: Decimal = Field(gt=0, max_digits=18, decimal_places=4)
    from_currency: str = Field(min_length=3, max_length=3)
    to_currency: str = Field(min_length=3, max_length=3)

    @field_validator("from_currency", "to_currency")
    @classmethod
    def _upper(cls, value: str) -> str:
        return value.upper()


class ConvertResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    original_amount: Decimal
    converted_amount: Decimal
    exchange_rate: Decimal
    from_currency: str
    to_currency: str
    rate_date: date | None
