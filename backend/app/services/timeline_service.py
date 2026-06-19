"""Life Timeline service (Sprint 6a) — gather a user's life events from the data
that already exists and hand them to the pure builder.

Deterministic, derive-on-read (no new table). Past wins/milestones come from the
same `success.detect` the mood/recap use; goals, loans, occasions, lessons and the
5a.5 timeline_candidate events fill in the rest; goal target dates + upcoming
occasions form the 'future' chapters (the rich Future-Me forecast lands in 6b).
"""

from __future__ import annotations

import re
import uuid
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.intelligence.learning import success as S
from app.intelligence.timeline import builder as B, chapters, query
from app.models import (
    AdviceMemory,
    CompanionEvent,
    Income,
    LifeEvent,
    LifeLesson,
    Person,
    PlannedExpense,
    Receivable,
    SavingsGoal,
)
from app.models.enums import (
    AdviceStatus,
    CompanionEventType,
    PlannedExpenseStatus,
    ReceivableKind,
    ReceivableStatus,
    SavingsGoalStatus,
)
from app.services import analytics_service, calendar_service, settings_service

_ACH_ICON = {S.FIRST_SALARY: "💼", S.GOAL_COMPLETED: "🏆", S.LOAN_REPAID: "🎉",
             S.DEBT_CLEARED: "🎉", S.SAVINGS_STREAK: "🔥", S.GOAL_MILESTONE: "📈"}
_OCCASION_ICON = {"birthday": "🎂", "anniversary": "💞", "date": "❤️", "outing": "❤️",
                  "trip": "✈️", "travel": "✈️", "vacation": "✈️", "festival": "🪔",
                  "celebration": "🎉", "graduation": "🎓", "shopping": "🛍️", "entertainment": "🎮"}


def _when(d: date | None, today: date) -> str:
    if d is None:
        return B.PRESENT
    return B.FUTURE if d > today else B.PAST


def _person_in_title(title: str) -> str | None:
    """Pull a person out of an event/title: 'Dinner with Naruse' -> 'Naruse'."""
    m = re.search(r"\bwith\s+([A-Z][a-zA-Z]+)", title) or re.search(r"\b([A-Z][a-zA-Z]+)’?'?s\b", title)
    return m.group(1) if m else None


async def gather(db: AsyncSession, user_id: uuid.UUID, *, today: date) -> list[B.Entry]:
    settings = await settings_service.get_settings(db, user_id)
    cur = settings.base_currency
    fmt = analytics_service._fmt  # noqa: SLF001
    entries: list[B.Entry] = []

    goals = (await db.execute(select(SavingsGoal).where(
        SavingsGoal.user_id == user_id, SavingsGoal.deleted_at.is_(None)))).scalars().all()
    recvs = (await db.execute(select(Receivable).where(
        Receivable.user_id == user_id, Receivable.deleted_at.is_(None)))).scalars().all()
    first_income = await db.scalar(select(func.min(Income.received_date)).where(
        Income.user_id == user_id, Income.deleted_at.is_(None)))

    # --- past wins via the canonical achievement engine ---
    completed = [(g.name, (g.updated_at.date() if g.updated_at else None))
                 for g in goals if g.status == SavingsGoalStatus.completed]
    repaid = [(r.source_name, (r.received_at.date() if r.received_at else
                               (r.updated_at.date() if r.updated_at else None)))
              for r in recvs if r.status == ReceivableStatus.received]
    for a in S.detect(completed_goals=completed, repaid_loans=repaid, first_salary=first_income, today=today):
        entries.append(B.Entry(date=a.when, title=a.label, kind="achievement", importance=a.importance,
                               when=_when(a.when, today), icon=_ACH_ICON.get(a.type, "🏆")))

    # --- goal arcs: started (past) + target (future) ---
    for g in goals:
        if g.start_date:
            entries.append(B.Entry(date=g.start_date, title=f"Started saving for {g.name}",
                                   detail=fmt(g.converted_amount, cur), kind="goal", importance="medium",
                                   when=_when(g.start_date, today), icon="🎯"))
        if g.status == SavingsGoalStatus.active and g.target_date and g.target_date > today:
            entries.append(B.Entry(date=g.target_date, title=f"Reach your {g.name} goal",
                                   detail=f"Target {fmt(g.converted_amount, cur)}", kind="goal",
                                   importance="high", when=B.FUTURE, icon="🎯"))

    # --- the loan story: lent (past) + expected repayment (future) / repaid ---
    for r in recvs:
        if r.status == ReceivableStatus.pending and r.kind == ReceivableKind.one_time:
            lent_on = r.created_at.date() if r.created_at else None
            entries.append(B.Entry(date=lent_on, title=f"Lent {fmt(r.converted_amount, cur)} to {r.source_name}",
                                   kind="loan", importance="medium", when=_when(lent_on, today), icon="💸",
                                   person=r.source_name))
            if r.expected_date and r.expected_date > today:
                entries.append(B.Entry(date=r.expected_date, title=f"{r.source_name} to repay {fmt(r.converted_amount, cur)}",
                                       kind="loan", importance="medium", when=B.FUTURE, icon="💸", person=r.source_name))

    # --- life events (occasions), past and upcoming ---
    events = (await db.execute(select(PlannedExpense).where(
        PlannedExpense.user_id == user_id, PlannedExpense.deleted_at.is_(None),
        PlannedExpense.occasion_type.is_not(None),
        PlannedExpense.status != PlannedExpenseStatus.cancelled))).scalars().all()
    for e in events:
        occ = e.occasion_type.value if e.occasion_type else "event"
        entries.append(B.Entry(date=e.planned_date, title=e.title or occ.title(),
                               detail=occ.replace("_", " ").title(), kind="event", importance="medium",
                               when=_when(e.planned_date, today), icon=_OCCASION_ICON.get(occ, "📅"),
                               person=_person_in_title(e.title or "")))

    # --- user-entered life events (the non-finance chapters: move, degree, job) ---
    for le in (await db.execute(select(LifeEvent).where(
            LifeEvent.user_id == user_id, LifeEvent.deleted_at.is_(None)))).scalars().all():
        entries.append(B.Entry(date=le.event_date, title=le.title, detail=le.note or "",
                               kind="life_event", importance="high", when=_when(le.event_date, today),
                               icon=le.icon or "🌟"))

    # --- lessons learned ---
    lessons = (await db.execute(select(LifeLesson).where(
        LifeLesson.user_id == user_id, LifeLesson.deleted_at.is_(None),
        LifeLesson.status == "confirmed"))).scalars().all()
    for ls in lessons:
        entries.append(B.Entry(date=ls.first_observed, title=f"Learned: {ls.lesson}", kind="lesson",
                               importance="medium", when=_when(ls.first_observed, today), icon="💡"))

    # --- repayment commitments (the advice_memory follow-up engine): "you
    # committed to repay X by …", and "you repaid X" once it's answered yes ---
    commitments = (await db.execute(select(AdviceMemory).where(
        AdviceMemory.user_id == user_id, AdviceMemory.deleted_at.is_(None),
        AdviceMemory.kind == "commitment"))).scalars().all()
    for cm in commitments:
        who = cm.subject_label or "someone"
        if cm.status == AdviceStatus.answered.value and (cm.answer or "").lower() in ("yes", "partial"):
            on = cm.updated_at.date() if cm.updated_at else None
            entries.append(B.Entry(date=on, title=f"Repaid {who}", kind="achievement", importance="high",
                                   when=_when(on, today), icon="🎉", person=who))
        else:
            on = cm.created_at.date() if cm.created_at else None
            by = f" by {cm.expected_date.isoformat()}" if cm.expected_date else ""
            entries.append(B.Entry(date=on, title=f"Committed to repay {who}{by}", kind="commitment",
                                   importance="medium", when=_when(on, today), icon="🪙", person=who))

    # --- explicitly recorded timeline candidates (5a.5 achievements; deduped in the builder) ---
    rows = (await db.execute(select(CompanionEvent).where(
        CompanionEvent.user_id == user_id, CompanionEvent.event_type == CompanionEventType.system,
        CompanionEvent.action == "timeline_candidate"))).scalars().all()
    for row in rows:
        label = (row.payload or {}).get("label")
        if not label:
            continue
        on = row.occurred_at.date() if row.occurred_at else None
        entries.append(B.Entry(date=on, title=label, kind="achievement", importance="high",
                               when=_when(on, today), icon="🏆"))

    return entries


async def known_people(db: AsyncSession, user_id: uuid.UUID) -> set[str]:
    """People the user actually tracks — receivable sources + Person rows."""
    names: set[str] = set()
    for (n,) in (await db.execute(select(Receivable.source_name).where(
            Receivable.user_id == user_id, Receivable.deleted_at.is_(None)))).all():
        if n:
            names.add(n)
    for p in (await db.execute(select(Person).where(Person.user_id == user_id))).scalars().all():
        names.add(p.name)
        if p.nickname:
            names.add(p.nickname)
    return {n for n in names if n and n.lower() not in ("salary", "freelance", "refund")}


def _tag_people(entries: list[B.Entry], people: set[str]) -> None:
    """Tag entries with a person when a tracked name appears in the title."""
    lowered = {p.lower(): p for p in people}
    for e in entries:
        if e.person:
            continue
        t = e.title.lower()
        for pl, p in lowered.items():
            if re.search(rf"\b{re.escape(pl)}\b", t):
                e.person = p
                break


async def collect(db: AsyncSession, user_id: uuid.UUID, today: date) -> tuple[list[B.Entry], set[str]]:
    """Gather + person-tag the timeline entries (shared by timeline / search /
    relationship pages — the single source of truth)."""
    people = await known_people(db, user_id)
    entries = await gather(db, user_id, today=today)
    _tag_people(entries, people)
    return entries, people


async def get_timeline(db: AsyncSession, user_id: uuid.UUID, *, today: date | None = None) -> B.Timeline:
    today = today or await calendar_service.user_today(db, user_id)
    entries, _ = await collect(db, user_id, today)
    return B.build(entries, today=today, grouper=chapters.assign)


_MONTH_NAMES = ["", "January", "February", "March", "April", "May", "June", "July",
                "August", "September", "October", "November", "December"]


def summarize_search(spec: query.QuerySpec, entries: list[B.Entry]) -> str:
    n = len(entries)
    if n == 0:
        return "I couldn’t find anything matching that yet."
    thing = "thing" if n == 1 else "things"
    if spec.earliest and entries[0].date:
        return f"It looks like that began on {entries[0].date.isoformat()}: {entries[0].title}."
    if spec.person:
        return f"{n} {thing} involving {spec.person}."
    if spec.kinds == frozenset({"achievement"}):
        return f"You’ve recorded {n} achievement{'s' if n != 1 else ''}."
    if spec.kinds == frozenset({"lesson"}):
        return f"You’ve learned {n} lesson{'s' if n != 1 else ''} so far."
    if spec.month:
        return f"{n} {thing} in {_MONTH_NAMES[spec.month]} {spec.year}."
    if spec.year:
        return f"{n} {thing} in {spec.year}."
    return f"I found {n} {thing}."


async def search(db: AsyncSession, user_id: uuid.UUID, *, q: str,
                 today: date | None = None) -> tuple[list[B.Entry], query.QuerySpec]:
    today = today or await calendar_service.user_today(db, user_id)
    entries, people = await collect(db, user_id, today)
    spec = query.parse_query(q, today=today, known_people=people)
    return query.filter_entries(B.prepare(entries, today=today), spec), spec
