"""Developer-only tools (gated by is_developer / allow-list).

Also hosts a deliberately tiny analytics pipe: clients fire lightweight events
(`POST /dev/track`, any user) recorded as CompanionEvents, and the developer
reads aggregate counts (`GET /dev/stats`). Friends-beta numbers > opinions; no
new table.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Response, status
from pydantic import BaseModel
from sqlalchemy import func, select

from app.api.deps import CurrentUser, DbSession, RequireDeveloper
from app.models import AdviceMemory, CompanionEvent
from app.models.enums import AdviceStatus, CompanionEventType
from app.services import backup_service, enrichment_service, reset_service

router = APIRouter(prefix="/dev", tags=["dev"])


class TrackIn(BaseModel):
    event: str
    props: dict[str, Any] | None = None


@router.post("/track", status_code=status.HTTP_204_NO_CONTENT,
             summary="Record a tiny client analytics event (any user)")
async def track(data: TrackIn, current_user: CurrentUser, db: DbSession) -> Response:
    db.add(CompanionEvent(
        user_id=current_user.id, event_type=CompanionEventType.system,
        surface="analytics", action=data.event[:60], payload=data.props or {}))
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/stats", summary="Aggregate beta-usage counts (developer-only)")
async def stats(current_user: RequireDeveloper, db: DbSession) -> dict[str, Any]:
    rows = (await db.execute(
        select(CompanionEvent.action, func.count())
        .where(CompanionEvent.surface == "analytics")
        .group_by(CompanionEvent.action))).all()
    events = {a: int(c) for a, c in rows}
    commitments = await db.scalar(select(func.count()).select_from(AdviceMemory).where(
        AdviceMemory.kind == "commitment", AdviceMemory.deleted_at.is_(None))) or 0
    answered = await db.scalar(select(func.count()).select_from(AdviceMemory).where(
        AdviceMemory.kind == "commitment", AdviceMemory.status == AdviceStatus.answered.value)) or 0
    shown = events.get("intervention_shown", 0)
    opened = events.get("intervention_opened", 0)
    return {
        "intervention_shown": shown,
        "intervention_opened": opened,
        "intervention_dismissed": events.get("intervention_dismissed", 0),
        "open_rate": round(opened / shown, 2) if shown else None,  # the annoyance signal
        "plan_accepted": events.get("plan_accepted", 0),
        "commitments_recorded": int(commitments),
        "follow_ups_answered": int(answered),
        "all_events": events,
    }


class CalendarPreviewOut(BaseModel):
    created: int
    message: str


class BackupOut(BaseModel):
    path: str
    total_rows: int
    tables: dict[str, int]
    message: str


@router.post("/calendar-preview", response_model=CalendarPreviewOut,
             summary="Seed this month with one of each event type to test calendar animations (developer-only)")
async def calendar_preview(current_user: RequireDeveloper, db: DbSession) -> CalendarPreviewOut:
    n = await reset_service.seed_calendar_preview(db, current_user.id)
    return CalendarPreviewOut(created=n, message=f"Added {n} sample events this month — open the calendar.")


@router.post("/backup", response_model=BackupOut,
             summary="Write a full-state snapshot to a JSON file (developer-only). Restore via the CLI.")
async def backup(current_user: RequireDeveloper, db: DbSession) -> BackupOut:
    path, counts = await backup_service.export_to_file(db)
    total = sum(counts.values())
    return BackupOut(path=str(path), total_rows=total, tables=counts,
                     message=f"Backed up {total} rows to {path.name}. Restore with: "
                             f"python -m app.scripts.backup restore --latest")


class EnrichmentSummaryOut(BaseModel):
    """Counts only. No payloads, no diary text, no user identities — this is a
    developer view of a queue, not a window into anyone's account."""

    pending: int
    done: int
    failed: int
    skipped: int
    oldest_pending_at: str | None = None
    model_available: bool


class DrainOut(BaseModel):
    ran: bool
    processed: int = 0
    done: int = 0
    skipped: int = 0
    failed: int = 0
    pending: int = 0
    reason: str | None = None


@router.get("/enrichment", response_model=EnrichmentSummaryOut,
            summary="How much work is waiting for the local model (developer-only)")
async def enrichment_summary(current_user: RequireDeveloper, db: DbSession) -> EnrichmentSummaryOut:
    return EnrichmentSummaryOut(**await enrichment_service.summary(db))


@router.post("/enrichment/drain", response_model=DrainOut,
             summary="Run the parked work now — call once your model is up (developer-only)")
async def enrichment_drain(current_user: RequireDeveloper, db: DbSession) -> DrainOut:
    # Safe to call whenever: with no model configured it reports ran=false and
    # changes nothing, rather than burning through the backlog with failures.
    return DrainOut(**await enrichment_service.drain(db))
