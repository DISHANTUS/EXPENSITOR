"""Income Quality metrics."""

from __future__ import annotations

from decimal import Decimal

from app.intelligence.behavior import scoring
from app.intelligence.behavior.data import BehaviorData, monthly_income_totals
from app.intelligence.behavior.registry import DESCRIPTIVE, HIGHER_BETTER, INCOME, register
from app.models.enums import IncomeKind

_MIN_MONTHS = 2


@register(key="income_reliability_score", dimension=INCOME, direction=HIGHER_BETTER,
          personality_tags=("conservative_saver", "risk_taker"))
def income_reliability_score(data: BehaviorData) -> scoring.BehavioralMetric:
    """Actual monthly income vs the expected recurring total (capped at 1.0/mo)."""
    key, dim = "income_reliability_score", INCOME
    expected_monthly = sum(
        (s.amount for s in data.income_sources if s.kind == IncomeKind.recurring.value), Decimal("0")
    )
    if expected_monthly <= 0:
        return scoring.insufficient(key, dim, "no_recurring_income")
    complete = data.window.complete_months
    if len(complete) < _MIN_MONTHS:
        return scoring.insufficient(key, dim, "insufficient_data", {"complete_months": len(complete)})

    inc = monthly_income_totals(data, complete)
    ratios = [min(Decimal("1"), inc[ym] / expected_monthly) for ym in complete]
    reliability = scoring.mean_dec(ratios)
    score = float(reliability) * 100

    last = complete[-1]
    recent = min(Decimal("1"), inc[last] / expected_monthly)
    earlier = [ym for ym in complete if ym != last]
    prior = scoring.mean_dec([min(Decimal("1"), inc[ym] / expected_monthly) for ym in earlier]) if earlier else None
    return scoring.metric(
        key=key, dimension=dim, value=reliability.quantize(Decimal("0.001")), score=scoring.clamp_score(score),
        confidence="normal", trend=scoring.classify_trend(recent, prior, HIGHER_BETTER),
        facts={"expected_monthly": str(expected_monthly), "reliability": str(reliability.quantize(Decimal("0.001"))),
               "months_observed": len(complete)},
    )


@register(key="recurring_income_dependency", dimension=INCOME, direction=DESCRIPTIVE,
          personality_tags=("conservative_saver",))
def recurring_income_dependency(data: BehaviorData) -> scoring.BehavioralMetric:
    """Share of expected income that comes from recurring sources (predictability)."""
    key, dim = "recurring_income_dependency", INCOME
    if not data.income_sources:
        return scoring.insufficient(key, dim, "no_income_sources")

    total = sum((s.amount for s in data.income_sources), Decimal("0"))
    recurring = sum((s.amount for s in data.income_sources if s.kind == IncomeKind.recurring.value), Decimal("0"))
    share = scoring.safe_ratio(recurring, total)
    if share is None:
        return scoring.insufficient(key, dim, "no_income_sources")

    # More recurring share => more predictable income => higher score.
    score = 40 + float(share) * 60
    return scoring.metric(
        key=key, dimension=dim, value=share.quantize(Decimal("0.001")), score=scoring.clamp_score(score),
        confidence="normal", trend="flat",
        facts={"recurring_share": str(share.quantize(Decimal("0.001"))),
               "source_count": len(data.income_sources)},
    )
