"""Companion orchestration: log events, return guided help, and (for completed
financial actions) generate engine-backed insights. The companion performs NO
financial math — it only calls the frozen engines via projection_service and
formats the returned facts.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.intelligence.behavior.insights import InsightContext, build_behavioral_insights
from app.intelligence.companion import guidance_content as gc
from app.models import CompanionEvent, CompanionInsight, SavingsGoal
from app.models.enums import (
    CompanionCategory,
    CompanionEntityType,
    CompanionEventType,
    CompanionSeverity,
    ReceivableKind,
    SavingsGoalStatus,
)
from app.schemas.companion import CompanionEventCreate, CompanionMessageOut
from app.services import behavior_service, projection_service
from app.services.exceptions import ResourceNotFoundError

# behavioral-insight kind -> (category, severity) for the companion feed (B2)
_BEHAVIOR_FEED_MAP = {
    "strength": (CompanionCategory.achievement, CompanionSeverity.success),
    "achievement": (CompanionCategory.achievement, CompanionSeverity.success),
    "improvement": (CompanionCategory.financial_insight, CompanionSeverity.success),
    "opportunity": (CompanionCategory.financial_insight, CompanionSeverity.info),
    "weakness": (CompanionCategory.warning, CompanionSeverity.warning),
    "risk": (CompanionCategory.warning, CompanionSeverity.alert),
    "dependency": (CompanionCategory.warning, CompanionSeverity.warning),
}

_SEVERE_ACTIONS = {"reduce_discretionary", "defer_planned", "use_reserve", "reduce_spending"}
_GUIDANCE_ENTITIES = {
    CompanionEntityType.expense,
    CompanionEntityType.income,
    CompanionEntityType.settings,
    CompanionEntityType.income_source,
}


# --- message builders -------------------------------------------------------

def _help_message(content: gc.GuidanceContent, surface: str | None) -> CompanionMessageOut:
    return CompanionMessageOut(
        kind="help",
        category=content.category,
        type=f"help.{(surface or 'generic')}",
        surface=surface,
        severity=content.severity,
        title=content.title,
        message=content.message,
        facts={},
        insight_id=None,
    )


def _insight_message(insight: CompanionInsight) -> CompanionMessageOut:
    return CompanionMessageOut(
        kind="insight",
        category=insight.category,
        type=insight.type,
        surface=insight.surface,
        severity=insight.severity,
        title=insight.title,
        message=insight.message,
        facts=insight.facts,
        insight_id=insight.id,
    )


# --- insight construction (reads engine facts only) -------------------------

def _guidance_insight(user_id, entity_type, data, guidance) -> CompanionInsight:
    threshold_remaining = (
        str(guidance.threshold_remaining) if guidance.threshold_remaining is not None else None
    )
    facts = {
        "safe_daily_spending": str(guidance.safe_daily_spending),
        "safe_weekly_spending": str(guidance.safe_weekly_spending),
        "threshold_remaining": threshold_remaining,
        "actions": [{"action": a.action, "data": a.data} for a in guidance.recommended_actions],
    }
    severe = any(a.action in _SEVERE_ACTIONS for a in guidance.recommended_actions)

    if severe:
        category, severity, title = CompanionCategory.warning, CompanionSeverity.alert, "Heads up on your spending"
        message = f"Your safe daily spend is now {guidance.safe_daily_spending}. Consider the suggested adjustments."
        itype = "spending_update"
    elif entity_type == CompanionEntityType.income:
        category, severity, title = CompanionCategory.financial_insight, CompanionSeverity.success, "Income recorded"
        message = f"Nice — your safe daily spend is now {guidance.safe_daily_spending}."
        itype = "income_outlook"
    elif entity_type == CompanionEntityType.settings:
        category, severity, title = CompanionCategory.financial_insight, CompanionSeverity.info, "Settings updated"
        message = f"Updated. Your safe daily spend is now {guidance.safe_daily_spending}."
        itype = "settings_updated"
    else:  # expense / income_source
        category, severity, title = CompanionCategory.financial_insight, CompanionSeverity.info, "Expense logged"
        tail = f" You have {threshold_remaining} left under your monthly limit." if threshold_remaining is not None else ""
        message = f"Your safe daily spend is now {guidance.safe_daily_spending}.{tail}"
        itype = "spending_update"

    return CompanionInsight(
        user_id=user_id, category=category, type=itype, surface=data.surface, severity=severity,
        title=title, message=message, facts=facts, source="engine",
        related_entity_type=entity_type, related_entity_id=data.entity_id,
    )


def _planned_insight(user_id, data, affordability) -> CompanionInsight:
    facts = {
        "verdict": affordability.verdict,
        "affordable": affordability.affordable,
        "probability": str(affordability.probability),
        "shortfall": str(affordability.shortfall),
    }
    if affordability.affordable:
        category, severity, title = CompanionCategory.financial_insight, CompanionSeverity.success, "Planned expense looks affordable"
        message = f"This looks affordable (verdict: {affordability.verdict})."
    else:
        category, severity, title = CompanionCategory.warning, CompanionSeverity.alert, "Planned expense may be tight"
        message = f"This may be hard to afford (verdict: {affordability.verdict}, shortfall {affordability.shortfall})."
    return CompanionInsight(
        user_id=user_id, category=category, type="planned_feasibility", surface=data.surface,
        severity=severity, title=title, message=message, facts=facts, source="engine",
        related_entity_type=CompanionEntityType.planned_expense, related_entity_id=data.entity_id,
    )


async def _build_insight(db: AsyncSession, user_id: uuid.UUID, data: CompanionEventCreate) -> CompanionInsight | None:
    entity = data.entity_type
    if entity == CompanionEntityType.planned_expense and data.entity_id is not None:
        try:
            affordability = await projection_service.evaluate_planned_expense(db, user_id, data.entity_id)
            return _planned_insight(user_id, data, affordability)
        except ResourceNotFoundError:
            pass  # fall back to a generic guidance snapshot
    if entity in _GUIDANCE_ENTITIES or entity == CompanionEntityType.planned_expense:
        guidance = await projection_service.compute_guidance(db, user_id)
        return _guidance_insight(user_id, entity, data, guidance)
    return None  # non-financial completed action: event logged, no insight


# --- public API -------------------------------------------------------------

async def handle_event(
    db: AsyncSession, user_id: uuid.UUID, data: CompanionEventCreate
) -> tuple[CompanionEvent, list[CompanionMessageOut]]:
    event = CompanionEvent(
        user_id=user_id, event_type=data.event_type, surface=data.surface, action=data.action,
        entity_type=data.entity_type, entity_id=data.entity_id, payload=data.payload,
    )
    db.add(event)
    await db.flush()  # assign event.id

    messages: list[CompanionMessageOut] = []
    if data.event_type == CompanionEventType.page_open:
        messages.append(_help_message(gc.for_page(data.surface), data.surface))
    elif data.event_type == CompanionEventType.button_click:
        messages.append(_help_message(gc.for_action(data.action or data.surface), data.surface))
    elif data.event_type == CompanionEventType.onboarding_step:
        messages.append(_help_message(gc.for_onboarding(data.action or data.surface), data.surface))
    elif data.event_type == CompanionEventType.action_completed:
        insight = await _build_insight(db, user_id, data)
        if insight is not None:
            db.add(insight)
            await db.flush()
            messages.append(_insight_message(insight))

    await db.commit()
    return event, messages


async def list_feed(
    db: AsyncSession, user_id: uuid.UUID, *, unread: bool | None, limit: int, offset: int
) -> tuple[list[CompanionInsight], int]:
    conditions = [CompanionInsight.user_id == user_id, CompanionInsight.deleted_at.is_(None)]
    if unread is True:
        conditions.append(CompanionInsight.is_read.is_(False))
    elif unread is False:
        conditions.append(CompanionInsight.is_read.is_(True))

    total = await db.scalar(select(func.count()).select_from(CompanionInsight).where(*conditions)) or 0
    result = await db.execute(
        select(CompanionInsight).where(*conditions).order_by(CompanionInsight.created_at.desc()).limit(limit).offset(offset)
    )
    return list(result.scalars().all()), int(total)


async def build_behavioral_feed(
    db: AsyncSession, user_id: uuid.UUID, *, today: date | None = None
) -> list[CompanionInsight]:
    """Surface the BehavioralProfile through the feed (B2). The Companion only
    maps + persists; all intelligence lives in the behavior insight layer.
    Supersedes the prior behavioral snapshot so the feed never floods."""
    profile = await behavior_service.build_profile(db, user_id, today=today)

    goal_rows = (
        await db.execute(
            select(SavingsGoal.kind, SavingsGoal.name).where(
                SavingsGoal.user_id == user_id,
                SavingsGoal.deleted_at.is_(None),
                SavingsGoal.status == SavingsGoalStatus.active,
            )
        )
    ).all()
    goals = tuple((k.value if hasattr(k, "value") else str(k), name) for k, name in goal_rows)
    deps, _ = await projection_service.analyze_dependencies(db, user_id, today=profile.today)
    context = InsightContext(goals=goals, dependencies=tuple(d.as_dict() for d in deps))

    insights = build_behavioral_insights(profile, context=context)

    # Supersede the previous behavioral snapshot (only behavior.* rows).
    await db.execute(
        update(CompanionInsight)
        .where(
            CompanionInsight.user_id == user_id,
            CompanionInsight.deleted_at.is_(None),
            CompanionInsight.type.like("behavior.%"),
        )
        .values(deleted_at=datetime.now(timezone.utc))
    )

    rows: list[CompanionInsight] = []
    for ins in insights:
        category, severity = _BEHAVIOR_FEED_MAP[ins.kind]
        row = CompanionInsight(
            user_id=user_id, category=category, type=f"behavior.{ins.kind}", surface="behavior",
            severity=severity, title=ins.finding[:200], message=ins.impact, facts=ins.as_dict(),
            source="engine", related_entity_type=CompanionEntityType.behavior, related_entity_id=None,
        )
        db.add(row)
        rows.append(row)

    await db.commit()
    for row in rows:
        await db.refresh(row)
    return rows


async def unread_count(db: AsyncSession, user_id: uuid.UUID) -> int:
    value = await db.scalar(
        select(func.count()).select_from(CompanionInsight).where(
            CompanionInsight.user_id == user_id,
            CompanionInsight.deleted_at.is_(None),
            CompanionInsight.is_read.is_(False),
        )
    )
    return int(value or 0)


async def mark_read(db: AsyncSession, user_id: uuid.UUID, insight_id: uuid.UUID) -> CompanionInsight:
    result = await db.execute(
        select(CompanionInsight).where(
            CompanionInsight.id == insight_id,
            CompanionInsight.user_id == user_id,
            CompanionInsight.deleted_at.is_(None),
        )
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise ResourceNotFoundError("Insight")
    row.is_read = True
    await db.commit()
    await db.refresh(row)
    return row


# --- receivable companion builders (used by receivables_service) ------------

def build_receivable_event(user_id, receivable, action: str) -> CompanionEvent:
    return CompanionEvent(
        user_id=user_id,
        event_type=CompanionEventType.action_completed,
        surface="receivables",
        action=action,
        entity_type=CompanionEntityType.receivable,
        entity_id=receivable.id,
        payload={
            "source_name": receivable.source_name,
            "amount": str(receivable.converted_amount),
            "kind": receivable.kind.value,
        },
    )


def build_receivable_created_insight(user_id, receivable, *, today, next_expected_date) -> CompanionInsight:
    base = {
        "source_name": receivable.source_name,
        "amount": str(receivable.converted_amount),
        "currency": receivable.base_currency,
        "kind": receivable.kind.value,
    }
    if receivable.kind == ReceivableKind.recurring:
        days = (next_expected_date - today).days if next_expected_date else None
        facts = {
            **base,
            "recurrence_day": receivable.recurrence_day,
            "next_expected_date": next_expected_date.isoformat() if next_expected_date else None,
            "days_until": days,
        }
        category, severity, itype, title = CompanionCategory.reminder, CompanionSeverity.info, "receivable_recurring", "Recurring money tracked"
        message = f"Expect {receivable.converted_amount} from {receivable.source_name} every month on day {receivable.recurrence_day}."
        if days is not None:
            message += f" Next in {days} days."
    elif receivable.expected_date is None:
        facts = {**base, "expected_date": None}
        category, severity, itype, title = CompanionCategory.reminder, CompanionSeverity.info, "receivable_tracked", "Receivable tracked"
        message = f"Tracking {receivable.converted_amount} from {receivable.source_name}."
    elif receivable.expected_date < today:
        days = (today - receivable.expected_date).days
        facts = {**base, "expected_date": receivable.expected_date.isoformat(), "days_overdue": days}
        category, severity, itype, title = CompanionCategory.warning, CompanionSeverity.alert, "receivable_overdue", "Overdue receivable"
        message = f"{receivable.converted_amount} from {receivable.source_name} was expected {days} days ago."
    else:
        days = (receivable.expected_date - today).days
        facts = {**base, "expected_date": receivable.expected_date.isoformat(), "days_until": days}
        category, severity, itype, title = CompanionCategory.reminder, CompanionSeverity.info, "receivable_expected", "Money expected soon"
        message = f"Expect {receivable.converted_amount} from {receivable.source_name} in {days} days."

    return CompanionInsight(
        user_id=user_id, category=category, type=itype, surface="receivables", severity=severity,
        title=title, message=message, facts=facts, source="companion",
        related_entity_type=CompanionEntityType.receivable, related_entity_id=receivable.id,
    )


def build_event_event(user_id, event_id, action: str) -> CompanionEvent:
    return CompanionEvent(
        user_id=user_id, event_type=CompanionEventType.action_completed, surface="events",
        action=action, entity_type=CompanionEntityType.planned_event, entity_id=event_id,
    )


def _event_base_facts(event, result) -> dict:
    return {
        "title": event.title,
        "amount": str(event.converted_amount),
        "event_date": event.planned_date.isoformat(),
        "occasion_type": event.occasion_type.value if event.occasion_type else None,
        "affordable": result.affordable,
        "risk_level": result.risk_level,
    }


def build_event_created_insight(user_id, event, result) -> CompanionInsight:
    return CompanionInsight(
        user_id=user_id, category=CompanionCategory.financial_insight, type="event_created",
        surface="events", severity=CompanionSeverity.info, title="Event planned",
        message=f"Planned '{event.title}' for {event.planned_date.isoformat()} ({event.converted_amount}).",
        facts=_event_base_facts(event, result), source="companion",
        related_entity_type=CompanionEntityType.planned_event, related_entity_id=event.id,
    )


def build_event_verdict_insight(user_id, event, result) -> CompanionInsight:
    if result.affordable:
        category, severity, itype, title = CompanionCategory.achievement, CompanionSeverity.success, "event_affordable", "Event looks affordable"
        message = f"'{event.title}' looks affordable."
        facts = {**_event_base_facts(event, result), "surplus_or_shortfall": str(result.projected_surplus_or_shortfall)}
    else:
        category, severity, itype, title = CompanionCategory.warning, CompanionSeverity.alert, "event_unaffordable", "Event may be unaffordable"
        message = f"'{event.title}' may be hard to afford."
        facts = {
            **_event_base_facts(event, result),
            "shortfall": result.affordability.get("shortfall"),
            "adjustments": [a.action for a in result.required_adjustments],
        }
    return CompanionInsight(
        user_id=user_id, category=category, type=itype, surface="events", severity=severity,
        title=title, message=message, facts=facts, source="companion",
        related_entity_type=CompanionEntityType.planned_event, related_entity_id=event.id,
    )


def build_event_warning_insight(user_id, event, result) -> CompanionInsight:
    return CompanionInsight(
        user_id=user_id, category=CompanionCategory.warning, type="event_warning", surface="events",
        severity=CompanionSeverity.alert, title="This event carries financial risk",
        message=f"Planning '{event.title}' raises your risk level to {result.risk_level}.",
        facts={"title": event.title, "risk_level": result.risk_level}, source="companion",
        related_entity_type=CompanionEntityType.planned_event, related_entity_id=event.id,
    )


def build_event_reschedule_insight(user_id, event, suggested_date: str) -> CompanionInsight:
    return CompanionInsight(
        user_id=user_id, category=CompanionCategory.reminder, type="event_reschedule_suggestion",
        surface="events", severity=CompanionSeverity.info, title="A better date may exist",
        message=f"Consider moving '{event.title}' from {event.planned_date.isoformat()} to {suggested_date}.",
        facts={"title": event.title, "current_date": event.planned_date.isoformat(), "suggested_date": suggested_date},
        source="companion", related_entity_type=CompanionEntityType.planned_event, related_entity_id=event.id,
    )


def build_session_event(user_id, session, action: str) -> CompanionEvent:
    return CompanionEvent(
        user_id=user_id,
        event_type=CompanionEventType.action_completed,
        surface="budget_sessions",
        action=action,
        entity_type=CompanionEntityType.budget_session,
        entity_id=session.id,
        payload={"title": session.title, "budget": str(session.converted_amount)},
    )


def build_session_started_insight(user_id, session, *, safe_daily, threshold_remaining, risk_level) -> CompanionInsight:
    facts = {
        "title": session.title,
        "budget": str(session.converted_amount),
        "safe_daily_spending": str(safe_daily),
        "threshold_remaining": str(threshold_remaining) if threshold_remaining is not None else None,
        "risk_level": risk_level,
    }
    message = f"Session '{session.title}' started with a budget of {session.converted_amount}. Safe daily spend: {safe_daily}."
    return CompanionInsight(
        user_id=user_id, category=CompanionCategory.financial_insight, type="session_started",
        surface="budget_sessions", severity=CompanionSeverity.info, title="Spending session started",
        message=message, facts=facts, source="companion",
        related_entity_type=CompanionEntityType.budget_session, related_entity_id=session.id,
    )


def build_session_warning_insight(user_id, session, *, threshold, spent, budget, remaining, utilization) -> CompanionInsight:
    facts = {
        "title": session.title, "threshold": threshold, "spent": str(spent), "budget": str(budget),
        "remaining": str(remaining), "utilization_percent": str(utilization),
    }
    severity = CompanionSeverity.alert if threshold >= 90 else CompanionSeverity.warning
    return CompanionInsight(
        user_id=user_id, category=CompanionCategory.warning, type="session_warning",
        surface="budget_sessions", severity=severity, title=f"{threshold}% of session budget used",
        message=f"You've used {utilization}% of your '{session.title}' budget ({spent} of {budget}).",
        facts=facts, source="companion",
        related_entity_type=CompanionEntityType.budget_session, related_entity_id=session.id,
    )


def build_session_completed_insight(user_id, session, *, budget, spent, saved, utilization, expense_count) -> CompanionInsight:
    facts = {
        "title": session.title, "budget": str(budget), "spent": str(spent), "saved": str(saved),
        "utilization_percent": str(utilization), "expense_count": expense_count,
    }
    if saved >= 0:
        category, severity, title = CompanionCategory.achievement, CompanionSeverity.success, "Session completed under budget"
        message = f"Session '{session.title}' done — you saved {saved} of {budget}."
    else:
        category, severity, title = CompanionCategory.warning, CompanionSeverity.alert, "Session over budget"
        message = f"Session '{session.title}' finished {-saved} over its {budget} budget."
    return CompanionInsight(
        user_id=user_id, category=category, type="session_completed", surface="budget_sessions",
        severity=severity, title=title, message=message, facts=facts, source="companion",
        related_entity_type=CompanionEntityType.budget_session, related_entity_id=session.id,
    )


def build_receivable_received_insight(user_id, receivable) -> CompanionInsight:
    facts = {
        "source_name": receivable.source_name,
        "amount": str(receivable.converted_amount),
        "currency": receivable.base_currency,
    }
    return CompanionInsight(
        user_id=user_id, category=CompanionCategory.achievement, type="receivable_received",
        surface="receivables", severity=CompanionSeverity.success, title="Received!",
        message=f"You received {receivable.converted_amount} from {receivable.source_name}.",
        facts=facts, source="companion",
        related_entity_type=CompanionEntityType.receivable, related_entity_id=receivable.id,
    )
