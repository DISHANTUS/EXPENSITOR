"""Aggregate router for API v1."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.endpoints import (
    advisor,
    auth,
    budget_sessions,
    companion,
    currency,
    decisions,
    expenses,
    income_sources,
    incomes,
    planned_expenses,
    receivables,
    savings_goals,
    system,
    users,
)

api_router = APIRouter()
api_router.include_router(system.router)
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(currency.router)
api_router.include_router(income_sources.router)
api_router.include_router(incomes.router)
api_router.include_router(expenses.router)
api_router.include_router(planned_expenses.router)
api_router.include_router(companion.router)
api_router.include_router(receivables.router)
api_router.include_router(budget_sessions.router)
api_router.include_router(advisor.router)
api_router.include_router(decisions.router)
api_router.include_router(savings_goals.router)
