"""4c-B1 tests: component greeting engine — relationship priority, special-day
hierarchy (one CRITICAL), presence-band depth, category rotation, style, variation,
voice-compat, and the always-alive-offline guarantee (no LLM in B1)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from app.intelligence.mood import greeting as G
from app.models import CompanionEvent, User
from app.models.enums import CompanionEventType

pytestmark = pytest.mark.asyncio

MOOD = "/api/v1/companion/mood"


def _today():
    return datetime.now(timezone.utc).date()


def _ctx(**kw) -> G.GreetingContext:
    base = dict(time_of_day="afternoon", tone="encouraging", style="balanced", presence_band="familiar",
                special_day=None, named_facts=[], goal_name=None, streak_days=0, follow_up=None)
    base.update(kw)
    return G.GreetingContext(**base)


def _inc(label="Salary"):
    return G.NamedFact(kind="income_today", tier=G.HIGH, label=label, amount="₹5,000", when_label="today")


def _date():
    return G.NamedFact(kind="event", tier=G.HIGH, occasion="date", person="Naruse", when_label="this evening")


# --- pure composition --------------------------------------------------------
def test_relationship_outranks_finance() -> None:
    g = G.build_greeting(_ctx(named_facts=[_inc(), _date()]), seed=1)
    assert g.category == "relationship"
    assert "❤️" in g.lines[0]                       # life first, money second


def test_special_day_critical_is_one_focused_celebration() -> None:
    g = G.build_greeting(_ctx(special_day="first_salary", named_facts=[_inc(), _date()], presence_band="familiar"), seed=1)
    assert g.special_day == "first_salary"
    assert "milestone" in g.lines[0].lower() or "first income" in g.lines[0].lower()
    # No competing event lines — one CRITICAL celebration only.
    assert not any("naruse" in ln.lower() or "salary" in ln.lower() for ln in g.lines)


def test_presence_band_controls_depth() -> None:
    new = G.build_greeting(_ctx(named_facts=[_inc()], presence_band="new"), seed=1)
    deep = G.build_greeting(_ctx(named_facts=[_inc()], goal_name="Japan Fund", streak_days=12,
                                 follow_up="You mentioned partial progress.", presence_band="deeply_personalized"), seed=1)
    assert len(new.lines) < len(deep.lines)


def test_category_rotation_avoids_repeating_focus() -> None:
    # Relationship led the last two days -> demote it, lead elsewhere today.
    g = G.build_greeting(_ctx(named_facts=[_date(), _inc()], goal_name="Japan Fund"),
                         seed=1, recent_categories=["relationship", "relationship"])
    assert g.category != "relationship"


def test_variation_by_day_seed() -> None:
    a = G.build_greeting(_ctx(named_facts=[_inc()]), seed=0)
    b = G.build_greeting(_ctx(named_facts=[_inc()]), seed=1)
    assert (a.salutation, a.lines) != (b.salutation, b.lines)   # different day -> different wording


def test_style_changes_wording_not_facts() -> None:
    anime = G.build_greeting(_ctx(named_facts=[_inc()], style="anime"), seed=1)
    minimal = G.build_greeting(_ctx(named_facts=[_inc()], style="minimal"), seed=1)
    assert "~" in anime.salutation                             # anime flair (+ a trailing time emoji)
    assert "Good " not in minimal.salutation                    # minimal drops the "Good "
    # The fact (salary today) survives in both.
    assert any("salary" in ln.lower() for ln in anime.lines)
    assert any("salary" in ln.lower() for ln in minimal.lines)


# --- API / service -----------------------------------------------------------
async def _auth(client: AsyncClient, email: str, **settings) -> dict[str, str]:
    await client.post("/api/v1/auth/register", json={"email": email, "password": "Password123"})
    tokens = (await client.post("/api/v1/auth/login", json={"email": email, "password": "Password123"})).json()
    h = {"Authorization": f"Bearer {tokens['access_token']}"}
    await client.patch("/api/v1/users/me/settings", json={"timezone": "UTC", "base_currency": "INR", **settings}, headers=h)
    return h


async def test_mood_endpoint_includes_greeting(client: AsyncClient) -> None:
    h = await _auth(client, "gr1@example.com")
    m = (await client.get(MOOD, headers=h)).json()
    g = m["greeting"]
    assert g and g["salutation"] and g["category"] and g["summary"]   # voice-compat fields present


async def test_companion_style_changes_greeting_wording(client: AsyncClient) -> None:
    h = await _auth(client, "gr2@example.com", companion_style="anime")
    g = (await client.get(MOOD, headers=h)).json()["greeting"]
    assert "~" in g["salutation"]


async def test_greeting_logged_once_per_day(client: AsyncClient, db_session) -> None:
    h = await _auth(client, "gr3@example.com")
    uid = await db_session.scalar(select(User.id).where(User.email == "gr3@example.com"))
    await client.get(MOOD, headers=h)
    await client.get(MOOD, headers=h)                                 # second fetch same day
    n = await db_session.scalar(select(func.count()).select_from(CompanionEvent).where(
        CompanionEvent.user_id == uid, CompanionEvent.event_type == CompanionEventType.system,
        CompanionEvent.action == "greeting"))
    assert n == 1                                                     # not spammed per poll


async def test_special_day_greeting_on_completed_goal(client: AsyncClient) -> None:
    h = await _auth(client, "gr4@example.com")
    g = (await client.post("/api/v1/savings-goals",
                           json={"name": "Japan Fund", "kind": "custom_goal", "original_amount": "300000",
                                 "original_currency": "INR",
                                 "target_date": (_today() + timedelta(days=400)).isoformat()}, headers=h)).json()
    await client.patch(f"/api/v1/savings-goals/{g['id']}", json={"status": "completed"}, headers=h)
    greeting = (await client.get(MOOD, headers=h)).json()["greeting"]
    assert greeting["special_day"] == "goal_completed"
    assert "🏆" in " ".join(greeting["lines"]) or "goal" in greeting["lines"][0].lower()
