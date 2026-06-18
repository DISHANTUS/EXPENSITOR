"""4c-A tests: mood engine — base selection (weather-proofed), event moods,
priority rotation + emergency override, lifetime windows, explainability, presence."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from httpx import AsyncClient

from app.intelligence.mood import composer, moods, presence
from app.intelligence.mood.base_mood import MoodContext, select_base

pytestmark = pytest.mark.asyncio

CHAT = "/api/v1/advisor/chat"
MOOD = "/api/v1/companion/mood"


def _today():
    return datetime.now(timezone.utc).date()


async def _auth(client: AsyncClient, email: str, **settings) -> dict[str, str]:
    await client.post("/api/v1/auth/register", json={"email": email, "password": "Password123"})
    tokens = (await client.post("/api/v1/auth/login", json={"email": email, "password": "Password123"})).json()
    h = {"Authorization": f"Bearer {tokens['access_token']}"}
    body = {"timezone": "UTC", "base_currency": "INR", **settings}
    await client.patch("/api/v1/users/me/settings", json=body, headers=h)
    return h


def _ctx(**kw) -> MoodContext:
    base = dict(has_data=True, total_spent=Decimal("0"), saved=Decimal("0"), red_days=0, crown_days=0,
                monthly_threshold=None, has_active_goal=False, overdue_loans=0)
    base.update(kw)
    return MoodContext(**base)


# --- base mood (pure, weather-proofed) ---------------------------------------
def test_base_mood_selection() -> None:
    assert select_base(_ctx(has_data=False)).mood_id == "neutral"
    assert select_base(_ctx(total_spent=Decimal("5000"), monthly_threshold=Decimal("4000"))).mood_id == "concerned"
    assert select_base(_ctx(total_spent=Decimal("4200"), monthly_threshold=Decimal("4000"))).mood_id == "slightly_over"
    assert select_base(_ctx(total_spent=Decimal("3000"), saved=Decimal("500"), crown_days=2,
                            monthly_threshold=Decimal("4000"))).mood_id == "saving_well"


def test_worst_mood_is_concerned_never_anger() -> None:
    # Even the bleakest finances bottom out at 'concerned'.
    worst = select_base(_ctx(total_spent=Decimal("99999"), monthly_threshold=Decimal("1000"),
                             red_days=20, overdue_loans=5)).mood_id
    assert worst == "concerned"
    # The library contains no anger/sad/dead mood at all.
    assert all(m.id not in ("angry", "sad", "dead", "furious") for m in moods.MOODS.values())
    assert "😡" not in {m.emoji for m in moods.MOODS.values()}


# --- composer: priority + override + rotation --------------------------------
def test_emergency_override_dominates() -> None:
    base = moods.get("concerned")                      # finances are rough...
    active = [moods.get("goal_completed"), moods.get("salary")]
    state = composer.compose(base, active)
    assert state.primary.id == "goal_completed"        # ...but a win takes over the face
    assert state.base.id == "concerned"
    assert len(state.rotation) > 1                     # never stuck on one emoji
    assert state.rotation[-1].id == "concerned"        # always returns to base


def test_rotation_orders_by_priority_and_weaves_base() -> None:
    base = moods.get("on_budget")
    state = composer.compose(base, [moods.get("salary"), moods.get("jlpt")])  # LOW + HIGH
    ids = [m.id for m in state.rotation]
    assert ids[0] == "on_budget"                       # no override -> base leads
    assert ids.index("jlpt") < ids.index("salary")     # higher-priority event surfaces first
    assert ids.count("on_budget") >= 2                 # base woven between events
    # no two consecutive identical faces
    assert all(ids[i] != ids[i + 1] for i in range(len(ids) - 1))


# --- lifetime windows --------------------------------------------------------
def test_mood_lifetimes() -> None:
    t = _today()
    assert moods.is_active(moods.get("goal_completed"), t - timedelta(days=2), t)   # days_3
    assert not moods.is_active(moods.get("goal_completed"), t - timedelta(days=4), t)
    assert moods.is_active(moods.get("first_salary"), t - timedelta(days=6), t)     # days_7
    assert moods.is_active(moods.get("salary"), t, t)                               # end_of_day
    assert not moods.is_active(moods.get("salary"), t - timedelta(days=1), t)


# --- presence ----------------------------------------------------------------
def test_presence_bands() -> None:
    assert presence.compute(days_logged=0, has_goal=False, has_income=False, has_receivables=False,
                            lessons=0, advice_count=0).band == "new"
    rich = presence.compute(days_logged=30, has_goal=True, has_income=True, has_receivables=True,
                            lessons=3, advice_count=5)
    assert rich.band == "deeply_personalized" and rich.score >= 80


# --- API / service -----------------------------------------------------------
async def test_mood_endpoint_neutral_on_thin_data(client: AsyncClient) -> None:
    h = await _auth(client, "md1@example.com")
    m = (await client.get(MOOD, headers=h)).json()
    assert m["primary"]["id"] == "neutral" and m["base"]["id"] == "neutral"
    assert m["presence_band"] == "new"


async def test_mood_concerned_when_over_budget(client: AsyncClient) -> None:
    h = await _auth(client, "md2@example.com", monthly_threshold="1000")
    await client.post("/api/v1/expenses",
                      json={"original_amount": "2500", "original_currency": "INR",
                            "expense_date": _today().isoformat()}, headers=h)
    m = (await client.get(MOOD, headers=h)).json()
    assert m["base"]["id"] == "concerned" and m["base"]["emoji"] == "😟"
    assert any(r["label"] == "Budget exceeded" for r in m["reasons"])


async def test_completed_goal_overrides_a_rough_budget(client: AsyncClient) -> None:
    h = await _auth(client, "md3@example.com", monthly_threshold="1000")
    await client.post("/api/v1/expenses",
                      json={"original_amount": "2500", "original_currency": "INR",
                            "expense_date": _today().isoformat()}, headers=h)
    g = (await client.post("/api/v1/savings-goals",
                           json={"name": "Japan Fund", "kind": "custom_goal", "original_amount": "300000",
                                 "original_currency": "INR",
                                 "target_date": (_today() + timedelta(days=400)).isoformat()}, headers=h)).json()
    await client.patch(f"/api/v1/savings-goals/{g['id']}", json={"status": "completed"}, headers=h)
    m = (await client.get(MOOD, headers=h)).json()
    assert m["primary"]["id"] == "goal_completed" and m["primary"]["emoji"] == "🏆"
    assert m["base"]["id"] == "concerned"          # base still honest underneath


async def test_event_mood_from_todays_income(client: AsyncClient) -> None:
    h = await _auth(client, "md4@example.com")
    await client.post("/api/v1/incomes", json={"source_type": "salary", "original_amount": "50000",
                                               "original_currency": "INR", "received_date": _today().isoformat()}, headers=h)
    m = (await client.get(MOOD, headers=h)).json()
    assert any(f["id"] == "salary" for f in m["rotation"])


async def test_chat_mood_is_explainable(client: AsyncClient) -> None:
    h = await _auth(client, "md5@example.com", monthly_threshold="1000")
    await client.post("/api/v1/expenses",
                      json={"original_amount": "2500", "original_currency": "INR",
                            "expense_date": _today().isoformat()}, headers=h)
    r = (await client.post(CHAT, json={"message": "why are you worried?"}, headers=h)).json()
    assert r["type"] == "advisory" and r["explain_ref"] == "mood:current"
    assert "concerned" in r["message"].lower()
    ex = (await client.post("/api/v1/advisor/explain", json={"ref": "mood:current"}, headers=h)).json()
    assert ex["claim"].startswith("Current mood")
    assert any(e["label"] == "Budget exceeded" for e in ex["evidence"])
