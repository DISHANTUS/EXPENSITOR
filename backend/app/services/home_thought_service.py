"""Home "thought" (UI-X — Advary's Room).

A short, contextual reflection for the top of Home — goal status, who owes you,
the next life milestone — composed deterministically from existing state, plus a
mood for the orb to wear. Resilient: degrades to a warm default, never errors.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Receivable
from app.models.enums import ReceivableKind, ReceivableStatus
from app.services import calendar_service, feasibility_service, profile_service, settings_service

_ZERO = Decimal("0")
_COUNTRY = {"IN": "India", "JP": "Japan", "US": "the US", "GB": "the UK"}
_POSITIVE = {"very_high", "high"}


def _money(cur: str, v: Decimal) -> str:
    return f"{cur} {v:,.0f}"


async def build(db: AsyncSession, user_id: uuid.UUID) -> dict:
    today = await calendar_service.user_today(db, user_id)
    cur = (await settings_service.get_settings(db, user_id)).base_currency
    profile = await profile_service.get_profile(db, user_id)

    lines: list[str] = []
    mood = "idle"

    # 1) Goal status (from the feasibility engine).
    feas = await feasibility_service.assess(db, user_id)
    if feas.goals:
        g = feas.goals[0]
        rate = _money(cur, g.target_monthly)
        if g.probability_band in _POSITIVE:
            lines.append(f"{g.goal} is on track — about {rate}/month keeps you on pace.")
            mood = "celebrating"
        elif g.probability_band == "medium":
            lines.append(f"{g.goal} is within reach — around {rate}/month gets you there.")
        else:
            lines.append(f"{g.goal} needs attention — it'd take about {rate}/month. Let's look at the plan.")
            mood = "concerned"

    # 2) Who owes you (receivables).
    pending = (await db.execute(select(Receivable).where(
        Receivable.user_id == user_id, Receivable.deleted_at.is_(None),
        Receivable.status == ReceivableStatus.pending).order_by(Receivable.expected_date))).scalars().all()
    if pending:
        total = sum((r.converted_amount for r in pending), _ZERO)
        overdue = [r for r in pending if r.kind == ReceivableKind.one_time
                   and r.expected_date and r.expected_date < today]
        if len(pending) == 1:
            r = pending[0]
            tail = " — that one's overdue." if overdue else " No urgency right now."
            lines.append(f"{r.source_name} still owes you {_money(cur, r.converted_amount)}.{tail}")
        else:
            tail = f" {len(overdue)} overdue." if overdue else ""
            lines.append(f"{len(pending)} people owe you {_money(cur, total)}.{tail}")
        if overdue:
            mood = "concerned"

    # 3) Next life milestone (future move).
    if profile.moving_country and profile.future_country:
        where = _COUNTRY.get(profile.future_country, profile.future_country)
        when = f" in {profile.future_move_year}" if profile.future_move_year else ""
        lines.append(f"Next up: moving to {where}{when}.")

    if not lines:
        lines.append("Nothing pressing today — a good day to get a little ahead.")

    return {"lines": lines, "mood": mood}
