"""Commitment analyzers: subscription (cadence break-even), EMI, and future
commitment (surface the real annual/total number). Generic by outflow_shape."""

from __future__ import annotations

import math
from decimal import Decimal

from app.intelligence.advisor import phrasing as ph
from app.intelligence.decision.modifiers.base import AnalyzerCtx, ModifierFinding, Question, register


def _shape(ctx: AnalyzerCtx) -> str:
    return getattr(ctx.request.outflow_shape, "value", str(ctx.request.outflow_shape))


def _kind(ctx: AnalyzerCtx) -> str:
    return getattr(ctx.request.decision_kind, "value", str(ctx.request.decision_kind))


# --------------------------------------------------------------------------- #
def _subscription_required(ctx: AnalyzerCtx) -> list[Question]:
    if ctx.inputs.subscription is None:
        return [Question("subscription", "subscription",
                         "Is there a cheaper longer-term plan, and how long do you expect to use this?",
                         "subscription_terms", why="A yearly plan only saves money if you'll use it long enough.")]
    return []


def _subscription_run(ctx: AnalyzerCtx) -> ModifierFinding:
    cur = ctx.currency
    cadence = ctx.request.recurrence_months or 1
    price = ctx.amount
    sub = ctx.inputs.subscription
    alt_months = int(sub["alt_cadence"])
    alt_price = Decimal(str(sub["alt_price"]))
    usage = int(sub["expected_usage_months"])

    monthly_chosen = price / cadence
    monthly_alt = alt_price / alt_months
    cost_chosen = math.ceil(usage / cadence) * price
    cost_alt = math.ceil(usage / alt_months) * alt_price
    break_even = round(float(alt_price) / float(monthly_chosen)) if monthly_chosen > 0 else None

    alt_cheaper_for_usage = cost_alt < cost_chosen
    saving = abs(cost_chosen - cost_alt)
    if alt_cheaper_for_usage:
        rec = f"The {alt_months}-month plan saves about {ph.money(saving, cur)} over your expected {usage} months."
        alts = (f"Stay on the {cadence}-month plan for flexibility.",)
    else:
        rec = f"Your current plan is cheaper for {usage} months of use."
        alts = (f"The {alt_months}-month plan would only pay off past about {break_even} months.",) if break_even else ()
    verdict = "wins" if alt_cheaper_for_usage else "does not pay off"
    return ModifierFinding(
        analyzer="subscription",
        finding=f"{ph.money(price, cur)} every {cadence} mo vs {ph.money(alt_price, cur)} every {alt_months} mo.",
        impact=f"Annualised: {ph.money(monthly_chosen * 12, cur)} vs {ph.money(monthly_alt * 12, cur)} per year.",
        reasoning=f"Over your expected {usage} months of use, the longer plan {verdict}.",
        recommendation=rec, alternatives=alts, recovery_time_days=None,
        facts={"break_even_months": break_even, "cost_chosen": str(cost_chosen), "cost_alt": str(cost_alt),
               "expected_usage_months": usage},
    )


register("subscription",
         trigger=lambda c: _shape(c) == "recurring" or _kind(c) == "subscription",
         required_inputs=_subscription_required, run=_subscription_run)


# --------------------------------------------------------------------------- #
def _emi_required(ctx: AnalyzerCtx) -> list[Question]:
    if ctx.inputs.emi is None:
        return [Question("emi", "emi", "EMI details: down payment, installment, duration (and cash price if known)?",
                         "emi_terms", why="Shows monthly load, total payable, and the cost vs paying upfront.")]
    return []


def _emi_run(ctx: AnalyzerCtx) -> ModifierFinding:
    cur = ctx.currency
    e = ctx.inputs.emi
    down = Decimal(str(e.get("down_payment", 0)))
    installment = Decimal(str(e["installment"]))
    duration = int(e["duration_months"])
    total = down + installment * duration
    cash = Decimal(str(e["cash_price"])) if e.get("cash_price") is not None else None
    extra = (total - cash) if cash is not None else None

    if extra is not None and extra > 0:
        rec = (f"Paying in full costs {ph.money(extra, cur)} less overall, but the EMI keeps "
               f"{ph.money(cash - down, cur)} available now.")
    else:
        rec = f"This spreads the cost into {ph.money(installment, cur)}/month for {duration} months."
    return ModifierFinding(
        analyzer="emi",
        finding=f"{ph.money(installment, cur)} per month for {duration} months (total {ph.money(total, cur)}).",
        impact=f"Monthly load: {ph.money(installment, cur)}; you're committed for {duration} months.",
        reasoning=(f"Total payable is {ph.money(extra, cur)} more than the cash price." if extra and extra > 0
                   else "Total reflects the down payment plus installments."),
        recommendation=rec, alternatives=(("Pay in full if the reserve allows.",) if cash is not None else ()),
        recovery_time_days=None,
        facts={"monthly_load": str(installment), "total_payable": str(total), "months_until_free": duration,
               "extra_vs_cash": (str(extra) if extra is not None else None)},
    )


register("emi", trigger=lambda c: _shape(c) == "tenured" or _kind(c) == "emi",
         required_inputs=_emi_required, run=_emi_run)


# --------------------------------------------------------------------------- #
def _future_commitment_run(ctx: AnalyzerCtx) -> ModifierFinding:
    cur = ctx.currency
    shape = _shape(ctx)
    if shape == "tenured":
        duration = ctx.request.tenure_months or 1
        monthly = ctx.amount / duration
        annual = monthly * 12
        total_future = ctx.amount
        dur_text = f"{duration} months"
    else:  # recurring
        cadence = ctx.request.recurrence_months or 1
        monthly = ctx.amount / cadence
        annual = monthly * 12
        duration = None
        total_future = annual
        dur_text = "ongoing"
    cancel = ctx.inputs.cancel_cost
    return ModifierFinding(
        analyzer="future_commitment",
        finding=f"This is about {ph.money(annual, cur)} per year, not just {ph.money(monthly, cur)} per month.",
        impact=f"Total future cost: {ph.money(total_future, cur)} ({dur_text}).",
        reasoning="Recurring/financed costs add up well beyond the headline price.",
        recommendation=(f"Cancelling early would cost about {ph.money(cancel, cur)}." if cancel is not None
                        else "Make sure the yearly figure fits your budget."),
        recovery_time_days=None,
        facts={"monthly_commitment": str(monthly), "annual_commitment": str(annual),
               "total_future_cost": str(total_future), "commitment_duration_months": duration,
               "cancel_cost": (str(cancel) if cancel is not None else None)},
    )


register("future_commitment",
         trigger=lambda c: _shape(c) in ("recurring", "tenured") or _kind(c) in ("subscription", "emi"),
         run=_future_commitment_run)
