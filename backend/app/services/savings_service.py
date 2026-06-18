"""Savings-goal service (Tier 1): CRUD + derived state + user-driven recovery.

Goals never mutate themselves. State is computed on read against one Scenario.
Recovery is applied ONLY from an explicit user choice. Structured outputs +
advisor explanations are returned so Companion/Decision/Recommendation reuse them.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.intelligence.advisor import explainers
from app.intelligence.projection.scenario import Scenario
from app.intelligence.savings import engine as savings_engine
from app.intelligence.savings import recovery as savings_recovery
from app.models import Expense, Income, SavingsGoal
from app.models.enums import RecoveryMode, SavingsGoalKind, SavingsGoalStatus
from app.schemas.savings import RecoveryIn, SavingsGoalCreate, SavingsGoalUpdate
from app.services import behavior_service, currency_service, projection_service, settings_service
from app.services.exceptions import InvalidOperationError, ResourceNotFoundError

_PLAIN_FIELDS = ("name", "target_date", "status", "notes", "reason", "importance", "ai_metadata")


async def _base_currency(db: AsyncSession, user_id: uuid.UUID) -> str:
    settings = await settings_service.get_settings(db, user_id)
    return settings.base_currency


async def create(db: AsyncSession, user_id: uuid.UUID, data: SavingsGoalCreate, *, today: date | None = None) -> SavingsGoal:
    base_currency = await _base_currency(db, user_id)
    await currency_service.get_currency(db, data.original_currency)
    rate, converted = await currency_service.convert_to_base(
        db, data.original_amount, data.original_currency, base_currency
    )
    anchor = today or await projection_service._today_for(db, user_id)  # noqa: SLF001 (shared tz helper)
    row = SavingsGoal(
        user_id=user_id, name=data.name, kind=data.kind,
        original_amount=data.original_amount, original_currency=data.original_currency,
        exchange_rate=rate, converted_amount=converted, base_currency=base_currency,
        target_date=data.target_date, start_date=anchor.replace(day=1), status=SavingsGoalStatus.active,
        notes=data.notes, reason=data.reason, importance=data.importance, ai_metadata=data.ai_metadata,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


async def list_(db: AsyncSession, user_id: uuid.UUID, *, limit: int, offset: int,
                status: SavingsGoalStatus | None = None) -> tuple[list[SavingsGoal], int]:
    conditions = [SavingsGoal.user_id == user_id, SavingsGoal.deleted_at.is_(None)]
    if status is not None:
        conditions.append(SavingsGoal.status == status)
    total = await db.scalar(select(func.count()).select_from(SavingsGoal).where(*conditions)) or 0
    result = await db.execute(
        select(SavingsGoal).where(*conditions).order_by(SavingsGoal.created_at.desc()).limit(limit).offset(offset)
    )
    return list(result.scalars().all()), int(total)


async def get(db: AsyncSession, user_id: uuid.UUID, goal_id: uuid.UUID) -> SavingsGoal:
    result = await db.execute(
        select(SavingsGoal).where(
            SavingsGoal.id == goal_id, SavingsGoal.user_id == user_id, SavingsGoal.deleted_at.is_(None)
        )
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise ResourceNotFoundError("Savings goal")
    return row


async def update(db: AsyncSession, user_id: uuid.UUID, goal_id: uuid.UUID, data: SavingsGoalUpdate) -> SavingsGoal:
    row = await get(db, user_id, goal_id)
    updates = data.model_dump(exclude_unset=True)
    for field in _PLAIN_FIELDS:
        if field in updates:
            setattr(row, field, updates[field])
    currency_changed = "original_currency" in updates and updates["original_currency"] is not None
    if currency_changed:
        await currency_service.get_currency(db, updates["original_currency"])
        row.original_currency = updates["original_currency"]
    if updates.get("original_amount") is not None:
        row.original_amount = updates["original_amount"]
    if currency_changed or updates.get("original_amount") is not None:
        rate, converted = await currency_service.convert_to_base(
            db, row.original_amount, row.original_currency, row.base_currency
        )
        row.exchange_rate, row.converted_amount = rate, converted
    await db.commit()
    await db.refresh(row)
    return row


async def soft_delete(db: AsyncSession, user_id: uuid.UUID, goal_id: uuid.UUID) -> None:
    row = await get(db, user_id, goal_id)
    row.deleted_at = datetime.now(timezone.utc)
    await db.commit()


# --- derived state -----------------------------------------------------------
async def _net_so_far(db: AsyncSession, user_id: uuid.UUID, today: date) -> Decimal:
    month_start = today.replace(day=1)
    income = await db.scalar(
        select(func.coalesce(func.sum(Income.converted_amount), 0)).where(
            Income.user_id == user_id, Income.deleted_at.is_(None),
            Income.received_date >= month_start, Income.received_date <= today,
        )
    )
    expense = await db.scalar(
        select(func.coalesce(func.sum(Expense.converted_amount), 0)).where(
            Expense.user_id == user_id, Expense.deleted_at.is_(None),
            Expense.expense_date >= month_start, Expense.expense_date <= today,
        )
    )
    return Decimal(income or 0) - Decimal(expense or 0)


async def _behavior_view(db: AsyncSession, user_id: uuid.UUID, today: date) -> dict | None:
    profile = await behavior_service.build_profile(db, user_id, today=today)
    return profile.advisor_view() if profile.confidence == "normal" else None


def _compute_state(goal: SavingsGoal, scenario: Scenario, *, net_so_far: Decimal, behavior_view: dict | None) -> dict[str, Any]:
    currency = scenario.base_currency
    if goal.kind == SavingsGoalKind.monthly_target:
        state = savings_engine.evaluate_monthly_target(
            scenario, base_target=goal.converted_amount, net_so_far=net_so_far,
            carried_deficit=goal.carried_deficit,
            recovery_mode=goal.recovery_mode.value if goal.recovery_mode else None,
            distribute_months=goal.distribute_months,
        )
        reasons = savings_engine.savings_reasons(scenario, behavior_view=behavior_view)
        options = []
        if state.status == "behind":
            months = goal.distribute_months or savings_recovery.DEFAULT_DISTRIBUTE_MONTHS
            options = savings_recovery.recovery_options(state.shortfall, distribute_months=months)
        explanation = explainers.explain_monthly_target(state, reasons, options, currency=currency)
    else:
        state = savings_engine.evaluate_custom_goal(
            scenario, target_amount=goal.converted_amount, target_date=goal.target_date,
        )
        reasons = savings_engine.savings_reasons(scenario, window_end=goal.target_date, behavior_view=behavior_view)
        options = []
        explanation = explainers.explain_custom_goal(state, reasons, currency=currency)
    return {
        "state": state.as_dict(),
        "reasons": reasons.as_dict(),
        "recovery_options": [o.as_dict() for o in options],
        "explanation": explanation.as_dict(),
    }


async def get_state(db: AsyncSession, user_id: uuid.UUID, goal_id: uuid.UUID, *, today: date | None = None) -> dict[str, Any]:
    goal = await get(db, user_id, goal_id)
    scenario = await projection_service.get_scenario(db, user_id, today=today)
    net = await _net_so_far(db, user_id, scenario.today)
    view = await _behavior_view(db, user_id, scenario.today)
    return _compute_state(goal, scenario, net_so_far=net, behavior_view=view)


async def apply_recovery(db: AsyncSession, user_id: uuid.UUID, goal_id: uuid.UUID, data: RecoveryIn, *, today: date | None = None) -> SavingsGoal:
    goal = await get(db, user_id, goal_id)
    if goal.kind != SavingsGoalKind.monthly_target and data.choice != RecoveryMode.new_plan:
        raise InvalidOperationError("Only monthly targets support keep/distribute recovery")

    if data.choice == RecoveryMode.keep_unchanged:
        goal.recovery_mode = RecoveryMode.keep_unchanged
        goal.carried_deficit = Decimal("0")
        goal.distribute_months = None
    elif data.choice == RecoveryMode.distribute:
        scenario = await projection_service.get_scenario(db, user_id, today=today)
        net = await _net_so_far(db, user_id, scenario.today)
        state = savings_engine.evaluate_monthly_target(
            scenario, base_target=goal.converted_amount, net_so_far=net,
        )
        goal.recovery_mode = RecoveryMode.distribute
        goal.carried_deficit = state.shortfall
        goal.distribute_months = data.distribute_months or savings_recovery.DEFAULT_DISTRIBUTE_MONTHS
    else:  # new_plan: the user sets a different target/date (never automatic)
        goal.recovery_mode = RecoveryMode.new_plan
        goal.carried_deficit = Decimal("0")
        goal.distribute_months = None
        if data.new_target_amount is not None:
            currency = data.new_target_currency or goal.original_currency
            await currency_service.get_currency(db, currency)
            rate, converted = await currency_service.convert_to_base(db, data.new_target_amount, currency, goal.base_currency)
            goal.original_amount, goal.original_currency = data.new_target_amount, currency
            goal.exchange_rate, goal.converted_amount = rate, converted
        if data.new_target_date is not None:
            goal.target_date = data.new_target_date

    await db.commit()
    await db.refresh(goal)
    return goal
