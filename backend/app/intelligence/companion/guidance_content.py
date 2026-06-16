"""Static guided-help registry (deterministic content, NOT calculation).

Keyed by screen `surface` and by button `action` / onboarding step. Returned
inline for page-open / button-click / onboarding events; never persisted.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.models.enums import CompanionCategory, CompanionSeverity

_INFO = CompanionSeverity.info
_PAGE = CompanionCategory.page_guidance
_ACTION = CompanionCategory.action_guidance


@dataclass(frozen=True)
class GuidanceContent:
    title: str
    message: str
    severity: CompanionSeverity
    category: CompanionCategory


PAGE_GUIDANCE: dict[str, GuidanceContent] = {
    "dashboard": GuidanceContent("Dashboard", "Your money at a glance — balance, spending, and what's coming up.", _INFO, _PAGE),
    "home": GuidanceContent("Home", "Your money at a glance — balance, spending, and what's coming up.", _INFO, _PAGE),
    "converter": GuidanceContent("Currency Converter", "Here you can convert currencies and view conversion rates.", _INFO, _PAGE),
    "expenses": GuidanceContent("Expenses", "Add expenses here to improve your spending analysis.", _INFO, _PAGE),
    "income": GuidanceContent("Income", "Record income here so your projections stay accurate.", _INFO, _PAGE),
    "income_sources": GuidanceContent("Income Sources", "Set up recurring or expected income so we can plan ahead.", _INFO, _PAGE),
    "planned_expenses": GuidanceContent("Planner", "Schedule future expenses and we'll check if they fit your budget.", _INFO, _PAGE),
    "timeline": GuidanceContent("Timeline", "See your projected balance and upcoming money events.", _INFO, _PAGE),
    "settings": GuidanceContent("Settings", "Set your base currency, monthly limit, and preferences here.", _INFO, _PAGE),
    "profile": GuidanceContent("Profile", "Manage your account details here.", _INFO, _PAGE),
}

ACTION_GUIDANCE: dict[str, GuidanceContent] = {
    "add_expense": GuidanceContent("Add expense", "Add an expense here — you can edit or delete it later.", _INFO, _ACTION),
    "edit_expense": GuidanceContent("Edit expense", "Update this expense; your analysis refreshes automatically.", _INFO, _ACTION),
    "delete_expense": GuidanceContent("Delete expense", "Remove this expense — it won't count toward your spending.", _INFO, _ACTION),
    "add_income": GuidanceContent("Add income", "Record income you've received; it improves your outlook.", _INFO, _ACTION),
    "add_planned_expense": GuidanceContent("Plan an expense", "Schedule a future expense and we'll check affordability.", _INFO, _ACTION),
    "convert": GuidanceContent("Convert", "Enter an amount and pick currencies to see the converted value.", _INFO, _ACTION),
    "save_settings": GuidanceContent("Save settings", "Save your preferences — projections will use them right away.", _INFO, _ACTION),
}

ONBOARDING_GUIDANCE: dict[str, GuidanceContent] = {
    "welcome": GuidanceContent("Welcome to Expensitor", "Let's set up your finances so I can guide you day to day.", _INFO, _PAGE),
    "set_currency": GuidanceContent("Pick your currency", "Choose your base currency — all amounts are shown in it.", _INFO, _PAGE),
    "set_threshold": GuidanceContent("Set a monthly limit", "Set a monthly spending limit and I'll help you stay under it.", _INFO, _PAGE),
    "add_first_income": GuidanceContent("Add your income", "Tell me your income so I can plan your month.", _INFO, _PAGE),
    "add_first_expense": GuidanceContent("Log an expense", "Log your first expense to start your spending analysis.", _INFO, _PAGE),
}

_DEFAULT_PAGE = GuidanceContent("Expensitor", "Explore and manage your finances here.", _INFO, _PAGE)
_DEFAULT_ACTION = GuidanceContent("Action", "You can perform this action here.", _INFO, _ACTION)


def _key(value: str | None) -> str:
    return (value or "").strip().lower()


def for_page(surface: str | None) -> GuidanceContent:
    return PAGE_GUIDANCE.get(_key(surface), _DEFAULT_PAGE)


def for_action(action_or_surface: str | None) -> GuidanceContent:
    return ACTION_GUIDANCE.get(_key(action_or_surface), _DEFAULT_ACTION)


def for_onboarding(step: str | None) -> GuidanceContent:
    return ONBOARDING_GUIDANCE.get(_key(step), _DEFAULT_PAGE)
