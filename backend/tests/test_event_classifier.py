"""The deterministic event classifier — title → planner occasion (no LLM)."""

from __future__ import annotations

from app.models.enums import OccasionType
from app.services.event_classifier import classify


def test_relationship_beats_food_for_dinner_with_someone():
    # "dinner with X" reads as a date, not a generic food outing.
    assert classify("Dinner with Naruse") == OccasionType.date


def test_plain_dinner_is_food():
    assert classify("Dinner at the new ramen place") == OccasionType.food


def test_common_events_map_to_expected_occasions():
    cases = {
        "Birthday party": OccasionType.birthday,
        "Trip to Tokyo": OccasionType.travel,
        "JLPT N4 exam": OccasionType.study,
        "Dentist appointment": OccasionType.medical,
        "Gaming night with the boys": OccasionType.gaming,
        "Movie night": OccasionType.entertainment,
        "Diwali festival": OccasionType.festival,
        "Our anniversary": OccasionType.anniversary,
        "Graduation ceremony": OccasionType.graduation,
    }
    for title, expected in cases.items():
        assert classify(title) == expected, title


def test_unknown_returns_none_for_low_confidence_fallback():
    # No keyword match → None, which the calendar renders as a neutral 📅.
    assert classify("Operation Crimson Moon") is None
    assert classify("") is None
    assert classify("   ") is None


def test_notes_are_used_when_the_title_is_vague():
    assert classify("Appointment", notes="dentist checkup") == OccasionType.medical
