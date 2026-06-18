"""The 4-bucket expense taxonomy (Budget Intelligence System — Reality Engine).

Every planned outflow belongs to exactly one bucket. When a savings goal doesn't
fit, Advary trims in this order — adjustable first, food (protected) last:

    ADJUSTABLE → GOAL → COMMITTED → PROTECTED

Deterministic classification (no LLM). VARCHAR-backed enums elsewhere keep it
extensible.
"""

from __future__ import annotations

from app.models.enums import ExpenseBucket, RecurringRuleType

# Cut priority: what Advary reduces first when a goal is short. Protected is last
# so essentials (food/medicine/transport/utilities) are touched only as a last resort.
CUT_ORDER: tuple[ExpenseBucket, ...] = (
    ExpenseBucket.adjustable,
    ExpenseBucket.goal,
    ExpenseBucket.committed,
    ExpenseBucket.protected,
)

# A recurring commitment's type → bucket. Utilities (bills) are PROTECTED; rent/
# loans/insurance are COMMITTED; subscriptions are ADJUSTABLE.
_RECURRING_BUCKET: dict[RecurringRuleType, ExpenseBucket] = {
    RecurringRuleType.subscription: ExpenseBucket.adjustable,
    RecurringRuleType.emi: ExpenseBucket.committed,
    RecurringRuleType.loan: ExpenseBucket.committed,
    RecurringRuleType.insurance: ExpenseBucket.committed,
    RecurringRuleType.borrowed: ExpenseBucket.committed,
    RecurringRuleType.bill: ExpenseBucket.protected,
}

# Keyword → bucket for classifying free-text expense categories (used when reasoning
# over logged actuals). Order matters: first hit wins. Unknown → adjustable, so an
# unrecognized category is treated as trimmable rather than wrongly protected.
_CATEGORY_KEYWORDS: tuple[tuple[ExpenseBucket, tuple[str, ...]], ...] = (
    # Housing is PROTECTED (cut last, like food) — checked first so "rent" wins.
    (ExpenseBucket.protected, ("rent", "dorm", "housing", "mortgage", "lodging")),
    (ExpenseBucket.committed, ("tuition", "fees", "insurance", "loan", "emi")),
    (ExpenseBucket.protected, (
        "food", "grocer", "vegetable", "medic", "medicine", "health", "pharma", "doctor", "hospital",
        "utilit", "electric", "water", "gas", "internet", "phone", "mobile", "transport", "bus", "train",
        "metro", "fuel", "petrol", "commute", "education", "school", "college", "books",
    )),
    (ExpenseBucket.adjustable, (
        "eat", "restaurant", "dining", "cafe", "coffee", "snack", "entertain", "movie", "game",
        "gaming", "arcade", "bowling", "shop", "clothes", "subscription", "netflix", "fun",
        "hobby", "trip", "travel", "outing", "party", "alcohol",
    )),
)


def bucket_for_recurring(rule_type: RecurringRuleType) -> ExpenseBucket:
    return _RECURRING_BUCKET.get(rule_type, ExpenseBucket.committed)


def bucket_for_category(name: str | None) -> ExpenseBucket:
    text = (name or "").lower()
    for bucket, keywords in _CATEGORY_KEYWORDS:
        if any(k in text for k in keywords):
            return bucket
    return ExpenseBucket.adjustable


def is_protected(bucket: ExpenseBucket) -> bool:
    return bucket == ExpenseBucket.protected


# Within PROTECTED: housing (rent/dorm/fees) vs essential living (food/utilities/...).
_HOUSING_WORDS = ("rent", "dorm", "housing", "mortgage", "lodging")


def protected_kind(label: str | None) -> str:
    return "housing" if any(w in (label or "").lower() for w in _HOUSING_WORDS) else "essential_living"
