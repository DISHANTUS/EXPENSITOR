"""Developer-only tools (gated by is_developer / allow-list)."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.api.deps import DbSession, RequireDeveloper
from app.services import backup_service, reset_service

router = APIRouter(prefix="/dev", tags=["dev"])


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
