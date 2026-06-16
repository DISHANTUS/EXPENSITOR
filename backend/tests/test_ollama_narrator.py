"""Pure tests for the generic narrator (C5 Phase 3b) — injected fake generate."""

from __future__ import annotations

import asyncio

import pytest

from app.intelligence.commentary.ollama import adapter, narrator

pytestmark = pytest.mark.asyncio

DET = {
    "paragraphs": [
        "₹250 expense added (Food & Dining). I checked this against today's budget, your goals and upcoming plans.",
        "₹683 left to spend today. Your next expected income is ₹15,000 from your father on Jun 24.",
    ],
    "attention": None,
    "timing_note": "Your next expected income is ₹15,000 from your father on Jun 24.",
    "most_useful_number": "₹683 left to spend today.",
    "confidence_note": None,
    "severity": "info",
    "facts": {"grounding": ["15000.0000", "2026-06-24", "your father", "250.0000", "683.0000"]},
}

FAITHFUL = (
    "I've logged your ₹250 Food & Dining expense, checked against today's budget, your goals and plans.\n\n"
    "That leaves ₹683 to spend today; your next expected income is ₹15,000 from your father on Jun 24."
)


def _req(style="balanced"):
    return adapter.from_commentary(DET, style=style)


async def test_faithful_succeeds():
    async def gen(_messages):
        return FAITHFUL
    r = await narrator.narrate(_req(), generate=gen)
    assert r.ok and r.status == "success" and len(r.paragraphs) == 2


async def test_hallucination_is_validation_failed():
    async def gen(_messages):
        return FAITHFUL.replace("to spend today;", "to spend today; also set aside ₹2,000;")
    r = await narrator.narrate(_req(), generate=gen)
    assert not r.ok and r.status == "validation_failed" and "2000" in r.offending_tokens


async def test_empty_output_is_error():
    async def gen(_messages):
        return "   "
    r = await narrator.narrate(_req(), generate=gen)
    assert not r.ok and r.status == "error"


async def test_timeout_falls_back():
    async def gen(_messages):
        raise asyncio.TimeoutError
    r = await narrator.narrate(_req(), generate=gen)
    assert not r.ok and r.status == "timeout"


async def test_exception_never_escapes():
    async def gen(_messages):
        raise RuntimeError("ollama down")
    r = await narrator.narrate(_req(), generate=gen)
    assert not r.ok and r.status == "error"


async def test_style_flows_into_prompt():
    captured = {}

    async def gen(messages):
        captured["user"] = messages[1]["content"]
        return FAITHFUL
    await narrator.narrate(_req(style="concise"), generate=gen)
    assert "short as possible" in captured["user"]
    assert "Facts you must preserve EXACTLY" in captured["user"]
