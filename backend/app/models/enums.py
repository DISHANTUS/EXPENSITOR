"""Enumerations used across the data model.

These are stored as validated VARCHAR (``native_enum=False``) to avoid the
migration pain of native PostgreSQL enum types. Member name == value.
"""

from __future__ import annotations

import enum


class IncomeSourceType(str, enum.Enum):
    salary = "salary"
    freelance = "freelance"
    bonus = "bonus"
    business = "business"
    gift = "gift"
    refund = "refund"
    other = "other"


class IncomeKind(str, enum.Enum):
    """Distinguishes recurring expected income from one-time planned income."""

    recurring = "recurring"
    one_time = "one_time"


class CategorySource(str, enum.Enum):
    """How an expense's category was assigned."""

    rule = "rule"
    manual = "manual"
    ai = "ai"


class PlannedExpenseStatus(str, enum.Enum):
    planned = "planned"
    completed = "completed"
    cancelled = "cancelled"


class PlannedExpensePriority(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class AiTone(str, enum.Enum):
    """Preferred voice/strictness of the AI co-pilot's commentary."""

    friendly = "friendly"
    balanced = "balanced"
    strict = "strict"


class CompanionEventType(str, enum.Enum):
    """How a companion event originated. VARCHAR-backed, so trivially extensible."""

    page_open = "page_open"
    button_click = "button_click"
    action_completed = "action_completed"
    onboarding_step = "onboarding_step"
    system = "system"  # reserved: companion-initiated / derived events (future)


class CompanionEntityType(str, enum.Enum):
    """Entity a companion event/insight relates to. Future entities are listed
    now so the schema is forward-compatible (column is VARCHAR)."""

    # C1
    expense = "expense"
    income = "income"
    income_source = "income_source"
    planned_expense = "planned_expense"
    settings = "settings"
    # reserved for future companion features
    receivable = "receivable"
    budget_session = "budget_session"
    planned_event = "planned_event"
    category = "category"
    goal = "goal"
    behavior = "behavior"  # behavioral-intelligence insights (B2)
    recommendation = "recommendation"  # recommendation feedback audit (C7b)


class CompanionSeverity(str, enum.Enum):
    """Urgency of a companion message (orthogonal to category)."""

    info = "info"
    success = "success"
    warning = "warning"
    alert = "alert"


class CompanionCategory(str, enum.Enum):
    """Purpose of a companion message. `reminder`/`achievement` are reserved for
    future features — declared now but no logic emits them in C1."""

    page_guidance = "page_guidance"
    action_guidance = "action_guidance"
    financial_insight = "financial_insight"
    reminder = "reminder"
    warning = "warning"
    achievement = "achievement"


class ReceivableSourceType(str, enum.Enum):
    friend = "friend"
    family = "family"
    salary = "salary"
    freelance = "freelance"
    refund = "refund"
    reimbursement = "reimbursement"
    gift = "gift"
    other = "other"


class ReceivableKind(str, enum.Enum):
    one_time = "one_time"
    recurring = "recurring"


class ReceivableStatus(str, enum.Enum):
    """`overdue` is DERIVED (pending one-time past its date) — never stored."""

    pending = "pending"
    received = "received"
    overdue = "overdue"
    cancelled = "cancelled"


class BudgetSessionStatus(str, enum.Enum):
    active = "active"
    completed = "completed"
    cancelled = "cancelled"


class OccasionType(str, enum.Enum):
    """Marks a planned_expense as a planner Event. VARCHAR-backed, extensible."""

    outing = "outing"
    shopping = "shopping"
    entertainment = "entertainment"
    travel = "travel"
    date = "date"
    birthday = "birthday"
    festival = "festival"
    vacation = "vacation"
    celebration = "celebration"
    custom = "custom"


class SavingsGoalKind(str, enum.Enum):
    """A recurring monthly savings target, or a one-off goal with a target date."""

    monthly_target = "monthly_target"
    custom_goal = "custom_goal"


class SavingsGoalStatus(str, enum.Enum):
    """Stored status. on_track / behind / completed-by-progress are DERIVED."""

    active = "active"
    completed = "completed"
    cancelled = "cancelled"


class RecoveryMode(str, enum.Enum):
    """The user's chosen response to a missed target. Never set automatically."""

    keep_unchanged = "keep_unchanged"   # acknowledge the miss, change nothing
    distribute = "distribute"           # carry the deficit across future months
    new_plan = "new_plan"               # a different target/date was set


class ExpectedTimeWindow(str, enum.Enum):
    """Rough time-of-day an inflow usually arrives. Collected only when useful;
    NULL means unknown (the advisor then omits time-of-day)."""

    morning = "morning"
    afternoon = "afternoon"
    evening = "evening"
    night = "night"
    no_fixed_time = "no_fixed_time"


class RecommendationAction(str, enum.Enum):
    """User feedback on a recommendation (C7b). Preference signal only — never
    auto-executes or changes any financial fact."""

    accepted = "accepted"
    rejected = "rejected"
    deferred = "deferred"


class RejectionReason(str, enum.Enum):
    not_now = "not_now"
    date_fixed = "date_fixed"
    dislike_approach = "dislike_approach"
    too_much_effort = "too_much_effort"
    other = "other"
