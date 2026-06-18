"""Analytics schemas: report sessions, graph series, story, timeline hooks."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel


class GraphPoint(BaseModel):
    label: str            # e.g. "Mon", "Wk 1", "7 Sep"
    spent: Decimal
    income: Decimal
    saved: Decimal        # max(0, budget - spent) for the bucket


class GraphSeries(BaseModel):
    granularity: str      # "day" | "week"
    points: list[GraphPoint]


class ReportSummary(BaseModel):
    currency: str
    total_spent: Decimal
    total_income: Decimal
    saved: Decimal
    red_days: int
    crown_days: int


class ReportStory(BaseModel):
    beginning: str
    middle: str
    end: str


class TimelineEvent(BaseModel):
    date: date
    label: str
    kind: str             # goal | receivable_overdue | big_expense | income | ...


class CategoryDelta(BaseModel):
    label: str
    current: Decimal
    previous: Decimal
    change_pct: float | None = None     # None when previous == 0 (can't divide)


class PeriodDelta(BaseModel):
    """Comparison vs another period (first-class)."""
    spent_change_pct: float | None = None
    income_change_pct: float | None = None
    saved_change_pct: float | None = None
    biggest_increase: CategoryDelta | None = None
    biggest_decrease: CategoryDelta | None = None
    categories: list[CategoryDelta] = []


class DrilldownItem(BaseModel):
    label: str
    amount: Decimal | None = None
    currency: str | None = None
    when: date | None = None
    subtitle: str | None = None


class DrilldownResult(BaseModel):
    kind: str                 # red_days | crown_days | category | tag | person | subscription | loan | ...
    title: str
    currency: str
    total: Decimal | None = None
    items: list[DrilldownItem]
    explanation: str          # plain-language "what this is / why"


class ReportSession(BaseModel):
    kind: str             # week | month
    period_from: date
    period_to: date
    period_label: str
    currency: str
    series: GraphSeries
    summary: ReportSummary
    story: ReportStory
    timeline_events: list[TimelineEvent]
    confidence: str       # high | medium | low | insufficient
    # First-class comparison hooks (filled in 4b-2):
    comparison_from: date | None = None
    comparison_to: date | None = None
    delta: PeriodDelta | None = None
