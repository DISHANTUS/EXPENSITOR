"""Date → Orb reaction (UI-X — the calendar as memory, not bookkeeping).

Tap a marked day and Advary says one warm, true line about it: a repayment that
came back, a strong saving day, the day income arrived, time spent with someone,
a planned occasion. Deterministic, derive-on-read; never scolds an over-budget
day. Composes the existing calendar day-detail + receivables.
"""

from __future__ import annotations

import re
import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Income, Receivable
from app.models.enums import IncomeSourceType, ReceivableKind, ReceivableStatus
from app.services import calendar_service, settings_service

_ZERO = Decimal("0")

_INCOME_PHRASE = {
    IncomeSourceType.salary: "your salary",
    IncomeSourceType.freelance: "your freelance income",
    IncomeSourceType.bonus: "a bonus",
    IncomeSourceType.business: "business income",
    IncomeSourceType.gift: "a gift",
    IncomeSourceType.refund: "a refund",
    IncomeSourceType.scholarship: "your scholarship",
    IncomeSourceType.part_time: "your part-time pay",
    IncomeSourceType.family_support: "support from family",
    IncomeSourceType.pension: "your pension",
}


def _money(cur: str, v: Decimal) -> str:
    return f"{cur} {v:,.0f}"


def _person(title: str) -> str | None:
    m = re.search(r"\bwith\s+([A-Z][a-zA-Z]+)", title or "")
    return m.group(1) if m else None


def _react(line: str, mood: str, emoji: str) -> dict:
    return {"line": line, "mood": mood, "emoji": emoji}


async def build(db: AsyncSession, user_id: uuid.UUID, day: date) -> dict:
    today = await calendar_service.user_today(db, user_id)
    cur = (await settings_service.get_settings(db, user_id)).base_currency
    detail = await calendar_service.day_detail(db, user_id, day, today=today)
    markers = set(detail.markers)

    recvs = (await db.execute(select(Receivable).where(
        Receivable.user_id == user_id, Receivable.deleted_at.is_(None)))).scalars().all()

    # 1) Money came back — the happiest calendar memory.
    returned = [r for r in recvs if r.status == ReceivableStatus.received
                and r.received_at and r.received_at.date() == day]
    if returned:
        r = returned[0]
        who = r.source_name or "Someone"
        return _react(f"That's the day {who} paid you back — {_money(cur, r.converted_amount)}. 🎉",
                      "celebrating", "💰")

    # 2) A strong saving day.
    if detail.classification == "saved":
        if detail.remaining and detail.remaining > _ZERO:
            return _react(f"One of your strong saving days — you came in {_money(cur, detail.remaining)} under budget.",
                          "celebrating", "👑")
        return _react("One of your strong saving days — you stayed well under budget.", "celebrating", "👑")

    # 3) Income arrived.
    if "income" in markers:
        incomes = (await db.execute(select(Income).where(
            Income.user_id == user_id, Income.deleted_at.is_(None),
            Income.received_date == day))).scalars().all()
        total = sum((i.converted_amount for i in incomes), _ZERO)
        phrase = _INCOME_PHRASE.get(incomes[0].source_type, "income") if incomes else "income"
        return _react(f"That's when {phrase} arrived — {_money(cur, total)}.", "celebrating", "💰")

    # 4) Time with someone, or a planned occasion.
    if detail.events:
        ev = detail.events[0]
        title = ev.title or "something planned"
        who = _person(title)
        if who:
            return _react(f"You spent time with {who} that day.", "idle", "❤️")
        return _react(f"You had {title} that day.", "idle", "📅")

    # 5) A loan you're still waiting on.
    pending = [r for r in recvs if r.status == ReceivableStatus.pending
               and r.kind == ReceivableKind.one_time and r.expected_date == day]
    if pending:
        r = pending[0]
        who = r.source_name or "someone"
        if "repay_overdue" in markers or (r.expected_date and r.expected_date < today):
            return _react(f"{who}'s repayment was due around then — maybe a gentle nudge.", "concerned", "🚨")
        return _react(f"You were expecting {_money(cur, r.converted_amount)} back from {who} around then.",
                      "idle", "💸")

    # 6) A recurring commitment fell due.
    if markers & {"subscription", "emi", "bill", "insurance"}:
        return _react("A recurring payment was due that day.", "idle", "💳")

    # 7) Budget days — warm, never scolding.
    if detail.classification == "over":
        return _react("That day ran a little over budget — it happens, and the month still moved forward.",
                      "idle", "🔴")
    if detail.classification == "within":
        return _react("You stayed right on budget that day.", "idle", "🟢")

    return _react("A quiet day — nothing major marked.", "idle", "✨")
