"""Budget Reality breakdown (Budget Intelligence System — Reality Engine).

Income broken out BY SOURCE (sources matter, not just the total) and every planned
outflow grouped into the 4 buckets, with survival (essentials) surfaced before
savings.
"""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel


class IncomeLine(BaseModel):
    label: str
    source_type: str
    monthly: Decimal


class BudgetLine(BaseModel):
    label: str
    monthly: Decimal
    origin: str        # "profile" | "recurring" | "goal"
    kind: str | None = None   # within PROTECTED: "housing" | "essential_living"


class BucketBreakdown(BaseModel):
    bucket: str        # protected | committed | adjustable | goal
    lines: list[BudgetLine]
    total: Decimal


class BudgetReality(BaseModel):
    base_currency: str
    optimization_style: str

    income_sources: list[IncomeLine]
    income_total: Decimal

    protected: BucketBreakdown
    committed: BucketBreakdown
    adjustable: BucketBreakdown
    goals: BucketBreakdown

    # Survival before savings:
    essentials_total: Decimal              # protected + committed
    available_after_essentials: Decimal    # income − essentials (negative ⇒ short)

    # Housing is a distinct problem from food (rent eating the income vs overspending).
    housing_total: Decimal                 # the "protected housing" slice (rent/dorm/fees)
    housing_ratio: float                   # housing / income (0..1); 0 if no income
