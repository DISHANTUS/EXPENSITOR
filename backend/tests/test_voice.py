"""Sprint 5a tests: concise, length-aware spoken_text for the voice companion.
spoken_text is built from the deterministic greeting (grounded, Ollama-independent),
emoji-free, and respects the voice_length setting."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio

MOOD = "/api/v1/companion/mood"
SETTINGS = "/api/v1/users/me/settings"


def _today():
    return datetime.now(timezone.utc).date()


async def _auth(client: AsyncClient, email: str) -> dict[str, str]:
    await client.post("/api/v1/auth/register", json={"email": email, "password": "Password123"})
    tokens = (await client.post("/api/v1/auth/login", json={"email": email, "password": "Password123"})).json()
    h = {"Authorization": f"Bearer {tokens['access_token']}"}
    await client.patch(SETTINGS, json={"timezone": "UTC", "base_currency": "INR"}, headers=h)
    return h


async def _seed_two_facts(client: AsyncClient, h: dict[str, str]) -> None:
    # A repayment (relationship) + a goal (goal) -> two distinct greeting facts.
    await client.post("/api/v1/receivables",
                      json={"title": "Loan", "source_name": "Ravi", "source_type": "friend", "kind": "one_time",
                            "original_amount": "3000", "original_currency": "INR",
                            "expected_date": _today().isoformat()}, headers=h)
    await client.post("/api/v1/savings-goals",
                      json={"name": "Japan Fund", "kind": "custom_goal", "original_amount": "300000",
                            "original_currency": "INR", "target_date": (_today() + timedelta(days=400)).isoformat()},
                      headers=h)


async def test_voice_length_controls_spoken_length(client: AsyncClient) -> None:
    h = await _auth(client, "v1@example.com")
    await _seed_two_facts(client, h)

    await client.patch(SETTINGS, json={"voice_length": "short"}, headers=h)
    short = (await client.get(MOOD, headers=h)).json()["greeting"]["spoken_text"]
    await client.patch(SETTINGS, json={"voice_length": "detailed"}, headers=h)
    detailed = (await client.get(MOOD, headers=h)).json()["greeting"]["spoken_text"]

    assert "Ravi" in short and "Ravi" in detailed                 # the top fact is always spoken
    assert "japan" not in short.lower()                           # short drops the secondary fact
    assert "japan" in detailed.lower()                            # detailed keeps it
    assert len(detailed) > len(short)


async def test_spoken_text_is_emoji_free_and_grounded(client: AsyncClient) -> None:
    h = await _auth(client, "v2@example.com")
    await _seed_two_facts(client, h)
    g = (await client.get(MOOD, headers=h)).json()["greeting"]
    assert "💸" not in g["spoken_text"] and "🔥" not in g["spoken_text"]   # TTS-friendly
    assert "3,000" in g["spoken_text"]                            # amount preserved (grounded)


async def test_voice_length_persists_and_validates(client: AsyncClient) -> None:
    h = await _auth(client, "v3@example.com")
    await client.patch(SETTINGS, json={"voice_length": "detailed"}, headers=h)
    s = (await client.get(SETTINGS, headers=h)).json()
    assert s["voice_length"] == "detailed"
    bad = await client.patch(SETTINGS, json={"voice_length": "loud"}, headers=h)
    assert bad.status_code == 422
