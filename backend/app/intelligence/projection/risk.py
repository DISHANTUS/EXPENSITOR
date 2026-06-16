"""Capability #14 — Risk Engine (pure).

Emits structured signals, a risk_level, and a risk_score (0-100), plus a
structured (non-prose, non-per-category) recovery plan when severe.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from app.intelligence.projection.calendar_utils import days_in_month
from app.intelligence.projection.engine import ScenarioMode, min_balance, project
from app.intelligence.projection.scenario import Scenario

_LOW_BUFFER_DAYS = 3
_THRESHOLD_HIGH_OVER = Decimal("0.10")  # >=10% over threshold -> high

_SCORE_WEIGHTS = {
    "expected_negative": 70,
    "worst_negative": 30,
    "threshold_pace_high": 25,
    "threshold_pace_moderate": 12,
    "overdue_planned_expense": 12,
    "low_buffer": 10,
    "receivable_overdue": 12,
    "budget_session_overrun": 20,
}


@dataclass(frozen=True)
class RiskSignal:
    code: str
    severity: str          # low | moderate | high | critical
    data: dict


@dataclass(frozen=True)
class RecoveryAction:
    action: str
    data: dict


@dataclass(frozen=True)
class RiskAssessment:
    risk_level: str        # none | low | moderate | high | critical
    risk_score: int        # 0-100
    emergency_mode: bool
    signals: list[RiskSignal]
    recovery_plan: list[RecoveryAction]
    min_expected_balance: Decimal
    min_expected_balance_date: date


def _projected_month_spend(scenario: Scenario) -> Decimal:
    today = scenario.today
    dim = days_in_month(today.year, today.month)
    month_start = today.replace(day=1)
    month_end = today.replace(day=dim)
    discretionary = scenario.spending.mu * dim
    planned = sum(
        (o.amount_base for o in scenario.outflows if month_start <= o.date <= month_end),
        Decimal("0"),
    )
    return discretionary + planned


def _risk_level(signals: list[RiskSignal], emergency: bool) -> str:
    codes = {s.code: s.severity for s in signals}
    if emergency:
        return "critical"
    if (
        "worst_negative" in codes
        or "budget_session_overrun" in codes
        or codes.get("threshold_pace") == "high"
    ):
        return "high"
    if (
        "overdue_planned_expense" in codes
        or "low_buffer" in codes
        or "receivable_overdue" in codes
        or codes.get("threshold_pace") == "moderate"
    ):
        return "moderate"
    if signals:
        return "low"
    return "none"


def _recovery_plan(scenario: Scenario, dip) -> list[RecoveryAction]:
    actions: list[RecoveryAction] = []
    candidates = sorted(
        (o for o in scenario.outflows if not o.overdue and o.priority in ("low", "medium")),
        key=lambda o: o.date,
    )
    if candidates:
        actions.append(
            RecoveryAction(
                "defer_planned",
                {
                    "candidates": [
                        {
                            "planned_id": str(o.planned_id),
                            "date": o.date.isoformat(),
                            "amount": str(o.amount_base),
                            "priority": o.priority,
                        }
                        for o in candidates
                    ]
                },
            )
        )
    deficit = -dip.balance if dip.balance < 0 else Decimal("0")
    if deficit > 0:
        days = max(1, (dip.date - scenario.today).days)
        actions.append(
            RecoveryAction(
                "reduce_discretionary",
                {
                    "total": str(deficit),
                    "per_day": str((deficit / days).quantize(Decimal("0.01"))),
                    "days": days,
                },
            )
        )
    if scenario.current_balance > 0:
        actions.append(RecoveryAction("use_reserve", {"available": str(scenario.current_balance)}))
    return actions


def assess(scenario: Scenario) -> RiskAssessment:
    worst_min = min_balance(project(scenario, ScenarioMode.worst))
    expected_min = min_balance(project(scenario, ScenarioMode.expected))

    signals: list[RiskSignal] = []
    score = 0

    # --- negative-balance signals (mutually exclusive) ---
    if expected_min.balance < 0:
        signals.append(
            RiskSignal("expected_negative", "critical",
                       {"date": expected_min.date.isoformat(), "deficit": str(-expected_min.balance)})
        )
        score += _SCORE_WEIGHTS["expected_negative"]
    elif worst_min.balance < 0:
        signals.append(
            RiskSignal("worst_negative", "high",
                       {"date": worst_min.date.isoformat(), "deficit": str(-worst_min.balance)})
        )
        score += _SCORE_WEIGHTS["worst_negative"]

    # --- low buffer ---
    buffer_floor = scenario.spending.mu * _LOW_BUFFER_DAYS
    if 0 <= expected_min.balance < buffer_floor:
        signals.append(
            RiskSignal("low_buffer", "moderate",
                       {"min_balance": str(expected_min.balance), "date": expected_min.date.isoformat(),
                        "floor": str(buffer_floor)})
        )
        score += _SCORE_WEIGHTS["low_buffer"]

    # --- overdue planned expenses ---
    overdue = [o for o in scenario.outflows if o.overdue]
    if overdue:
        total = sum((o.amount_base for o in overdue), Decimal("0"))
        signals.append(
            RiskSignal("overdue_planned_expense", "moderate",
                       {"count": len(overdue), "total": str(total),
                        "max_days_overdue": max(o.days_overdue for o in overdue)})
        )
        score += _SCORE_WEIGHTS["overdue_planned_expense"]

    # --- threshold pace (proportional severity) ---
    threshold = scenario.monthly_threshold
    if threshold is not None and threshold > 0:
        projected = _projected_month_spend(scenario)
        if projected > threshold:
            over = (projected - threshold) / threshold
            severity = "high" if over >= _THRESHOLD_HIGH_OVER else "moderate"
            score += _SCORE_WEIGHTS["threshold_pace_high" if severity == "high" else "threshold_pace_moderate"]
            signals.append(
                RiskSignal("threshold_pace", severity,
                           {"projected": str(projected), "threshold": str(threshold),
                            "over": str(round(over, 4))})
            )

    # --- overdue receivables (money owed to the user that's late) ---
    if scenario.overdue_receivables:
        total = sum((r.amount_base for r in scenario.overdue_receivables), Decimal("0"))
        signals.append(
            RiskSignal(
                "receivable_overdue",
                "moderate",
                {
                    "count": len(scenario.overdue_receivables),
                    "total_amount": str(total),
                    "max_days_overdue": max(r.days_overdue for r in scenario.overdue_receivables),
                },
            )
        )
        score += _SCORE_WEIGHTS["receivable_overdue"]

    # --- budget session overrun (spent past the session budget) ---
    overruns = [s for s in scenario.active_sessions if s.utilization_percent >= 100]
    if overruns:
        total_over = sum((s.spent_base - s.budget_base for s in overruns), Decimal("0"))
        signals.append(
            RiskSignal(
                "budget_session_overrun",
                "high",
                {
                    "count": len(overruns),
                    "total_over_by": str(total_over),
                    "sessions": [
                        {"session_id": str(s.session_id), "title": s.title,
                         "budget": str(s.budget_base), "spent": str(s.spent_base)}
                        for s in overruns
                    ],
                },
            )
        )
        score += _SCORE_WEIGHTS["budget_session_overrun"]

    score = min(100, score)
    emergency = expected_min.balance < 0
    risk_level = _risk_level(signals, emergency)
    recovery = _recovery_plan(scenario, expected_min) if (emergency or risk_level == "high") else []

    return RiskAssessment(
        risk_level=risk_level,
        risk_score=score,
        emergency_mode=emergency,
        signals=signals,
        recovery_plan=recovery,
        min_expected_balance=expected_min.balance,
        min_expected_balance_date=expected_min.date,
    )
