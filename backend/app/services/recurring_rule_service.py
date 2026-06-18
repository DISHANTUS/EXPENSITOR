"""Recurring-rule CRUD with multi-currency snapshot (mirrors expense_service)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import RecurringRule
from app.schemas.recurring_rule import RecurringRuleCreate, RecurringRuleUpdate
from app.services import category_service, currency_service, person_service, settings_service
from app.services.exceptions import ResourceNotFoundError


async def _base_currency(db: AsyncSession, user_id: uuid.UUID) -> str:
    settings = await settings_service.get_settings(db, user_id)
    return settings.base_currency


async def create(db: AsyncSession, user_id: uuid.UUID, data: RecurringRuleCreate) -> RecurringRule:
    base_currency = await _base_currency(db, user_id)
    await currency_service.get_currency(db, data.original_currency)
    await category_service.validate_category(db, user_id, data.category_id)
    await person_service.validate_person(db, user_id, data.person_id)
    rate, converted = await currency_service.convert_to_base(
        db, data.original_amount, data.original_currency, base_currency
    )
    row = RecurringRule(
        user_id=user_id,
        rule_type=data.rule_type,
        label=data.label,
        original_amount=data.original_amount,
        original_currency=data.original_currency,
        exchange_rate=rate,
        converted_amount=converted,
        base_currency=base_currency,
        recurrence_day=data.recurrence_day,
        start_date=data.start_date,
        category_id=data.category_id,
        person_id=data.person_id,
        reason=data.reason,
        importance=data.importance,
        is_active=data.is_active,
        ai_metadata=data.ai_metadata,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


async def list_(
    db: AsyncSession, user_id: uuid.UUID, *, limit: int, offset: int, active_only: bool = False
) -> tuple[list[RecurringRule], int]:
    conditions = [RecurringRule.user_id == user_id, RecurringRule.deleted_at.is_(None)]
    if active_only:
        conditions.append(RecurringRule.is_active.is_(True))
    total = await db.scalar(select(func.count()).select_from(RecurringRule).where(*conditions)) or 0
    result = await db.execute(
        select(RecurringRule).where(*conditions).order_by(RecurringRule.recurrence_day.asc()).limit(limit).offset(offset)
    )
    return list(result.scalars().all()), int(total)


async def get(db: AsyncSession, user_id: uuid.UUID, rule_id: uuid.UUID) -> RecurringRule:
    result = await db.execute(
        select(RecurringRule).where(
            RecurringRule.id == rule_id, RecurringRule.user_id == user_id, RecurringRule.deleted_at.is_(None)
        )
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise ResourceNotFoundError("RecurringRule")
    return row


async def update(
    db: AsyncSession, user_id: uuid.UUID, rule_id: uuid.UUID, data: RecurringRuleUpdate
) -> RecurringRule:
    row = await get(db, user_id, rule_id)
    updates = data.model_dump(exclude_unset=True)

    if "category_id" in updates:
        await category_service.validate_category(db, user_id, updates["category_id"])
    if "person_id" in updates:
        await person_service.validate_person(db, user_id, updates["person_id"])

    for field in ("rule_type", "label", "recurrence_day", "start_date", "category_id",
                  "person_id", "reason", "importance", "is_active", "ai_metadata"):
        if field in updates:
            setattr(row, field, updates[field])

    currency_changed = "original_currency" in updates and updates["original_currency"] is not None
    amount_changed = "original_amount" in updates and updates["original_amount"] is not None
    if currency_changed:
        await currency_service.get_currency(db, updates["original_currency"])
        row.original_currency = updates["original_currency"]
    if amount_changed:
        row.original_amount = updates["original_amount"]
    if currency_changed or amount_changed:
        rate, converted = await currency_service.convert_to_base(
            db, row.original_amount, row.original_currency, row.base_currency
        )
        row.exchange_rate = rate
        row.converted_amount = converted

    await db.commit()
    await db.refresh(row)
    return row


async def soft_delete(db: AsyncSession, user_id: uuid.UUID, rule_id: uuid.UUID) -> None:
    row = await get(db, user_id, rule_id)
    row.deleted_at = datetime.now(timezone.utc)
    await db.commit()
