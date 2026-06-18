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
    # Budget Intelligence System — multi-income support (sources matter, not just total).
    scholarship = "scholarship"
    part_time = "part_time"
    family_support = "family_support"
    pension = "pension"
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


class RelationshipType(str, enum.Enum):
    """How a Person relates to the user (V2 relationship memory)."""

    friend = "friend"
    family = "family"
    partner = "partner"
    coworker = "coworker"
    other = "other"


class RecurringRuleType(str, enum.Enum):
    """A recurring financial commitment (V2 calendar materialization)."""

    subscription = "subscription"
    emi = "emi"
    loan = "loan"
    bill = "bill"
    insurance = "insurance"
    borrowed = "borrowed"  # money the user borrowed and repays periodically


class ImportanceLevel(str, enum.Enum):
    """Significance of an event/memory — drives retention, timeline, mood priority."""

    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"
    life_milestone = "life_milestone"


class AdviceKind(str, enum.Enum):
    """What the companion said, so it can come back and ask what happened (4b-5)."""

    forecast = "forecast"            # a goal ETA / what-if projection
    relationship = "relationship"   # lending / repayment advice
    recommendation = "recommendation"  # a lever (reduce category, cancel sub, save more)
    budget = "budget"               # a monthly budget intention
    reflection = "reflection"       # a month-end reflection prompt (4b-5b)
    success = "success"             # a streak / win worth remembering (4b-5b)


class AdviceStatus(str, enum.Enum):
    """Lifecycle of a tracked piece of advice."""

    pending = "pending"     # recorded, no follow-up due yet
    due = "due"             # follow-up is due to be asked
    answered = "answered"   # the user told us what happened (-> Outcome)
    resolved = "resolved"   # derived/closed without a question
    expired = "expired"     # window passed without an answer


class LessonStatus(str, enum.Enum):
    """Life-lesson lifecycle (4b-5b). Never auto-deleted; `forgotten` is reversible."""

    active = "active"        # seen once
    confirmed = "confirmed"  # recurred (>=2) — trusted enough to surface
    archived = "archived"    # no recurrence in a long time (kept for the timeline)
    forgotten = "forgotten"  # user asked to forget it (restorable)


class LessonConfidence(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"


class AchievementType(str, enum.Enum):
    """A win worth remembering (4b-5b). One good day is NOT one of these."""

    first_salary = "first_salary"
    goal_completed = "goal_completed"
    debt_cleared = "debt_cleared"
    goal_milestone = "goal_milestone"      # e.g. 25/50/75% of a goal
    savings_streak = "savings_streak"      # N consecutive months on target
    loan_repaid = "loan_repaid"            # someone repaid the user


class PredictionAccuracyBand(str, enum.Enum):
    accurate = "accurate"
    partial = "partial"
    inaccurate = "inaccurate"
    pending = "pending"     # not enough elapsed/actual yet to judge


# --- Financial profile (Budget Intelligence System) ---------------------------
# Who the user is / how they live. Drives profile-specific country baselines and
# the realistic budget engine. All VARCHAR-backed and freely editable later.


class LifeStage(str, enum.Enum):
    middle_school = "middle_school"
    high_school = "high_school"
    ug_student = "ug_student"
    pg_student = "pg_student"
    scholarship_student = "scholarship_student"
    working_professional = "working_professional"
    self_employed = "self_employed"
    business_owner = "business_owner"
    homemaker = "homemaker"
    retired = "retired"
    unemployed = "unemployed"
    other = "other"


class LivingSituation(str, enum.Enum):
    with_parents = "with_parents"
    with_partner = "with_partner"
    with_friends = "with_friends"
    alone = "alone"
    dormitory = "dormitory"
    other = "other"


class FoodSituation(str, enum.Enum):
    home_cooked = "home_cooked"
    mostly_outside = "mostly_outside"
    mix = "mix"
    other = "other"


class TransportMode(str, enum.Enum):
    walk = "walk"
    bicycle = "bicycle"
    motorcycle = "motorcycle"      # bike / scooter — personal vehicle (fuel + upkeep)
    bus = "bus"
    train = "train"
    car = "car"
    auto = "auto"                  # auto-rickshaw / shared cab
    mixed = "mixed"
    other = "other"                # free-text lives in transport_note


class TuitionResponsibility(str, enum.Enum):
    self_paid = "self_paid"
    none = "none"
    scholarship_covered = "scholarship_covered"


class OptimizationStyle(str, enum.Enum):
    """What Advary optimizes the plan for — two identical budgets can want very
    different plans."""

    max_savings = "max_savings"
    balanced = "balanced"
    comfort_first = "comfort_first"
    aggressive_goal = "aggressive_goal"


class ExpenseBucket(str, enum.Enum):
    """Every planned outflow belongs to exactly one bucket. Cut priority when a
    goal doesn't fit: ADJUSTABLE → GOAL → COMMITTED → PROTECTED (food is last)."""

    protected = "protected"     # food, groceries, essential transport, medicine, utilities
    committed = "committed"     # rent, tuition, insurance, loans/EMI
    adjustable = "adjustable"   # eating out, entertainment, shopping, subscriptions
    goal = "goal"               # savings / emergency / laptop / travel funds
