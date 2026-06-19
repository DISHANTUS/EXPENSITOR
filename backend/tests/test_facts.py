"""Fun facts — parser correctness (no numbers/headings/dividers leak), the
drop-in category model, and the endpoints. Plus: a fact is the companion's
*last* resort, only when nothing user-specific exists."""

from __future__ import annotations

import datetime as dt

from httpx import AsyncClient

from app.services import facts_service

# asyncio_mode = "auto" (pyproject) auto-detects the async tests; the sync parser
# tests below run as plain functions.


# --- Parser: the single guard that decides what reaches the user ---

_RAW = """1000 FACTS ABOUT FOOD
======================

--- FRUIT ---

1. Honey never spoils and has been found edible in ancient tombs.
2. Bananas are berries, but strawberries are not.

--- SPICES ---

3. Saffron is among the most expensive spices by weight.

==============
END OF 1000 FOOD FACTS
==============
"""


def test_parser_keeps_only_fact_text():
    facts = facts_service.parse_facts(_RAW)
    assert facts == [
        "Honey never spoils and has been found edible in ancient tombs.",
        "Bananas are berries, but strawberries are not.",
        "Saffron is among the most expensive spices by weight.",
    ]


def test_parser_strips_numbers_headings_dividers_footers():
    facts = facts_service.parse_facts(_RAW)
    blob = "\n".join(facts)
    # No serial numbers, banners, section dividers or footers survive.
    assert "1000 FACTS" not in blob
    assert "END OF" not in blob
    assert "---" not in blob and "===" not in blob
    for f in facts:
        assert not f[:3].strip().rstrip(".").isdigit()  # never starts with "N."


def test_parser_ignores_non_fact_lines():
    assert facts_service.parse_facts("--- ASIA ---\n\nJust a stray sentence.\n1990 was a year.") == []


# --- Endpoints ---

async def _auth(client: AsyncClient, email: str = "facts@example.com") -> dict[str, str]:
    await client.post("/api/v1/auth/register", json={"email": email, "password": "Password123"})
    tok = (await client.post("/api/v1/auth/login", json={"email": email, "password": "Password123"})).json()
    return {"Authorization": f"Bearer {tok['access_token']}"}


async def test_categories_endpoint_lists_starter_packs(client: AsyncClient):
    h = await _auth(client)
    cats = (await client.get("/api/v1/facts/categories", headers=h)).json()
    keys = {c["key"] for c in cats}
    assert {"money", "study", "world"} <= keys
    for c in cats:
        assert c["count"] > 0 and c["label"] and c["emoji"]


async def test_random_fact_has_no_leading_number(client: AsyncClient):
    h = await _auth(client)
    f = (await client.get("/api/v1/facts/random", headers=h)).json()
    assert f["text"] and f["category"] and f["category_label"]
    assert not f["text"].lstrip()[:4].split(".")[0].strip().isdigit()


async def test_random_respects_category_filter(client: AsyncClient):
    h = await _auth(client)
    f = (await client.get("/api/v1/facts/random?categories=money", headers=h)).json()
    assert f["category"] == "money"


async def test_daily_fact_is_deterministic_per_day(client: AsyncClient):
    h = await _auth(client)
    a = (await client.get("/api/v1/facts/daily?date=2026-06-18", headers=h)).json()
    b = (await client.get("/api/v1/facts/daily?date=2026-06-18", headers=h)).json()
    assert a == b  # same day → same fact (Home card doesn't reshuffle on refresh)


async def test_pack_endpoint_and_unknown_category(client: AsyncClient):
    h = await _auth(client)
    pack = (await client.get("/api/v1/facts/pack/money", headers=h)).json()
    assert pack["category"] == "money" and len(pack["facts"]) > 5
    missing = await client.get("/api/v1/facts/pack/nope-not-real", headers=h)
    assert missing.status_code == 404


# --- Fallback-only behaviour ---

def test_fallback_thought_prefixed_and_present():
    line = facts_service.fallback_thought(dt.date(2026, 6, 18))
    assert line and line.startswith("Did you know? ")


async def test_home_thought_stays_quiet_when_nothing_user_specific(client: AsyncClient):
    """A brand-new user's orb thought stays quiet (no fallback fact) — facts now
    live only in the Did You Know card. Once they add a goal, the goal line shows."""
    h = await _auth(client, "fallback@example.com")
    await client.patch("/api/v1/users/me/settings",
                       json={"base_currency": "INR", "timezone": "UTC"}, headers=h)

    empty = (await client.get("/api/v1/companion/home-thought", headers=h)).json()
    assert empty["lines"] == []

    # Add an income + a goal → the goal line takes over; the fact disappears.
    await client.post("/api/v1/income-sources", json={
        "label": "Salary", "source_type": "salary", "kind": "recurring",
        "original_amount": "50000", "original_currency": "INR", "recurrence_day": 1}, headers=h)
    await client.post("/api/v1/savings-goals", json={
        "name": "Japan Fund", "kind": "monthly_target",
        "original_amount": "2000", "original_currency": "INR"}, headers=h)

    after = (await client.get("/api/v1/companion/home-thought", headers=h)).json()
    blob = " ".join(after["lines"])
    assert "Did you know?" not in blob
    assert "Japan Fund" in blob
