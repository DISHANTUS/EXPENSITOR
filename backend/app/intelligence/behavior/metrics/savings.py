"""Savings & Resilience metrics."""

from __future__ import annotations

from decimal import Decimal

from app.intelligence.behavior import scoring
from app.intelligence.behavior.data import BehaviorData, monthly_expense_totals, monthly_income_totals
from app.intelligence.behavior.registry import HIGHER_BETTER, SAVINGS, register
from app.models.enums import ReceivableKind, ReceivableStatus

_MIN_MONTHS = 3
_MIN_RESOLVED = 3


@register(key="savings_consistency", dimension=SAVINGS, direction=HIGHER_BETTER,
          controllable=True, personality_tags=("conservative_saver", "financial_planner"))
def savings_consistency(data: BehaviorData) -> scoring.BehavioralMetric:
    key, dim = "savings_consistency", SAVINGS
    complete = data.window.complete_months
    inc = monthly_income_totals(data, complete)
    exp = monthly_expense_totals(data, complete)
    with_income = [ym for ym in complete if inc[ym] > 0]
    if len(with_income) < _MIN_MONTHS:
        return scoring.insufficient(key, dim, "no_income_data", {"months_with_income": len(with_income)})

    nets = {ym: inc[ym] - exp[ym] for ym in with_income}
    positive_rate = Decimal(sum(1 for ym in with_income if nets[ym] > 0)) / Decimal(len(with_income))
    avg_savings_rate = scoring.mean_dec([nets[ym] / inc[ym] for ym in with_income])
    rate_component = max(0.0, min(1.0, float(avg_savings_rate) / 0.20))
    score = float(positive_rate) * 70 + rate_component * 30

    last = with_income[-1]
    recent = nets[last]
    earlier = [ym for ym in with_income if ym != last]
    prior = scoring.mean_dec([nets[ym] for ym in earlier]) if earlier else None
    return scoring.metric(
        key=key, dimension=dim, value=positive_rate.quantize(Decimal("0.001")), score=scoring.clamp_score(score),
        confidence="normal", trend=scoring.classify_trend(recent, prior, HIGHER_BETTER),
        facts={"months_positive": sum(1 for ym in with_income if nets[ym] > 0),
               "months_observed": len(with_income),
               "positive_rate": str(positive_rate.quantize(Decimal("0.001"))),
               "avg_savings_rate": str(avg_savings_rate.quantize(Decimal("0.001")))},
    )


@register(key="emergency_buffer_stability", dimension=SAVINGS, direction=HIGHER_BETTER,
          forward_risk=True, personality_tags=("conservative_saver", "risk_taker"))
def emergency_buffer_stability(data: BehaviorData) -> scoring.BehavioralMetric:
    """Reconstructs month-end balances from starting_balance + monthly net flows.

    Approximate (starting_balance is the onboarding anchor), so reported as a
    stability rate with normal confidence only when an anchor and >=3 months exist.
    """
    key, dim = "emergency_buffer_stability", SAVINGS
    complete = data.window.complete_months
    if data.starting_balance <= 0 or len(complete) < _MIN_MONTHS:
        return scoring.insufficient(key, dim, "insufficient_data",
                                    {"complete_months": len(complete), "starting_balance": str(data.starting_balance)})

    inc = monthly_income_totals(data, complete)
    exp = monthly_expense_totals(data, complete)
    active = [ym for ym in complete if exp[ym] > 0]  # need spend history to define a floor
    if len(active) < _MIN_MONTHS:
        return scoring.insufficient(key, dim, "insufficient_data", {"active_months": len(active)})
    floor = scoring.mean_dec([exp[ym] for ym in active])  # ~one month of spending

    balance = data.starting_balance
    end_balances: list[Decimal] = []
    for ym in complete:
        balance = balance + (inc[ym] - exp[ym])
        end_balances.append(balance)

    below = sum(1 for b in end_balances if b < floor)
    min_bal = min([data.starting_balance, *end_balances])
    stability_rate = Decimal(1) - Decimal(below) / Decimal(len(end_balances))
    score = float(stability_rate) * 100
    if min_bal < 0:
        score = min(score, 20.0)
    return scoring.metric(
        key=key, dimension=dim, value=stability_rate.quantize(Decimal("0.001")), score=scoring.clamp_score(score),
        confidence="normal", trend="unknown",
        facts={"stability_rate": str(stability_rate.quantize(Decimal("0.001"))),
               "months_below_floor": below, "floor": str(floor.quantize(Decimal("0.01"))),
               "min_reconstructed_balance": str(min_bal.quantize(Decimal("0.01"))), "approximate": True},
    )


@register(key="receivable_recovery_rate", dimension=SAVINGS, direction=HIGHER_BETTER,
          controllable=True, personality_tags=("financial_planner",))
def receivable_recovery_rate(data: BehaviorData) -> scoring.BehavioralMetric:
    key, dim = "receivable_recovery_rate", SAVINGS
    today = data.window.today
    received, resolved, days = 0, 0, []
    for r in data.receivables:
        is_overdue = (
            r.status == ReceivableStatus.pending.value
            and r.kind == ReceivableKind.one_time.value
            and r.expected_date is not None
            and r.expected_date < today
        )
        if r.status == ReceivableStatus.received.value:
            received += 1
            resolved += 1
            if r.received_at:
                days.append((r.received_at - r.created_on).days)
        elif r.status == ReceivableStatus.cancelled.value or is_overdue:
            resolved += 1

    if resolved < _MIN_RESOLVED:
        return scoring.insufficient(key, dim, "insufficient_data", {"resolved": resolved})

    rate = Decimal(received) / Decimal(resolved)
    avg_days = scoring.mean_dec([Decimal(d) for d in days]) if days else None
    return scoring.metric(
        key=key, dimension=dim, value=rate.quantize(Decimal("0.001")),
        score=scoring.clamp_score(float(rate) * 100), confidence="normal", trend="unknown",
        facts={"received": received, "resolved": resolved,
               "recovery_rate": str(rate.quantize(Decimal("0.001"))),
               "avg_days_to_receive": (str(avg_days.quantize(Decimal("0.1"))) if avg_days is not None else None)},
    )
