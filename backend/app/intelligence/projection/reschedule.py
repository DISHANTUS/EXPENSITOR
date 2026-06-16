"""Rescheduling analysis (pure) — score alternative dates for an event.

Each candidate carries a 0-100 score and STRUCTURED scoring factors
({type, impact}) explaining it (salary/receivable arrivals before the event,
planned expenses in the way, session overlap). Factors are returned for every
candidate so a future commentary layer can narrate them.
"""

from __future__ import annotations

import dataclasses
import uuid
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from app.intelligence.projection import risk
from app.intelligence.projection.engine import ScenarioMode, project
from app.intelligence.projection.planned_projection import OutflowEvent
from app.intelligence.projection.scenario import Scenario

DEFAULT_WINDOW_DAYS = 30
MAX_WINDOW_DAYS = 60


@dataclass(frozen=True)
class ScoringFactor:
    type: str
    impact: Decimal | int   # signed: inflows positive, costs/overlaps negative


@dataclass(frozen=True)
class CandidateDate:
    date: date
    score: int
    affordable: bool
    projected_balance: Decimal
    risk_score: int
    factors: list[ScoringFactor]


@dataclass(frozen=True)
class RescheduleResult:
    current_date: date
    window_days: int
    candidates: list[CandidateDate]
    best_date: date | None
    better_dates: list[date]
    worst_dates: list[date]


def _classify(origin: str) -> str:
    if origin.startswith("receivable"):
        return "receivable_arrival"
    if "salary" in origin:
        return "salary_arrival"
    return "income_arrival"


def _move_event(scenario: Scenario, planned_id: uuid.UUID, amount: Decimal, new_date: date) -> Scenario:
    others = tuple(o for o in scenario.outflows if o.planned_id != planned_id)
    moved = OutflowEvent(new_date, amount, "event", planned_id, False, 0)
    return dataclasses.replace(scenario, outflows=(*others, moved))


def _min_after(points, when: date) -> Decimal:
    values = [p.balance for p in points if p.date >= when]
    return min(values) if values else points[-1].balance


def _factors(scenario: Scenario, current_date: date, candidate: date, planned_id: uuid.UUID) -> list[ScoringFactor]:
    salary = receivable = income = Decimal("0")
    for event in scenario.income_events:
        if current_date < event.date <= candidate:
            kind = _classify(event.origin)
            if kind == "salary_arrival":
                salary += event.amount_base
            elif kind == "receivable_arrival":
                receivable += event.amount_base
            else:
                income += event.amount_base
    factors: list[ScoringFactor] = []
    if salary > 0:
        factors.append(ScoringFactor("salary_arrival", salary))
    if receivable > 0:
        factors.append(ScoringFactor("receivable_arrival", receivable))
    if income > 0:
        factors.append(ScoringFactor("income_arrival", income))
    planned = sum(
        (o.amount_base for o in scenario.outflows if o.planned_id != planned_id and current_date < o.date <= candidate),
        Decimal("0"),
    )
    if planned > 0:
        factors.append(ScoringFactor("planned_expense_before_event", -planned))
    if scenario.active_sessions:
        factors.append(ScoringFactor("budget_session_overlap", -len(scenario.active_sessions)))
    return factors


def _score(affordable: bool, expected_after: Decimal, amount: Decimal, risk_score: int, session_count: int) -> int:
    affordability_pts = 50 if affordable else (30 if expected_after >= 0 else 0)
    if amount > 0:
        ratio = float(expected_after) / float(amount)
    else:
        ratio = 1.0
    balance_pts = max(0, min(40, round(ratio * 40)))
    risk_pts = round((100 - risk_score) / 100 * 10)
    return max(0, min(100, affordability_pts + balance_pts + risk_pts - session_count))


def analyze(
    scenario: Scenario,
    *,
    planned_id: uuid.UUID,
    amount: Decimal,
    current_date: date,
    window_days: int = DEFAULT_WINDOW_DAYS,
) -> RescheduleResult:
    window = max(1, min(window_days, MAX_WINDOW_DAYS))
    end = min(current_date + timedelta(days=window), scenario.horizon)
    session_count = len(scenario.active_sessions)

    candidates: list[CandidateDate] = []
    day = current_date
    while day <= end:
        moved = _move_event(scenario, planned_id, amount, day)
        worst_after = _min_after(project(moved, ScenarioMode.worst), day)
        expected_after = _min_after(project(moved, ScenarioMode.expected), day)
        affordable = worst_after >= 0
        risk_score = risk.assess(moved).risk_score
        candidates.append(
            CandidateDate(
                date=day,
                score=_score(affordable, expected_after, amount, risk_score, session_count),
                affordable=affordable,
                projected_balance=expected_after,
                risk_score=risk_score,
                factors=_factors(scenario, current_date, day, planned_id),
            )
        )
        day += timedelta(days=1)

    if not candidates:
        return RescheduleResult(current_date, window, [], None, [], [])

    ranked = sorted(candidates, key=lambda c: (-c.score, c.date))
    best = ranked[0]
    better = [c.date for c in ranked[1:] if c.affordable]
    worst = [c.date for c in sorted(candidates, key=lambda c: (c.score, c.date)) if not c.affordable]
    return RescheduleResult(current_date, window, candidates, best.date, better, worst)
