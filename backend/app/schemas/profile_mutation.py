"""Conversational profile mutation (Budget Intelligence System — Phase 5).

Parse a life change → preview → confirm → apply → recalculate → explain the impact.
Nothing changes without a preview; the user just tells Advary.
"""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class ProposedChange(BaseModel):
    target: str            # profile | income_add | income_remove | future_move
    field: str
    value: str | None = None
    label: str             # human-readable diff line


class MutationIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=1, max_length=500)


class ProfileChangeProposal(BaseModel):
    understood: bool
    changes: list[ProposedChange]
    preview: str           # "I'll update: Country → Japan, Rent → ¥80,000. Apply?"
    needs_amount: bool = False


class ImpactDiff(BaseModel):
    housing_ratio_before: float
    housing_ratio_after: float
    probability_before: str
    probability_after: str
    comfortable_surplus_before: Decimal
    comfortable_surplus_after: Decimal
    notes: list[str]


class ProfileChangeResult(BaseModel):
    applied: list[ProposedChange]
    impact: ImpactDiff
    message: str
