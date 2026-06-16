"""Lifestyle Profile metrics."""

from __future__ import annotations

from decimal import Decimal

from app.intelligence.behavior import scoring
from app.intelligence.behavior.data import BehaviorData, ExpenseRow, monthly_expense_totals, monthly_income_totals
from app.intelligence.behavior.registry import LIFESTYLE, LOWER_BETTER, register

_MIN_ROWS = 20


def _discretionary_ratio(data: BehaviorData, rows: list[ExpenseRow]) -> Decimal | None:
    total = sum((e.amount for e in rows), Decimal("0"))
    disc = sum((e.amount for e in rows if not data.is_essential(e.category_id)), Decimal("0"))
    return scoring.safe_ratio(disc, total)


@register(key="discretionary_spend_ratio", dimension=LIFESTYLE, direction=LOWER_BETTER,
          controllable=True, forward_risk=True, personality_tags=("experience_seeker", "social_spender"))
def discretionary_spend_ratio(data: BehaviorData) -> scoring.BehavioralMetric:
    key, dim = "discretionary_spend_ratio", LIFESTYLE
    months = set(data.window.complete_months or data.window.months)
    rows = [e for e in data.expenses if (e.on.year, e.on.month) in months]
    if len(rows) < _MIN_ROWS:
        return scoring.insufficient(key, dim, "insufficient_data", {"rows": len(rows)})

    ratio = _discretionary_ratio(data, rows)
    if ratio is None:
        return scoring.insufficient(key, dim, "insufficient_data", {"rows": len(rows)})
    score = 100 - max(0.0, float(ratio) - 0.50) * 200

    complete = data.window.complete_months
    if len(complete) >= 2:
        last = complete[-1]
        recent = _discretionary_ratio(data, [e for e in rows if (e.on.year, e.on.month) == last])
        prior = _discretionary_ratio(data, [e for e in rows if (e.on.year, e.on.month) != last])
    else:
        recent = prior = None
    return scoring.metric(
        key=key, dimension=dim, value=ratio.quantize(Decimal("0.001")), score=scoring.clamp_score(score),
        confidence="normal", trend=scoring.classify_trend(recent, prior, LOWER_BETTER),
        facts={"discretionary_ratio": str(ratio.quantize(Decimal("0.001")))},
    )


@register(key="recurring_cost_load", dimension=LIFESTYLE, direction=LOWER_BETTER,
          forward_risk=True, personality_tags=("risk_taker",))
def recurring_cost_load(data: BehaviorData) -> scoring.BehavioralMetric:
    key, dim = "recurring_cost_load", LIFESTYLE
    recurring_monthly = sum((p.amount for p in data.planned if p.is_recurring), Decimal("0"))
    # With no recurring commitments AND no planned expenses at all, there is no
    # evidence to judge commitment behaviour -> stay neutral / low confidence.
    if recurring_monthly == 0 and not data.planned:
        return scoring.insufficient(key, dim, "no_commitment_data")

    denom = data.monthly_income_estimate
    if not denom or denom <= 0:
        inc = monthly_income_totals(data)
        denom = scoring.mean_dec([v for v in inc.values()]) if inc else Decimal("0")
    if not denom or denom <= 0:
        exp = monthly_expense_totals(data)
        denom = scoring.mean_dec([v for v in exp.values()]) if exp else Decimal("0")
    if not denom or denom <= 0:
        return scoring.insufficient(key, dim, "no_income_reference")

    ratio = recurring_monthly / denom
    score = 100 - max(0.0, float(ratio) - 0.30) * 200
    return scoring.metric(
        key=key, dimension=dim, value=ratio.quantize(Decimal("0.001")), score=scoring.clamp_score(score),
        confidence="normal", trend="unknown",
        facts={"recurring_monthly": str(recurring_monthly), "reference": str(denom),
               "load_ratio": str(ratio.quantize(Decimal("0.001")))},
    )
