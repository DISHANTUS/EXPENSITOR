"""Diary entries + the branching follow-ups + what they add up to.

Nothing is scheduled and nothing is precomputed: patterns are derived on read
from the entries themselves, same as the rest of the app.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.core.config import settings as app_settings
from app.intelligence.companion import diary_followup, diary_patterns
from app.models.diary_entry import DiaryEntry
from app.services import calendar_service, enrichment_service, ollama_service

# How far back the pattern view looks. Long enough for a weekday habit to show
# up several times, short enough that it describes who you are now.
PATTERN_WINDOW_DAYS = 90

_MAX_ANSWER_LEN = 500


def _generate():
    return ollama_service.complete if app_settings.OLLAMA_ENABLED else None


async def create(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    text: str,
    entry_date: date | None = None,
) -> tuple[DiaryEntry, str | None]:
    """Save the note and work out the first thing worth asking about it.
    Returns (entry, question) — question is None when there's nothing to ask,
    which is a normal outcome, not a failure."""
    entry_date = entry_date or await calendar_service.user_today(db, user_id)
    entry = DiaryEntry(user_id=user_id, entry_date=entry_date, text=text.strip(), details=[])
    db.add(entry)
    await db.commit()
    await db.refresh(entry)

    question = await diary_followup.next_question(entry.text, details=[], generate=_generate())
    await _park_if_worth_a_second_look(db, entry, question)
    return entry, question


def _exhausted(entry: DiaryEntry) -> bool:
    """We've asked as much as we're ever going to about this entry.

    Distinct from "nothing could see a question": the cap is final, and no model
    will ever get past it. Confusing the two both parks jobs that are guaranteed
    to do nothing AND leaves finished entries open forever."""
    return len(entry.details or []) >= diary_followup.MAX_QUESTIONS


async def _park_if_worth_a_second_look(db: AsyncSession, entry: DiaryEntry, question: str | None) -> None:
    """Park this entry for the model IF, and only if, a model could still add
    something: the rules found nothing, we haven't hit the question cap, AND no
    model was reachable to try.

    If the rules answered, there's nothing to catch up on. If we've asked
    enough, no model may ask more. If a model already looked and found nothing,
    asking the same model the same question tomorrow gets the same nothing.

    Never lets a queue problem reach the user — they've already got their
    answer; this is a bonus that either lands later or doesn't."""
    if question is not None or enrichment_service.model_available() or _exhausted(entry):
        return
    try:
        await enrichment_service.enqueue_diary_followup(db, entry.user_id, entry.id)
        await db.commit()
    except Exception:  # noqa: BLE001 — a failed park is a missed bonus, never an error
        await db.rollback()
        # A rollback expires every object in the session, INCLUDING the entry
        # the caller is about to serialize — which then tries to lazy-load
        # outside the async context and 500s. The user would lose their note
        # because a bonus failed, which is precisely backwards. Reload it.
        try:
            await db.refresh(entry)
        except Exception:  # noqa: BLE001 — nothing left to try; the note is already saved
            pass


async def get(db: AsyncSession, user_id: uuid.UUID, entry_id: uuid.UUID) -> DiaryEntry:
    entry = await db.scalar(
        select(DiaryEntry).where(
            DiaryEntry.id == entry_id,
            DiaryEntry.user_id == user_id,
            DiaryEntry.deleted_at.is_(None),
        )
    )
    if entry is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Diary entry not found")
    return entry


async def list_(
    db: AsyncSession, user_id: uuid.UUID, *, limit: int = 50, offset: int = 0
) -> list[DiaryEntry]:
    result = await db.execute(
        select(DiaryEntry)
        .where(DiaryEntry.user_id == user_id, DiaryEntry.deleted_at.is_(None))
        .order_by(DiaryEntry.entry_date.desc(), DiaryEntry.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all())


async def answer(
    db: AsyncSession,
    user_id: uuid.UUID,
    entry_id: uuid.UUID,
    *,
    question: str,
    answer_text: str,
) -> tuple[DiaryEntry, str | None]:
    """Record an answer to a follow-up and return the next question, if any."""
    entry = await get(db, user_id, entry_id)

    details = list(entry.details or [])
    details.append({"question": question.strip(), "answer": answer_text.strip()[:_MAX_ANSWER_LEN]})
    entry.details = details
    # JSONB reassignment isn't always seen by the ORM's change tracking when the
    # list is mutated-then-rebound; be explicit rather than lose the answer.
    flag_modified(entry, "details")
    entry.pending_question = None  # they just answered it; it isn't pending any more

    next_q = await diary_followup.next_question(entry.text, details=details, generate=_generate())
    if next_q is None and (enrichment_service.model_available() or _exhausted(entry)):
        # Either a model looked and had nothing more, or we've asked our fill.
        # Genuinely done — close it and stop pestering. The only case left open
        # is "no model was around to look", which the park below handles.
        entry.closed = True

    await db.commit()
    await db.refresh(entry)

    # Rules found nothing and no model was around to try: park it rather than
    # close the entry on a question that was never actually asked.
    await _park_if_worth_a_second_look(db, entry, next_q)
    return entry, next_q


async def close(db: AsyncSession, user_id: uuid.UUID, entry_id: uuid.UUID) -> DiaryEntry:
    """The user waving off the questions. Always available — a diary that won't
    stop asking is a diary nobody writes in twice."""
    entry = await get(db, user_id, entry_id)
    entry.closed = True
    await db.commit()
    await db.refresh(entry)
    return entry


async def soft_delete(db: AsyncSession, user_id: uuid.UUID, entry_id: uuid.UUID) -> None:
    entry = await get(db, user_id, entry_id)
    entry.deleted_at = datetime.now(timezone.utc)
    await db.commit()


async def patterns(db: AsyncSession, user_id: uuid.UUID, *, today: date | None = None) -> dict[str, Any]:
    today = today or await calendar_service.user_today(db, user_id)
    since = today - timedelta(days=PATTERN_WINDOW_DAYS)
    result = await db.execute(
        select(DiaryEntry).where(
            DiaryEntry.user_id == user_id,
            DiaryEntry.deleted_at.is_(None),
            DiaryEntry.entry_date >= since,
            DiaryEntry.entry_date <= today,
        )
    )
    entries = [
        {"entry_date": e.entry_date, "text": e.text, "details": e.details or []}
        for e in result.scalars().all()
    ]
    return diary_patterns.describe(entries)
