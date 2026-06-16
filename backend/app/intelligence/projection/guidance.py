"""Capability #13 — Guidance Engine (pure).

Consumes a Scenario (projection), a RiskAssessment (risk), and optional
affordability results for upcoming planned expenses. Emits safe-spend numbers,
threshold_remaining, and STRUCTURED recommended actions (no prose).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from app.intelligence.projection.affordability import AffordabilityResult
from app.intelligence.projection.calendar_utils import days_in_month
from app.intelligence.projection.risk import RiskAssessment
from app.intelligence.projection.scenario import Scenario

_RESERVE_BUFFER = Decimal("0")   # no reserve-target field yet (future)
_Q = Decimal("0.01")


@dataclass(frozen=True)
class GuidanceAction:
    action: str
    data: dict


@dataclass(frozen=True)
class GuidanceResult:
    safe_daily_spending: Decimal
    safe_weekly_spending: Decimal
    threshold_remaining: Decimal | None
    recommended_actions: list[GuidanceAction]


def _expected_income_remaining(scenario: Scenario, start_exclusive, end_inclusive) -> Decimal:
    tau = scenario.guaranteed_reliability_threshold
    total = Decimal("0")
    for event in scenario.income_events:
        if start_exclusive < event.date <= end_inclusive:
            total += event.amount_base if event.reliability >= tau else event.amount_base * event.reliability
    return total


def build(
    scenario: Scenario,
    risk_assessment: RiskAssessment | None = None,
    *,
    planned_affordability: list[tuple[object, AffordabilityResult]] | None = None,
) -> GuidanceResult:
    today = scenario.today
    dim = days_in_month(today.year, today.month)
    month_end = today.replace(day=dim)
    days_remaining = dim - today.day + 1  # includes today, always >= 1
    mu = scenario.spending.mu

    income_remaining = _expected_income_remaining(scenario, today, month_end)
    committed = sum(
        (o.amount_base for o in scenario.outflows if today <= o.date <= month_end), Decimal("0")
    )
    income_based = scenario.current_balance + income_remaining - committed - _RESERVE_BUFFER
    safe_daily = income_based / days_remaining if income_based > 0 else Decimal("0")

    threshold = scenario.monthly_threshold
    threshold_remaining: Decimal | None = None
    threshold_binding = False
    if threshold is not None:
        spent_mtd = mu * today.day  # Decision 1 (B): estimate from mu
        threshold_remaining = (threshold - spent_mtd).quantize(_Q, rounding=ROUND_HALF_UP)
        threshold_daily = threshold_remaining / days_remaining if threshold_remaining > 0 else Decimal("0")
        if threshold_daily < safe_daily:
            safe_daily = threshold_daily
            threshold_binding = True

    safe_daily = max(Decimal("0"), safe_daily).quantize(_Q, rounding=ROUND_HALF_UP)
    safe_weekly = (safe_daily * 7).quantize(_Q, rounding=ROUND_HALF_UP)

    actions: list[GuidanceAction] = [
        GuidanceAction("daily_spend_limit", {"amount": str(safe_daily)}),
        GuidanceAction("weekly_spend_limit", {"amount": str(safe_weekly)}),
    ]
    if threshold_binding and threshold_remaining is not None:
        actions.append(
            GuidanceAction("threshold_binding", {"threshold_remaining": str(threshold_remaining), "daily_cap": str(safe_daily)})
        )
    if risk_assessment is not None and (
        risk_assessment.emergency_mode or risk_assessment.risk_level in ("high", "critical")
    ):
        for recovery in risk_assessment.recovery_plan:
            actions.append(GuidanceAction(recovery.action, recovery.data))
    if scenario.overdue_receivables:
        total = sum((r.amount_base for r in scenario.overdue_receivables), Decimal("0"))
        actions.append(
            GuidanceAction(
                "follow_up_receivable",
                {"count": len(scenario.overdue_receivables), "total_amount": str(total)},
            )
        )
    exceeded = [s for s in scenario.active_sessions if s.utilization_percent >= 100]
    if exceeded:
        actions.append(
            GuidanceAction(
                "session_budget_exceeded",
                {
                    "count": len(exceeded),
                    "sessions": [
                        {"session_id": str(s.session_id), "over_by": str(s.spent_base - s.budget_base)}
                        for s in exceeded
                    ],
                },
            )
        )
    slowing = [s for s in scenario.active_sessions if 75 <= s.utilization_percent < 100]
    if slowing:
        actions.append(
            GuidanceAction(
                "slow_spending",
                {
                    "count": len(slowing),
                    "sessions": [
                        {"session_id": str(s.session_id), "utilization_percent": str(s.utilization_percent)}
                        for s in slowing
                    ],
                },
            )
        )
    if planned_affordability:
        for planned_id, result in planned_affordability:
            if not result.affordable:
                actions.append(
                    GuidanceAction(
                        "review_planned_expense",
                        {"planned_id": str(planned_id), "verdict": result.verdict, "shortfall": str(result.shortfall)},
                    )
                )

    return GuidanceResult(
        safe_daily_spending=safe_daily,
        safe_weekly_spending=safe_weekly,
        threshold_remaining=threshold_remaining,
        recommended_actions=actions,
    )
