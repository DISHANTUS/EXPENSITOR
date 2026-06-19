"""Deterministic event classifier (no LLM) — title → planner occasion.

So Advary tags a calendar event with a fitting emoji/animation and the user
never has to pick one. Pure keyword rules over the title (+ optional notes),
ordered most-specific first; returns ``None`` when nothing matches, which the
calendar renders as a neutral 📅 (the explicit low-confidence fallback).

The marker emoji + animation for the chosen occasion live in the marker registry
(``marker_types.py``) — this module only decides the category, keeping emoji and
animation assignment in one place.
"""

from __future__ import annotations

from app.models.enums import OccasionType

# (occasion, keywords). Order matters: the first rule that matches wins, so the
# more specific / relationship-flavoured rules sit above the generic ones (e.g.
# "dinner with …" → date, before plain "dinner" → food).
_RULES: list[tuple[OccasionType, tuple[str, ...]]] = [
    (OccasionType.birthday, ("birthday", "bday", "b'day", "turns ")),
    (OccasionType.anniversary, ("anniversary", "wedding")),
    (OccasionType.graduation, ("graduation", "convocation", "degree")),
    (OccasionType.date, ("date with", "date night", "dinner with", "lunch with",
                         "with gf", "with girlfriend", "with boyfriend", "with bf",
                         "romantic", "valentine")),
    (OccasionType.medical, ("doctor", "dentist", "hospital", "clinic", "appointment",
                            "checkup", "check-up", "surgery", "medical", "vaccine",
                            "therapy", "physio")),
    (OccasionType.study, ("exam", "jlpt", "test", "study", "assignment", "lecture",
                          "course", "revision", "homework", "semester", "quiz",
                          "interview prep")),
    (OccasionType.travel, ("trip", "flight", "travel", "tokyo", "japan", "goa",
                           "airport", "visa", "abroad", "tour", "train to",
                           "road trip")),
    (OccasionType.vacation, ("vacation", "holiday", "getaway", "staycation")),
    (OccasionType.gaming, ("gaming", "game night", "lan party", "esports", "valorant",
                           "playstation", "xbox", "tournament")),
    (OccasionType.festival, ("festival", "diwali", "holi", "christmas", "eid",
                             "navratri", "pongal", "onam", "new year")),
    (OccasionType.food, ("dinner", "lunch", "breakfast", "brunch", "restaurant",
                         "ramen", "cafe", "café", "pizza", "buffet", "eat out",
                         "food")),
    (OccasionType.entertainment, ("movie", "cinema", "concert", "show", "gig",
                                  "theatre", "theater", "netflix", "match", "play")),
    (OccasionType.celebration, ("party", "celebrate", "celebration", "farewell",
                                "reunion", "get together", "get-together", "send-off")),
    (OccasionType.shopping, ("shopping", "mall", "groceries", "grocery")),
    (OccasionType.outing, ("outing", "hangout", "hang out", "going out", "meetup",
                           "meet up", "picnic", "with friends", "trek", "hike")),
]


def classify(title: str, notes: str | None = None) -> OccasionType | None:
    """Best-fit occasion for an event, or ``None`` (→ generic 📅) when unsure."""
    text = f"{title or ''} {notes or ''}".lower()
    if not text.strip():
        return None
    for occasion, keywords in _RULES:
        if any(kw in text for kw in keywords):
            return occasion
    return None
