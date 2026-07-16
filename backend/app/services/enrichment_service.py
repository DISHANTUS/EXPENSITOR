"""The catch-up queue: park what the model couldn't do, run it when it can.

The contract, in order of importance:

1. **Enqueueing must never slow down or break a user's request.** They already
   got their real answer from the rules. This is a bonus that either lands later
   or doesn't; it is never worth an error on the user's screen.
2. **Only park what a model could actually add.** If the rules answered, there
   is nothing to catch up on. Queueing everything would mean a backlog of work
   whose results get thrown away.
3. **Only park what is still worth answering later.** A planning question is
   useless once the user has finished the flow and gone; a diary follow-up is
   still perfectly good tomorrow. So diary is queued and planning is not — see
   `KIND_DIARY_FOLLOWUP` being the only kind.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings as app_settings
from app.intelligence.companion import diary_followup
from app.models.diary_entry import DiaryEntry
from app.models.enrichment_job import (
    KIND_DIARY_FOLLOWUP,
    STATUS_DONE,
    STATUS_FAILED,
    STATUS_PENDING,
    STATUS_SKIPPED,
    EnrichmentJob,
)
from app.services import ollama_service

# A job that keeps failing is a job that will keep failing. Stop rather than
# grind the same broken payload every time the model comes up.
MAX_ATTEMPTS = 3

# How many to run in one drain. The model is single-threaded and a laptop is a
# laptop; a huge backlog drains over several passes rather than one long stall.
DRAIN_BATCH = 25


def model_available() -> bool:
    return bool(app_settings.OLLAMA_ENABLED)


async def enqueue_diary_followup(db: AsyncSession, user_id: uuid.UUID, entry_id: uuid.UUID) -> None:
    """Park a diary entry for a follow-up question the rules couldn't find.

    Caller must have already established that (a) the rules found nothing and
    (b) no model was reachable. No commit here — this rides along with the
    caller's transaction so a parked job can't outlive the thing it's about."""
    db.add(
        EnrichmentJob(
            user_id=user_id,
            kind=KIND_DIARY_FOLLOWUP,
            payload={"entry_id": str(entry_id)},
            status=STATUS_PENDING,
        )
    )


async def pending_count(db: AsyncSession) -> int:
    return int(
        await db.scalar(
            select(func.count()).select_from(EnrichmentJob).where(EnrichmentJob.status == STATUS_PENDING)
        )
        or 0
    )


async def summary(db: AsyncSession) -> dict[str, Any]:
    """Counts only. Deliberately no payloads and no user text: this feeds a
    developer screen and a developer email, and neither has any business
    carrying what someone wrote in their private diary."""
    rows = await db.execute(
        select(EnrichmentJob.status, func.count()).group_by(EnrichmentJob.status)
    )
    by_status = {status: int(count) for status, count in rows}
    oldest = await db.scalar(
        select(func.min(EnrichmentJob.created_at)).where(EnrichmentJob.status == STATUS_PENDING)
    )
    return {
        "pending": by_status.get(STATUS_PENDING, 0),
        "done": by_status.get(STATUS_DONE, 0),
        "failed": by_status.get(STATUS_FAILED, 0),
        "skipped": by_status.get(STATUS_SKIPPED, 0),
        "oldest_pending_at": oldest.isoformat() if oldest else None,
        "model_available": model_available(),
    }


async def _run_diary_followup(db: AsyncSession, job: EnrichmentJob) -> str:
    entry_id = (job.payload or {}).get("entry_id")
    if not entry_id:
        return STATUS_FAILED

    entry = await db.scalar(
        select(DiaryEntry).where(
            DiaryEntry.id == uuid.UUID(str(entry_id)),
            DiaryEntry.deleted_at.is_(None),
        )
    )
    # The entry was deleted, or the user already waved the questions off. Their
    # choice wins over a stale job — this is not a failure, there's just nothing
    # left to do.
    if entry is None or entry.closed:
        return STATUS_SKIPPED

    question = await diary_followup.next_question(
        entry.text, details=entry.details or [], generate=ollama_service.complete
    )
    if question is None:
        # The model looked and had nothing to add. That's a real outcome, not an
        # error — don't retry it forever.
        entry.closed = True
        return STATUS_SKIPPED

    entry.pending_question = question
    return STATUS_DONE


async def drain(db: AsyncSession, *, limit: int = DRAIN_BATCH) -> dict[str, Any]:
    """Work the backlog. Only call when a model is expected to be reachable.

    Each job is committed on its own: a laptop that goes to sleep halfway
    through must not throw away the questions already worked out."""
    if not model_available():
        return {"ran": False, "reason": "no model configured", "processed": 0, "done": 0,
                "skipped": 0, "failed": 0, "pending": await pending_count(db)}

    rows = await db.execute(
        select(EnrichmentJob)
        .where(EnrichmentJob.status == STATUS_PENDING, EnrichmentJob.attempts < MAX_ATTEMPTS)
        .order_by(EnrichmentJob.created_at)
        .limit(limit)
    )
    jobs = list(rows.scalars().all())

    counts = {"done": 0, "skipped": 0, "failed": 0}
    for job in jobs:
        job.attempts += 1
        try:
            if job.kind == KIND_DIARY_FOLLOWUP:
                result = await _run_diary_followup(db, job)
            else:
                job.last_error = f"unknown kind: {job.kind}"
                result = STATUS_FAILED
        except Exception as exc:  # noqa: BLE001 — one bad job must not stop the drain
            job.last_error = str(exc)[:500]
            # Out of retries? Stop. Otherwise leave it pending for the next pass.
            result = STATUS_FAILED if job.attempts >= MAX_ATTEMPTS else STATUS_PENDING

        job.status = result
        if result != STATUS_PENDING:
            job.processed_at = datetime.now(timezone.utc)
        if result in counts:
            counts[result] += 1
        await db.commit()

    return {
        "ran": True,
        "processed": len(jobs),
        **counts,
        "pending": await pending_count(db),
    }
