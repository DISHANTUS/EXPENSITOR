"""Conversational advisor — a GENERAL intent layer (4b), not a command list.

Deterministic (no LLM): classify the question, route to the right engine/data,
answer with confidence + evidence refs, and when data is insufficient say so
explicitly. Engines that don't exist yet (full forecast = 4b-4, mood = S5)
answer honestly rather than faking it.
"""

from __future__ import annotations

import re
import uuid
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Expense, Receivable, SavingsGoal
from app.models.enums import ReceivableKind, ReceivableStatus, SavingsGoalKind, SavingsGoalStatus
from app.intelligence.budget import life_changes
from app.intelligence.companion import app_help
from app.intelligence.learning import lessons as _lessons
from app.schemas.advisor_chat import ChatContext, ChatOption, ChatTurn
from app.schemas.forecast import Forecast
from app.schemas.learning import CompanionRecap, FollowUpQuestion, ReflectionPrompt
from app.services import (
    advice_memory_service,
    analytics_service,
    calendar_service,
    companion_recap_service,
    explain_service,
    forecast_service,
    life_lesson_service,
    profile_mutation_service,
    reflection_service,
    settings_service,
    timeline_service,
)

_ZERO = Decimal("0")
_REPORT_HINTS = ("report", "how did i do", "spending", "summary", "analysis", "overview", "how am i doing")
_DRILL_FOLLOWUPS = [
    ChatOption(label="Red days", message="show red days"),
    ChatOption(label="Crown days", message="show crown days"),
    ChatOption(label="Subscriptions", message="show subscriptions"),
    ChatOption(label="Compare to previous", message="compare to previous"),
]
_FMT = analytics_service._fmt  # noqa: SLF001


def _ctx(session: ChatContext | None) -> ChatContext:
    return session or ChatContext()


def _answer(text: str, ctx: ChatContext, *, explain_ref: str | None = None, confidence: str | None = None,
            follow_ups: list[ChatOption] | None = None, kind: str = "answer") -> ChatTurn:
    new = ctx.model_copy(update={"last_explain_ref": explain_ref or ctx.last_explain_ref})
    return ChatTurn(type=kind, message=text, explain_ref=explain_ref, confidence=confidence,
                    follow_ups=follow_ups or [], session=new)


async def _data_days(db: AsyncSession, user_id: uuid.UUID) -> int:
    return await db.scalar(
        select(func.count(func.distinct(Expense.expense_date)))
        .where(Expense.user_id == user_id, Expense.deleted_at.is_(None))
    ) or 0


def _drill_period(session: ChatContext | None, today: date) -> tuple[date, date]:
    if session and session.period_from and session.period_to:
        return session.period_from, session.period_to
    return today.replace(day=1), today


def _drill_kind(t: str) -> tuple[str | None, str | None]:
    if "red day" in t:
        return "red_days", None
    if "crown" in t or "saved day" in t:
        return "crown_days", None
    if "subscription" in t:
        return "subscription", None
    if "emi" in t:
        return "emi", None
    if "loan" in t and "down" not in t:
        return "loan", None
    m = re.match(r"\s*(?:show|how much (?:did i|have i) (?:spend|spent)) (?:me )?(?:on )?(?:my )?(.+?)"
                 r"(?: spending| expenses| report)?\s*$", t)
    if m:
        term = m.group(1).strip()
        if term and term not in {"spending", "expenses", "expense", "report", "money", "budget", "it", "this"}:
            return "keyword", term
    return None, None


_CAPABILITY = (
    "I can talk through your money — and show you how to use the app. Ask me things like: "
    "“how do I set a budget?”, “where do I add an expense?”, “show me around”, "
    "“weekly/monthly report”, “compare this month to last”, “where is my money going?”, "
    "“show red days”, “who owes me money?”, “should I lend more to Ravi?”, "
    "“do I spend more on weekends?”, “when will I reach my goal?”, “what if I reduce food 10%?”, "
    "“can I afford a ₹60000 laptop in October?”, or “what do you know about me?”. "
    "If I don’t have enough data yet, I’ll say so."
)


def _name_after(patterns: list[str], t: str) -> str | None:
    for p in patterns:
        m = re.search(p, t)
        if m:
            return m.group(1).capitalize()
    return None


async def _recap(db, user_id, today, ctx) -> ChatTurn:
    """Structured Companion Recap (4b-5b) — Financial Identity + goals/habits/…"""
    days = await _data_days(db, user_id)
    recap = await companion_recap_service.build(db, user_id, today=today)
    fi = recap["financial_identity"]
    bits = []
    if fi["focus_areas"]:
        bits.append("focused on " + ", ".join(fi["focus_areas"]))
    if fi["strongest_habit"]:
        bits.append(f"strongest habit is {fi['strongest_habit'].lower()}")
    if fi["current_challenge"]:
        bits.append(f"current challenge is {fi['current_challenge'].lower()}")
    msg = ("Here’s what I know about you — " + "; ".join(bits) + "."
           if bits else f"Honestly, not much yet — I’ve only seen {days} day(s) of activity. Keep logging and I’ll learn.")
    conf = "high" if bits else "insufficient"
    return ChatTurn(type="recap", message=msg, recap=CompanionRecap.model_validate(recap),
                    confidence=conf, session=ctx)


async def _who_owes(db, user_id, today, ctx) -> ChatTurn:
    rows = (await db.execute(
        select(Receivable).where(Receivable.user_id == user_id, Receivable.deleted_at.is_(None),
                                 Receivable.status == ReceivableStatus.pending).order_by(Receivable.expected_date)
    )).scalars().all()
    if not rows:
        return _answer("No one owes you money right now — nothing outstanding.", ctx, confidence="high")
    cur = (await settings_service.get_settings(db, user_id)).base_currency
    parts = []
    for r in rows:
        overdue = (r.kind == ReceivableKind.one_time and r.expected_date and r.expected_date < today)
        parts.append(f"{r.source_name} — {_FMT(r.converted_amount, cur)}" + (" (overdue)" if overdue else ""))
    return _answer("Outstanding: " + "; ".join(parts) + ".", ctx, confidence="high")


async def _top_category(db, user_id, today, ctx) -> ChatTurn:
    cats = await analytics_service._category_sums(db, user_id, today.replace(day=1), today)  # noqa: SLF001
    if not cats:
        return _answer("No spending recorded this month yet — add some and I’ll show where it goes.",
                       ctx, confidence="insufficient")
    label, amount = max(cats.items(), key=lambda kv: kv[1])
    cur = (await settings_service.get_settings(db, user_id)).base_currency
    conf = await analytics_service._span_confidence(db, user_id)  # noqa: SLF001
    word = explain_service.confidence_word(conf) or "currently"
    return _answer(f"Most of your money {word} goes to {label} — {_FMT(amount, cur)} this month.",
                   ctx, explain_ref=f"category:{label}", confidence=conf,
                   follow_ups=[ChatOption(label="Show the expenses", message=f"show {label.lower()}")])


async def _weekend_habit(db, user_id, today, ctx) -> ChatTurn:
    start = today - timedelta(days=60)
    rows = (await db.execute(
        select(Expense.expense_date, Expense.converted_amount).where(
            Expense.user_id == user_id, Expense.deleted_at.is_(None), Expense.expense_date >= start)
    )).all()
    if len({d for d, _ in rows}) < 6:
        return _answer("I don’t have enough day-to-day history to judge weekends yet — ask again in a couple of weeks.",
                       ctx, confidence="insufficient")
    we = sum((a for d, a in rows if d.weekday() >= 5), _ZERO)
    wd = sum((a for d, a in rows if d.weekday() < 5), _ZERO)
    we_days = len({d for d, _ in rows if d.weekday() >= 5}) or 1
    wd_days = len({d for d, _ in rows if d.weekday() < 5}) or 1
    we_avg, wd_avg = we / we_days, wd / wd_days
    cur = (await settings_service.get_settings(db, user_id)).base_currency
    conf = await analytics_service._span_confidence(db, user_id)  # noqa: SLF001
    word = explain_service.confidence_word(conf) or "sometimes"
    if we_avg > wd_avg * Decimal("1.15"):
        msg = f"Yes — you {word} spend more on weekends ({_FMT(we_avg, cur)}/day vs {_FMT(wd_avg, cur)}/day on weekdays)."
    elif we_avg < wd_avg * Decimal("0.85"):
        msg = f"Actually no — weekends are lighter ({_FMT(we_avg, cur)}/day vs {_FMT(wd_avg, cur)}/day weekdays)."
    else:
        msg = f"They’re about even — {_FMT(we_avg, cur)}/day weekends vs {_FMT(wd_avg, cur)}/day weekdays."
    return _answer(msg, ctx, confidence=conf)


# --- forecasting (4b-4) -------------------------------------------------------
_FORECAST_HINTS = (
    "when will i", "reach my goal", "can i reach", "what is slowing", "what's slowing", "whats slowing",
    "how much should i save", "what if", "what happens if", "if i keep spending", "if i continue",
    "spend like this", "show future me", "future me", "compare goal", "opportunity cost",
    "recovery plan", "biggest obstacle", "save more", "afford my goal", "forecast",
    "can i afford", "can i buy", "can i move", "never return", "never repay", "never pay",
    "cancel my subscription", "stop my subscription", "stop this subscription",
)

_MONTHS = {"january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6, "july": 7,
           "august": 8, "september": 9, "october": 10, "november": 11, "december": 12}


def _levers_from_text(t: str) -> list[str]:
    """Map free text to round-trippable lever refs (the same refs the chips send)."""
    refs: list[str] = []
    for m in re.finditer(r"(?:reduce|cut|lower|trim|less)\s+(?:my\s+|on\s+|spending on\s+)?"
                         r"([a-z &]+?)\s+(?:spending\s+)?(?:by\s+)?(\d{1,2})\s*%", t):
        cat = m.group(1).strip().strip("&").strip()
        if cat and cat not in {"spending", "it", "this", "everything"}:
            refs.append(f"category:{cat.title()}:-{m.group(2)}")
    m = re.search(r"save\s+(?:an?\s+(?:extra|additional)\s+)?(?:₹|rs\.?\s*)?(\d{3,})", t)
    if m:
        refs.append(f"save:+{m.group(1)}")
    if re.search(r"(?:cancel|stop|drop)\s+(?:my\s+)?(?:all\s+)?subscription", t):
        refs.append("sub:*:cancel")
    else:
        m = re.search(r"(?:cancel|stop|drop)\s+(?:my\s+)?([a-z][a-z ]*?)\s+subscription", t)
        if m:
            refs.append(f"sub:{m.group(1).strip().title()}:cancel")
    m = re.search(r"if\s+([a-z]+)\s+(?:never|doesn'?t|does not|won'?t)\s+(?:return|returns|repay|repays|pay|pays)", t)
    if m:
        refs.append(f"recv:{m.group(1).title()}:default")
    if "keep spending" in t or "if i continue" in t or "spend like this" in t:
        refs.append("spending:current")
    return refs


def _life_event_from_text(t: str, today: date) -> tuple[Decimal | None, date | None, str | None]:
    if not any(p in t for p in ("can i afford", "can i buy", "can i move", "afford a", "afford this", "afford the")):
        return None, None, None
    etype = "purchase" if "buy" in t else ("move" if "move" in t else "trip")
    cm = re.search(r"(?:₹|rs\.?\s*)?(\d{4,})", t.replace(",", ""))
    cost = Decimal(cm.group(1)) if cm else None
    tdate: date | None = None
    for name, mon in _MONTHS.items():
        if name in t:
            year = today.year if mon >= today.month else today.year + 1
            tdate = date(year, mon, 28)
            break
    if tdate is None and "next year" in t:
        tdate = date(today.year + 1, today.month, min(today.day, 28))
    return cost, tdate, etype


def _forecast_turn(fc: Forecast) -> ChatTurn:
    return ChatTurn(type="forecast", forecast=fc, explain_ref=fc.explain_ref,
                    confidence=fc.confidence, follow_ups=fc.follow_ups, session=fc.session)


# --- learning loop (4b-5a) ----------------------------------------------------
_RECALL_PATTERNS = [
    r"what did (?:you|we) (?:tell|say|talk to me)(?: me)?.*?about (.+)",
    r"what did we discuss about (.+)",
    r"do you remember (?:about |what.*?about )?(.+)",
    r"remind me (?:about|what.*?about) (.+)",
    r"what do you remember about (.+)",
]
_CHECKIN_HINTS = ("check in", "check-in", "checkin", "follow up", "follow-up", "any update",
                  "anything to update", "anything to tell you", "what should i tell you", "any check")


def _recall_subject(t: str) -> str | None:
    for p in _RECALL_PATTERNS:
        m = re.search(p, t)
        if m:
            subj = m.group(1).strip().strip("?.! ")
            for pre in ("my ", "the ", "our "):
                if subj.startswith(pre):
                    subj = subj[len(pre):]
            return subj or None
    return None


def _recall_message(recall: dict) -> str:
    items = recall.get("items", [])
    about = recall.get("about")
    if not items:
        return (f"I don’t have anything recorded about {about} yet." if about
                else "I haven’t given you any tracked advice yet — ask me for a forecast or about someone you’ve lent to.")
    lines = []
    for it in items[:4]:
        when = f" ({it['when']})" if it.get("when") else ""
        if it.get("answer"):
            verdict = {"yes": "you said it worked", "partial": "you said partial progress",
                       "no": "you said it didn’t happen"}.get(it["answer"], f"you said {it['answer']}")
            extra = f" — {it['circumstance'].replace('_', ' ')}" if it.get("circumstance") else ""
            lines.append(f"• {it['claim']}{when}: {verdict}{extra}.")
        else:
            lines.append(f"• {it['claim']}{when}: still open.")
    head = f"Here’s what we talked about regarding {about}:" if about else "Here’s what we’ve talked about:"
    return head + "\n" + "\n".join(lines)


def _followup_turn(question: dict, ctx: ChatContext) -> ChatTurn:
    return ChatTurn(type="follow_up", follow_up=FollowUpQuestion.model_validate(question), session=ctx)


# --- lessons / reflection / accuracy (4b-5b) ---------------------------------
_TEACH_PATTERNS = [
    r"remember that (.+)",
    r"note that (.+)",
    r"i overspent because (.+)",
    r"lesson:\s*(.+)",
    r"i (?:always |often |tend to |keep )?(?:overspend|struggle|get caught) (?:with|on|because|by) (.+)",
]
_FORGET_PATTERNS = [
    r"forget (?:that |about )?(.+?)(?: lesson)?$",
    r"delete (?:the |my )?(.+?) lesson",
]
_ACCURACY_HINTS = ("how accurate", "prediction accuracy", "forecast accuracy", "how reliable are your",
                   "how good are your forecast", "are your forecasts accurate")
_REFLECT_HINTS = ("reflect", "reflection", "what helped me", "how did i do this month")
# Memory search (7) — deterministic search over the life timeline.
_MEMORY_HINTS = ("what happened in", "everything involving", "everything about", "show everything",
                 "show me everything", "my achievements", "show my achievement", "what lessons",
                 "lessons have i learned", "show my lessons", "what lessons have i", "when did i start",
                 "timeline with", "relationship timeline", "show my timeline")


def _teach_text(t: str) -> str | None:
    for p in _TEACH_PATTERNS:
        m = re.search(p, t)
        if m:
            return m.group(1).strip().strip(".! ")
    return None


def _forget_text(t: str) -> str | None:
    for p in _FORGET_PATTERNS:
        m = re.search(p, t)
        if m:
            txt = m.group(1).strip().strip(".! ")
            for pre in ("my ", "the ", "that "):
                if txt.startswith(pre):
                    txt = txt[len(pre):]
            return txt or None
    return None


async def _goal_answer(db, user_id, today, ctx, *, message: str) -> ChatTurn:
    cost, tdate, etype = _life_event_from_text(message, today)
    if any(p in message for p in ("can i afford", "can i buy", "can i move", "afford a", "afford this")) \
            and (cost is None or tdate is None):
        return _answer("Tell me the amount and roughly when, e.g. “can I afford a ₹60000 laptop in October”.",
                       ctx, confidence="high")
    fc = await forecast_service.forecast(
        db, user_id, question=message, levers=_levers_from_text(message),
        expected_cost=cost, target_date=tdate, event_type=etype, session=ctx)
    return _forecast_turn(fc)


async def chat(db: AsyncSession, user_id: uuid.UUID, *, message: str, session: ChatContext | None) -> ChatTurn:
    today = await calendar_service.user_today(db, user_id)
    t = message.lower().strip()
    ctx = _ctx(session)

    # --- conversational profile mutation (Phase 5): tell Advary about life changes ---
    if ctx.pending_profile_text:
        if re.search(r"\b(yes|yeah|yep|sure|go ahead|do it|apply|confirm|update|okay|ok)\b", t):
            result = await profile_mutation_service.apply(db, user_id, ctx.pending_profile_text)
            return ChatTurn(type="profile_updated", message=result.message, confidence="high",
                            session=ctx.model_copy(update={"pending_profile_text": None}))
        if re.search(r"\b(no|nope|cancel|never ?mind|don'?t|stop)\b", t):
            return _answer("Okay, I won't change anything.",
                           ctx.model_copy(update={"pending_profile_text": None}), confidence="high")
    if life_changes.parse(message, today):
        proposal = await profile_mutation_service.propose(db, user_id, message)
        return ChatTurn(type="profile_preview", message=proposal.preview, confidence="high",
                        follow_ups=[ChatOption(label="Yes, update", message="yes, update my profile"),
                                    ChatOption(label="No", message="no, leave it")],
                        session=ctx.model_copy(update={"pending_profile_text": message}))

    # --- teach the app: launch the tour / answer "how do I…" (works by voice too) ---
    if app_help.wants_tour(t):
        return ChatTurn(type="tour", message="Sure — let me show you around.", route="/home", session=ctx)
    _help = app_help.how_to(t)
    if _help is not None:
        return ChatTurn(type="help", message=_help.message, route=_help.route, confidence="high",
                        follow_ups=[ChatOption(label="Show me around", message="show me around")], session=ctx)

    # --- the AI itself ---
    if any(p in t for p in ("what can you do", "what do you do", "how can you help", "help me")):
        return _answer(_CAPABILITY, ctx)
    if "know about me" in t or "what do you know" in t:
        return await _recap(db, user_id, today, ctx)
    if any(p in t for p in ("why are you worried", "why are you happy", "why are you", "how are you feeling",
                            "how do you feel", "your mood", "what mood", "how are you doing")):
        ex = await explain_service.explain(db, user_id, ref="mood:current", session=ctx)
        msg = ex.claim + (("\n" + ex.reasoning) if ex.reasoning else "")
        return ChatTurn(type="advisory", message=msg, explain_ref="mood:current", confidence=ex.confidence,
                        follow_ups=[ChatOption(label="Show evidence", message="why")],
                        session=ctx.model_copy(update={"last_explain_ref": "mood:current"}))
    if t in ("why", "why?", "why did you say that", "why does that matter", "why does this matter", "explain") \
            and ctx.last_explain_ref:
        ex = await explain_service.explain(db, user_id, ref=ctx.last_explain_ref, session=ctx)
        return ChatTurn(type="advisory", message=ex.why_it_matters or ex.reasoning, explain_ref=ctx.last_explain_ref,
                        confidence=ex.confidence, session=ctx)

    # --- learning loop: teach / forget / recall / check-ins / reflection / accuracy ---
    forget_text = _forget_text(t) if t.startswith(("forget", "delete")) else None
    if forget_text is not None:
        lessons = await life_lesson_service.list_(db, user_id, today=today)
        terms = set(forget_text.lower().split())
        cat = _lessons.classify_category(forget_text)
        match = next((lr for lr in lessons
                      if lr["category"] == cat or terms & set((lr["lesson"] + " " + lr["category"]).lower().split())),
                     None)
        if match:
            await life_lesson_service.forget(db, user_id, uuid.UUID(match["id"]))
            return _answer(f"Done — I’ve forgotten that lesson about {match['category'].replace('_', ' ')}. "
                           "You can ask me to restore it later.", ctx, confidence="high")
        return _answer("I couldn’t find a matching lesson to forget. Ask “what do you know about me?” to see what I hold.",
                       ctx, confidence="high")

    teach_text = _teach_text(t)
    if teach_text is not None:
        row = await life_lesson_service.teach(db, user_id, source_text=teach_text, today=today)
        return _answer(f"Got it — I’ll remember that ({row.confidence} confidence so far). "
                       f"{row.lesson}", ctx, confidence="high")

    subject = _recall_subject(t)
    if subject is not None:
        recall = await advice_memory_service.recall(db, user_id, about=subject, today=today)
        return _answer(_recall_message(recall), ctx, confidence="high" if recall["items"] else "insufficient")
    if any(h in t for h in _CHECKIN_HINTS):
        due = await advice_memory_service.due_follow_ups(db, user_id, today=today)
        if due:
            return _followup_turn(due[0], ctx)
        return _answer("Nothing to check in on right now — I’ll ask when one of my suggestions is due a review.",
                       ctx, confidence="high")
    if any(h in t for h in _ACCURACY_HINTS):
        acc = await advice_memory_service.prediction_accuracy(db, user_id, today=today)
        return _answer(acc["note"], ctx, confidence="high" if acc["tracked"] else "insufficient")
    if any(h in t for h in _REFLECT_HINTS):
        prompt = await reflection_service.monthly_reflection(db, user_id, today=today)
        if prompt:
            return ChatTurn(type="reflection", reflection=ReflectionPrompt.model_validate(prompt), session=ctx)
        return _answer("Nothing stands out to reflect on this month yet — keep going and I’ll check back.",
                       ctx, confidence="high")

    # --- memory search (7): deterministic search over the life timeline ---
    if any(h in t for h in _MEMORY_HINTS):
        entries, spec = await timeline_service.search(db, user_id, q=message)
        summary = timeline_service.summarize_search(spec, entries)
        if not entries:
            return _answer(summary, ctx, confidence="high")
        lines = [f"• {e.icon} {e.title}" + (f" ({e.date.isoformat()})" if e.date else "") for e in entries[:6]]
        return _answer(summary + "\n" + "\n".join(lines), ctx, confidence="high")

    # --- people / lending ---
    if any(p in t for p in ("who owes", "owes me", "who needs to pay", "owe me")):
        return await _who_owes(db, user_id, today, ctx)
    name = _name_after([r"lend (?:more )?(?:money )?to (\w+)", r"should i (?:lend|trust) (\w+)",
                        r"how much did (\w+) (?:borrow|owe)", r"is (\w+) reliable",
                        r"about (\w+)", r"(\w+)'s (?:history|reliability|trust)"], t)
    if name and any(w in t for w in ("lend", "borrow", "owe", "reliable", "trust", "about", "history")):
        ex = await explain_service.explain(db, user_id, ref=f"relationship:{name}", session=ctx)
        # Remember this lending advice so we can follow up on the repayment (4b-5a).
        await advice_memory_service.record_advice(
            db, user_id, kind="relationship", subject_type="person", subject_label=name,
            claim=ex.claim, today=today)
        return ChatTurn(type="advisory", message=ex.claim, explain_ref=f"relationship:{name}",
                        confidence=ex.confidence,
                        follow_ups=[ChatOption(label="Show evidence", message="why")],
                        session=ctx.model_copy(update={"last_explain_ref": f"relationship:{name}"}))

    # --- spending shape ---
    if any(p in t for p in ("where is my money", "where's my money", "where does my money", "what hurts my savings",
                            "biggest category", "what category", "what did i waste", "most of my money")):
        return await _top_category(db, user_id, today, ctx)
    if any(p in t for p in ("why am i spending more", "what changed", "spending more recently")):
        report = await analytics_service.build_comparison(db, user_id, kind="month", ref="this", today=today)
        return ChatTurn(type="comparison", report=report, explain_ref="impact:red_days", confidence=report.confidence,
                        follow_ups=[ChatOption(label="Show red days", message="show red days")],
                        session=ctx.model_copy(update={"last_kind": "month", "last_ref": "this",
                                                       "period_from": report.period_from, "period_to": report.period_to}))

    # --- habits ---
    if "weekend" in t:
        return await _weekend_habit(db, user_id, today, ctx)
    if any(p in t for p in ("am i improving", "getting better", "am i doing better")):
        cur = await analytics_service.build_comparison(db, user_id, kind="month", ref="this", today=today)
        d = cur.delta
        if d and d.saved_change_pct is not None:
            better = d.saved_change_pct >= 0
            return _answer(f"{'Yes' if better else 'Not quite'} — savings {'up' if better else 'down'} "
                           f"{abs(d.saved_change_pct):.0f}% vs last month.", ctx, confidence=cur.confidence)
        return _answer("I need a couple of months side by side before I can say — ask again later.",
                       ctx, confidence="insufficient")

    # --- goals / forecasting (4b-4): ETAs, what-if levers, opportunity cost, Future Me ---
    if any(h in t for h in _FORECAST_HINTS):
        return await _goal_answer(db, user_id, today, ctx, message=t)

    # --- comparison ---
    if any(w in t for w in ("compare", "versus", " vs ", "difference")):
        kind = "month" if "month" in t else "week"
        if ctx.last_kind and "previous" in t:
            kind = ctx.last_kind
        ref = "last" if any(w in t for w in ("last", "previous")) else "this"
        report = await analytics_service.build_comparison(db, user_id, kind=kind, ref=ref, today=today)
        return ChatTurn(type="comparison", report=report, confidence=report.confidence,
                        follow_ups=[ChatOption(label="Red days", message="show red days")],
                        session=ctx.model_copy(update={"last_kind": kind, "last_ref": ref,
                                                       "period_from": report.period_from, "period_to": report.period_to}))

    # --- drilldowns ---
    if "show" in t or "day" in t or t.startswith("how much"):
        dkind, arg = _drill_kind(t)
        if dkind is not None:
            start, end = _drill_period(session, today)
            result = await analytics_service.drilldown(db, user_id, kind=dkind, arg=arg, start=start, end=end, today=today)
            ref = f"impact:{dkind}" if dkind in ("red_days", "crown_days") else None
            return ChatTurn(type="drilldown", drilldown=result, explain_ref=ref, follow_ups=_DRILL_FOLLOWUPS,
                            session=ctx.model_copy(update={"last_explain_ref": ref or ctx.last_explain_ref}))

    # --- reports (week/month) ---
    is_report = any(h in t for h in _REPORT_HINTS)
    kind = "month" if "month" in t else ("week" if "week" in t else None)
    ref = "last" if any(w in t for w in ("last", "previous")) else ("this" if any(w in t for w in ("this", "current", "so far")) else None)

    if is_report and kind is None:
        return ChatTurn(type="clarify", message="Which report would you like?",
                        options=[ChatOption(label="Weekly", message="weekly report"),
                                 ChatOption(label="Monthly", message="monthly report")], session=ctx)
    if kind is not None and ref is None:
        unit = "week" if kind == "week" else "month"
        return ChatTurn(type="clarify", message=f"Which {unit}?",
                        options=[ChatOption(label=f"Last {unit}", message=f"last {unit} report"),
                                 ChatOption(label=f"This {unit} so far", message=f"this {unit} report")], session=ctx)
    if kind is not None and ref is not None:
        start, end, label, gran = analytics_service.resolve_period(kind, ref, today)
        report = await analytics_service.build_report(db, user_id, kind=kind, start=start, end=end, label=label,
                                                      granularity=gran, today=today)
        new_ctx = ctx.model_copy(update={"last_kind": kind, "last_ref": ref, "period_from": start, "period_to": end})
        if report.confidence == "insufficient":
            return _answer(f"I don’t have enough activity for {label} yet — add some and ask again.", new_ctx,
                           confidence="insufficient")
        return ChatTurn(type="report", report=report,
                        follow_ups=[ChatOption(label="Last week", message="last week report"),
                                    ChatOption(label="This month", message="this month report")], session=new_ctx)

    # --- honest fallback ---
    days = await _data_days(db, user_id)
    if days == 0:
        return _answer("I don’t have any activity to go on yet. Add an expense or income and ask me again.",
                       ctx, confidence="insufficient")
    return _answer("I’m not sure how to answer that one yet. Try “weekly report”, “where is my money going?”, "
                   "“who owes me money?”, or “show red days”.", ctx,
                   follow_ups=[ChatOption(label="What can you do?", message="what can you do")])
