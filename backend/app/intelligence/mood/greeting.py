"""Greeting engine (Sprint 4c-B + polish, pure/deterministic).

Composes greetings from COMPONENTS — salutation · ranked items (top 2-3) · advice ·
encouragement — so the companion stays varied with no LLM. Polish:
  * Multi-event: rank all of today's facts (CRITICAL/HIGH/MEDIUM/LOW) and show the
    top few — not just one lead.
  * Named/relationship facts ("Naruse's outing", "Ravi returns ₹3,000 today").
  * Event-specific advice (date / interview / repayment / income ...).
  * Explainability: every shown item carries a reason.
  * Rotation memory: avoid repeating the same encouragement / lead topic.

Mood/greeting alignment: `tone` comes from the same mood layer.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.intelligence.mood import styles
from app.intelligence.mood.advice_library import advice_for

CATEGORIES = ("special_day", "relationship", "event", "achievement", "financial", "goal", "streak", "neutral")

CRITICAL, HIGH, MEDIUM, LOW = "critical", "high", "medium", "low"
_RANK = {CRITICAL: 3, HIGH: 2, MEDIUM: 1, LOW: 0}
# Within the same tier: life before money (relationship > financial), then the rest.
_CAT_ORDER = {"special_day": 0, "relationship": 1, "financial": 2, "event": 3,
              "streak": 4, "goal": 5, "achievement": 6, "neutral": 9}

# occasion (planned event) -> (tier, emoji, category)
_OCCASION = {
    "birthday": (CRITICAL, "🎂", "special_day"), "date": (HIGH, "❤️", "relationship"),
    "outing": (HIGH, "❤️", "relationship"), "travel": (HIGH, "✈️", "event"),
    "vacation": (HIGH, "✈️", "event"), "festival": (MEDIUM, "🪔", "event"),
    "celebration": (HIGH, "🎉", "event"), "shopping": (MEDIUM, "🛍️", "event"),
    "entertainment": (MEDIUM, "🎮", "event"), "custom": (MEDIUM, "📅", "event"),
}
# override mood id -> celebration phrasings (CRITICAL special days)
_CELEBRATION = {
    "first_salary": ["Congratulations on your first income! 🎉", "Your very first income — a real milestone! 🎉"],
    "goal_completed": ["You completed your goal! 🏆", "Goal complete — outstanding work! 🏆"],
    "graduation": ["Congratulations on graduating! 🎓"],
    "job_offer": ["A job offer — congratulations! 💼"],
    "debt_cleared": ["You cleared your debt — huge! 🎉"],
    "birthday": ["Happy birthday! 🎂", "Wishing you a wonderful birthday! 🎂"],
    "anniversary": ["Happy anniversary! 💞"],
}
# Emoji-free spoken forms for the special-day celebrations (Sprint 5b voice).
_CELEBRATION_SPOKEN = {
    "first_salary": "You recorded your very first income.", "goal_completed": "You completed your goal.",
    "graduation": "You graduated.", "job_offer": "You received a job offer.",
    "debt_cleared": "You cleared your debt.", "birthday": "It’s your birthday.",
    "anniversary": "It’s your anniversary.",
}
_SALUTATIONS = {
    "morning": ["Good morning.", "Morning.", "Good morning to you."],
    "afternoon": ["Good afternoon.", "Afternoon.", "Hope your day’s going well."],
    "evening": ["Good evening.", "Evening.", "Hope you had a good day."],
    "night": ["Hope you’re winding down.", "Good evening.", "Late one tonight?"],
}
_TIME_EMOJI = {"morning": "☀️", "afternoon": "🌤️", "evening": "🌆", "night": "🌙"}
_DEPTH = {"new": 1, "learning": 2, "familiar": 2, "deeply_personalized": 3}


def _pick(pool: list[str], seed: int) -> str:
    return pool[seed % len(pool)] if pool else ""


@dataclass(frozen=True)
class NamedFact:
    """A today-fact with people/amounts, from the DB (mood_service builds these)."""
    kind: str                       # repay_due | repay_overdue | event | income_today
    tier: str = MEDIUM
    person: str | None = None       # already relationship-natural ("Ravi", "your father")
    amount: str | None = None       # already currency-formatted ("₹3,000")
    occasion: str | None = None
    title: str | None = None
    label: str | None = None        # income source label
    when_label: str | None = None   # "this evening", "today"


@dataclass(frozen=True)
class GreetingContext:
    time_of_day: str
    tone: str
    style: str
    presence_band: str
    special_day: str | None = None
    named_facts: list[NamedFact] = field(default_factory=list)
    goal_name: str | None = None
    streak_days: int = 0
    follow_up: str | None = None


@dataclass(frozen=True)
class _Item:
    tier: str
    category: str
    line: str                       # display phrasing (with emoji)
    advice: str | None = None
    reason_label: str = ""
    reason_detail: str = ""
    spoken: str = ""                # voice phrasing (emoji-free, relationship-softened) — Sprint 5b
    serious: bool = False           # a stacked concern (drives voice intensity)


def _cap(s: str) -> str:
    return s[:1].upper() + s[1:] if s else s


@dataclass(frozen=True)
class Greeting:
    salutation: str
    lines: list[str]
    category: str
    summary: str
    reasons: list[dict[str, str]] = field(default_factory=list)
    voice_lines: list[str] = field(default_factory=list)   # the fact lines only (for concise TTS)
    voice_segments: list[str] = field(default_factory=list)  # emoji-free, paced spoken phrasing (5b)
    voice_flags: dict = field(default_factory=dict)          # relationship/event/overdue → voice profile/intensity (5b)
    special_day: str | None = None
    tone: str = "supportive"
    encouragement: str = ""
    narration_source: str = "deterministic"


def _fact_item(f: NamedFact, ctx: GreetingContext) -> _Item:
    when = f.when_label or "today"
    if f.kind == "repay_due":
        return _Item(HIGH, "relationship", f"{f.person} is expected to return {f.amount} {when} 💸",
                     advice_for("repay_due", person=f.person), "Repayment due today", f"{f.person}: {f.amount}",
                     spoken=_cap(f"{f.person} is due to return {f.amount} {when}."))
    if f.kind == "repay_overdue":
        return _Item(HIGH, "relationship", f"{f.person}’s repayment of {f.amount} is overdue ⏰",
                     advice_for("repay_overdue", person=f.person), "Repayment overdue", f"{f.person}: {f.amount}",
                     spoken=_cap(f"{f.person} still hasn’t returned the {f.amount}. You may want to check in."),
                     serious=True)
    if f.kind == "income_today":
        if f.person:                                  # money from a person ("your father")
            line = _cap(f"{f.person} is expected to transfer {f.amount} {when} 💰")
            spoken = _cap(f"Looks like {f.person} may be sending {f.amount} {when}.")
            detail = f.person
        else:                                         # a generic source ("Salary")
            line = f"Your {f.label} should arrive {when} 💰"
            spoken = f"Your {f.label} should arrive {when}."
            detail = f.label or ""
        return _Item(HIGH, "financial", line, advice_for("income_today", goal=ctx.goal_name),
                     "Income expected today", detail, spoken=spoken)
    if f.kind == "event":
        tier, emoji, cat = _OCCASION.get(f.occasion or "custom", (MEDIUM, "📅", "event"))
        who = f" with {f.person}" if f.person else ""
        title = f": {f.title}" if f.title and not f.person else ""
        line = f"Your {f.occasion or 'plan'}{who} {when} {emoji}{title}".replace("  ", " ").strip()
        spoken = (_cap(f"Your {f.occasion or 'plan'}{who} is {when}.") if (f.occasion or who)
                  else _cap(f"You have {f.title} {when}.") if f.title else "Something is planned today.")
        return _Item(tier, cat, line, advice_for(f.occasion, person=f.person), f"{(f.occasion or 'event').title()} {when}",
                     f.title or (f.person or ""), spoken=spoken)
    return _Item(MEDIUM, "event", f.title or "Something’s planned today.", None, "Planned today", f.title or "",
                 spoken=(f"You have {f.title} {when}." if f.title else "Something is planned today."))


def _candidates(ctx: GreetingContext, seed: int) -> list[_Item]:
    items: list[_Item] = []
    if ctx.special_day:
        line = _pick(_CELEBRATION.get(ctx.special_day, ["Something worth celebrating today."]), seed)
        items.append(_Item(CRITICAL, "special_day", line + styles.flair(ctx.style),
                           reason_label="Milestone", reason_detail=ctx.special_day.replace("_", " "),
                           spoken=_CELEBRATION_SPOKEN.get(ctx.special_day, "Something worth celebrating today.")))
    for f in ctx.named_facts:
        items.append(_fact_item(f, ctx))
    if ctx.streak_days >= 2:
        items.append(_Item(MEDIUM, "streak", f"You’re on a {ctx.streak_days}-day budget streak 🔥",
                           reason_label="Budget streak", reason_detail=f"{ctx.streak_days} days",
                           spoken=f"You’re on a {ctx.streak_days}-day budget streak."))
    elif ctx.goal_name:
        items.append(_Item(MEDIUM, "goal", f"Your {ctx.goal_name} is moving in the right direction.",
                           reason_label="Goal on track", reason_detail=ctx.goal_name,
                           spoken=f"Your {ctx.goal_name} is moving in the right direction."))
    return items


def build_greeting(ctx: GreetingContext, *, seed: int, recent_categories: list[str] | None = None,
                   recent_encouragements: list[str] | None = None) -> Greeting:
    recent_cats = recent_categories or []
    recent_enc = recent_encouragements or []
    salutation = styles.salutation(_pick(_SALUTATIONS.get(ctx.time_of_day, ["Hello."]), seed), ctx.style)
    if ctx.style != "minimal" and (emoji := _TIME_EMOJI.get(ctx.time_of_day)):
        salutation = f"{salutation} {emoji}"

    items = _candidates(ctx, seed)
    # Rank by tier, then life-before-money within a tier. Dedup by category.
    items.sort(key=lambda it: (-_RANK.get(it.tier, 0), _CAT_ORDER.get(it.category, 9)))
    seen_cat: set[str] = set()
    ranked: list[_Item] = []
    for it in items:
        if it.category in seen_cat:
            continue
        seen_cat.add(it.category)
        ranked.append(it)

    # Category rotation: if the top item's theme led the last 2 days and it isn't
    # CRITICAL, promote a different fresh theme.
    if ranked and ranked[0].tier != CRITICAL and ranked[0].category in recent_cats[:2]:
        alt = next((i for i, it in enumerate(ranked) if it.category not in recent_cats[:2]), None)
        if alt:
            ranked.insert(0, ranked.pop(alt))

    cap = _DEPTH.get(ctx.presence_band, 2)
    show = ranked[:cap] if ranked else []
    if show and show[0].tier == CRITICAL:
        show = [show[0]]              # one focused CRITICAL celebration — no competing lines

    lines = [it.line for it in show]
    reasons = [{"label": it.reason_label, "detail": it.reason_detail} for it in show if it.reason_label]

    # Advice: only the top item's advice, and only for familiar+ users.
    if show and ctx.presence_band in ("familiar", "deeply_personalized") and show[0].advice:
        lines.append(show[0].advice)
    # Follow-up reference for the most-engaged users.
    if ctx.presence_band == "deeply_personalized" and ctx.follow_up:
        lines.append(ctx.follow_up)

    # Encouragement: rotate so it isn't the same line repeatedly.
    encouragement = ""
    if ctx.presence_band != "new":
        pool = [e for e in styles.encouragements(ctx.style) if e and e not in recent_enc] or styles.encouragements(ctx.style)
        encouragement = _pick(pool, seed + 5)
        if encouragement:
            lines.append(encouragement)

    if not show:                      # nothing notable — keep it gentle
        lines.insert(0, _pick(["Nothing pressing today — a good chance to plan.", "A steady day ahead."], seed))

    lead = show[0] if show else None
    category = lead.category if lead else "neutral"
    special = ctx.special_day if (lead and lead.category == "special_day") else None
    summary = f"{category}:{(lead.reason_detail if lead else 'neutral')}"
    voice_flags = {
        "relationship": any(it.category == "relationship" for it in show),
        "event": any(it.category == "event" for it in show),
        "overdue_count": sum(1 for it in show if it.serious),
    }
    return Greeting(salutation=salutation, lines=[s for s in lines if s], category=category, summary=summary,
                    reasons=reasons, voice_lines=[it.line for it in show],
                    voice_segments=[it.spoken for it in show if it.spoken], voice_flags=voice_flags,
                    special_day=special, tone=ctx.tone, encouragement=encouragement)
