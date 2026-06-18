"""Aggregate router for API v1."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.endpoints import (
    advisor,
    advisor_chat,
    advisor_memory,
    assistant,
    auth,
    budget,
    budget_sessions,
    calendar,
    categories,
    commentary,
    companion,
    currency,
    daily_plans,
    decisions,
    dev,
    expenses,
    financial_health,
    income_sources,
    incomes,
    life_events,
    outcomes,
    persons,
    planned_expenses,
    preferences,
    reason,
    receivables,
    recommendations,
    recurring_rules,
    relationships,
    reset,
    savings_goals,
    system,
    timeline,
    users,
    voice,
)

api_router = APIRouter()
api_router.include_router(system.router)
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(dev.router)
api_router.include_router(currency.router)
api_router.include_router(categories.router)
api_router.include_router(calendar.router)
api_router.include_router(daily_plans.router)
api_router.include_router(budget.router)
api_router.include_router(persons.router)
api_router.include_router(recurring_rules.router)
api_router.include_router(reason.router)
api_router.include_router(income_sources.router)
api_router.include_router(incomes.router)
api_router.include_router(expenses.router)
api_router.include_router(planned_expenses.router)
api_router.include_router(companion.router)
api_router.include_router(receivables.router)
api_router.include_router(budget_sessions.router)
api_router.include_router(advisor.router)
api_router.include_router(advisor_chat.router)
api_router.include_router(advisor_memory.router)
api_router.include_router(decisions.router)
api_router.include_router(savings_goals.router)
api_router.include_router(recommendations.router)
api_router.include_router(preferences.router)
api_router.include_router(assistant.router)
api_router.include_router(commentary.router)
api_router.include_router(financial_health.router)
api_router.include_router(outcomes.router)
api_router.include_router(voice.router)
api_router.include_router(timeline.router)
api_router.include_router(life_events.router)
api_router.include_router(relationships.router)
api_router.include_router(reset.router)
