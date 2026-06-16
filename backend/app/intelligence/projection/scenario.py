"""Capability #2 (assembly) — build an immutable Scenario in one bounded pass.

Performance contract: built once per request; ~6 queries; horizon capped.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.intelligence.projection.balance import BalanceBreakdown, compute_balance
from app.intelligence.projection.income_projection import IncomeEvent, expand_income_events
from app.intelligence.projection.planned_projection import OutflowEvent, expand_outflows
from app.intelligence.projection.budget_session_state import ActiveSession, load_active_sessions
from app.intelligence.projection.receivable_income import OverdueReceivable, expand_receivable_events
from app.intelligence.projection.spending_model import SpendingModel, compute_spending_model
from app.models import UserSettings

MAX_HORIZON_DAYS = 400
GUARANTEED_RELIABILITY_THRESHOLD = Decimal("0.85")


@dataclass(frozen=True)
class Scenario:
    today: date
    horizon: date
    base_currency: str
    current_balance: Decimal
    spending: SpendingModel
    income_events: tuple[IncomeEvent, ...]
    outflows: tuple[OutflowEvent, ...]
    monthly_threshold: Decimal | None = None
    balance: BalanceBreakdown | None = None
    overdue_receivables: tuple[OverdueReceivable, ...] = ()
    active_sessions: tuple[ActiveSession, ...] = ()
    guaranteed_reliability_threshold: Decimal = GUARANTEED_RELIABILITY_THRESHOLD


async def build_scenario(
    db: AsyncSession, user_id: uuid.UUID, *, today: date, horizon: date
) -> Scenario:
    # Clamp horizon to [today, today + MAX_HORIZON_DAYS].
    horizon = max(today, min(horizon, today + timedelta(days=MAX_HORIZON_DAYS)))

    settings = await db.scalar(select(UserSettings).where(UserSettings.user_id == user_id))
    if settings is None:
        raise ValueError("User settings not found")

    balance = await compute_balance(db, user_id, today, settings)
    spending = await compute_spending_model(
        db,
        user_id,
        today,
        monthly_threshold=settings.monthly_threshold,
        monthly_income_estimate=settings.monthly_income_estimate,
    )
    income_events = await expand_income_events(db, user_id, today, horizon)
    receivable_events, overdue_receivables = await expand_receivable_events(db, user_id, today, horizon)
    merged_income = sorted([*income_events, *receivable_events], key=lambda event: event.date)
    outflows = await expand_outflows(db, user_id, today, horizon)
    active_sessions = await load_active_sessions(db, user_id)

    return Scenario(
        today=today,
        horizon=horizon,
        base_currency=settings.base_currency,
        current_balance=balance.current_balance,
        spending=spending,
        income_events=tuple(merged_income),
        outflows=tuple(outflows),
        monthly_threshold=settings.monthly_threshold,
        balance=balance,
        overdue_receivables=tuple(overdue_receivables),
        active_sessions=tuple(active_sessions),
    )
