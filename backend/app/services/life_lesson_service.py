"""Life-lesson service (Sprint 4b-5b).

The user TEACHES the companion about their own life; the companion stores it,
grows confidence with repetition, surfaces it in relevant moments, and lets the
user forget/restore it. Never inferred by an LLM; never auto-deleted.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.intelligence.learning import lessons as L
from app.models import LifeLesson
from app.services import settings_service
from app.services.exceptions import ResourceNotFoundError


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def _today(db: AsyncSession, user_id: uuid.UUID) -> date:
    settings = await settings_service.get_settings(db, user_id)
    from zoneinfo import ZoneInfo
    return datetime.now(ZoneInfo(settings.timezone or "UTC")).date()


def _to_read(row: LifeLesson) -> dict[str, Any]:
    return {
        "id": str(row.id), "lesson": row.lesson, "category": row.category, "source": row.source,
        "occurrences": row.occurrences, "confidence": row.confidence, "status": row.status,
        "importance": row.importance, "times_surfaced": row.times_surfaced, "times_helpful": row.times_helpful,
        "first_observed": row.first_observed.isoformat(), "last_observed": row.last_observed.isoformat(),
    }


# --------------------------------------------------------------------------- #
async def teach(db: AsyncSession, user_id: uuid.UUID, *, source_text: str, category: str | None = None,
                source: str = "user_taught", canonical: str | None = None, today: date | None = None) -> LifeLesson:
    """Record a lesson. Re-teaching the same category raises confidence (req 1)."""
    today = today or await _today(db, user_id)
    cat = category or L.classify_category(source_text)
    lesson_text = canonical or L.canonical_lesson(cat, source_text)
    importance = L.importance_for(cat)

    existing = (await db.execute(
        select(LifeLesson).where(
            LifeLesson.user_id == user_id, LifeLesson.deleted_at.is_(None), LifeLesson.category == cat)
        .order_by(LifeLesson.created_at.desc()).limit(1)
    )).scalar_one_or_none()

    if existing is not None:
        existing.occurrences += 1
        existing.last_observed = today
        existing.source_text = source_text or existing.source_text
        existing.confidence = L.confidence_for(existing.occurrences)
        # Re-teaching a forgotten/archived lesson revives it.
        existing.status = L.CONFIRMED if existing.occurrences >= 2 else L.ACTIVE
        await db.commit()
        await db.refresh(existing)
        return existing

    row = LifeLesson(
        user_id=user_id, lesson=lesson_text, category=cat, source=source, source_text=source_text,
        trigger_context=cat, occurrences=1, confidence=L.confidence_for(1), status=L.ACTIVE,
        importance=importance, first_observed=today, last_observed=today,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


async def _archive_stale(db: AsyncSession, user_id: uuid.UUID, today: date) -> None:
    rows = (await db.execute(
        select(LifeLesson).where(
            LifeLesson.user_id == user_id, LifeLesson.deleted_at.is_(None),
            LifeLesson.status.in_([L.ACTIVE, L.CONFIRMED]))
    )).scalars().all()
    changed = False
    for r in rows:
        new = L.status_for(r.occurrences, r.last_observed, today, current=r.status)
        if new != r.status:
            r.status = new
            changed = True
    if changed:
        await db.commit()


async def list_(db: AsyncSession, user_id: uuid.UUID, *, include_forgotten: bool = False,
                today: date | None = None) -> list[dict[str, Any]]:
    today = today or await _today(db, user_id)
    await _archive_stale(db, user_id, today)
    rows = (await db.execute(
        select(LifeLesson).where(LifeLesson.user_id == user_id, LifeLesson.deleted_at.is_(None))
        .order_by(LifeLesson.last_observed.desc())
    )).scalars().all()
    out = [r for r in rows if include_forgotten or r.status != L.FORGOTTEN]
    return [_to_read(r) for r in out]


async def relevant(db: AsyncSession, user_id: uuid.UUID, *, context: str, today: date | None = None,
                   limit: int = 1) -> list[LifeLesson]:
    """CONFIRMED-only lessons matching the current context (req 8 + the
    'don't overlearn' rule)."""
    today = today or await _today(db, user_id)
    await _archive_stale(db, user_id, today)
    rows = (await db.execute(
        select(LifeLesson).where(
            LifeLesson.user_id == user_id, LifeLesson.deleted_at.is_(None), LifeLesson.status == L.CONFIRMED)
    )).scalars().all()
    terms = L.context_terms(context)
    hits = [r for r in rows if L.surfaceable(r.status, r.confidence)
            and L.matches_context(r.category, r.trigger_context, terms)]
    rank = {L.HIGH: 0, L.MEDIUM: 1, L.LOW: 2}
    hits.sort(key=lambda r: (rank.get(r.confidence, 3), -r.times_helpful))
    return hits[:limit]


async def mark_surfaced(db: AsyncSession, lesson: LifeLesson) -> None:
    lesson.times_surfaced += 1
    lesson.last_surfaced_at = _now()
    await db.commit()


async def mark_helpful(db: AsyncSession, user_id: uuid.UUID, lesson_id: uuid.UUID) -> dict[str, Any]:
    row = await _get(db, user_id, lesson_id)
    row.times_helpful += 1
    await db.commit()
    await db.refresh(row)
    return _to_read(row)


async def _get(db: AsyncSession, user_id: uuid.UUID, lesson_id: uuid.UUID) -> LifeLesson:
    row = (await db.execute(
        select(LifeLesson).where(
            LifeLesson.id == lesson_id, LifeLesson.user_id == user_id, LifeLesson.deleted_at.is_(None))
    )).scalar_one_or_none()
    if row is None:
        raise ResourceNotFoundError("Lesson")
    return row


async def forget(db: AsyncSession, user_id: uuid.UUID, lesson_id: uuid.UUID) -> dict[str, Any]:
    """User-controlled, REVERSIBLE forget (req 3 + reversible refinement)."""
    row = await _get(db, user_id, lesson_id)
    row.status = L.FORGOTTEN
    await db.commit()
    await db.refresh(row)
    return _to_read(row)


async def restore(db: AsyncSession, user_id: uuid.UUID, lesson_id: uuid.UUID, *,
                  today: date | None = None) -> dict[str, Any]:
    today = today or await _today(db, user_id)
    row = await _get(db, user_id, lesson_id)
    row.status = L.status_for(row.occurrences, row.last_observed, today, current=L.ACTIVE)
    await db.commit()
    await db.refresh(row)
    return _to_read(row)
