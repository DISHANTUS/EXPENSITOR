"""Financial Decision Engine — strategy generators (C7a, pure, structured-only).

Each generator returns a StrategyPlan (the "what to do") or None when a HARD
constraint blocks it — so the engine never proposes an impossible action. The
engine later enriches each plan with outcome lenses (balance/risk/impact/score).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from app.intelligence.decision import funding
from app.intelligence.decision.attributes import DecisionAttributes
from app.intelligence.decision.request import DecisionRequest
from app.intelligence.decision.result import FundingPart
from app.intelligence.projection import reschedule
from app.intelligence.projection.scenario import Scenario


@dataclass(frozen=True)
class StrategyPlan:
    kind: str
    purchase_date: date
    funding: tuple[FundingPart, ...] = ()
    savings_used: Decimal = Decimal("0")
    income_events_used: tuple[dict[str, Any], ...] = ()
    expenses_to_reduce: tuple[dict[str, Any], ...] = ()
    daily_saving_required: Decimal = Decimal("0")
    saving_days: int = 0
    assumptions: tuple[str, ...] = ()
    constraints_used: tuple[str, ...] = ()


def _intended_date(request: DecisionRequest, today: date) -> date:
    if request.target_date and request.target_date >= today:
        return request.target_date
    return today


def plan_buy_now(request, attrs, scenario) -> StrategyPlan:
    when = _intended_date(request, scenario.today)
    return StrategyPlan(
        kind="buy_now", purchase_date=when,
        funding=(FundingPart("immediate_balance", request.amount_base),),
        assumptions=("Funded from your current balance.",),
    )


def plan_use_savings(request, attrs: DecisionAttributes, scenario) -> StrategyPlan | None:
    if not attrs.can_use_savings:
        return None
    avail = funding.available_now(scenario)
    if avail <= 0 or request.amount_base > avail:
        return None  # pure floor-protected savings can't cover it alone
    when = _intended_date(request, scenario.today)
    return StrategyPlan(
        kind="use_savings", purchase_date=when,
        funding=(FundingPart("savings_reserve", request.amount_base),),
        savings_used=request.amount_base,
        assumptions=(f"Uses part of your available savings; your emergency reserve stays intact.",),
        constraints_used=("emergency_reserve_preserved",),
    )


def plan_wait_for_income(request, attrs: DecisionAttributes, scenario: Scenario) -> StrategyPlan | None:
    if not attrs.can_delay:
        return None
    avail = funding.available_now(scenario)
    used: list[dict[str, Any]] = []
    for e in scenario.income_events:  # sorted, strictly future
        covered = avail + funding.counted_income_until(scenario, e.date)
        used.append({"date": e.date.isoformat(), "amount": str(e.amount_base), "origin": e.origin})
        if covered >= request.amount_base:
            return StrategyPlan(
                kind="wait_for_income", purchase_date=e.date,
                funding=(
                    FundingPart("immediate_balance", min(avail, request.amount_base)),
                    FundingPart("future_income", max(Decimal("0"), request.amount_base - avail), ref=e.date.isoformat()),
                ),
                income_events_used=tuple(used),
                assumptions=(f"Your income by {e.date.isoformat()} covers it without touching your reserve.",),
            )
    return None  # no income within the horizon covers it


def plan_reduce_discretionary(request, attrs: DecisionAttributes, scenario, *, behavior_view=None) -> StrategyPlan | None:
    if not attrs.can_reduce_spending:
        return None
    gap = request.amount_base - funding.available_now(scenario)
    if gap <= 0:
        return None  # already coverable from savings; cutting isn't needed
    today = scenario.today
    if request.target_date and request.target_date > today:
        days = (request.target_date - today).days
    else:
        days = funding.DEFAULT_SAVE_DAYS
    daily = funding.daily_save_required(gap, days)

    cuts: list[dict[str, Any]] = []
    if behavior_view:
        top = behavior_view.get("best_categories_to_cut", [])[:3]
        per_cat = str(daily / max(1, len(top)))
        cuts = [{"category": c.get("category"), "per_day": per_cat} for c in top]
    if not cuts:
        cuts = [{"category": "discretionary spending", "per_day": str(daily)}]

    return StrategyPlan(
        kind="reduce_discretionary", purchase_date=today + timedelta(days=days),
        funding=(FundingPart("daily_savings", gap),),
        expenses_to_reduce=tuple(cuts), daily_saving_required=daily, saving_days=days,
        assumptions=(f"Set aside about {daily} per day for {days} days.",),
        constraints_used=tuple(request.constraints.reducible_categories),
    )


def plan_split_into_stages(request, attrs: DecisionAttributes, scenario: Scenario) -> StrategyPlan | None:
    avail = funding.available_now(scenario)
    if request.amount_base <= avail:
        return None  # affordable in one go; no need to split
    future = [e for e in scenario.income_events]
    if not future:
        return None  # nothing to fund the later stage
    first_stage = min(avail, request.amount_base)
    second_event = future[0]
    return StrategyPlan(
        kind="split_into_stages", purchase_date=second_event.date,
        funding=(
            FundingPart("immediate_balance", first_stage),
            FundingPart("future_income", request.amount_base - first_stage, ref=second_event.date.isoformat()),
        ),
        income_events_used=({"date": second_event.date.isoformat(), "amount": str(second_event.amount_base)},),
        assumptions=("Buy in stages: part now, the rest after your next income.",),
    )


def plan_move_date(request, attrs: DecisionAttributes, scenario: Scenario) -> StrategyPlan | None:
    if not attrs.can_move_date:
        return None
    current = _intended_date(request, scenario.today)
    result = reschedule.analyze(
        scenario, planned_id=uuid.uuid4(), amount=request.amount_base,
        current_date=current, window_days=reschedule.DEFAULT_WINDOW_DAYS,
    )
    if result.best_date is None or result.best_date <= current:
        return None  # no better date than intended
    best = next((c for c in result.candidates if c.date == result.best_date), None)
    note = f"{result.best_date.isoformat()} keeps your balance healthier."
    if best is not None:
        factor = next((f for f in best.factors if f.type in ("salary_arrival", "receivable_arrival") and f.impact > 0), None)
        if factor is not None:
            note = f"{result.best_date.isoformat()} is safer because expected income arrives before then."
    return StrategyPlan(
        kind="move_date", purchase_date=result.best_date,
        funding=(FundingPart("immediate_balance", request.amount_base),),
        assumptions=(note,),
    )
