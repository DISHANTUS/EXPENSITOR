"""4c-B2 tests: Ollama greeting narration — rephrase-only, grounded (reject any
added/dropped fact), similarity regeneration, and deterministic fallback. The
LLM call is injected as a stub, so these run with no network."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.core.config import settings
from app.intelligence.mood import greeting_narration as gn
from app.services import ollama_service

pytestmark = pytest.mark.asyncio

MOOD = "/api/v1/companion/mood"
_SAL = "Good afternoon."
_LINES = ["Your salary arrives today.", "Your 12-day budget streak is alive."]


def _stub(text: str):
    async def gen(_messages):
        return text
    return gen


# --- adapter (pure) ----------------------------------------------------------
def test_spoken_text_is_plain_and_fact_complete() -> None:
    spoken = gn.spoken_text("Good afternoon~", ["Enjoy your outing ❤️", "Your 12-day streak is alive."])
    assert "❤️" not in spoken and "~" not in spoken
    assert "12-day" in spoken and "outing" in spoken          # facts survive for TTS


def test_grounding_captures_numbers() -> None:
    req = gn.build_request(_LINES, style="anime")              # facts (lines) only; salutation is verbatim
    assert "12" in req.grounding.allowed.get("number", set())  # streak count is grounded


# --- narrate_greeting (injected generate). The stub returns the BODY only; the
#     time salutation is prepended verbatim by narrate_greeting. ---------------
async def test_narration_accepts_faithful_rephrase() -> None:
    res = await ollama_service.narrate_greeting(
        _SAL, _LINES, recent_texts=[],
        generate=_stub("Your salary arrives today, and your 12-day budget streak is alive."))
    assert res["ok"] and res["source"] == "ollama"
    assert res["text"].startswith(_SAL)                        # time salutation preserved verbatim
    assert "12-day" in res["text"]


async def test_grounding_rejects_invented_numbers() -> None:
    res = await ollama_service.narrate_greeting(
        _SAL, _LINES, recent_texts=[],
        generate=_stub("Your salary of ₹500 arrives today, 99-day streak!"))
    assert not res["ok"] and res["status"] == "validation_failed" and res["source"] == "deterministic"


async def test_grounding_rejects_dropped_fact() -> None:
    res = await ollama_service.narrate_greeting(
        _SAL, _LINES, recent_texts=[], generate=_stub("Your salary arrives today."))
    assert not res["ok"] and res["status"] == "validation_failed"   # dropped the 12-day streak


async def test_similarity_triggers_fallback() -> None:
    body = "Your salary arrives today, and your 12-day budget streak is alive."
    full = f"{_SAL} {body}"                                    # narrate_greeting composes this
    res = await ollama_service.narrate_greeting(_SAL, _LINES, recent_texts=[full], generate=_stub(body))
    assert not res["ok"] and res["status"] == "too_similar" and res["source"] == "deterministic"


async def test_disabled_falls_back_to_deterministic(monkeypatch) -> None:
    monkeypatch.setattr(settings, "OLLAMA_ENABLED", False)
    res = await ollama_service.narrate_greeting(_SAL, _LINES, recent_texts=[])   # no injected generate
    assert not res["ok"] and res["status"] == "disabled" and res["source"] == "deterministic"


# --- end-to-end: app stays deterministic with Ollama off ---------------------
async def test_mood_greeting_is_deterministic_when_ollama_off(client: AsyncClient, monkeypatch) -> None:
    monkeypatch.setattr(settings, "OLLAMA_ENABLED", False)
    await client.post("/api/v1/auth/register", json={"email": "gn1@example.com", "password": "Password123"})
    tokens = (await client.post("/api/v1/auth/login", json={"email": "gn1@example.com", "password": "Password123"})).json()
    h = {"Authorization": f"Bearer {tokens['access_token']}"}
    await client.patch("/api/v1/users/me/settings", json={"timezone": "UTC", "base_currency": "INR"}, headers=h)
    g = (await client.get(MOOD, headers=h)).json()["greeting"]
    assert g["narration_source"] == "deterministic"
    assert g["display_text"] and g["spoken_text"]              # both always present (voice-ready)
