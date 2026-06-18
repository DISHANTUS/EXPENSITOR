"""Natural-Language Action Layer (Phase 2) — the operational interface.

Deterministic parse → resolve → clarify → preview → confirm → execute (via the
existing services) → verify → advisor-style response. The parser is authoritative;
mutations always require confirmation; nothing is forced (user-is-king). Audit via
companion_event. No LLM.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, time, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.intelligence.advisor import phrasing as ph
from app.intelligence.advisor.context_block import build_context
from app.intelligence.commentary import ActionPreview
from app.intelligence.commentary import context as ctxmod
from app.intelligence.nlp import parser as nlp
from app.models import Category, CompanionEvent, PlannedExpense, Receivable, SavingsGoal, UserSettings
from app.models.enums import (
    CompanionEntityType,
    CompanionEventType,
    IncomeSourceType,
    OccasionType,
    PlannedExpenseStatus,
    ReceivableStatus,
    RecommendationAction,
    RejectionReason,
    SavingsGoalKind,
    SavingsGoalStatus,
)
from app.schemas.expense import ExpenseCreate
from app.schemas.income import IncomeCreate
from app.schemas.planned_expense import PlannedExpenseUpdate
from app.schemas.receivable import ReceivableCreate
from app.schemas.savings import SavingsGoalCreate, SavingsGoalUpdate
from app.services import (
    commentary_service,
    decision_service,
    event_service,
    expense_service,
    income_service,
    planned_expense_service,
    preference_service,
    projection_service,
    receivables_service,
    recommendation_service,
    savings_service,
)
from app.services.exceptions import InvalidOperationError, ResourceNotFoundError

_OCCASION_VALUES = {o.value for o in OccasionType}
_REJECT_RE = ("can't move", "cannot move", "won't move", "can not move", "keep the date", "don't move", "keep the outing")


async def _today(db: AsyncSession, user_id: uuid.UUID) -> date:
    tz = await db.scalar(select(UserSettings.timezone).where(UserSettings.user_id == user_id))
    from zoneinfo import ZoneInfo
    return datetime.now(ZoneInfo(tz or "UTC")).date()


async def _category_names(db: AsyncSession, user_id: uuid.UUID) -> set[str]:
    rows = (await db.execute(select(Category.name).where((Category.user_id == user_id) | (Category.user_id.is_(None))))).all()
    return {r[0] for r in rows}


async def _category_id(db: AsyncSession, user_id: uuid.UUID, name: str | None) -> uuid.UUID | None:
    if not name:
        return None
    return await db.scalar(
        select(Category.id).where(Category.name == name, (Category.user_id == user_id) | (Category.user_id.is_(None))).limit(1)
    )


def _coerce_answers(fields: dict[str, Any], answers: dict[str, Any] | None) -> None:
    if not answers:
        return
    for key, val in answers.items():
        if val is None or val == "":
            continue
        if key == "amount":
            fields["amount"] = Decimal(str(val))
        elif key == "date":
            fields["date"] = date.fromisoformat(val) if isinstance(val, str) else val
        elif key == "exact_time":
            fields["exact_time"] = time.fromisoformat(val) if isinstance(val, str) else val
        elif key == "target_id":
            fields["target_id"] = uuid.UUID(str(val))
        else:
            fields[key] = val


def _question(field_name: str) -> dict[str, Any]:
    prompts = {
        "amount": "How much?", "date": "For which date?", "source_name": "Who is it from?",
        "target_id": "Which one did you mean?", "category": "Which category?",
    }
    return {"field": field_name, "prompt": prompts.get(field_name, f"Please provide {field_name}."),
            "why": "Needed to complete this action accurately."}


def _candidate(intent: str, fields: dict[str, Any], reason_context: str | None = None) -> dict[str, Any]:
    out: dict[str, Any] = {"intent": intent, "reason_context": reason_context}
    for k, v in fields.items():
        if isinstance(v, (date, time)):
            out[k] = v.isoformat()
        elif isinstance(v, Decimal):
            out[k] = str(v)
        elif isinstance(v, uuid.UUID):
            out[k] = str(v)
        else:
            out[k] = v
    return out


# --------------------------------------------------------------------------- #
async def _build_outcome(db: AsyncSession, user_id: uuid.UUID, summary: str, today: date, *, why: str) -> dict[str, Any]:
    """The advisor-thinking success contract — surfaces the useful numbers so the
    user never calculates anything, and explains the whole-month picture."""
    scenario = await projection_service.get_scenario(db, user_id, today=today)
    guidance, risk = await projection_service.compute_guidance_and_risk(db, user_id, today=scenario.today)
    ctx = build_context(scenario, guidance).as_dict()

    goals = (await db.execute(
        select(SavingsGoal).where(SavingsGoal.user_id == user_id, SavingsGoal.deleted_at.is_(None),
                                  SavingsGoal.status == SavingsGoalStatus.active))).scalars().all()
    behind = []
    for g in goals:
        if g.kind == SavingsGoalKind.custom_goal and g.target_date is not None and g.target_date <= scenario.horizon:
            st = savings_engine_eval_custom(scenario, g)
            if st == "behind":
                behind.append(g.name)
    goal_impact = ("This doesn't set back your savings goals." if not behind
                   else f"Watch: behind on {', '.join(behind)}.")

    risk_note = ("Your risk level stays low." if risk.risk_level in ("none", "low")
                 else f"Heads up — risk level is {risk.risk_level}.")
    plans_impact = ("No upcoming plans are affected." if not scenario.overdue_receivables and risk.risk_level != "critical"
                    else "Some upcoming plans may be tight.")

    cur = scenario.base_currency
    next_income = None
    if ctx["next_income_date"]:
        when = ctx["next_income_date"]
        tail = ctx.get("income_time_exact") or ctx.get("income_time_window")
        amt = ph.money(Decimal(ctx["next_income_amount"]), cur) if ctx.get("next_income_amount") else None
        next_income = f"Next expected income: {amt} on {when}" + (f" around {tail}." if tail else ".")

    most_useful = f"You have about {ph.money(guidance.safe_daily_spending, cur)} available for the rest of today."
    return {
        "what_changed": summary,
        "why": why,
        "safe_or_risky": risk_note,
        "daily_budget": f"{ph.money(guidance.safe_daily_spending, cur)} left today",
        "weekly_budget": f"{ph.money(guidance.safe_weekly_spending, cur)} this week",
        "monthly_discretionary": (f"{ph.money(Decimal(ctx['monthly_discretionary_remaining']), cur)} left under your monthly limit"
                                  if ctx.get("monthly_discretionary_remaining") else None),
        "savings_goal_impact": goal_impact,
        "upcoming_plans_impact": plans_impact,
        "next_income": next_income,
        "most_useful_number": most_useful,
        "context": ctx,
    }


def savings_engine_eval_custom(scenario, goal) -> str:
    from app.intelligence.savings import engine as se
    return se.evaluate_custom_goal(scenario, target_amount=goal.converted_amount, target_date=goal.target_date).status


# --------------------------------------------------------------------------- #
async def _resolve_target(db, user_id, intent, fields, today):
    """Resolve which event/goal/receivable. Returns (row, clarification_or_None)."""
    label = fields.get("target_label")
    target_id = fields.get("target_id")

    if intent == nlp.MOVE_EVENT:
        stmt = select(PlannedExpense).where(
            PlannedExpense.user_id == user_id, PlannedExpense.deleted_at.is_(None),
            PlannedExpense.status == PlannedExpenseStatus.planned, PlannedExpense.occasion_type.is_not(None))
        if label and label in _OCCASION_VALUES:
            stmt = stmt.where(PlannedExpense.occasion_type == OccasionType(label))
        rows = (await db.execute(stmt.order_by(PlannedExpense.planned_date))).scalars().all()
        return _pick(rows, target_id, "event", lambda r: f"{r.title} on {r.planned_date.isoformat()}")
    if intent == nlp.CHANGE_SAVINGS_TARGET:
        stmt = select(SavingsGoal).where(SavingsGoal.user_id == user_id, SavingsGoal.deleted_at.is_(None),
                                         SavingsGoal.status == SavingsGoalStatus.active)
        if label:
            stmt = stmt.where(SavingsGoal.name.ilike(f"%{label}%"))
        rows = (await db.execute(stmt)).scalars().all()
        return _pick(rows, target_id, "savings goal", lambda r: r.name)
    if intent == nlp.MARK_RECEIVABLE_RECEIVED:
        stmt = select(Receivable).where(Receivable.user_id == user_id, Receivable.deleted_at.is_(None),
                                        Receivable.status == ReceivableStatus.pending)
        if label:
            stmt = stmt.where(Receivable.source_name.ilike(f"%{label}%"))
        rows = (await db.execute(stmt)).scalars().all()
        return _pick(rows, target_id, "receivable", lambda r: f"{r.source_name} ({r.converted_amount})")
    return None, None


def _pick(rows, target_id, kind, labeler):
    if target_id is not None:
        row = next((r for r in rows if r.id == target_id), None)
        return (row, None) if row else (None, _clarify_missing(kind))
    if not rows:
        return None, _clarify_missing(kind)
    if len(rows) == 1:
        return rows[0], None
    options = [{"target_id": str(r.id), "label": labeler(r)} for r in rows]
    return None, {"type": "clarification",
                  "questions": [{"field": "target_id", "prompt": f"Which {kind}?", "options": options,
                                 "why": "Several match — pick one."}]}


def _clarify_missing(kind):
    return {"type": "clarification",
            "questions": [{"field": "target_id", "prompt": f"I couldn't find that {kind}. Which one?",
                           "options": [], "why": f"No matching {kind} found."}]}


# --------------------------------------------------------------------------- #
async def act(db: AsyncSession, user_id: uuid.UUID, *, text: str, confirm: bool = False,
              answers: dict[str, Any] | None = None, request_id: str | None = None,
              today: date | None = None) -> dict[str, Any]:
    today = today or await _today(db, user_id)
    low = text.lower()
    if any(p in low for p in _REJECT_RE):
        return await _handle_reject(db, user_id, today)

    pr = nlp.parse(text, today=today, valid_category_names=await _category_names(db, user_id))
    if pr.intent == nlp.UNKNOWN:
        return {"type": "unsupported",
                "message": "I couldn't read that as an action. Try e.g. 'add ₹250 lunch', "
                           "'move outing to Jul 18', 'father will give ₹15,000 on Jun 20 evening'."}

    fields = dict(pr.fields)
    _coerce_answers(fields, answers)

    if pr.intent == nlp.BUY_DECISION:
        return await _handle_buy(db, user_id, fields, answers, today)

    if request_id and confirm and await _already_done(db, user_id, request_id):
        return {"type": "result", "idempotent_replay": True, "message": "Already done."}

    target = None
    if pr.intent in (nlp.MOVE_EVENT, nlp.CHANGE_SAVINGS_TARGET, nlp.MARK_RECEIVABLE_RECEIVED):
        target, clar = await _resolve_target(db, user_id, pr.intent, fields, today)
        if clar:
            return clar

    missing = [m for m in pr.missing if fields.get(m) in (None, "")]
    if missing:
        return {"type": "clarification", "questions": [_question(m) for m in missing],
                "candidate": _candidate(pr.intent, fields, pr.reason_context)}

    # move_event needs a date; if absent, suggest safer dates instead of assuming
    if pr.intent == nlp.MOVE_EVENT and fields.get("date") is None:
        resched = await event_service.analyze_reschedule(db, user_id, target.id, today=today)
        opts = [{"date": c.date.isoformat(), "label": f"{c.date.isoformat()} (score {c.score})"}
                for c in resched.candidates if c.affordable][:5]
        return {"type": "clarification",
                "questions": [{"field": "date", "prompt": "Which date should I move it to?",
                               "options": opts, "why": "These dates keep your balance healthiest."}],
                "candidate": _candidate(pr.intent, fields, pr.reason_context)}

    if not confirm:
        return await _preview(db, user_id, pr, fields, target, today)
    return await _execute(db, user_id, pr, fields, target, today, request_id)


# --- preview ----------------------------------------------------------------
# A6: per-intent "what would change / what would stay the same" — standalone
# sentences so they compose cleanly after the summary (always-true, honest).
_PREVIEW_EFFECT = {
    nlp.ADD_EXPENSE: ("It would record this against today's budget.",
                      "Your upcoming plans and savings goals stay the same."),
    nlp.ADD_INCOME: ("It would record this as income you've received, so your available budget goes up.",
                     "Your spending plan and savings goals stay the same."),
    nlp.ADD_RECEIVABLE: ("It would add this to your expected income, so future planning accounts for it.",
                         "Nothing you've already planned changes."),
    nlp.MARK_RECEIVABLE_RECEIVED: ("It would mark this money as received.",
                                   "Your planned spending stays the same."),
    nlp.MOVE_EVENT: ("It would change only the date, not the amount.",
                     "The budget stays the same — only the date changes."),
    nlp.CHANGE_SAVINGS_TARGET: ("It would update this savings target.",
                                "Your day-to-day spending plan stays the same."),
    nlp.CREATE_SAVINGS_GOAL: ("It would set this savings goal.",
                              "Your day-to-day spending plan stays the same."),
}


async def _preview(db, user_id, pr, fields, target, today) -> dict[str, Any]:
    cur = await db.scalar(select(UserSettings.base_currency).where(UserSettings.user_id == user_id)) or "INR"
    c = fields.get("currency") or cur
    amt = ph.money(fields["amount"], c) if fields.get("amount") is not None else ""
    on = (f" on {fields['date'].isoformat()}" if fields.get("date") else "")
    cat = (f" ({fields['category']})" if fields.get("category") else "")
    summaries = {
        nlp.ADD_EXPENSE: lambda: f"Add a {amt} expense{cat} on {(fields.get('date') or today).isoformat()}.",
        nlp.ADD_INCOME: lambda: f"Record {amt} income on {(fields.get('date') or today).isoformat()}.",
        nlp.ADD_RECEIVABLE: lambda: f"Track {amt} expected from {fields['source_name']}{on}.",
        nlp.MARK_RECEIVABLE_RECEIVED: lambda: f"Mark {target.source_name}'s {ph.money(target.converted_amount, cur)} as received.",
        nlp.MOVE_EVENT: lambda: f"Move '{target.title}' to {fields['date'].isoformat()}.",
        nlp.CHANGE_SAVINGS_TARGET: lambda: f"Change '{target.name}' target to {amt}.",
        nlp.CREATE_SAVINGS_GOAL: lambda: f"Set a {fields.get('kind', 'monthly_target')} of {amt}.",
    }
    summary = summaries[pr.intent]()
    change, stay = _PREVIEW_EFFECT.get(pr.intent, ("It would apply this change.", "The rest of your plan stays the same."))
    preview = ActionPreview(summary=summary, would_change=change, would_stay_same=stay)
    commentary = await commentary_service.narrate(
        db, user_id, trigger=ctxmod.ACTION_PREVIEW, today=today, action_preview=preview)
    return {"type": "preview", "action": _candidate(pr.intent, fields, pr.reason_context),
            "summary": summary, "requires_confirmation": True, "commentary": commentary,
            "note": "Confirm to apply. I'll then show the full impact."}


# --- execute + verify + respond ---------------------------------------------
async def _execute(db, user_id, pr, fields, target, today, request_id) -> dict[str, Any]:
    cur = await db.scalar(select(UserSettings.base_currency).where(UserSettings.user_id == user_id)) or "INR"
    currency = fields.get("currency") or cur
    intent = pr.intent
    try:
        if intent == nlp.ADD_EXPENSE:
            cat_id = await _category_id(db, user_id, fields.get("category"))
            row = await expense_service.create(db, user_id, ExpenseCreate(
                original_amount=fields["amount"], original_currency=currency,
                expense_date=fields.get("date") or today, category_id=cat_id))
            verified = await db.get(type(row), row.id) is not None
            cat_tail = f" ({fields['category']})" if fields.get("category") else ""
            summary = f"{ph.money(fields['amount'], currency)} expense added{cat_tail}."
            entity_type, entity_id = CompanionEntityType.expense, row.id
        elif intent == nlp.ADD_INCOME:
            stype = fields.get("source_type") or "other"
            row = await income_service.create(db, user_id, IncomeCreate(
                source_type=IncomeSourceType(stype), original_amount=fields["amount"],
                original_currency=currency, received_date=fields.get("date") or today))
            verified = await db.get(type(row), row.id) is not None
            summary = f"{ph.money(fields['amount'], currency)} income recorded."
            entity_type, entity_id = CompanionEntityType.income, row.id
        elif intent == nlp.ADD_RECEIVABLE:
            read = await receivables_service.create(db, user_id, ReceivableCreate(
                title=f"From {fields['source_name']}", source_name=fields["source_name"],
                source_type=fields.get("source_type") or "other", kind="one_time",
                original_amount=fields["amount"], original_currency=currency,
                expected_date=fields.get("date") or today, expected_time_window=fields.get("time_window"),
                expected_time=fields.get("exact_time")))
            verified = True
            when = (fields.get("date") or today).isoformat()
            summary = f"Tracking {ph.money(fields['amount'], currency)} expected from {fields['source_name']} on {when}."
            entity_type, entity_id = CompanionEntityType.receivable, read.id
        elif intent == nlp.MARK_RECEIVABLE_RECEIVED:
            from app.schemas.receivable import ReceivableUpdate
            await receivables_service.update(db, user_id, target.id, ReceivableUpdate(status=ReceivableStatus.received))
            verified = (await db.get(Receivable, target.id)).status == ReceivableStatus.received
            summary = f"Marked {target.source_name}'s {ph.money(target.converted_amount, cur)} as received."
            entity_type, entity_id = CompanionEntityType.receivable, target.id
        elif intent == nlp.MOVE_EVENT:
            await planned_expense_service.update(db, user_id, target.id, PlannedExpenseUpdate(planned_date=fields["date"]))
            verified = (await db.get(PlannedExpense, target.id)).planned_date == fields["date"]
            summary = f"Moved '{target.title}' to {fields['date'].isoformat()}."
            entity_type, entity_id = CompanionEntityType.planned_event, target.id
        elif intent == nlp.CHANGE_SAVINGS_TARGET:
            await savings_service.update(db, user_id, target.id, SavingsGoalUpdate(
                original_amount=fields["amount"], original_currency=currency))
            verified = True
            summary = f"Updated '{target.name}' target to {ph.money(fields['amount'], currency)}."
            entity_type, entity_id = CompanionEntityType.goal, target.id
        else:  # CREATE_SAVINGS_GOAL
            kind = fields.get("kind", "monthly_target")
            row = await savings_service.create(db, user_id, SavingsGoalCreate(
                name="Monthly savings" if kind == "monthly_target" else "Savings goal", kind=kind,
                original_amount=fields["amount"], original_currency=currency, target_date=fields.get("date")), today=today)
            verified = True
            summary = f"Set a {kind.replace('_', ' ')} of {ph.money(fields['amount'], currency)}."
            entity_type, entity_id = CompanionEntityType.goal, row.id
    except (InvalidOperationError, ResourceNotFoundError) as exc:
        return {"type": "clarification",
                "questions": [{"field": "error", "prompt": f"I couldn't complete that: {exc}", "why": "Please adjust and retry."}]}

    db.add(CompanionEvent(user_id=user_id, event_type=CompanionEventType.action_completed, surface="assistant",
                          action=intent, entity_type=entity_type, entity_id=entity_id,
                          payload={"intent": intent, "request_id": request_id}))
    await db.commit()

    why = _why_for(intent, fields, target)
    outcome = await _build_outcome(db, user_id, summary, today, why=why)
    outcome["verified"] = bool(verified)
    commentary = await commentary_service.narrate(
        db, user_id, trigger=ctxmod.AFTER_ACTION, today=today, headline_hint=summary)
    return {"type": "result", "action": intent, "outcome": outcome, "commentary": commentary}


def _why_for(intent, fields, target) -> str:
    if intent == nlp.MOVE_EVENT:
        return ("Only the date changed, not the amount, so your monthly projection is essentially unchanged. "
                "I checked for conflicts, upcoming expenses, savings goals and expected income.")
    if intent == nlp.ADD_EXPENSE:
        return "I checked this against today's budget, your savings goals and upcoming plans."
    if intent == nlp.ADD_INCOME:
        return "I've recorded this income so your available budget and projections reflect it."
    if intent == nlp.ADD_RECEIVABLE:
        return "I've added this to your expected income so future planning accounts for it."
    return "I checked the whole-month picture, not just today."


# --- buy / order (advisory; routes through C7a-2 modifier questioning) -------
async def _handle_buy(db, user_id, fields, answers, today) -> dict[str, Any]:
    cur = await db.scalar(select(UserSettings.base_currency).where(UserSettings.user_id == user_id)) or "INR"
    if fields.get("amount") is None:
        return {"type": "clarification", "questions": [_question("amount")],
                "candidate": _candidate(nlp.BUY_DECISION, fields)}
    modifier_inputs = (answers or {}).get("modifiers")
    from app.intelligence.decision.modifiers.base import ModifierInputs
    mi = None
    if modifier_inputs:
        mi = ModifierInputs(**modifier_inputs)
    quote = await decision_service.quote(
        db, user_id, item_label=fields.get("item_label") or "this purchase",
        original_amount=fields["amount"], original_currency=fields.get("currency") or cur,
        target_date=fields.get("date"), modifier_inputs=mi, today=today)
    await _log_buy_decision(db, user_id, quote, mi)   # B1.5c: offer-exposure proxy source
    if quote.get("pending_questions"):
        return {"type": "clarification", "questions": quote["pending_questions"],
                "candidate": _candidate(nlp.BUY_DECISION, fields),
                "note": "A few details would sharpen this — answer what's relevant."}
    return {"type": "advisory", "quote": quote}


_OFFER_ANALYZERS = {"free_delivery", "offer", "bundle", "decision_change"}
_OFFER_INVOLVES = {"offer", "cashback", "free_delivery", "bundle"}


async def _log_buy_decision(db, user_id, quote, mi) -> None:
    """Record which offer classes appeared in this decision (exposure, not influence)."""
    involved = {f["analyzer"] for f in quote.get("modifier_findings", []) if f.get("analyzer") in _OFFER_ANALYZERS}
    involved |= {q["analyzer"] for q in quote.get("pending_questions", []) if q.get("analyzer") in _OFFER_ANALYZERS}
    involves = (set(mi.involves) if (mi and mi.involves) else set()) & _OFFER_INVOLVES
    offer_involved = bool(involved or involves)
    db.add(CompanionEvent(
        user_id=user_id, event_type=CompanionEventType.action_completed, surface="decisions",
        action="buy_decision", entity_type=None, entity_id=None,
        payload={"offer_involved": offer_involved, "offer_classes": sorted(involved | involves)}))
    await db.commit()


# --- user-is-king: reject a date move -> alternatives ------------------------
async def _handle_reject(db, user_id, today) -> dict[str, Any]:
    # find the soonest upcoming event and record that its date is fixed (emotional-aware)
    event = (await db.execute(
        select(PlannedExpense).where(
            PlannedExpense.user_id == user_id, PlannedExpense.deleted_at.is_(None),
            PlannedExpense.status == PlannedExpenseStatus.planned, PlannedExpense.occasion_type.is_not(None),
            PlannedExpense.planned_date >= today).order_by(PlannedExpense.planned_date))).scalars().first()
    emotional = "high" if (event and event.occasion_type in (OccasionType.birthday, OccasionType.date, OccasionType.celebration)) else None
    await preference_service.record_feedback(
        db, user_id, recommendation_id="timing_opportunity:move_date", action=RecommendationAction.rejected,
        reason=RejectionReason.date_fixed, reason_context=(event.title if event else None), emotional_importance=emotional)
    recs = await recommendation_service.build(db, user_id, excluded_levers=("move_date",), today=today)
    commentary = await commentary_service.narrate(db, user_id, trigger=ctxmod.RECOMMENDATIONS, today=today)
    return {"type": "alternatives",
            "message": "Understood — I won't suggest moving the date. Here are other ways to make it work.",
            "recommendations": recs["recommendations"], "bundles": recs["bundles"], "commentary": commentary}


async def _already_done(db, user_id, request_id) -> bool:
    found = await db.scalar(
        select(CompanionEvent.id).where(
            CompanionEvent.user_id == user_id,
            CompanionEvent.payload["request_id"].astext == request_id).limit(1))
    return found is not None
