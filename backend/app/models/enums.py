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
    confirmed = "confirmed"
    cancelled = "cancelled"
    converted = "converted"


class PlannedExpensePriority(str, enum.Enum):
    essential = "essential"
    important = "important"
    optional = "optional"
