"""Aggregate router for API v1.

Feature routers (auth, expenses, incomes, currency, co-pilot, ...) are added in
later phases. Only system probes exist in Week 1.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.endpoints import system

api_router = APIRouter()
api_router.include_router(system.router)
