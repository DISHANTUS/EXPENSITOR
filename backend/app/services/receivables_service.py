"""Business logic for receivables (expected money). Server computes the FX
snapshot; `overdue` and `next_expected_date` are derived (not stored)."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.intelligence.projection.calendar_utils import add_months, clamp_day
from app.models import Receivable, UserSettings
from app.models.enums import ReceivableKind, ReceivableSourceType, ReceivableStatus
from app.schemas.receivable import ReceivableCreate, ReceivableRead, ReceivableUpdate
from app.services import companion_service, currency_service
from app.services.exceptions import InvalidOperationError, ResourceNotFoundError

_DEFAULT_RELIABILITY = {
    ReceivableSourceType.salary: Decimal("0.9"),
    ReceivableSourceType.family: Decimal("0.7"),
    ReceivableSourceType.reimbursement: Decimal("0.7"),
    ReceivableSourceType.refund: Decimal("0.7"),
    ReceivableSourceType.friend: Decimal("0.6"),
    ReceivableSourceType.freelance: Decimal("0.6"),
    ReceivableSourceType.gift: Decimal("0.4"),
    ReceivableSourceType.other: Decimal("0.5"),
}


def _today_from_settings(settings: UserSettings) -> date:
    return datetime.now(ZoneInfo(settings.timezone or "UTC")).date()


async def _settings(db: AsyncSession, user_id: uuid.UUID) -> UserSettings:
    settings = await db.scalar(select(UserSettings).where(UserSettings.user_id == user_id))
    if settings is None:
        raise ValueError("User settings not found")
    return settings


def _effective_status(r: Receivable, today: date) -> tuple[ReceivableStatus, int]:
    if (
        r.status == ReceivableStatus.pending
        and r.kind == ReceivableKind.one_time
        and r.expected_date is not None
        and r.expected_date < today
    ):
        return ReceivableStatus.overdue, (today - r.expected_date).days
    return r.status, 0


def _next_expected_date(r: Receivable, today: date) -> date | None:
    if r.kind != ReceivableKind.recurring or r.recurrence_day is None or r.status != ReceivableStatus.pending:
        return None
    occurrence = clamp_day(today.year, today.month, r.recurrence_day)
    if occurrence < today:
        following = add_months(date(today.year, today.month, 1), 1)
        occurrence = clamp_day(following.year, following.month, r.recurrence_day)
    return occurrence


def _to_read(r: Receivable, today: date) -> ReceivableRead:
    status, days_overdue = _effective_status(r, today)
    return ReceivableRead(
        id=r.id, title=r.title, source_name=r.source_name, source_type=r.source_type, kind=r.kind,
        status=status, days_overdue=days_overdue,
        original_amount=r.original_amount, original_currency=r.original_currency,
        exchange_rate=r.exchange_rate, converted_amount=r.converted_amount, base_currency=r.base_currency,
        expected_date=r.expected_date, recurrence_day=r.recurrence_day,
        next_expected_date=_next_expected_date(r, today), reliability=r.reliability, notes=r.notes,
        expected_time_window=r.expected_time_window,
        received_at=r.received_at, last_follow_up_at=r.last_follow_up_at, follow_up_count=r.follow_up_count,
        created_at=r.created_at, updated_at=r.updated_at,
    )


def _validate_kind_consistency(r: Receivable) -> None:
    if r.kind == ReceivableKind.recurring:
        if r.recurrence_day is None:
            raise InvalidOperationError("recurrence_day is required for recurring receivables")
        r.expected_date = None
    else:
        if r.expected_date is None:
            raise InvalidOperationError("expected_date is required for one-time receivables")
        r.recurrence_day = None


async def _get_row(db: AsyncSession, user_id: uuid.UUID, receivable_id: uuid.UUID) -> Receivable:
    result = await db.execute(
        select(Receivable).where(
            Receivable.id == receivable_id,
            Receivable.user_id == user_id,
            Receivable.deleted_at.is_(None),
        )
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise ResourceNotFoundError("Receivable")
    return row


async def create(db: AsyncSession, user_id: uuid.UUID, data: ReceivableCreate) -> ReceivableRead:
    settings = await _settings(db, user_id)
    today = _today_from_settings(settings)
    await currency_service.get_currency(db, data.original_currency)
    rate, converted = await currency_service.convert_to_base(
        db, data.original_amount, data.original_currency, settings.base_currency
    )
    reliability = data.reliability if data.reliability is not None else _DEFAULT_RELIABILITY[data.source_type]

    row = Receivable(
        user_id=user_id, title=data.title, source_name=data.source_name, source_type=data.source_type,
        kind=data.kind, status=ReceivableStatus.pending, original_amount=data.original_amount,
        original_currency=data.original_currency, exchange_rate=rate, converted_amount=converted,
        base_currency=settings.base_currency, expected_date=data.expected_date,
        recurrence_day=data.recurrence_day, reliability=reliability, notes=data.notes,
        expected_time_window=data.expected_time_window,
    )
    db.add(row)
    await db.flush()

    next_expected = _next_expected_date(row, today)
    db.add(companion_service.build_receivable_event(user_id, row, "created"))
    db.add(companion_service.build_receivable_created_insight(user_id, row, today=today, next_expected_date=next_expected))

    await db.commit()
    await db.refresh(row)
    return _to_read(row, today)


async def list_(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    status: ReceivableStatus | None,
    source_type: ReceivableSourceType | None,
    limit: int,
    offset: int,
) -> tuple[list[ReceivableRead], int]:
    today = _today_from_settings(await _settings(db, user_id))
    conditions = [Receivable.user_id == user_id, Receivable.deleted_at.is_(None)]
    if source_type is not None:
        conditions.append(Receivable.source_type == source_type)
    if status == ReceivableStatus.overdue:
        conditions += [
            Receivable.status == ReceivableStatus.pending,
            Receivable.kind == ReceivableKind.one_time,
            Receivable.expected_date.is_not(None),
            Receivable.expected_date < today,
        ]
    elif status is not None:
        conditions.append(Receivable.status == status)

    total = await db.scalar(select(func.count()).select_from(Receivable).where(*conditions)) or 0
    result = await db.execute(
        select(Receivable).where(*conditions).order_by(Receivable.created_at.desc()).limit(limit).offset(offset)
    )
    return [_to_read(r, today) for r in result.scalars().all()], int(total)


async def get(db: AsyncSession, user_id: uuid.UUID, receivable_id: uuid.UUID) -> ReceivableRead:
    today = _today_from_settings(await _settings(db, user_id))
    row = await _get_row(db, user_id, receivable_id)
    return _to_read(row, today)


async def update(
    db: AsyncSession, user_id: uuid.UUID, receivable_id: uuid.UUID, data: ReceivableUpdate
) -> ReceivableRead:
    settings = await _settings(db, user_id)
    today = _today_from_settings(settings)
    row = await _get_row(db, user_id, receivable_id)
    updates = data.model_dump(exclude_unset=True)

    received_now = False
    if "status" in updates:
        new_status = updates["status"]
        if new_status == ReceivableStatus.received and row.status != ReceivableStatus.received:
            row.received_at = datetime.now(timezone.utc)
            received_now = True
        elif new_status != ReceivableStatus.received and row.status == ReceivableStatus.received:
            row.received_at = None
        row.status = new_status

    for field in ("title", "source_name", "source_type", "kind", "notes", "reliability",
                  "recurrence_day", "expected_date", "expected_time_window"):
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

    _validate_kind_consistency(row)

    if received_now:
        db.add(companion_service.build_receivable_event(user_id, row, "received"))
        db.add(companion_service.build_receivable_received_insight(user_id, row))

    await db.commit()
    await db.refresh(row)
    return _to_read(row, today)


async def soft_delete(db: AsyncSession, user_id: uuid.UUID, receivable_id: uuid.UUID) -> None:
    row = await _get_row(db, user_id, receivable_id)
    row.deleted_at = datetime.now(timezone.utc)
    await db.commit()
