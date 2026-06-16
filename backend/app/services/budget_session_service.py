"""Business logic for daily budget sessions.

A session groups ordinary expenses (via session_expenses); spend is derived
from linked expenses — no duplicate accounting. Budget carries an FX snapshot.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import BudgetSession, Category, Expense, SessionExpense, UserSettings
from app.models.enums import BudgetSessionStatus
from app.schemas.budget_session import BudgetSessionCreate, BudgetSessionUpdate, SessionRead
from app.services import companion_service, currency_service, projection_service
from app.services.exceptions import InvalidOperationError, ResourceNotFoundError

_THRESHOLDS = (50, 75, 90, 100)
_Q = Decimal("0.01")


async def _settings(db: AsyncSession, user_id: uuid.UUID) -> UserSettings:
    settings = await db.scalar(select(UserSettings).where(UserSettings.user_id == user_id))
    if settings is None:
        raise ValueError("User settings not found")
    return settings


async def _stats(db: AsyncSession, session_ids: list[uuid.UUID]) -> dict[uuid.UUID, dict]:
    acc = {sid: {"spent": Decimal("0"), "count": 0, "breakdown": {}} for sid in session_ids}
    if not session_ids:
        return acc
    stmt = (
        select(SessionExpense.session_id, Category.name, Expense.converted_amount)
        .join(Expense, and_(Expense.id == SessionExpense.expense_id, Expense.deleted_at.is_(None)))
        .outerjoin(Category, Category.id == Expense.category_id)
        .where(SessionExpense.session_id.in_(session_ids))
    )
    for session_id, category_name, amount in (await db.execute(stmt)).all():
        entry = acc[session_id]
        entry["spent"] += amount
        entry["count"] += 1
        key = category_name or "Uncategorized"
        entry["breakdown"][key] = entry["breakdown"].get(key, Decimal("0")) + amount
    return acc


def _to_read(session: BudgetSession, stat: dict) -> SessionRead:
    budget = session.converted_amount
    spent = stat["spent"]
    remaining = budget - spent
    utilization = (spent / budget * 100).quantize(_Q, rounding=ROUND_HALF_UP) if budget > 0 else Decimal("0.00")
    return SessionRead(
        id=session.id, title=session.title, original_amount=session.original_amount,
        original_currency=session.original_currency, exchange_rate=session.exchange_rate,
        converted_amount=session.converted_amount, base_currency=session.base_currency,
        started_at=session.started_at, ended_at=session.ended_at, status=session.status,
        spent=spent, remaining=remaining, saved=remaining, utilization_percent=utilization,
        expense_count=stat["count"], category_breakdown=stat["breakdown"],
        alerted_thresholds=list(session.alerted_thresholds or []),
        created_at=session.created_at, updated_at=session.updated_at,
    )


async def _get_session(db: AsyncSession, user_id: uuid.UUID, session_id: uuid.UUID) -> BudgetSession:
    result = await db.execute(
        select(BudgetSession).where(
            BudgetSession.id == session_id,
            BudgetSession.user_id == user_id,
            BudgetSession.deleted_at.is_(None),
        )
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise ResourceNotFoundError("Budget session")
    return row


async def _read_one(db: AsyncSession, session: BudgetSession) -> SessionRead:
    stats = await _stats(db, [session.id])
    return _to_read(session, stats[session.id])


async def create(db: AsyncSession, user_id: uuid.UUID, data: BudgetSessionCreate) -> SessionRead:
    settings = await _settings(db, user_id)
    await currency_service.get_currency(db, data.currency)
    rate, converted = await currency_service.convert_to_base(db, data.budget_amount, data.currency, settings.base_currency)

    session = BudgetSession(
        user_id=user_id, title=data.title, original_amount=data.budget_amount, original_currency=data.currency,
        exchange_rate=rate, converted_amount=converted, base_currency=settings.base_currency,
        status=BudgetSessionStatus.active, alerted_thresholds=[],
    )
    db.add(session)
    await db.flush()

    guidance_result, risk_assessment = await projection_service.compute_guidance_and_risk(db, user_id)
    db.add(companion_service.build_session_event(user_id, session, "started"))
    db.add(
        companion_service.build_session_started_insight(
            user_id, session,
            safe_daily=guidance_result.safe_daily_spending,
            threshold_remaining=guidance_result.threshold_remaining,
            risk_level=risk_assessment.risk_level,
        )
    )
    await db.commit()
    await db.refresh(session)
    return _to_read(session, {"spent": Decimal("0"), "count": 0, "breakdown": {}})


async def list_(
    db: AsyncSession, user_id: uuid.UUID, *, status: BudgetSessionStatus | None, limit: int, offset: int
) -> tuple[list[SessionRead], int]:
    conditions = [BudgetSession.user_id == user_id, BudgetSession.deleted_at.is_(None)]
    if status is not None:
        conditions.append(BudgetSession.status == status)
    total = await db.scalar(select(func.count()).select_from(BudgetSession).where(*conditions)) or 0
    rows = (
        await db.execute(
            select(BudgetSession).where(*conditions).order_by(BudgetSession.started_at.desc()).limit(limit).offset(offset)
        )
    ).scalars().all()
    stats = await _stats(db, [r.id for r in rows])
    return [_to_read(r, stats[r.id]) for r in rows], int(total)


async def list_active(db: AsyncSession, user_id: uuid.UUID) -> list[SessionRead]:
    rows = (
        await db.execute(
            select(BudgetSession).where(
                BudgetSession.user_id == user_id,
                BudgetSession.deleted_at.is_(None),
                BudgetSession.status == BudgetSessionStatus.active,
            ).order_by(BudgetSession.started_at.desc())
        )
    ).scalars().all()
    stats = await _stats(db, [r.id for r in rows])
    return [_to_read(r, stats[r.id]) for r in rows]


async def get(db: AsyncSession, user_id: uuid.UUID, session_id: uuid.UUID) -> SessionRead:
    return await _read_one(db, await _get_session(db, user_id, session_id))


async def update(db: AsyncSession, user_id: uuid.UUID, session_id: uuid.UUID, data: BudgetSessionUpdate) -> SessionRead:
    session = await _get_session(db, user_id, session_id)
    updates = data.model_dump(exclude_unset=True)
    if "title" in updates:
        session.title = updates["title"]
    currency_changed = updates.get("currency") is not None
    if currency_changed:
        await currency_service.get_currency(db, updates["currency"])
        session.original_currency = updates["currency"]
    if updates.get("budget_amount") is not None:
        session.original_amount = updates["budget_amount"]
    if currency_changed or updates.get("budget_amount") is not None:
        rate, converted = await currency_service.convert_to_base(
            db, session.original_amount, session.original_currency, session.base_currency
        )
        session.exchange_rate = rate
        session.converted_amount = converted
    await db.commit()
    await db.refresh(session)
    return await _read_one(db, session)


async def link_expense(db: AsyncSession, user_id: uuid.UUID, session_id: uuid.UUID, expense_id: uuid.UUID) -> SessionRead:
    session = await _get_session(db, user_id, session_id)
    if session.status != BudgetSessionStatus.active:
        raise InvalidOperationError("Session is not active")

    expense = await db.scalar(
        select(Expense).where(Expense.id == expense_id, Expense.user_id == user_id, Expense.deleted_at.is_(None))
    )
    if expense is None:
        raise ResourceNotFoundError("Expense")
    existing = await db.scalar(select(SessionExpense).where(SessionExpense.expense_id == expense_id))
    if existing is not None:
        raise InvalidOperationError("Expense is already linked to a session")

    db.add(SessionExpense(session_id=session.id, expense_id=expense_id))
    await db.flush()

    stat = (await _stats(db, [session.id]))[session.id]
    budget = session.converted_amount
    spent = stat["spent"]
    utilization = (spent / budget * 100).quantize(_Q, rounding=ROUND_HALF_UP) if budget > 0 else Decimal("0.00")

    already = list(session.alerted_thresholds or [])
    crossed = [t for t in _THRESHOLDS if utilization >= t and t not in already]
    if crossed:
        session.alerted_thresholds = sorted({*already, *crossed})
        highest = max(crossed)
        db.add(companion_service.build_session_event(user_id, session, "warning"))
        db.add(
            companion_service.build_session_warning_insight(
                user_id, session, threshold=highest, spent=spent, budget=budget,
                remaining=budget - spent, utilization=utilization,
            )
        )

    await db.commit()
    await db.refresh(session)
    return _to_read(session, stat)


async def unlink_expense(db: AsyncSession, user_id: uuid.UUID, session_id: uuid.UUID, expense_id: uuid.UUID) -> SessionRead:
    session = await _get_session(db, user_id, session_id)
    link = await db.scalar(
        select(SessionExpense).where(SessionExpense.session_id == session.id, SessionExpense.expense_id == expense_id)
    )
    if link is None:
        raise ResourceNotFoundError("Linked expense")
    await db.delete(link)
    await db.commit()
    await db.refresh(session)
    return await _read_one(db, session)


async def complete(db: AsyncSession, user_id: uuid.UUID, session_id: uuid.UUID) -> SessionRead:
    session = await _get_session(db, user_id, session_id)
    if session.status != BudgetSessionStatus.active:
        raise InvalidOperationError("Only an active session can be completed")
    session.status = BudgetSessionStatus.completed
    session.ended_at = datetime.now(timezone.utc)

    stat = (await _stats(db, [session.id]))[session.id]
    budget = session.converted_amount
    spent = stat["spent"]
    utilization = (spent / budget * 100).quantize(_Q, rounding=ROUND_HALF_UP) if budget > 0 else Decimal("0.00")
    db.add(companion_service.build_session_event(user_id, session, "completed"))
    db.add(
        companion_service.build_session_completed_insight(
            user_id, session, budget=budget, spent=spent, saved=budget - spent,
            utilization=utilization, expense_count=stat["count"],
        )
    )
    await db.commit()
    await db.refresh(session)
    return _to_read(session, stat)


async def cancel(db: AsyncSession, user_id: uuid.UUID, session_id: uuid.UUID) -> SessionRead:
    session = await _get_session(db, user_id, session_id)
    session.status = BudgetSessionStatus.cancelled
    session.ended_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(session)
    return await _read_one(db, session)


async def soft_delete(db: AsyncSession, user_id: uuid.UUID, session_id: uuid.UUID) -> None:
    session = await _get_session(db, user_id, session_id)
    session.deleted_at = datetime.now(timezone.utc)
    await db.commit()
