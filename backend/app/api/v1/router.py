"""Aggregate router for API v1."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.endpoints import (
    advisor,
    assistant,
    auth,
    budget_sessions,
    categories,
    commentary,
    companion,
    currency,
    decisions,
    expenses,
    financial_health,
    income_sources,
    incomes,
    outcomes,
    planned_expenses,
    preferences,
    receivables,
    recommendations,
    savings_goals,
    system,
    users,
)

api_router = APIRouter()
api_router.include_router(system.router)
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(currency.router)
api_router.include_router(categories.router)
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
api_router.include_router(recommendations.router)
api_router.include_router(preferences.router)
api_router.include_router(assistant.router)
api_router.include_router(commentary.router)
api_router.include_router(financial_health.router)
api_router.include_router(outcomes.router)
