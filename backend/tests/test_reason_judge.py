"""Reason-sufficiency judge: deterministic fast-path, Ollama escalation (with an
injected fake `generate`), and the always-safe fallback when the model fails."""

from __future__ import annotations

import pytest

from app.intelligence.companion.reason_judge import judge_sufficiency

pytestmark = pytest.mark.asyncio


async def test_empty_or_filler_reasons_are_insufficient_without_a_model():
    assert await judge_sufficiency(None) is False
    assert await judge_sufficiency("") is False
    assert await judge_sufficiency("idk") is False
    assert await judge_sufficiency("just did") is False
    assert await judge_sufficiency("no reason") is False


async def test_recognized_circumstance_is_accepted_without_a_model():
    assert await judge_sufficiency("had a medical emergency this week") is True
    assert await judge_sufficiency("went on a trip with friends") is True


async def test_ambiguous_reason_escalates_to_the_model_when_available():
    calls = []

    async def fake_generate(messages):
        calls.append(messages)
        return '{"sufficient": true}'

    result = await judge_sufficiency("ordering more takeout lately", category="Food", generate=fake_generate)
    assert result is True
    assert len(calls) == 1
    assert "Food" in calls[0][1]["content"]


async def test_model_can_reject_a_plausible_looking_but_empty_answer():
    async def fake_generate(messages):
        return '{"sufficient": false}'

    result = await judge_sufficiency("just spending as usual", generate=fake_generate)
    assert result is False


async def test_model_failure_falls_back_to_deterministic_heuristic():
    async def broken_generate(messages):
        raise RuntimeError("model unreachable")

    # Long enough, multi-word -> fallback accepts.
    assert await judge_sufficiency("started ordering lunch delivery most days", generate=broken_generate) is True
    # Short and vague -> fallback still rejects.
    assert await judge_sufficiency("dunno really", generate=broken_generate) is False


async def test_filler_wrapped_in_a_trailing_word_is_still_rejected():
    assert await judge_sufficiency("nothing much") is False
    assert await judge_sufficiency("not sure tbh") is False


async def test_substantive_reasons_are_never_falsely_flagged_as_filler():
    # Regression guard: an early substring-based filler check would wrongly
    # match "na" inside "banana", or "because" as a prefix of a real sentence.
    assert await judge_sufficiency("bought a lot of banana chips this week") is True
    assert await judge_sufficiency("because I had a work event every night this week") is True
    assert await judge_sufficiency("not sure why, but I've been ordering takeout most nights") is True


async def test_malformed_model_reply_falls_back_to_deterministic_heuristic():
    async def bad_json(messages):
        return "not json at all"

    assert await judge_sufficiency("started ordering lunch delivery most days", generate=bad_json) is True


async def test_no_generate_callable_uses_fallback_directly():
    assert await judge_sufficiency("started ordering lunch delivery most days", generate=None) is True
    assert await judge_sufficiency("eh", generate=None) is False
