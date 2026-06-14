"""System endpoints: liveness and readiness probes."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db

router = APIRouter(tags=["system"])


@router.get("/health", summary="Liveness probe")
async def health() -> dict[str, str]:
    """Cheap liveness check — does not touch the database."""
    return {
        "status": "ok",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
    }


@router.get("/ready", summary="Readiness probe")
async def ready(db: AsyncSession = Depends(get_db)) -> JSONResponse:
    """Readiness check — verifies database connectivity."""
    try:
        await db.execute(text("SELECT 1"))
    except Exception:  # noqa: BLE001 - surface any DB failure as not-ready
        return JSONResponse(
            status_code=503,
            content={"status": "unavailable", "database": "down"},
        )
    return JSONResponse(status_code=200, content={"status": "ready", "database": "up"})
