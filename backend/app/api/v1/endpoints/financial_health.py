"""Financial Health Score endpoint (C8): GET /financial-health (compute-on-read).

Multi-dimensional, fact-backed. The score never appears without its contributors.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from app.api.deps import CurrentUser, DbSession
from app.services import health_service

router = APIRouter(prefix="/financial-health", tags=["financial-health"])


@router.get("")
async def get_financial_health(current_user: CurrentUser, db: DbSession) -> dict[str, Any]:
    """The decomposed Financial Health Score: overall + six explainable pillars."""
    return await health_service.build(db, current_user.id)
