"""Learning-loop endpoints (Sprint 4b-5a): follow-ups, answers, memory recall."""

from __future__ import annotations

import uuid

from fastapi import APIRouter

from app.api.deps import CurrentUser, DbSession
from app.schemas.learning import (
    CompanionRecap,
    FollowUpAck,
    FollowUpAnswerIn,
    FollowUpQuestion,
    LifeLessonIn,
    LifeLessonRead,
    MemoryRecall,
    PredictionAccuracy,
    ReflectionAnswerIn,
    ReflectionPrompt,
)
from app.services import (
    advice_memory_service,
    companion_recap_service,
    life_lesson_service,
    reflection_service,
)

router = APIRouter(prefix="/advisor", tags=["advisor-memory"])


@router.get("/follow-ups", response_model=list[FollowUpQuestion], summary="Due 'what happened?' check-ins")
async def follow_ups(current_user: CurrentUser, db: DbSession) -> list[FollowUpQuestion]:
    rows = await advice_memory_service.due_follow_ups(db, current_user.id)
    return [FollowUpQuestion.model_validate(r) for r in rows]


@router.post("/follow-ups/{advice_id}/answer", response_model=FollowUpAck, summary="Answer a check-in (records an Outcome)")
async def answer_follow_up(advice_id: uuid.UUID, data: FollowUpAnswerIn, current_user: CurrentUser,
                           db: DbSession) -> FollowUpAck:
    res = await advice_memory_service.answer(db, current_user.id, advice_id, answer=data.answer, detail=data.detail)
    return FollowUpAck.model_validate(res)


@router.get("/memory", response_model=MemoryRecall, summary="What did you tell me about X?")
async def memory(current_user: CurrentUser, db: DbSession, about: str | None = None) -> MemoryRecall:
    res = await advice_memory_service.recall(db, current_user.id, about=about)
    return MemoryRecall.model_validate(res)


# --- 4b-5b: lessons, reflection, accuracy, recap ----------------------------
@router.get("/lessons", response_model=list[LifeLessonRead], summary="Lessons you've taught me")
async def lessons(current_user: CurrentUser, db: DbSession, include_forgotten: bool = False) -> list[LifeLessonRead]:
    rows = await life_lesson_service.list_(db, current_user.id, include_forgotten=include_forgotten)
    return [LifeLessonRead.model_validate(r) for r in rows]


@router.post("/lessons", response_model=LifeLessonRead, summary="Teach me a lesson")
async def teach_lesson(data: LifeLessonIn, current_user: CurrentUser, db: DbSession) -> LifeLessonRead:
    row = await life_lesson_service.teach(db, current_user.id, source_text=data.text, category=data.category)
    return LifeLessonRead.model_validate({
        "id": str(row.id), "lesson": row.lesson, "category": row.category, "source": row.source,
        "occurrences": row.occurrences, "confidence": row.confidence, "status": row.status,
        "importance": row.importance, "times_surfaced": row.times_surfaced, "times_helpful": row.times_helpful,
        "first_observed": row.first_observed.isoformat(), "last_observed": row.last_observed.isoformat()})


@router.post("/lessons/{lesson_id}/forget", response_model=LifeLessonRead, summary="Forget a lesson (reversible)")
async def forget_lesson(lesson_id: uuid.UUID, current_user: CurrentUser, db: DbSession) -> LifeLessonRead:
    return LifeLessonRead.model_validate(await life_lesson_service.forget(db, current_user.id, lesson_id))


@router.post("/lessons/{lesson_id}/restore", response_model=LifeLessonRead, summary="Restore a forgotten lesson")
async def restore_lesson(lesson_id: uuid.UUID, current_user: CurrentUser, db: DbSession) -> LifeLessonRead:
    return LifeLessonRead.model_validate(await life_lesson_service.restore(db, current_user.id, lesson_id))


@router.get("/reflection", response_model=ReflectionPrompt | None, summary="A month-end reflection, if any")
async def reflection(current_user: CurrentUser, db: DbSession) -> ReflectionPrompt | None:
    res = await reflection_service.monthly_reflection(db, current_user.id)
    return ReflectionPrompt.model_validate(res) if res else None


@router.post("/reflection/answer", summary="Answer a reflection (becomes a lesson)")
async def answer_reflection(data: ReflectionAnswerIn, current_user: CurrentUser, db: DbSession) -> dict:
    return await reflection_service.record_reflection(db, current_user.id, trigger=data.trigger, answer=data.answer)


@router.get("/prediction-accuracy", response_model=PredictionAccuracy, summary="How reliable my forecasts have been")
async def prediction_accuracy(current_user: CurrentUser, db: DbSession) -> PredictionAccuracy:
    return PredictionAccuracy.model_validate(await advice_memory_service.prediction_accuracy(db, current_user.id))


@router.get("/recap", response_model=CompanionRecap, summary="What do you know about me?")
async def recap(current_user: CurrentUser, db: DbSession) -> CompanionRecap:
    return CompanionRecap.model_validate(await companion_recap_service.build(db, current_user.id))
