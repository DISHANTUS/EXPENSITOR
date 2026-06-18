"""First-launch guided tour + 'how do I…' app-help (chat & voice).

The companion teaches the app: a sequenced tour and step-by-step how-to answers
that surface in both the chat advisor and the voice layer.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def _auth(client: AsyncClient, email: str = "tourist@example.com") -> dict[str, str]:
    await client.post("/api/v1/auth/register", json={"email": email, "password": "Password123"})
    tok = (await client.post("/api/v1/auth/login", json={"email": email, "password": "Password123"})).json()
    return {"Authorization": f"Bearer {tok['access_token']}"}


async def test_new_user_has_not_seen_tour(client: AsyncClient):
    h = await _auth(client)
    assert (await client.get("/api/v1/users/me", headers=h)).json()["has_seen_tour"] is False


async def test_tour_steps_ordered_named_and_tts_clean(client: AsyncClient):
    h = await _auth(client)
    await client.patch("/api/v1/users/me/settings", json={"companion_name": "Kai"}, headers=h)
    out = (await client.get("/api/v1/companion/tour", headers=h)).json()

    assert out["companion_name"] == "Kai"
    keys = [s["key"] for s in out["steps"]]
    assert keys[0] == "welcome" and keys[-1] == "done"
    assert {"home", "budget_setup", "plan_today", "timeline", "future_me",
            "advisor", "relationships", "settings"} <= set(keys)

    routes = {s["key"]: s["route"] for s in out["steps"]}
    assert routes["budget_setup"] == "/budget-setup"
    assert routes["advisor"] == "/advisor"
    assert routes["future_me"] == "/future-me"

    for s in out["steps"]:
        assert s["narration"] and s["spoken_text"]
        # spoken_text is plain text for TTS — no emoji from the card icons.
        assert all(emoji not in s["spoken_text"] for emoji in ("🗓️", "🎯", "🔮", "✨", "👋"))
    # the named companion is woven into the intro
    assert "Kai" in out["steps"][0]["narration"]


async def test_complete_tour_sets_flag(client: AsyncClient):
    h = await _auth(client)
    r = (await client.post("/api/v1/companion/tour/complete", headers=h)).json()
    assert r["ok"] is True and r["has_seen_tour"] is True
    assert (await client.get("/api/v1/users/me", headers=h)).json()["has_seen_tour"] is True


@pytest.mark.parametrize("question,route", [
    ("how do i set a budget?", "/budget-setup"),
    ("where do i add an expense", "/home"),
    ("how do i record my income", "/home"),
    ("how do i plan a purchase", "/budget-setup"),
    ("how do i mark an event on a date", "/home"),
    ("how do i lend money to a friend", "/home"),
    ("how do i talk to you", "/advisor"),
    ("how do i change my currency", "/convert"),
    ("how do i rename you", "/settings"),
    ("how do i see future me", "/future-me"),
    ("help me add an expense", "/home"),
])
async def test_chat_how_to(client: AsyncClient, question: str, route: str):
    h = await _auth(client)
    turn = (await client.post("/api/v1/advisor/chat", json={"message": question}, headers=h)).json()
    assert turn["type"] == "help"
    assert turn["route"] == route
    assert turn["message"]


async def test_chat_show_me_around_launches_tour(client: AsyncClient):
    h = await _auth(client)
    for q in ("show me around", "give me a tour", "how does this app work"):
        turn = (await client.post("/api/v1/advisor/chat", json={"message": q}, headers=h)).json()
        assert turn["type"] == "tour", q
        assert turn["route"] == "/home"


async def test_capability_mentions_help_and_tour(client: AsyncClient):
    h = await _auth(client)
    turn = (await client.post("/api/v1/advisor/chat", json={"message": "what can you do"}, headers=h)).json()
    low = (turn["message"] or "").lower()
    assert "how do i" in low and "show me around" in low


async def test_financial_query_not_hijacked_by_help(client: AsyncClient):
    h = await _auth(client)
    # A plain how-much/report question must NOT be captured by the how-to layer.
    for q in ("weekly report", "who owes me money", "how much did i spend on food"):
        turn = (await client.post("/api/v1/advisor/chat", json={"message": q}, headers=h)).json()
        assert turn["type"] not in ("help", "tour"), q


async def test_voice_how_to_round_trips(client: AsyncClient):
    h = await _auth(client)
    out = (await client.post("/api/v1/voice/ask", json={"text": "how do i set a budget"}, headers=h)).json()
    assert out["navigate"] == "/budget-setup"
    assert "budget" in out["speech"].lower()


async def test_voice_show_me_around(client: AsyncClient):
    h = await _auth(client)
    out = (await client.post("/api/v1/voice/ask", json={"text": "show me around"}, headers=h)).json()
    assert out["type"] == "tour"


async def test_full_reset_replays_tour(client: AsyncClient):
    h = await _auth(client, "advary2006@gmail.com")   # developer can reset
    await client.post("/api/v1/companion/tour/complete", headers=h)
    assert (await client.get("/api/v1/users/me", headers=h)).json()["has_seen_tour"] is True
    await client.post("/api/v1/reset", json={"mode": "full"}, headers=h)
    assert (await client.get("/api/v1/users/me", headers=h)).json()["has_seen_tour"] is False
