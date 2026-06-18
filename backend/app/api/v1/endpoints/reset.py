"""Reset / Clean-Slate endpoint (pre-Sprint-8): POST /reset {mode}."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import DbSession, RequireDeveloper
from app.schemas.reset import ResetIn, ResetOut
from app.services import reset_service

router = APIRouter(prefix="/reset", tags=["reset"])

_MESSAGES = {
    "soft": "Cleared your companion data. Advary is starting fresh.",
    "full": "Full reset complete. Advary is starting fresh.",
    "demo": "Loaded a demo so you can explore right away.",
}


@router.post("", response_model=ResetOut, summary="Soft / full reset or load a demo (developer-only, irreversible)")
async def reset(data: ResetIn, current_user: RequireDeveloper, db: DbSession) -> ResetOut:
    if data.mode == "soft":
        await reset_service.soft_reset(db, current_user.id)
    elif data.mode == "full":
        await reset_service.full_reset(db, current_user.id)
    else:
        await reset_service.demo_seed(db, current_user.id)
    return ResetOut(mode=data.mode, message=_MESSAGES[data.mode])
