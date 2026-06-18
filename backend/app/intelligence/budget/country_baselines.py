"""Country baseline living costs (Budget Intelligence System — Phase 6).

Reference data ONLY — never the truth. The user's real spending always wins; a
baseline lets Advary say "you're below/above the local average for someone like
you," never "spend up to the average."

Profile-specific (a PG student in Tokyo ≠ a 35-year-old salaried worker in Tokyo)
and confidence-scored (some countries have better data than others). Amounts are in
the country's local currency. Bundled here so the app works offline from day one; an
optional best-effort web refresh can update the cache later (see baseline_service).
"""

from __future__ import annotations

from app.models.enums import LifeStage

# life_stage → coarse baseline group.
_STUDENT = {
    LifeStage.middle_school, LifeStage.high_school, LifeStage.ug_student,
    LifeStage.pg_student, LifeStage.scholarship_student,
}
_WORKING = {LifeStage.working_professional, LifeStage.self_employed, LifeStage.business_owner}


def group_for(life_stage: LifeStage | None) -> str:
    if life_stage in _STUDENT:
        return "student"
    if life_stage in _WORKING:
        return "working"
    return "default"


# country (ISO alpha-2) → { currency, confidence, groups{student/working/default},
# optional per-life-stage overrides }. food_daily + transport_monthly in local currency.
_BASELINES: dict[str, dict] = {
    "IN": {
        "currency": "INR", "confidence": "high",
        "groups": {
            "student": {"food_daily": 180, "transport_monthly": 1500},
            "working": {"food_daily": 300, "transport_monthly": 3000},
            "default": {"food_daily": 220, "transport_monthly": 2000},
        },
        "life_stage": {
            "pg_student": {"food_daily": 200, "transport_monthly": 1800},
        },
    },
    "JP": {
        "currency": "JPY", "confidence": "high",
        "groups": {
            "student": {"food_daily": 900, "transport_monthly": 8000},
            "working": {"food_daily": 1400, "transport_monthly": 12000},
            "default": {"food_daily": 1100, "transport_monthly": 10000},
        },
        "life_stage": {
            "pg_student": {"food_daily": 950, "transport_monthly": 9000},
        },
    },
    "US": {
        "currency": "USD", "confidence": "medium",
        "groups": {
            "student": {"food_daily": 18, "transport_monthly": 70},
            "working": {"food_daily": 30, "transport_monthly": 120},
            "default": {"food_daily": 22, "transport_monthly": 90},
        },
    },
    "GB": {
        "currency": "GBP", "confidence": "medium",
        "groups": {
            "student": {"food_daily": 12, "transport_monthly": 80},
            "working": {"food_daily": 20, "transport_monthly": 140},
            "default": {"food_daily": 15, "transport_monthly": 100},
        },
    },
}

_UNKNOWN = {"currency": None, "confidence": "low",
            "groups": {"default": {"food_daily": None, "transport_monthly": None}}}


def lookup(country: str | None, life_stage: LifeStage | None) -> dict:
    """Return the profile-specific baseline for a country, with confidence and source.
    Unknown country → low-confidence empty baseline (Advary then omits comparisons)."""
    code = (country or "").upper()
    entry = _BASELINES.get(code)
    if entry is None:
        return {"country": code or None, "group": group_for(life_stage), "currency": None,
                "food_daily": None, "transport_monthly": None, "confidence": "low", "source": "none"}

    group = group_for(life_stage)
    values = dict(entry["groups"].get(group, entry["groups"]["default"]))
    # A per-life-stage override (e.g. PG students) refines the group when present.
    ls_override = entry.get("life_stage", {}).get(life_stage.value if life_stage else "")
    if ls_override:
        values.update(ls_override)
    return {
        "country": code, "group": group, "currency": entry["currency"],
        "food_daily": values.get("food_daily"), "transport_monthly": values.get("transport_monthly"),
        "confidence": entry["confidence"], "source": "bundled",
    }


def compare(user_value: float | None, baseline_value: float | None) -> str:
    """Position a user's spend against the baseline. NEVER prescriptive — pure context.
    Returns: below | typical | above | unknown."""
    if user_value is None or not baseline_value:
        return "unknown"
    if user_value < baseline_value * 0.85:
        return "below"
    if user_value > baseline_value * 1.15:
        return "above"
    return "typical"
