"""Reflection service (Sprint 4b-5b).

Month-end / win reflections — importance-gated so the user isn't nagged. An
answer becomes a (positive) life lesson the companion can reuse later.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.intelligence.learning import reflection as R
from app.models import AdviceMemory
from app.services import analytics_service, calendar_service, life_lesson_service, settings_service


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _prompt_dict(p: R.ReflectionPrompt) -> dict[str, Any]:
    return {"trigger": p.trigger, "importance": p.importance, "question": p.question,
            "options": [{"label": lbl, "value": val} for lbl, val in p.options]}


async def _already_reflected_this_month(db: AsyncSession, user_id: uuid.UUID, today: date) -> bool:
    month_start = today.replace(day=1)
    row = (await db.execute(
        select(AdviceMemory.id).where(
            AdviceMemory.user_id == user_id, AdviceMemory.kind == "reflection",
            AdviceMemory.deleted_at.is_(None), AdviceMemory.created_at >= datetime(
                month_start.year, month_start.month, 1, tzinfo=timezone.utc))
        .limit(1)
    )).scalar_one_or_none()
    return row is not None


async def monthly_reflection(db: AsyncSession, user_id: uuid.UUID, *, today: date | None = None) -> dict[str, Any] | None:
    """A reflection prompt if this month is worth reflecting on, else None."""
    today = today or await calendar_service.user_today(db, user_id)
    if await _already_reflected_this_month(db, user_id, today):
        return None
    cmp = await analytics_service.build_comparison(db, user_id, kind="month", ref="this", today=today)
    delta = cmp.delta
    if delta is None or delta.saved_change_pct is None or delta.saved_change_pct <= 0:
        return None   # only reflect on genuine improvement (no fatigue)
    cur = (await settings_service.get_settings(db, user_id)).base_currency
    saved = cmp.summary.saved
    text = f"This month you saved {analytics_service._fmt(saved, cur)} — up {delta.saved_change_pct:.0f}% on last month."  # noqa: SLF001
    return _prompt_dict(R.improvement_prompt(text))


async def record_reflection(db: AsyncSession, user_id: uuid.UUID, *, trigger: str, answer: str,
                            today: date | None = None) -> dict[str, Any]:
    """Store the reflection (for recall) and turn a positive answer into a lesson."""
    today = today or await calendar_service.user_today(db, user_id)
    db.add(AdviceMemory(
        user_id=user_id, kind="reflection", importance=R.importance_for(trigger), status="answered",
        subject_type="reflection", subject_label=trigger, claim=f"reflection: {trigger}",
        answer=answer, answered_at=_now(),
    ))
    await db.commit()

    learned = R.lesson_from_answer(answer)
    lesson = None
    if learned is not None:
        category, canonical = learned
        row = await life_lesson_service.teach(db, user_id, source_text=canonical, category=category,
                                              source="reflection", canonical=canonical, today=today)
        lesson = {"id": str(row.id), "lesson": row.lesson, "confidence": row.confidence}
    return {"acknowledged": "Thanks for reflecting — I’ll remember what works for you.", "lesson": lesson}
