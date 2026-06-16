"""Schemas for the Financial Decision Engine quote endpoint (C7a)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.intelligence.decision.request import (
    DecisionKind,
    EmotionalImportance,
    Flexibility,
    OutflowShape,
)

Money = Annotated[Decimal, Field(gt=0, max_digits=18, decimal_places=4)]


class ConstraintsIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # hard constraints (block strategies)
    date_fixed: bool = False
    no_savings: bool = False
    no_delay: bool = False
    mandatory: bool = False
    # soft preferences (prioritize strategies)
    willing_to_delay: bool = False
    willing_to_use_savings: bool = False
    willing_to_reduce_spending: bool = False
    reducible_categories: list[str] = Field(default_factory=list)


class ModifierInputsIn(BaseModel):
    """Optional modifier-analyzer inputs (collected via the influence step + follow-ups)."""

    model_config = ConfigDict(extra="forbid")

    involves: list[str] | None = None
    original_amount: Decimal | None = None
    final_amount: Decimal | None = None
    items_useful: str | None = None
    delivery_fee: Decimal | None = None
    free_delivery_threshold: Decimal | None = None
    offer: dict | None = None
    bundle_add_ons: list[dict] | None = None
    hidden_items: list[dict] | None = None
    subscription: dict | None = None
    emi: dict | None = None
    cancel_cost: Decimal | None = None
    change_trigger: str | None = None


class DecisionQuoteIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item_label: str = Field(min_length=1, max_length=255)
    original_amount: Money
    original_currency: str = Field(min_length=3, max_length=3)
    decision_kind: DecisionKind = DecisionKind.purchase
    outflow_shape: OutflowShape = OutflowShape.one_time
    recurrence_months: int | None = Field(default=None, ge=1, le=120)
    tenure_months: int | None = Field(default=None, ge=1, le=600)
    target_date: date | None = None
    flexibility: Flexibility = Flexibility.flexible
    emotional_importance: EmotionalImportance = EmotionalImportance.medium
    constraints: ConstraintsIn = Field(default_factory=ConstraintsIn)
    excluded_strategies: list[str] = Field(default_factory=list)
    modifiers: ModifierInputsIn | None = None

    @field_validator("original_currency")
    @classmethod
    def _upper(cls, value: str) -> str:
        return value.upper()
