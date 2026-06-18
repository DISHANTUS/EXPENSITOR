"""Calendar marker registry — the single source of truth for what a day can show.

A marker is pure reference data (key, icon, color, title, category, commentary
template). The calendar API returns per-day marker *keys*; clients render from
this catalog. Adding a new marker later (Sprint 4+) is a data edit here — no
calendar redesign. Sprint 3 only *emits* the budget/income/event keys; the full
taxonomy is declared now so nothing needs refactoring when S4 fills it in.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MarkerType:
    key: str
    icon: str
    color: str
    title: str
    category: str  # budget | income | expense | commitment | planning | advisor | relationship | life_event
    commentary_template: str


# (key, icon, color, title, category, template)
_DEFS: list[tuple[str, str, str, str, str, str]] = [
    # --- budget performance (Sprint 3 emits these) ---
    ("budget_over", "🔴", "#E53935", "Over budget", "budget", "You went over budget by {amount} on {date}."),
    ("budget_within", "🟢", "#43A047", "Within budget", "budget", "You stayed within budget on {date}."),
    ("budget_saved", "👑", "#FBC02D", "Saved money", "budget", "You saved {amount} from your budget on {date}."),
    ("budget_streak", "🔥", "#FB8C00", "Streak day", "budget", "Another day within budget — your streak continues."),
    ("budget_exceptional", "⭐", "#FDD835", "Exceptional saving", "budget", "An exceptional saving day."),
    ("budget_major_win", "💎", "#00ACC1", "Major win", "budget", "A major financial win."),
    # --- income (Sprint 3 emits a generic 'income'; S4 refines by source) ---
    ("income", "💼", "#1E88E5", "Income", "income", "{amount} received on {date}."),
    ("income_salary", "💼", "#1E88E5", "Salary", "income", "Salary of {amount} received."),
    ("income_family", "👨‍👩‍👦", "#8E24AA", "From family", "income", "{amount} received from family."),
    ("income_gift", "🎁", "#D81B60", "Gift", "income", "Gift of {amount} received."),
    ("income_freelance", "💵", "#00897B", "Freelance", "income", "Freelance income of {amount}."),
    ("income_bonus", "🏆", "#F4511E", "Bonus", "income", "Bonus of {amount} received."),
    ("borrowed_received", "📥", "#6D4C41", "Borrowed", "income", "Borrowed {amount} received."),
    # --- expense flavour (S4) ---
    ("expense_shopping", "🛒", "#AB47BC", "Shopping", "expense", "A shopping day."),
    ("expense_food", "🍔", "#FF7043", "Food", "expense", "Higher food spending."),
    ("expense_travel", "🚕", "#42A5F5", "Travel", "expense", "Travel-heavy spending."),
    ("expense_entertainment", "🎮", "#EC407A", "Entertainment", "expense", "Entertainment spending."),
    ("expense_medical", "🏥", "#EF5350", "Medical", "expense", "A medical expense."),
    ("expense_education", "🎓", "#26A69A", "Education", "expense", "An education expense."),
    ("expense_rent", "🏠", "#8D6E63", "Rent", "expense", "Rent paid."),
    # --- financial commitments (S4) ---
    ("subscription", "💳", "#5C6BC0", "Subscription", "commitment", "{name} subscription of {amount}."),
    ("emi", "🏦", "#3949AB", "EMI / Loan", "commitment", "{name} EMI of {amount}."),
    ("bill", "📄", "#78909C", "Bill", "commitment", "{name} bill of {amount}."),
    ("insurance", "🛡️", "#546E7A", "Insurance", "commitment", "{name} insurance of {amount}."),
    ("payment_due", "⚠️", "#FB8C00", "Payment due soon", "commitment", "{name} of {amount} is due {when}."),
    # --- planning (Sprint 3 emits 'event') ---
    ("event", "📅", "#7E57C2", "Planned event", "planning", "{title} planned for {date}."),
    ("trip", "✈️", "#29B6F6", "Trip", "planning", "{title} trip planned."),
    ("outing", "❤️", "#EC407A", "Outing", "planning", "{title} outing planned."),
    ("birthday", "🎂", "#FFB300", "Birthday", "planning", "{title}."),
    ("celebration", "🎉", "#FDD835", "Celebration", "planning", "{title}."),
    ("gift", "🎁", "#D81B60", "Gift", "planning", "A gift you're planning."),
    ("surprise_gift", "🤫", "#AB47BC", "Surprise gift", "planning", "A surprise gift — kept under wraps. {title}."),
    ("anniversary", "💞", "#EC407A", "Anniversary", "planning", "{title}."),
    ("graduation", "🎓", "#26A69A", "Graduation", "planning", "{title}."),
    ("festival", "🪔", "#FF7043", "Festival", "planning", "{title}."),
    ("goal_milestone", "🎯", "#26C6DA", "Goal milestone", "planning", "Goal milestone reached."),
    ("goal_completed", "🏁", "#43A047", "Goal completed", "planning", "Goal completed — well done."),
    # --- advisor (S4) ---
    ("advisor_rec", "🤖", "#5E35B1", "Advisor note", "advisor", "I have a recommendation for you."),
    ("advisor_warning", "❗", "#E53935", "Warning", "advisor", "An important financial note."),
    ("trend_up", "📈", "#43A047", "Positive trend", "advisor", "A positive trend."),
    ("trend_down", "📉", "#E53935", "Negative trend", "advisor", "A trend worth watching."),
    ("review", "🔍", "#1E88E5", "Review", "advisor", "A review is recommended."),
    # --- relationship / lent money (S4; mostly commentary, light markers) ---
    ("lent", "💸", "#FB8C00", "Money lent", "relationship", "You lent {amount} to {person}."),
    ("returned", "💰", "#43A047", "Money returned", "relationship", "{person} returned {amount}."),
    ("repay_due_soon", "⏰", "#FB8C00", "Repayment due soon", "relationship", "{person} should return {amount} soon."),
    ("repay_overdue", "🚨", "#E53935", "Repayment overdue", "relationship", "{person}'s repayment is overdue."),
    # --- life events (S4; context for advice) ---
    ("life_child", "👶", "#26A69A", "Child", "life_event", "A child-related expense."),
    ("life_wedding", "💍", "#D81B60", "Wedding", "life_event", "A wedding-related expense."),
    ("life_house", "🏡", "#8D6E63", "House", "life_event", "A house-related expense."),
    ("life_vehicle", "🚗", "#42A5F5", "Vehicle", "life_event", "A vehicle-related expense."),
    ("life_laptop", "💻", "#546E7A", "Laptop", "life_event", "A laptop purchase."),
    ("life_phone", "📱", "#546E7A", "Phone", "life_event", "A phone purchase."),
    ("life_pet", "🐕", "#8D6E63", "Pet", "life_event", "A pet-related expense."),
]

MARKER_TYPES: dict[str, MarkerType] = {d[0]: MarkerType(*d) for d in _DEFS}

# Keys Sprint 3 actually computes from existing data.
SPRINT3_KEYS = frozenset({"budget_over", "budget_within", "budget_saved", "income", "event"})


def all_markers() -> list[MarkerType]:
    return list(MARKER_TYPES.values())
