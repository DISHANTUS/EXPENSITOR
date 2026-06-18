"""Companion Evolution / Reflection Engine (Sprint 8).

Advary reflecting on the user's journey — deterministic observations and a
monthly recap, composed from engines that already exist (home stats, recap,
timeline chapters, achievements, calendar, analytics). No new financial math, no
fake emotion: just meaningful, true reflections.
"""

from __future__ import annotations

import calendar as _cal
import uuid
from collections import Counter
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.intelligence.timeline import builder as B
from app.models import SavingsGoal, User
from app.models.enums import SavingsGoalStatus
from app.services import (
    analytics_service,
    calendar_service,
    companion_recap_service,
    home_stats_service,
    profile_service,
    relationship_service,
    timeline_service,
)

_ZERO = Decimal("0")
_MONTHS = ["", "January", "February", "March", "April", "May", "June", "July",
           "August", "September", "October", "November", "December"]
_COUNTRY = {"IN": "India", "JP": "Japan", "US": "the US", "GB": "the UK"}
_ACH_ICON = {"first_salary": "💼", "goal_completed": "🏆", "loan_repaid": "🎉",
             "debt_cleared": "🎉", "savings_streak": "🔥", "goal_milestone": "📈"}


def _plural(n: int, word: str) -> str:
    return f"{n} {word}" if n == 1 else f"{n} {word}s"


def _humanize(category: str) -> str:
    return category.replace("_", " ").strip().title()


# --------------------------------------------------------------------------- #
#  The journey view (reflections + chapter progress + milestones)
# --------------------------------------------------------------------------- #
async def evolution(db: AsyncSession, user: User) -> dict:
    user_id = user.id
    today = await calendar_service.user_today(db, user_id)
    stats = await home_stats_service.build(db, user)
    recap = await companion_recap_service.build(db, user_id, today=today)
    tl = await timeline_service.get_timeline(db, user_id, today=today)

    days = stats["days_with_advary"]
    reflections: list[dict] = [
        {"icon": "📅", "text": f"You've been with Advary for {_plural(days, 'day')}."}
    ]

    if stats.get("strongest_habit"):
        reflections.append({"icon": "🔥", "text": f"Your strongest habit is {stats['strongest_habit'][0].lower()}{stats['strongest_habit'][1:]}."})

    completed = int(stats.get("goals_completed") or 0)
    if completed:
        reflections.append({"icon": "🏆", "text": f"You've completed {_plural(completed, 'goal')} since we started."})

    # Chapters: current (last with a past/present entry) + longest.
    current = None
    for ch in tl.chapters:
        if any(e.when != B.FUTURE for e in ch.entries):
            current = ch
    if current is None and tl.chapters:
        current = tl.chapters[-1]
    longest = max(tl.chapters, key=lambda c: len(c.entries)) if tl.chapters else None
    if longest and len(longest.entries) >= 3:
        reflections.append({"icon": "📖", "text": f"{longest.label} has become your longest chapter."})

    people = await relationship_service.list_people(db, user_id, today=today)
    if people and people[0].memory_count >= 2:
        reflections.append({"icon": "❤️", "text": f"You and {people[0].name} share the most moments together."})

    lessons = recap.get("lessons") or []
    if lessons:
        reflections.append({"icon": "💡", "text": f"You've taught me {_plural(len(lessons), 'lesson')} about your money."})

    current_chapter = None
    if current is not None:
        past = sum(1 for e in current.entries if e.when != B.FUTURE)
        fut = sum(1 for e in current.entries if e.when == B.FUTURE)
        progress = round(100 * past / (past + fut)) if fut > 0 and (past + fut) > 0 else None
        started = min((e.date for e in current.entries if e.date), default=None)
        current_chapter = {
            "label": current.label,
            "subtitle": current.subtitle,
            "started": started.isoformat() if started else None,
            "progress": progress,
            "moments": len(current.entries),
        }

    # Milestones Advary knows: the "firsts"/achievements + the next life move.
    milestones: list[dict] = []
    seen: set[str] = set()
    for a in recap.get("achievements") or []:
        key = f"{a['type']}:{a.get('label')}"
        if key in seen:
            continue
        seen.add(key)
        milestones.append({"icon": _ACH_ICON.get(a["type"], "⭐"), "label": a["label"],
                           "date": a.get("when"), "tense": "past"})
    profile = await profile_service.get_profile(db, user_id)
    if profile.moving_country and profile.future_country:
        where = _COUNTRY.get(profile.future_country, profile.future_country)
        milestones.append({"icon": "✈️", "label": f"Move to {where}",
                           "date": (f"{profile.future_move_year}-01-01" if profile.future_move_year else None),
                           "tense": "future"})

    return {
        "days_with_advary": days,
        "reflections": reflections,
        "current_chapter": current_chapter,
        "longest_chapter": (longest.label if longest else None),
        "milestones": milestones,
    }


# --------------------------------------------------------------------------- #
#  Monthly reflection
# --------------------------------------------------------------------------- #
async def monthly_reflection(db: AsyncSession, user_id: uuid.UUID,
                             year: int | None = None, month: int | None = None) -> dict:
    today = await calendar_service.user_today(db, user_id)
    year = year or today.year
    month = month or today.month
    label = f"{_MONTHS[month]} {year}"

    mv = await calendar_service.month_view(db, user_id, year, month, today=today)
    within = sum(1 for d in mv.days if d.classification in ("saved", "within"))
    tracked = sum(1 for d in mv.days if d.classification != "none")

    if tracked == 0:
        return {"month_label": label, "available": False,
                "headline": f"Not enough activity in {_MONTHS[month]} yet — keep going and I'll reflect on it.",
                "within_budget_days": 0, "tracked_days": 0}

    last = _cal.monthrange(year, month)[1]
    start, end = date(year, month, 1), date(year, month, last)

    # Biggest win: a goal completed this month, else one started this month.
    goals = (await db.execute(select(SavingsGoal).where(
        SavingsGoal.user_id == user_id, SavingsGoal.deleted_at.is_(None)))).scalars().all()
    biggest_win = None
    for g in goals:
        if g.status == SavingsGoalStatus.completed and g.updated_at and start <= g.updated_at.date() <= end:
            biggest_win = f"Completing {g.name}"
            break
    if biggest_win is None:
        for g in goals:
            if g.start_date and start <= g.start_date <= end:
                biggest_win = f"Starting {g.name}"
                break

    # Most active relationship this month (people in this month's timeline entries).
    entries, _people = await timeline_service.collect(db, user_id, today)
    counts = Counter(e.person for e in entries
                     if e.person and e.date and start <= e.date <= end)
    most_active = counts.most_common(1)[0][0] if counts else None

    # Most improved area: the category whose spend dropped most vs last month.
    pstart = date(year - 1, 12, 1) if month == 1 else date(year, month - 1, 1)
    pend = start - timedelta(days=1)
    cur = await analytics_service._category_sums(db, user_id, start, end)  # noqa: SLF001
    prev = await analytics_service._category_sums(db, user_id, pstart, pend)  # noqa: SLF001
    most_improved = None
    best_drop = _ZERO
    for cat, prev_amt in prev.items():
        drop = prev_amt - cur.get(cat, _ZERO)
        if drop > best_drop:
            best_drop = drop
            most_improved = _humanize(cat)

    return {
        "month_label": label,
        "available": True,
        "headline": f"In {label}, you stayed within budget {_plural(within, 'day')}.",
        "within_budget_days": within,
        "tracked_days": tracked,
        "biggest_win": biggest_win,
        "most_active_relationship": most_active,
        "most_improved_area": (f"{most_improved} spending" if most_improved else None),
    }
