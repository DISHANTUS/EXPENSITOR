"""Business logic for payables (money the user borrowed and owes).

The server computes the FX snapshot; ``days_overdue`` is derived on read (open +
past ``due_date``). Kept entirely separate from receivables so borrowed money
never leaks into the income projection.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Payable, UserSettings
from app.models.enums import PayableStatus
from app.schemas.payable import PayableCreate, PayableRead, PayableUpdate
from app.services import currency_service, person_service
from app.services.exceptions import ResourceNotFoundError


def _today_from_settings(settings: UserSettings) -> date:
    return datetime.now(ZoneInfo(settings.timezone or "UTC")).date()


async def _settings(db: AsyncSession, user_id: uuid.UUID) -> UserSettings:
    settings = await db.scalar(select(UserSettings).where(UserSettings.user_id == user_id))
    if settings is None:
        raise ValueError("User settings not found")
    return settings


def _days_overdue(p: Payable, today: date) -> int:
    if p.status == PayableStatus.open and p.due_date is not None and p.due_date < today:
        return (today - p.due_date).days
    return 0


def _to_read(p: Payable, today: date) -> PayableRead:
    return PayableRead(
        id=p.id, source_name=p.source_name, person_id=p.person_id,
        original_amount=p.original_amount, original_currency=p.original_currency,
        exchange_rate=p.exchange_rate, converted_amount=p.converted_amount, base_currency=p.base_currency,
        return_expectation=p.return_expectation, due_date=p.due_date, reason=p.reason,
        status=p.status, days_overdue=_days_overdue(p, today), settled_at=p.settled_at,
        importance=p.importance, ai_metadata=p.ai_metadata,
        created_at=p.created_at, updated_at=p.updated_at,
    )


async def _get_row(db: AsyncSession, user_id: uuid.UUID, payable_id: uuid.UUID) -> Payable:
    row = await db.scalar(
        select(Payable).where(
            Payable.id == payable_id,
            Payable.user_id == user_id,
            Payable.deleted_at.is_(None),
        )
    )
    if row is None:
        raise ResourceNotFoundError("Payable")
    return row


async def create(db: AsyncSession, user_id: uuid.UUID, data: PayableCreate) -> PayableRead:
    settings = await _settings(db, user_id)
    today = _today_from_settings(settings)
    await currency_service.get_currency(db, data.original_currency)
    await person_service.validate_person(db, user_id, data.person_id)
    rate, converted = await currency_service.convert_to_base(
        db, data.original_amount, data.original_currency, settings.base_currency
    )
    row = Payable(
        user_id=user_id, source_name=data.source_name, person_id=data.person_id,
        original_amount=data.original_amount, original_currency=data.original_currency,
        exchange_rate=rate, converted_amount=converted, base_currency=settings.base_currency,
        return_expectation=data.return_expectation, due_date=data.due_date, reason=data.reason,
        status=PayableStatus.open, importance=data.importance, ai_metadata=data.ai_metadata,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return _to_read(row, today)


async def list_(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    status: PayableStatus | None,
    limit: int,
    offset: int,
) -> tuple[list[PayableRead], int]:
    today = _today_from_settings(await _settings(db, user_id))
    conditions = [Payable.user_id == user_id, Payable.deleted_at.is_(None)]
    if status is not None:
        conditions.append(Payable.status == status)
    total = await db.scalar(select(func.count()).select_from(Payable).where(*conditions)) or 0
    result = await db.execute(
        select(Payable).where(*conditions).order_by(Payable.created_at.desc()).limit(limit).offset(offset)
    )
    return [_to_read(p, today) for p in result.scalars().all()], int(total)


async def get(db: AsyncSession, user_id: uuid.UUID, payable_id: uuid.UUID) -> PayableRead:
    today = _today_from_settings(await _settings(db, user_id))
    return _to_read(await _get_row(db, user_id, payable_id), today)


async def update(
    db: AsyncSession, user_id: uuid.UUID, payable_id: uuid.UUID, data: PayableUpdate
) -> PayableRead:
    settings = await _settings(db, user_id)
    today = _today_from_settings(settings)
    row = await _get_row(db, user_id, payable_id)
    updates = data.model_dump(exclude_unset=True)

    if "status" in updates:
        new_status = updates["status"]
        if new_status == PayableStatus.settled and row.status != PayableStatus.settled:
            row.settled_at = datetime.now(timezone.utc)
        elif new_status != PayableStatus.settled and row.status == PayableStatus.settled:
            row.settled_at = None
        row.status = new_status

    if "person_id" in updates:
        await person_service.validate_person(db, user_id, updates["person_id"])

    for field in ("source_name", "return_expectation", "due_date", "reason", "person_id",
                  "importance", "ai_metadata"):
        if field in updates:
            setattr(row, field, updates[field])

    currency_changed = updates.get("original_currency") is not None
    if currency_changed:
        await currency_service.get_currency(db, updates["original_currency"])
        row.original_currency = updates["original_currency"]
    if updates.get("original_amount") is not None:
        row.original_amount = updates["original_amount"]
    if currency_changed or updates.get("original_amount") is not None:
        rate, converted = await currency_service.convert_to_base(
            db, row.original_amount, row.original_currency, row.base_currency
        )
        row.exchange_rate = rate
        row.converted_amount = converted

    await db.commit()
    await db.refresh(row)
    return _to_read(row, today)


async def soft_delete(db: AsyncSession, user_id: uuid.UUID, payable_id: uuid.UUID) -> None:
    row = await _get_row(db, user_id, payable_id)
    row.deleted_at = datetime.now(timezone.utc)
    await db.commit()
