"""Home preview cards (UI-X — Living Quick Cards).

Turns the old Home quick-action buttons into *previews* of the user's life:

  • Your Story        — the chapter they're in + their most recent memory
  • Future You        — the next milestone ahead
  • People Who Matter — the person with the most shared memories + what's next
  • Today's Focus     — one thing to lean into today (from the Home thought)

All deterministic, derive-on-read, composed from existing engines (timeline,
future-me, relationships, home-thought). Each card degrades to a warm,
get-started default so a brand-new account still sees something inviting.
"""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.intelligence.timeline import builder as B, chapters as C
from app.services import (
    calendar_service,
    feasibility_service,
    future_me_service,
    home_thought_service,
    profile_service,
    relationship_service,
    timeline_service,
)


def _card(key: str, icon: str, title: str, headline: str, route: str,
          subtitle: str | None = None) -> dict:
    return {"key": key, "icon": icon, "title": title, "headline": headline,
            "subtitle": subtitle, "route": route}


def _latest_memory(entries: list[B.Entry]) -> B.Entry | None:
    """The most recent thing that has actually happened."""
    past = [e for e in entries if e.when != B.FUTURE]
    dated = sorted((e for e in past if e.date), key=lambda e: e.date)
    return dated[-1] if dated else (past[0] if past else None)


def _story_card(entries: list[B.Entry], today: date) -> dict:
    if not entries:
        return _card("story", "📖", "Your Story", "Your story starts here",
                     "/timeline", subtitle="Log a goal or moment and I'll remember it")

    timeline = B.build(entries, today=today, grouper=C.assign)
    # The chapter the user is living in: the last one holding a past/present event.
    current = None
    for ch in timeline.chapters:
        if any(e.when != B.FUTURE for e in ch.entries):
            current = ch
    if current is None and timeline.chapters:
        current = timeline.chapters[0]

    latest = _latest_memory(entries)
    headline = current.label if current else "Your Story"
    subtitle = f"{latest.icon} {latest.title}" if latest else None
    return _card("story", "📖", "Your Story", headline, "/timeline", subtitle=subtitle)


_COUNTRY = {"IN": "India", "JP": "Japan", "US": "the US", "GB": "the UK"}


async def _future_card(db: AsyncSession, user_id: uuid.UUID, today: date) -> dict:
    fm = await future_me_service.get_future_me(db, user_id, today=today)
    milestones = fm.get("milestones") or []
    if milestones:
        m = milestones[0]
        when = ""
        if m.get("date"):
            d: date = m["date"]
            when = f"{d.strftime('%b %Y')}"
        headline = f"{m.get('icon', '🔮')} {m['title']}"
        subtitle = when or (m.get("detail") or None)
        return _card("future", "✨", "Future You", headline, "/future-me", subtitle=subtitle)

    # No dated milestone yet — surface the real plan we DO know: a future move…
    profile = await profile_service.get_profile(db, user_id)
    if profile.moving_country and profile.future_country:
        where = _COUNTRY.get(profile.future_country, profile.future_country)
        sub = f"Expected {profile.future_move_year}" if profile.future_move_year else "On the horizon"
        return _card("future", "✨", "Future You", f"✈️ Move to {where}", "/future-me", subtitle=sub)

    # …else the goal they're working toward.
    feas = await feasibility_service.assess(db, user_id)
    if feas.goals:
        g = feas.goals[0]
        return _card("future", "✨", "Future You", f"🎯 {g.goal}", "/future-me",
                     subtitle="See where this goal takes you")

    # Nothing forward-looking yet — invite them to look ahead.
    return _card("future", "✨", "Future You", "Plan your future",
                 "/future-me", subtitle="Set a goal and see where it takes you")


async def _people_card(db: AsyncSession, user_id: uuid.UUID, today: date,
                       entries: list[B.Entry]) -> dict | None:
    people = await relationship_service.list_people(db, user_id, today=today)
    if not people:
        return None
    top = people[0]

    # What's next with them: their soonest upcoming event/repayment.
    upcoming = sorted(
        (e for e in entries
         if e.when == B.FUTURE and e.date and (e.person or "").lower() == top.name.lower()),
        key=lambda e: e.date)
    if upcoming:
        nxt = upcoming[0]
        subtitle = f"{nxt.icon} {nxt.title} · {nxt.date.strftime('%b %d')}"
    elif top.memory_count:
        noun = "memory" if top.memory_count == 1 else "memories"
        subtitle = f"{top.memory_count} {noun} together"
    else:
        subtitle = top.relationship_type

    return _card("people", "❤️", "People Who Matter", top.name, "/relationships", subtitle=subtitle)


async def _focus_card(db: AsyncSession, user_id: uuid.UUID) -> dict:
    thought = await home_thought_service.build(db, user_id)
    lines = thought.get("lines") or []
    headline = lines[0] if lines else "A good day to get a little ahead"
    icon = {"concerned": "🛟", "celebrating": "🌟"}.get(thought.get("mood"), "🎯")
    return _card("focus", icon, "Today's Focus", headline, "/plan-today")


async def build(db: AsyncSession, user_id: uuid.UUID) -> dict:
    today = await calendar_service.user_today(db, user_id)
    # Timeline entries are gathered once and shared by Story + People.
    entries, _people = await timeline_service.collect(db, user_id, today)

    cards = [_story_card(entries, today), await _future_card(db, user_id, today)]
    people = await _people_card(db, user_id, today, entries)
    if people:
        cards.append(people)
    cards.append(await _focus_card(db, user_id))
    return {"cards": cards}
