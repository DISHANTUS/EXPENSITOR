"""Diary endpoints — the user's notes, Advary's follow-ups, and the patterns."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, BackgroundTasks, Query, Response, status

from app.api.deps import CurrentUser, DbSession
from app.schemas.diary import (
    DiaryAnswerIn,
    DiaryEntryCreate,
    DiaryEntryOut,
    DiaryEntryWithQuestion,
    DiaryPatternsOut,
)
from app.services import diary_service, mail_service

router = APIRouter(prefix="/diary", tags=["diary"])


@router.post(
    "",
    response_model=DiaryEntryWithQuestion,
    status_code=status.HTTP_201_CREATED,
    summary="Write a diary entry",
)
async def create_entry(
    data: DiaryEntryCreate,
    db: DbSession,
    current_user: CurrentUser,
    background_tasks: BackgroundTasks,
) -> DiaryEntryWithQuestion:
    entry, question = await diary_service.create(db, current_user.id, text=data.text, entry_date=data.entry_date)
    # After the response, never during it: if this note parked work for the
    # model, let the developer know there's a backlog (a count, once a day).
    # SMTP is slow and blocking — nobody writing a diary note should wait on it.
    background_tasks.add_task(mail_service.notify_backlog_if_due)
    return DiaryEntryWithQuestion(entry=DiaryEntryOut.model_validate(entry), question=question)


@router.get("", response_model=list[DiaryEntryOut], summary="Recent diary entries")
async def list_entries(
    db: DbSession,
    current_user: CurrentUser,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[DiaryEntryOut]:
    entries = await diary_service.list_(db, current_user.id, limit=limit, offset=offset)
    return [DiaryEntryOut.model_validate(e) for e in entries]


@router.post(
    "/{entry_id}/answer",
    response_model=DiaryEntryWithQuestion,
    summary="Answer a follow-up (returns the next one, if any)",
)
async def answer_followup(
    entry_id: uuid.UUID, data: DiaryAnswerIn, db: DbSession, current_user: CurrentUser
) -> DiaryEntryWithQuestion:
    entry, question = await diary_service.answer(
        db, current_user.id, entry_id, question=data.question, answer_text=data.answer
    )
    return DiaryEntryWithQuestion(entry=DiaryEntryOut.model_validate(entry), question=question)


@router.post("/{entry_id}/close", response_model=DiaryEntryOut, summary="Stop asking about this entry")
async def close_entry(entry_id: uuid.UUID, db: DbSession, current_user: CurrentUser) -> DiaryEntryOut:
    return DiaryEntryOut.model_validate(await diary_service.close(db, current_user.id, entry_id))


@router.delete("/{entry_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete an entry")
async def delete_entry(entry_id: uuid.UUID, db: DbSession, current_user: CurrentUser) -> Response:
    await diary_service.soft_delete(db, current_user.id, entry_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/patterns", response_model=DiaryPatternsOut, summary="What the diary adds up to")
async def get_patterns(db: DbSession, current_user: CurrentUser) -> DiaryPatternsOut:
    return DiaryPatternsOut(**await diary_service.patterns(db, current_user.id))
