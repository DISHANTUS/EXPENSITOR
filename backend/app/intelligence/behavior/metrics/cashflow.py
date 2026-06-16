"""Cashflow Health metrics."""

from __future__ import annotations

from decimal import Decimal

from app.intelligence.behavior import scoring
from app.intelligence.behavior.data import BehaviorData, monthly_expense_totals, monthly_income_totals
from app.intelligence.behavior.registry import CASHFLOW, HIGHER_BETTER, LOWER_BETTER, register

_MIN_MONTHS = 3


@register(key="average_monthly_surplus", dimension=CASHFLOW, direction=HIGHER_BETTER,
          forward_risk=True, personality_tags=("conservative_saver", "risk_taker"))
def average_monthly_surplus(data: BehaviorData) -> scoring.BehavioralMetric:
    key, dim = "average_monthly_surplus", CASHFLOW
    complete = data.window.complete_months
    if len(complete) < _MIN_MONTHS:
        return scoring.insufficient(key, dim, "insufficient_data", {"complete_months": len(complete)})

    inc = monthly_income_totals(data, complete)
    exp = monthly_expense_totals(data, complete)
    avg_income = scoring.mean_dec([inc[ym] for ym in complete])
    if avg_income <= 0:
        return scoring.insufficient(key, dim, "no_income_data", {"complete_months": len(complete)})

    nets = {ym: inc[ym] - exp[ym] for ym in complete}
    avg_surplus = scoring.mean_dec([nets[ym] for ym in complete])
    surplus_ratio = avg_surplus / avg_income
    score = 50 + float(surplus_ratio) * 200

    last = complete[-1]
    recent = nets[last]
    earlier = [ym for ym in complete if ym != last]
    prior = scoring.mean_dec([nets[ym] for ym in earlier]) if earlier else None
    return scoring.metric(
        key=key, dimension=dim, value=avg_surplus.quantize(Decimal("0.01")), score=scoring.clamp_score(score),
        confidence="normal", trend=scoring.classify_trend(recent, prior, HIGHER_BETTER),
        facts={"avg_monthly_surplus": str(avg_surplus.quantize(Decimal("0.01"))),
               "avg_monthly_income": str(avg_income.quantize(Decimal("0.01"))),
               "surplus_ratio": str(surplus_ratio.quantize(Decimal("0.001")))},
    )


@register(key="spending_stability", dimension=CASHFLOW, direction=LOWER_BETTER,
          forward_risk=True, personality_tags=("conservative_saver", "risk_taker"))
def spending_stability(data: BehaviorData) -> scoring.BehavioralMetric:
    key, dim = "spending_stability", CASHFLOW
    complete = data.window.complete_months
    if len(complete) < _MIN_MONTHS:
        return scoring.insufficient(key, dim, "insufficient_data", {"complete_months": len(complete)})

    totals = monthly_expense_totals(data, complete)
    active = [ym for ym in complete if totals[ym] > 0]  # need real spend to judge volatility
    if len(active) < _MIN_MONTHS:
        return scoring.insufficient(key, dim, "insufficient_data", {"active_months": len(active)})

    series = [totals[ym] for ym in active]
    cov = scoring.coefficient_of_variation(series)
    score = 100 - float(cov) * 200

    half = len(series) // 2
    prior = scoring.coefficient_of_variation(series[:half + 1])
    recent = scoring.coefficient_of_variation(series[half:])
    return scoring.metric(
        key=key, dimension=dim, value=cov.quantize(Decimal("0.001")), score=scoring.clamp_score(score),
        confidence="normal", trend=scoring.classify_trend(recent, prior, LOWER_BETTER),
        facts={"coefficient_of_variation": str(cov.quantize(Decimal("0.001"))), "months": len(active)},
    )
