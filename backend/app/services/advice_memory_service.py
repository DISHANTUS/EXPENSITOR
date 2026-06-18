"""Advice-memory service (Sprint 4b-5a) — the core learning loop.

    record_advice  -> the companion remembers what it told you
    due_follow_ups -> importance-gated "what happened?" questions
    answer         -> records a Phase-E Outcome (the evidence) + closes the loop
    recall         -> "what did you tell me about X?"

Deterministic, no LLM. Outcomes/advice influence ordering/annotations/confidence
ONLY — never financial facts. Honesty: no follow-up exists without recorded
advice; nothing is fabricated.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.intelligence.learning import accuracy as acc
from app.intelligence.learning import importance as imp
from app.intelligence.outcomes.types import classify_circumstance
from app.models import AdviceMemory, Outcome
from app.models.enums import AdviceStatus
from app.schemas.outcome import OutcomeReportIn
from app.services import life_lesson_service, outcome_service, projection_service, settings_service

_DEDUP_WINDOW_DAYS = 30
_ANSWER_TO_OUTCOME = {"yes": "success", "partial": "partial", "no": "failed"}
# advice kind -> (Outcome kind, default subject_type)
_KIND_TO_OUTCOME = {
    "forecast": ("goal", "savings_goal"),
    "recommendation": ("recommendation", "recommendation_lever"),
    "relationship": ("decision", "relationship"),
    "budget": ("plan", "budget"),
}

_FOLLOWUP_TEMPLATES = {
    "forecast": "Last time we talked about reaching {subject}. How is it going?",
    "recommendation": "A while back I suggested {claim}. Did you manage it?",
    "relationship": "Last time we talked about {subject}'s repayment. What happened?",
    "budget": "How did your budget for {subject} go?",
}
_OPTIONS = [("Yes", "yes"), ("Partially", "partial"), ("No", "no")]


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def _today(db: AsyncSession, user_id: uuid.UUID) -> date:
    settings = await settings_service.get_settings(db, user_id)
    from zoneinfo import ZoneInfo
    return datetime.now(ZoneInfo(settings.timezone or "UTC")).date()


# --------------------------------------------------------------------------- #
async def record_advice(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    kind: str,
    subject_type: str,
    claim: str,
    subject_label: str | None = None,
    subject_id: uuid.UUID | None = None,
    lever_key: str | None = None,
    category_id: uuid.UUID | None = None,
    expected_value: Decimal | None = None,
    expected_date: date | None = None,
    assumptions: dict | None = None,
    base_currency: str | None = None,
    today: date | None = None,
) -> AdviceMemory:
    """Remember a piece of advice. Importance-gated follow-up; deduped so the
    companion doesn't re-promise the same thing every turn."""
    today = today or await _today(db, user_id)

    # Dedup: an open row about the same subject within the window -> reuse it.
    label_cond = (AdviceMemory.subject_label.is_(None) if subject_label is None
                  else AdviceMemory.subject_label == subject_label)
    existing = (await db.execute(
        select(AdviceMemory).where(
            AdviceMemory.user_id == user_id, AdviceMemory.deleted_at.is_(None),
            AdviceMemory.kind == kind, AdviceMemory.subject_type == subject_type,
            AdviceMemory.status == AdviceStatus.pending.value,
            AdviceMemory.created_at >= _now() - timedelta(days=_DEDUP_WINDOW_DAYS),
            label_cond,
        ).order_by(AdviceMemory.created_at.desc()).limit(1)
    )).scalar_one_or_none()
    if existing is not None:
        existing.claim = claim
        if expected_date is not None:
            existing.expected_date = expected_date
        if expected_value is not None:
            existing.expected_value = expected_value
        if assumptions is not None:
            existing.assumptions = assumptions
        await db.commit()
        await db.refresh(existing)
        return existing

    importance = imp.importance_for(kind, subject_type)
    row = AdviceMemory(
        user_id=user_id, kind=kind, importance=importance, status=AdviceStatus.pending.value,
        subject_type=subject_type, subject_id=subject_id, subject_label=subject_label,
        lever_key=lever_key, category_id=category_id, claim=claim,
        expected_value=expected_value, expected_date=expected_date, assumptions=assumptions,
        follow_up_due=imp.first_due(today, importance), base_currency=base_currency,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


# --------------------------------------------------------------------------- #
def _question(row: AdviceMemory) -> str:
    subject = row.subject_label or "it"
    template = _FOLLOWUP_TEMPLATES.get(row.kind, "Last time we talked about {subject}. What happened?")
    return template.format(subject=subject, claim=row.claim)


def _to_question_dict(row: AdviceMemory) -> dict[str, Any]:
    return {
        "id": str(row.id), "kind": row.kind, "importance": row.importance,
        "subject_label": row.subject_label, "claim": row.claim,
        "question": _question(row),
        "options": [{"label": lbl, "value": val} for lbl, val in _OPTIONS],
    }


async def due_follow_ups(db: AsyncSession, user_id: uuid.UUID, *, today: date | None = None,
                         limit: int = 5) -> list[dict[str, Any]]:
    today = today or await _today(db, user_id)
    rows = (await db.execute(
        select(AdviceMemory).where(
            AdviceMemory.user_id == user_id, AdviceMemory.deleted_at.is_(None),
            AdviceMemory.status == AdviceStatus.pending.value,
            AdviceMemory.follow_up_due.is_not(None), AdviceMemory.follow_up_due <= today,
        )
    )).scalars().all()

    # Lazily expire stale items (window passed without an answer).
    live: list[AdviceMemory] = []
    changed = False
    for row in rows:
        if (today - row.follow_up_due).days > imp.EXPIRE_AFTER_DAYS:
            row.status = AdviceStatus.expired.value
            changed = True
        else:
            live.append(row)
    if changed:
        await db.commit()

    rank = {imp.HIGH: 0, imp.MEDIUM: 1, imp.LOW: 2}
    live.sort(key=lambda r: (rank.get(r.importance, 3), r.follow_up_due))
    return [_to_question_dict(r) for r in live[:limit]]


# --------------------------------------------------------------------------- #
async def answer(db: AsyncSession, user_id: uuid.UUID, advice_id: uuid.UUID, *,
                 answer: str, detail: str | None = None, today: date | None = None) -> dict[str, Any]:
    today = today or await _today(db, user_id)
    row = (await db.execute(
        select(AdviceMemory).where(
            AdviceMemory.id == advice_id, AdviceMemory.user_id == user_id, AdviceMemory.deleted_at.is_(None))
    )).scalar_one_or_none()
    if row is None:
        from app.services.exceptions import ResourceNotFoundError
        raise ResourceNotFoundError("Advice")

    ans = answer.lower().strip()
    outcome_status = _ANSWER_TO_OUTCOME.get(ans, "unknown")
    circumstance = classify_circumstance(detail)
    out_kind, out_subject = _KIND_TO_OUTCOME.get(row.kind, ("decision", row.subject_type))

    # Record the Phase-E Outcome (the evidence). Circumstance failures (E7) are
    # preserved by outcome_service.record via classify_circumstance(outcome_reason).
    outcome = await outcome_service.record(
        db, user_id,
        OutcomeReportIn(
            kind=out_kind, subject_type=out_subject, subject_id=row.subject_id,
            lever_key=row.lever_key, category_id=row.category_id,
            outcome=outcome_status, outcome_reason=detail,
            expected_value=row.expected_value,
        ),
        today=today,
    )

    row.answer = ans
    row.answer_detail = detail
    row.circumstance = circumstance
    row.outcome_id = outcome.id
    row.status = AdviceStatus.answered.value
    row.answered_at = _now()
    row.follow_up_count = row.follow_up_count + 1
    await db.commit()
    await db.refresh(row)

    # A circumstance answer ("laptop broke") teaches a real, confidence-weighted
    # life lesson (4b-5b) — repeated circumstances grow toward CONFIRMED.
    lesson = None
    if circumstance and detail:
        row_l = await life_lesson_service.teach(db, user_id, source_text=detail, source="derived", today=today)
        lesson = {"id": str(row_l.id), "lesson": row_l.lesson, "confidence": row_l.confidence,
                  "occurrences": row_l.occurrences}

    ack = _acknowledge(row, ans, circumstance)
    return {"acknowledged": ack, "outcome_id": str(outcome.id), "circumstance": circumstance,
            "advice_id": str(row.id), "lesson_suggestion": lesson["lesson"] if lesson else None, "lesson": lesson}


def _acknowledge(row: AdviceMemory, ans: str, circumstance: str | None) -> str:
    subject = row.subject_label or "that"
    if circumstance:
        return (f"Thanks for telling me — that sounds like a one-off ({circumstance.replace('_', ' ')}), "
                f"so I won’t count it against the plan.")
    if ans == "yes":
        return f"Great — I’ll remember that worked for {subject}."
    if ans == "partial":
        return f"Got it — partial progress on {subject}. I’ll keep that in mind."
    return f"Understood — it didn’t happen this time. No judgement; I’ll factor it in."


# --------------------------------------------------------------------------- #
async def prediction_accuracy(db: AsyncSession, user_id: uuid.UUID, *, today: date | None = None) -> dict[str, Any]:
    """How reliable have my forecasts been? Compares each stored forecast snapshot
    to actual progress, banded and broken down by forecast type (4b-5b req 7)."""
    today = today or await _today(db, user_id)
    rows = (await db.execute(
        select(AdviceMemory).where(
            AdviceMemory.user_id == user_id, AdviceMemory.deleted_at.is_(None),
            AdviceMemory.kind == "forecast")
    )).scalars().all()
    if not rows:
        return acc.summarize([]).as_dict()

    actual_progress = float((await projection_service.get_scenario(db, user_id, today=today)).current_balance)
    items = []
    for r in rows:
        a = r.assumptions or {}
        ftype = a.get("forecast_type", acc.GOAL_ETA)
        try:
            net = float(a.get("monthly_net", 0))
            p0 = float(a.get("progress", 0))
        except (TypeError, ValueError):
            net, p0 = 0.0, 0.0
        elapsed_months = max(0.0, (today - r.created_at.date()).days / 30.0)
        expected = p0 + net * elapsed_months
        band = acc.band(expected, actual_progress, elapsed_months=elapsed_months)
        items.append({"band": band, "forecast_type": ftype})
    return acc.summarize(items).as_dict()


# --------------------------------------------------------------------------- #
async def recall(db: AsyncSession, user_id: uuid.UUID, *, about: str | None = None,
                 today: date | None = None) -> dict[str, Any]:
    """"What did you tell me about X?" — past advice + how it turned out."""
    conditions = [AdviceMemory.user_id == user_id, AdviceMemory.deleted_at.is_(None)]
    if about:
        term = f"%{about.strip()}%"
        conditions.append(or_(AdviceMemory.subject_label.ilike(term), AdviceMemory.claim.ilike(term),
                              AdviceMemory.lever_key.ilike(term)))
    rows = (await db.execute(
        select(AdviceMemory).where(*conditions).order_by(AdviceMemory.created_at.desc()).limit(10)
    )).scalars().all()

    items = [{
        "id": str(r.id), "kind": r.kind, "subject_label": r.subject_label, "claim": r.claim,
        "status": r.status, "answer": r.answer, "answer_detail": r.answer_detail,
        "circumstance": r.circumstance,
        "when": r.created_at.date().isoformat() if r.created_at else None,
    } for r in rows]
    return {"about": about, "items": items}
