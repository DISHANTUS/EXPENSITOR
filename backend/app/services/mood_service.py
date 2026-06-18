"""Mood service (Sprint 4c-A).

Assembles a MoodContext from already-computed state, composes a priority-ordered,
lifetime-aware mood rotation, and exposes mood explainability (reusing the 4b-3
Explanation shape). Deterministic, no LLM. Weather-proofed and honest: no mood
without a reason; thin data -> neutral.
"""

from __future__ import annotations

import re
import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.intelligence.learning import success as S
from app.intelligence.mood import composer, greeting as G, greeting_narration, moods, presence, voice as V
from app.intelligence.mood.base_mood import MoodContext, select_base
from app.core.config import settings as app_config
from app.core.database import AsyncSessionLocal
from app.models import (
    AdviceMemory,
    CompanionEvent,
    DailyPlan,
    Expense,
    Income,
    IncomeSource,
    LifeLesson,
    PlannedExpense,
    Receivable,
    SavingsGoal,
)
from app.models.enums import (
    AdviceStatus,
    CompanionEventType,
    IncomeKind,
    PlannedExpenseStatus,
    ReceivableKind,
    ReceivableStatus,
    SavingsGoalStatus,
)
from app.schemas.explain import EvidenceItem, Explanation
from app.services import analytics_service, calendar_service, ollama_service, settings_service

# Family relation words -> natural "your X" phrasing (relationship-aware greetings).
_RELATION_WORDS = {"father", "dad", "papa", "mother", "mom", "mum", "mama", "brother", "sister",
                   "parents", "uncle", "aunt", "grandfather", "grandmother", "grandpa", "grandma"}

_ZERO = Decimal("0")
_TONE = {"concerned": "supportive", "slightly_over": "observant", "neutral": "curious",
         "on_budget": "encouraging", "goal_progress": "encouraging", "saving_well": "encouraging",
         "big_win": "encouraging"}

# achievement type (success.detect) -> mood id
_ACHIEVEMENT_MOOD = {
    S.GOAL_COMPLETED: "goal_completed", S.FIRST_SALARY: "first_salary", S.DEBT_CLEARED: "debt_cleared",
    S.SAVINGS_STREAK: "streak", S.GOAL_MILESTONE: "milestone", S.LOAN_REPAID: "returned",
}


async def _context(db: AsyncSession, user_id: uuid.UUID, today: date) -> tuple[MoodContext, list[SavingsGoal]]:
    settings = await settings_service.get_settings(db, user_id)
    start, end, label, gran = analytics_service.resolve_period("month", "this", today)
    report = await analytics_service.build_report(db, user_id, kind="month", start=start, end=end,
                                                  label=label, granularity=gran, today=today)
    total_spent = Decimal(report.summary.total_spent)
    saved = Decimal(report.summary.saved)
    goals = (await db.execute(select(SavingsGoal).where(
        SavingsGoal.user_id == user_id, SavingsGoal.deleted_at.is_(None),
        SavingsGoal.status == SavingsGoalStatus.active))).scalars().all()
    overdue = await db.scalar(select(func.count()).select_from(Receivable).where(
        Receivable.user_id == user_id, Receivable.deleted_at.is_(None),
        Receivable.status == ReceivableStatus.pending, Receivable.expected_date < today)) or 0
    has_data = total_spent > 0 or report.summary.red_days > 0 or report.summary.crown_days > 0
    ctx = MoodContext(
        has_data=has_data, total_spent=total_spent, saved=saved,
        red_days=report.summary.red_days, crown_days=report.summary.crown_days,
        monthly_threshold=settings.monthly_threshold, has_active_goal=bool(goals), overdue_loans=int(overdue),
    )
    return ctx, list(goals)


async def _active_moods(db, user_id, today, goals) -> list[moods.Mood]:
    pairs: list[tuple[moods.Mood, date]] = []

    # Today's calendar markers -> event/relationship/badge moods.
    detail = await calendar_service.day_detail(db, user_id, today, today=today)
    for key in detail.markers:
        mid = moods.MARKER_TO_MOOD.get(key)
        if mid:
            pairs.append((moods.get(mid), today))

    # Achievements (success.detect) -> override/badge moods within their lifetime.
    completed = (await db.execute(select(SavingsGoal.name, SavingsGoal.updated_at).where(
        SavingsGoal.user_id == user_id, SavingsGoal.deleted_at.is_(None),
        SavingsGoal.status == SavingsGoalStatus.completed))).all()
    repaid = (await db.execute(select(Receivable.source_name, Receivable.updated_at).where(
        Receivable.user_id == user_id, Receivable.deleted_at.is_(None),
        Receivable.status == ReceivableStatus.received))).all()
    first_income = await db.scalar(select(func.min(Income.received_date)).where(
        Income.user_id == user_id, Income.deleted_at.is_(None)))
    achievements = S.detect(
        completed_goals=[(n, d.date() if d else None) for n, d in completed],
        repaid_loans=[(n, d.date() if d else None) for n, d in repaid],
        first_salary=first_income, today=today,
    )
    for a in achievements:
        mid = _ACHIEVEMENT_MOOD.get(a.type)
        if mid:
            pairs.append((moods.get(mid), a.when or today))

    # Keep only currently-active moods (lifetime windows); dedup by id keeping highest priority.
    active: dict[str, moods.Mood] = {}
    for m, trig in pairs:
        if moods.is_active(m, trig, today):
            if m.id not in active or m.priority > active[m.id].priority:
                active[m.id] = m
    return list(active.values())


async def _presence(db, user_id, today) -> presence.Presence:
    days_logged = await db.scalar(select(func.count(func.distinct(Expense.expense_date))).where(
        Expense.user_id == user_id, Expense.deleted_at.is_(None))) or 0
    has_income = bool(await db.scalar(select(Income.id).where(
        Income.user_id == user_id, Income.deleted_at.is_(None)).limit(1)))
    has_recv = bool(await db.scalar(select(Receivable.id).where(
        Receivable.user_id == user_id, Receivable.deleted_at.is_(None)).limit(1)))
    has_goal = bool(await db.scalar(select(SavingsGoal.id).where(
        SavingsGoal.user_id == user_id, SavingsGoal.deleted_at.is_(None)).limit(1)))
    return presence.compute(days_logged=int(days_logged), has_goal=has_goal, has_income=has_income,
                            has_receivables=has_recv, lessons=0, advice_count=0)


def _face(m: moods.Mood) -> dict[str, Any]:
    return {"id": m.id, "emoji": m.emoji, "label": m.label, "kind": m.kind, "priority": int(m.priority)}


def _time_of_day(hour: int) -> str:
    if 5 <= hour <= 11:
        return "morning"
    if 12 <= hour <= 16:
        return "afternoon"
    if 17 <= hour <= 21:
        return "evening"
    return "night"


async def _budget_streak(db, user_id, today, settings) -> int:
    """Consecutive days ending today that were not over budget (0 if unknown)."""
    start = today - timedelta(days=60)
    spent_by = await analytics_service._sum_by_day(  # noqa: SLF001
        db, Expense, Expense.expense_date, Expense.converted_amount, user_id, start, today)
    plans = {r[0]: r[1] for r in (await db.execute(
        select(DailyPlan.plan_date, DailyPlan.planned_budget).where(
            DailyPlan.user_id == user_id, DailyPlan.plan_date >= start, DailyPlan.plan_date <= today))).all()}
    streak = 0
    d = today
    while d >= start:
        budget = analytics_service._budget_for(settings, plans.get(d), d)  # noqa: SLF001
        if budget is None:
            break
        if calendar_service.classify(spent_by.get(d, _ZERO), budget, d, today) == "over":
            break
        streak += 1
        d -= timedelta(days=1)
    return streak


async def _follow_up_ref(db, user_id) -> str | None:
    row = (await db.execute(
        select(AdviceMemory).where(
            AdviceMemory.user_id == user_id, AdviceMemory.deleted_at.is_(None),
            AdviceMemory.status == AdviceStatus.answered.value, AdviceMemory.answer.is_not(None))
        .order_by(AdviceMemory.answered_at.desc()).limit(1))).scalar_one_or_none()
    if row is None or not row.subject_label:
        return None
    phr = {"partial": f"You mentioned partial progress on {row.subject_label} — small steps still count.",
           "yes": f"Glad {row.subject_label} worked out last time.",
           "no": f"Last time {row.subject_label} didn’t pan out — no worries, today’s a fresh start."}
    return phr.get(row.answer)


async def _recent_greetings(db, user_id, *, limit: int = 4) -> list[dict[str, Any]]:
    rows = (await db.execute(
        select(CompanionEvent.payload).where(
            CompanionEvent.user_id == user_id, CompanionEvent.event_type == CompanionEventType.system,
            CompanionEvent.action == "greeting").order_by(CompanionEvent.occurred_at.desc()).limit(limit))).all()
    return [p[0] or {} for p in rows]


async def _todays_greeting(db, user_id, today, style, tod) -> dict[str, Any] | None:
    """Reuse today's greeting for the same style AND part-of-day, so morning's
    greeting isn't still shown in the evening."""
    rows = (await db.execute(
        select(CompanionEvent.payload).where(
            CompanionEvent.user_id == user_id, CompanionEvent.event_type == CompanionEventType.system,
            CompanionEvent.action == "greeting", func.date(CompanionEvent.occurred_at) == today)
        .order_by(CompanionEvent.occurred_at.desc()).limit(8))).all()
    for (p,) in rows:
        if (p or {}).get("style") == style and (p or {}).get("time_of_day") == tod:
            return {k: v for k, v in p.items() if k != "style"}
    return None


async def _save_greeting(db, user_id, payload: dict[str, Any]) -> None:
    db.add(CompanionEvent(user_id=user_id, event_type=CompanionEventType.system, action="greeting",
                          surface="companion", payload=payload))
    await db.commit()


def _natural_person(name: str | None) -> str:
    """Relationship-aware phrasing: 'father' -> 'your father'; names stay as-is."""
    if not name:
        return "someone"
    low = name.strip().lower()
    return f"your {low}" if low in _RELATION_WORDS else name.strip()


async def _named_today_facts(db, user_id, today, currency) -> list[G.NamedFact]:
    """People + amounts + events happening TODAY (the relationship/event lines)."""
    facts: list[G.NamedFact] = []

    recvs = (await db.execute(select(Receivable).where(
        Receivable.user_id == user_id, Receivable.deleted_at.is_(None),
        Receivable.status == ReceivableStatus.pending, Receivable.kind == ReceivableKind.one_time))).scalars().all()
    for r in recvs:
        if r.expected_date == today:
            facts.append(G.NamedFact(kind="repay_due", tier=G.HIGH, person=_natural_person(r.source_name),
                                     amount=analytics_service._fmt(r.converted_amount, currency), when_label="today"))  # noqa: SLF001
        elif r.expected_date is not None and r.expected_date < today:
            facts.append(G.NamedFact(kind="repay_overdue", tier=G.HIGH, person=_natural_person(r.source_name),
                                     amount=analytics_service._fmt(r.converted_amount, currency)))  # noqa: SLF001

    events = (await db.execute(select(PlannedExpense).where(
        PlannedExpense.user_id == user_id, PlannedExpense.deleted_at.is_(None),
        PlannedExpense.planned_date == today, PlannedExpense.occasion_type.is_not(None),
        PlannedExpense.status == PlannedExpenseStatus.planned))).scalars().all()
    for e in events:
        facts.append(G.NamedFact(kind="event", occasion=e.occasion_type.value if e.occasion_type else None,
                                 title=e.title, when_label="today"))

    sources = (await db.execute(select(IncomeSource).where(
        IncomeSource.user_id == user_id, IncomeSource.deleted_at.is_(None), IncomeSource.is_active.is_(True)))).scalars().all()
    for s in sources:
        due = ((s.kind == IncomeKind.recurring and s.recurrence_day == today.day)
               or (s.kind == IncomeKind.one_time and s.expected_date == today))
        if not due:
            continue
        amount = analytics_service._fmt(s.converted_amount, currency)  # noqa: SLF001
        is_person = s.label.strip().lower() in _RELATION_WORDS
        if is_person:
            facts.append(G.NamedFact(kind="income_today", tier=G.HIGH, person=_natural_person(s.label),
                                     amount=amount, when_label="today"))
        else:
            facts.append(G.NamedFact(kind="income_today", tier=G.HIGH, label=s.label,
                                     amount=amount, when_label="today"))
    return facts[:4]


async def _narrate_bg(user_id: uuid.UUID, today: date, style: str) -> None:
    """Background: rephrase today's deterministic greeting via Ollama and update
    the cache in place (so app-open is instant; the wording upgrades after)."""
    async with AsyncSessionLocal() as db:
        rows = (await db.execute(select(CompanionEvent).where(
            CompanionEvent.user_id == user_id, CompanionEvent.event_type == CompanionEventType.system,
            CompanionEvent.action == "greeting", func.date(CompanionEvent.occurred_at) == today)
            .order_by(CompanionEvent.occurred_at.desc()).limit(5))).scalars().all()
        row = next((r for r in rows if (r.payload or {}).get("style") == style
                    and (r.payload or {}).get("narration_source") == "deterministic"), None)
        if row is None:
            return
        p = dict(row.payload)
        # Compare only against OTHER days' greetings — not this greeting's own
        # deterministic baseline (its facts are identical by design, which would
        # always read as "too similar").
        recent_texts = [g.get("display_text", "") for g in await _recent_greetings(db, user_id, limit=6)
                        if g.get("display_text") and g.get("display_text") != p["display_text"]]
        res = await ollama_service.narrate_greeting(p["salutation"], p["lines"], style=style, recent_texts=recent_texts)
        if res["ok"] and res["text"]:
            p["display_text"], p["narration_source"] = res["text"], "ollama"
        # Optionally reword the SPOKEN fact segments too (rephrase-only, grounded);
        # falls back to deterministic per-segment, so voice never hallucinates (5b).
        facts = list(p.get("voice_segments", []))
        if facts:
            vres = await ollama_service.narrate_greeting("", facts, style=style)
            if vres["ok"] and vres["text"]:
                p["voice_narrated"] = _split_sentences(vres["text"])
        p["pending_narration"] = False
        row.payload = p
        await db.commit()


def _spoken_for(payload: dict[str, Any], voice_length: str) -> str:
    """Concise TTS text (Sprint 5): top-N facts by voice_length + a closer.
    Computed on READ so changing voice_length takes effect without a cache bust."""
    n = {"short": 1, "normal": 2, "detailed": 3}.get(voice_length, 2)
    lines = list(payload.get("voice_lines", []))[:n]
    if payload.get("encouragement"):
        lines.append(payload["encouragement"])
    return greeting_narration.spoken_text(payload.get("salutation", ""), lines)


# Spoken salutations vary with the user's ENERGY (time-of-day), independent of the
# visual greeting — evening speaks in past tense, late night softens (Sprint 5b).
_ENERGY_SALUTATION = {
    "morning": "Good morning.", "afternoon": "Good afternoon.",
    "evening": "Hope your day went well.", "late_night": "It’s getting late.",
}


def _user_energy(time_of_day: str) -> str:
    return "late_night" if time_of_day == "night" else time_of_day


def _split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", (text or "").strip())
    return [p.strip() for p in parts if p.strip()]


def _voice_for(payload: dict[str, Any], voice_length: str, today: date, *, mood_id: str) -> dict[str, Any]:
    """Build the VoicePlan on READ (so voice_length applies without a cache bust).
    Merges Ollama-narrated fact segments from the cache when present."""
    n = {"short": 1, "normal": 2, "detailed": 3}.get(voice_length, 2)
    flags = payload.get("voice_flags", {}) or {}
    energy = _user_energy(payload.get("time_of_day", "morning"))
    ctx = V.VoiceContext(
        mood=mood_id, user_energy=energy, presence_band=payload.get("presence_band", "new"),
        relationship=bool(flags.get("relationship")), event=bool(flags.get("event")),
        special_day=payload.get("special_day"),
        concern_count=int(flags.get("overdue_count", 0)) + (1 if mood_id in ("concerned", "slightly_over") else 0),
    )
    facts = list(payload.get("voice_segments", []))[:n]
    narrated = payload.get("voice_narrated")
    plan = V.build_voice_plan(
        ctx, salutation=_ENERGY_SALUTATION.get(energy, "Hello."), fact_segments=facts,
        signature=f"greet:{today.isoformat()}:{payload.get('time_of_day', '')}",
        encouragement=payload.get("encouragement", ""),
        narrated_facts=list(narrated)[:n] if narrated else None,
    )
    return V.as_dict(plan)


async def _greeting(db, user_id, today, *, settings, base, state, goals, pres, currency, background=None,
                    local_hour=None) -> dict[str, Any]:
    from zoneinfo import ZoneInfo
    style = settings.companion_style
    vlen = getattr(settings, "voice_length", "normal")
    # Prefer the device's local hour (so the greeting matches what the user sees);
    # fall back to the user's stored timezone.
    hour = local_hour if local_hour is not None else datetime.now(ZoneInfo(settings.timezone or "UTC")).hour
    tod = _time_of_day(hour)
    cached = await _todays_greeting(db, user_id, today, style, tod)
    if cached:                                                        # voice length applied on read
        return {**cached, "spoken_text": _spoken_for(cached, vlen),
                "voice": _voice_for(cached, vlen, today, mood_id=base.id)}

    recent = await _recent_greetings(db, user_id)
    special = state.primary.id if state.primary.kind == "override" else None
    gctx = G.GreetingContext(
        time_of_day=tod, tone=_TONE.get(base.id, "supportive"),
        style=style, presence_band=pres.band, special_day=special,
        named_facts=await _named_today_facts(db, user_id, today, currency),
        goal_name=goals[0].name if goals else None,
        streak_days=await _budget_streak(db, user_id, today, settings),
        follow_up=await _follow_up_ref(db, user_id) if pres.band == "deeply_personalized" else None,
    )
    g = G.build_greeting(gctx, seed=today.toordinal(),
                         recent_categories=[r.get("category", "") for r in recent],
                         recent_encouragements=[r.get("encouragement", "") for r in recent])

    display = greeting_narration.display_text(g.salutation, g.lines)
    scheduled = app_config.OLLAMA_ENABLED and background is not None
    payload = {"salutation": g.salutation, "lines": g.lines, "voice_lines": g.voice_lines, "category": g.category,
               "summary": g.summary, "reasons": g.reasons, "special_day": g.special_day, "tone": g.tone,
               "encouragement": g.encouragement, "display_text": display, "narration_source": "deterministic",
               "pending_narration": scheduled, "time_of_day": tod,
               "voice_segments": g.voice_segments, "voice_flags": g.voice_flags, "presence_band": pres.band}
    payload["spoken_text"] = _spoken_for(payload, vlen)
    await _save_greeting(db, user_id, {**payload, "style": style})
    payload["voice"] = _voice_for(payload, vlen, today, mood_id=base.id)
    if scheduled:
        background.add_task(_narrate_bg, user_id, today, style)
    return payload


def _rx(kind, emoji, headline, detail, importance, signature, *, tap_route=None, timeline_label=None) -> dict[str, Any]:
    return {"kind": kind, "emoji": emoji, "headline": headline, "detail": detail, "importance": importance,
            "signature": signature, "tap_route": tap_route, "timeline_label": timeline_label}


async def _surfaced_signatures(db, user_id) -> set[str]:
    rows = (await db.execute(select(CompanionEvent.payload).where(
        CompanionEvent.user_id == user_id, CompanionEvent.event_type == CompanionEventType.system,
        CompanionEvent.action == "reaction_surfaced").order_by(CompanionEvent.occurred_at.desc()).limit(40))).all()
    out: set[str] = set()
    for (p,) in rows:
        out.update((p or {}).get("signatures", []))
    return out


async def _pending_reactions(db, user_id, today, *, settings, currency) -> list[dict[str, Any]]:
    """Intelligence-driven reactions (overspend / achievement / lesson / streak),
    surfaced once each. Action acks (income/expense/…) are emitted client-side."""
    surfaced = await _surfaced_signatures(db, user_id)
    out: list[dict[str, Any]] = []

    # Overspend today (tap -> Plan Today to add a reason).
    spent_by = await analytics_service._sum_by_day(  # noqa: SLF001
        db, Expense, Expense.expense_date, Expense.converted_amount, user_id, today, today)
    plan = await db.scalar(select(DailyPlan.planned_budget).where(
        DailyPlan.user_id == user_id, DailyPlan.plan_date == today))
    budget = analytics_service._budget_for(settings, plan, today)  # noqa: SLF001
    spent = spent_by.get(today, _ZERO)
    if budget is not None and calendar_service.classify(spent, budget, today, today) == "over":
        sig = f"overspend:{today}"
        if sig not in surfaced:
            over = analytics_service._fmt(spent - budget, currency)  # noqa: SLF001
            out.append(_rx("overspend", "⚠️", f"You’re {over} over today’s budget.",
                           "That’s okay — tell me what happened so I can learn.", "normal", sig, tap_route="/plan-today"))

    # Achievements (success.detect): goal completed / first salary -> achievement; loan repaid -> milestone.
    completed = (await db.execute(select(SavingsGoal.name, SavingsGoal.updated_at).where(
        SavingsGoal.user_id == user_id, SavingsGoal.deleted_at.is_(None),
        SavingsGoal.status == SavingsGoalStatus.completed))).all()
    repaid = (await db.execute(select(Receivable.source_name, Receivable.updated_at).where(
        Receivable.user_id == user_id, Receivable.deleted_at.is_(None),
        Receivable.status == ReceivableStatus.received))).all()
    first_income = await db.scalar(select(func.min(Income.received_date)).where(
        Income.user_id == user_id, Income.deleted_at.is_(None)))
    for a in S.detect(completed_goals=[(n, d.date() if d else None) for n, d in completed],
                      repaid_loans=[(n, d.date() if d else None) for n, d in repaid],
                      first_salary=first_income, today=today):
        sig = f"ach:{a.type}:{a.when}"
        if sig in surfaced:
            continue
        if a.type == S.LOAN_REPAID:
            out.append(_rx("loan_repaid", "🎉", "Good news", f"{a.label}.", "milestone", sig))
        else:
            out.append(_rx("achievement", "🏆", "Achievement unlocked!", a.label, "achievement", sig,
                           timeline_label=a.label))

    # A newly-confirmed lesson the user taught (4b-5b).
    lessons = (await db.execute(select(LifeLesson.id, LifeLesson.lesson).where(
        LifeLesson.user_id == user_id, LifeLesson.deleted_at.is_(None),
        LifeLesson.status == "confirmed").order_by(LifeLesson.last_observed.desc()).limit(1))).all()
    for lid, lesson in lessons:
        sig = f"lesson:{lid}"
        if sig not in surfaced:
            out.append(_rx("lesson_learned", "💡", "I learned something new.", lesson, "normal", sig))

    # Budget streak worth celebrating.
    streak = await _budget_streak(db, user_id, today, settings)
    if streak >= 3:
        sig = f"streak:{today}:{streak}"
        if sig not in surfaced:
            out.append(_rx("streak", "🔥", "Budget streak going strong", f"You’re at {streak} days.", "milestone", sig))

    out = out[:3]
    if out:
        db.add(CompanionEvent(user_id=user_id, event_type=CompanionEventType.system, action="reaction_surfaced",
                              surface="companion", payload={"signatures": [r["signature"] for r in out]}))
        await db.commit()
    return out


async def get_mood(db: AsyncSession, user_id: uuid.UUID, *, today: date | None = None, background=None,
                   local_hour: int | None = None) -> dict[str, Any]:
    today = today or await calendar_service.user_today(db, user_id)
    settings = await settings_service.get_settings(db, user_id)
    ctx, goals = await _context(db, user_id, today)
    base = select_base(ctx)
    base_mood = moods.get(moods.weather_proof(base.mood_id))
    active = await _active_moods(db, user_id, today, goals)
    state = composer.compose(base_mood, active, base_reasons=base.reasons)
    pres = await _presence(db, user_id, today)
    greeting = await _greeting(db, user_id, today, settings=settings, base=base_mood, state=state,
                               goals=goals, pres=pres, currency=settings.base_currency, background=background,
                               local_hour=local_hour)
    pending = await _pending_reactions(db, user_id, today, settings=settings, currency=settings.base_currency)
    return {
        "primary": _face(state.primary),
        "base": _face(state.base),
        "rotation": [_face(m) for m in state.rotation],
        "reasons": state.reasons,
        "mood_word": state.primary.label,
        "presence_score": pres.score,
        "presence_band": pres.band,
        "greeting": greeting,
        "pending_reactions": pending,
        "companion_name": settings.companion_name or "Advary",   # canonical default identity
    }


async def explain(db: AsyncSession, user_id: uuid.UUID, *, today: date | None = None) -> Explanation:
    """Mood explainability (4c-6) — reuses the 4b-3 Explanation shape."""
    state = await get_mood(db, user_id, today=today)
    reasons = state["reasons"]
    evidence = [EvidenceItem(label=r["label"], value=r["value"]) for r in reasons]
    claim = f"Current mood: {state['mood_word']}"
    if reasons:
        reasoning = "Because " + "; ".join(f"{r['label'].lower()} {r['value']}" for r in reasons) + "."
    else:
        reasoning = "I’m steady — nothing notable is pulling my mood either way right now."
    return Explanation(
        claim=claim, confidence="high" if reasons else "medium", confidence_word=None,
        reasoning=reasoning, why_it_matters=None, evidence=evidence,
    )
