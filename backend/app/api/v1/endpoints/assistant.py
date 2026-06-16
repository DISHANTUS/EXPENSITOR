"""Natural-Language Action Layer endpoint (Phase 2): POST /assistant/act.

Single conversational entry point. Returns a tagged union: clarification |
preview | result | advisory | alternatives | unsupported.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentUser, DbSession
from app.schemas.assistant import ActIn
from app.services import assistant_service
from app.services.exceptions import CurrencyNotFoundError, InvalidOperationError, RateNotAvailableError

router = APIRouter(prefix="/assistant", tags=["assistant"])


@router.post("/act")
async def act(data: ActIn, current_user: CurrentUser, db: DbSession) -> dict[str, Any]:
    try:
        return await assistant_service.act(
            db, current_user.id, text=data.text, confirm=data.confirm,
            answers=data.answers, request_id=data.request_id,
        )
    except (CurrencyNotFoundError, RateNotAvailableError, InvalidOperationError) as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
