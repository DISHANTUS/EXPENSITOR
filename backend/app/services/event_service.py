"""Event Planner service: create events (planned_expenses with an occasion) and
run consequence / reschedule analysis. No HTTP endpoints yet (C4)."""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.intelligence.projection import consequence, reschedule
from app.models import PlannedExpense
from app.schemas.planned_expense import PlannedExpenseCreate
from app.services import companion_service, planned_expense_service, projection_service
from app.services.exceptions import ResourceNotFoundError

_EVENT_HORIZON_DAYS = 400  # build_scenario caps here; covers any in-range event


async def _scenario_with_event(db: AsyncSession, user_id: uuid.UUID, planned_id: uuid.UUID, today: date | None):
    scenario = await projection_service.get_scenario(db, user_id, today=today, horizon_days=_EVENT_HORIZON_DAYS)
    outflow = next((o for o in scenario.outflows if o.planned_id == planned_id), None)
    if outflow is None:
        raise ResourceNotFoundError("Event")
    return scenario, outflow


async def analyze_consequences(
    db: AsyncSession, user_id: uuid.UUID, planned_id: uuid.UUID, *, today: date | None = None
) -> consequence.ConsequenceResult:
    scenario, outflow = await _scenario_with_event(db, user_id, planned_id, today)
    return consequence.evaluate(scenario, planned_id=planned_id, amount=outflow.amount_base, event_date=outflow.date)


async def analyze_reschedule(
    db: AsyncSession, user_id: uuid.UUID, planned_id: uuid.UUID, *, window_days: int = reschedule.DEFAULT_WINDOW_DAYS, today: date | None = None
) -> reschedule.RescheduleResult:
    scenario, outflow = await _scenario_with_event(db, user_id, planned_id, today)
    return reschedule.analyze(
        scenario, planned_id=planned_id, amount=outflow.amount_base, current_date=outflow.date, window_days=window_days
    )


async def create_event(
    db: AsyncSession, user_id: uuid.UUID, data: PlannedExpenseCreate, *, today: date | None = None
) -> tuple[PlannedExpense, consequence.ConsequenceResult]:
    event = await planned_expense_service.create(db, user_id, data)
    result = await analyze_consequences(db, user_id, event.id, today=today)

    db.add(companion_service.build_event_event(user_id, event.id, "created"))
    db.add(companion_service.build_event_created_insight(user_id, event, result))
    db.add(companion_service.build_event_verdict_insight(user_id, event, result))
    if result.risk_level in ("high", "critical"):
        db.add(companion_service.build_event_warning_insight(user_id, event, result))
    suggested = next(
        (a.data.get("suggested_date") for a in result.required_adjustments if a.action == "reschedule_event"), None
    )
    if suggested:
        db.add(companion_service.build_event_reschedule_insight(user_id, event, suggested))

    await db.commit()
    return event, result
