"""Business logic for planned (future) expenses."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import PlannedExpense
from app.models.enums import PlannedExpensePriority, PlannedExpenseStatus
from app.schemas.planned_expense import PlannedExpenseCreate, PlannedExpenseUpdate
from app.services import category_service, currency_service, event_classifier, settings_service
from app.services.exceptions import FieldNotNullableError, ResourceNotFoundError

# Non-nullable fields that must not be set to null via PATCH.
_NON_NULLABLE_FIELDS = {
    "title",
    "planned_date",
    "original_amount",
    "original_currency",
    "priority",
    "status",
    "is_recurring",
}
_PLAIN_FIELDS = ("title", "planned_date", "priority", "status", "notes", "is_recurring", "occasion_type")


async def _base_currency(db: AsyncSession, user_id: uuid.UUID) -> str:
    settings = await settings_service.get_settings(db, user_id)
    return settings.base_currency


async def create(
    db: AsyncSession, user_id: uuid.UUID, data: PlannedExpenseCreate
) -> PlannedExpense:
    base_currency = await _base_currency(db, user_id)
    await currency_service.get_currency(db, data.original_currency)
    await category_service.validate_category(db, user_id, data.category_id)
    rate, converted = await currency_service.convert_to_base(
        db, data.original_amount, data.original_currency, base_currency
    )
    # Advary tags the event automatically from its title when the user didn't pick
    # an occasion — so the calendar gets a fitting emoji/animation, no picker needed.
    occasion = data.occasion_type or event_classifier.classify(data.title, data.notes)
    row = PlannedExpense(
        user_id=user_id,
        category_id=data.category_id,
        title=data.title,
        planned_date=data.planned_date,
        original_amount=data.original_amount,
        original_currency=data.original_currency,
        exchange_rate=rate,
        converted_amount=converted,
        base_currency=base_currency,
        priority=data.priority,
        status=PlannedExpenseStatus.planned,
        notes=data.notes,
        is_recurring=data.is_recurring,
        occasion_type=occasion,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


async def list_(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    limit: int,
    offset: int,
    status: PlannedExpenseStatus | None = None,
    priority: PlannedExpensePriority | None = None,
) -> tuple[list[PlannedExpense], int]:
    conditions = [PlannedExpense.user_id == user_id, PlannedExpense.deleted_at.is_(None)]
    if status is not None:
        conditions.append(PlannedExpense.status == status)
    if priority is not None:
        conditions.append(PlannedExpense.priority == priority)

    total = (
        await db.scalar(select(func.count()).select_from(PlannedExpense).where(*conditions)) or 0
    )
    result = await db.execute(
        select(PlannedExpense)
        .where(*conditions)
        .order_by(PlannedExpense.planned_date.asc(), PlannedExpense.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all()), int(total)


async def get(db: AsyncSession, user_id: uuid.UUID, planned_id: uuid.UUID) -> PlannedExpense:
    result = await db.execute(
        select(PlannedExpense).where(
            PlannedExpense.id == planned_id,
            PlannedExpense.user_id == user_id,
            PlannedExpense.deleted_at.is_(None),
        )
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise ResourceNotFoundError("Planned expense")
    return row


async def update(
    db: AsyncSession, user_id: uuid.UUID, planned_id: uuid.UUID, data: PlannedExpenseUpdate
) -> PlannedExpense:
    row = await get(db, user_id, planned_id)
    updates = data.model_dump(exclude_unset=True)

    for field in _PLAIN_FIELDS:
        if field in updates:
            if updates[field] is None and field in _NON_NULLABLE_FIELDS:
                raise FieldNotNullableError(field)
            setattr(row, field, updates[field])

    if "category_id" in updates:
        await category_service.validate_category(db, user_id, updates["category_id"])
        row.category_id = updates["category_id"]

    currency_changed = "original_currency" in updates
    if currency_changed:
        if updates["original_currency"] is None:
            raise FieldNotNullableError("original_currency")
        await currency_service.get_currency(db, updates["original_currency"])
        row.original_currency = updates["original_currency"]
    if "original_amount" in updates:
        if updates["original_amount"] is None:
            raise FieldNotNullableError("original_amount")
        row.original_amount = updates["original_amount"]
    if currency_changed or "original_amount" in updates:
        rate, converted = await currency_service.convert_to_base(
            db, row.original_amount, row.original_currency, row.base_currency
        )
        row.exchange_rate = rate
        row.converted_amount = converted

    await db.commit()
    await db.refresh(row)
    return row


async def soft_delete(db: AsyncSession, user_id: uuid.UUID, planned_id: uuid.UUID) -> None:
    row = await get(db, user_id, planned_id)
    row.deleted_at = datetime.now(timezone.utc)
    await db.commit()
