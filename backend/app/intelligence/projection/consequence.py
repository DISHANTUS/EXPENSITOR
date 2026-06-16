"""Consequence Analysis (pure) — what happens if this event's spend goes ahead.

Diffs the existing engines across "with event" vs "without event" (the event is
a planned_expense already in the scenario's outflows). All in-memory off one
built scenario. Required adjustments are structured ({action, data}); no prose.
"""

from __future__ import annotations

import dataclasses
import uuid
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from app.intelligence.projection import affordability, goal_feasibility, guidance, reschedule, risk
from app.intelligence.projection.engine import ScenarioMode, project
from app.intelligence.projection.scenario import Scenario

_Q = Decimal("0.01")


@dataclass(frozen=True)
class Adjustment:
    action: str
    data: dict


@dataclass(frozen=True)
class ConsequenceResult:
    affordable: bool
    risk_level: str
    projected_balance_on_date: Decimal     # before the event
    projected_balance_after: Decimal       # after the event
    projected_surplus_or_shortfall: Decimal
    safe_daily_impact: dict
    threshold_impact: dict | None
    affordability: dict
    goal_feasibility: dict
    planned_expense_impacts: list[dict]
    active_sessions: list[dict]
    required_adjustments: list[Adjustment]


def _balance_on(points, when: date) -> Decimal:
    value = points[0].balance
    for point in points:
        if point.date <= when:
            value = point.balance
        else:
            break
    return value


def evaluate(scenario: Scenario, *, planned_id: uuid.UUID, amount: Decimal, event_date: date) -> ConsequenceResult:
    without = dataclasses.replace(
        scenario, outflows=tuple(o for o in scenario.outflows if o.planned_id != planned_id)
    )

    with_expected = project(scenario, ScenarioMode.expected)
    without_expected = project(without, ScenarioMode.expected)
    balance_before = _balance_on(without_expected, event_date)
    balance_after = _balance_on(with_expected, event_date)
    surplus = min((p.balance for p in with_expected if p.date >= event_date), default=balance_after)

    aff = affordability.evaluate(without, amount, event_date)
    goal = goal_feasibility.evaluate(without, amount, event_date)

    g_with = guidance.build(scenario, risk.assess(scenario))
    g_without = guidance.build(without, risk.assess(without))
    risk_with = risk.assess(scenario)

    def _delta(a: Decimal | None, b: Decimal | None) -> str | None:
        if a is None or b is None:
            return None
        return str(a - b)

    safe_daily_impact = {
        "without": str(g_without.safe_daily_spending),
        "with": str(g_with.safe_daily_spending),
        "delta": str(g_with.safe_daily_spending - g_without.safe_daily_spending),
    }
    threshold_impact = None
    if scenario.monthly_threshold is not None:
        threshold_impact = {
            "without": str(g_without.threshold_remaining) if g_without.threshold_remaining is not None else None,
            "with": str(g_with.threshold_remaining) if g_with.threshold_remaining is not None else None,
            "delta": _delta(g_with.threshold_remaining, g_without.threshold_remaining),
        }

    # Other planned expenses that flip affordable -> not when the event is added.
    impacts: list[dict] = []
    for other in without.outflows:
        base = dataclasses.replace(without, outflows=tuple(x for x in without.outflows if x.planned_id != other.planned_id))
        with_event = dataclasses.replace(scenario, outflows=tuple(x for x in scenario.outflows if x.planned_id != other.planned_id))
        before = affordability.evaluate(base, other.amount_base, other.date).affordable
        after = affordability.evaluate(with_event, other.amount_base, other.date).affordable
        if before and not after:
            impacts.append({"planned_id": str(other.planned_id), "became_unaffordable": True})

    adjustments: list[Adjustment] = []
    if not aff.affordable:
        shortfall = aff.shortfall
        days = max(1, (event_date - scenario.today).days)
        adjustments.append(
            Adjustment("reduce_discretionary", {"total": str(shortfall), "per_day": str((shortfall / days).quantize(_Q, rounding=ROUND_HALF_UP)), "days": days})
        )
        deferrable = [o for o in without.outflows if o.priority in ("low", "medium") and o.date <= event_date]
        if deferrable:
            adjustments.append(
                Adjustment("defer_planned", {"candidates": [{"planned_id": str(o.planned_id), "date": o.date.isoformat(), "amount": str(o.amount_base)} for o in deferrable]})
            )
        resched = reschedule.analyze(without, planned_id=planned_id, amount=amount, current_date=event_date)
        if resched.best_date is not None and resched.best_date != event_date:
            adjustments.append(Adjustment("reschedule_event", {"suggested_date": resched.best_date.isoformat()}))
        reduced = amount - shortfall
        if reduced > 0:
            adjustments.append(Adjustment("reduce_event_budget", {"to_amount": str(reduced.quantize(_Q, rounding=ROUND_HALF_UP))}))

    return ConsequenceResult(
        affordable=aff.affordable,
        risk_level=risk_with.risk_level,
        projected_balance_on_date=balance_before,
        projected_balance_after=balance_after,
        projected_surplus_or_shortfall=surplus,
        safe_daily_impact=safe_daily_impact,
        threshold_impact=threshold_impact,
        affordability={
            "verdict": aff.verdict, "probability": str(aff.probability), "shortfall": str(aff.shortfall),
            "min_after_expected": str(aff.min_after["expected"]),
        },
        goal_feasibility={
            "feasible": goal.feasible, "probability": str(goal.probability), "confidence": goal.confidence,
            "required_daily_saving": str(goal.required_daily_saving),
            "required_weekly_saving": str(goal.required_weekly_saving),
            "required_monthly_saving": str(goal.required_monthly_saving),
        },
        planned_expense_impacts=impacts,
        active_sessions=[
            {"session_id": str(s.session_id), "title": s.title, "utilization_percent": str(s.utilization_percent)}
            for s in scenario.active_sessions
        ],
        required_adjustments=adjustments,
    )
