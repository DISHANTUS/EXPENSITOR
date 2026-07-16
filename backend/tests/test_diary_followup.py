"""Branching follow-ups: the "which fruits? -> what did it cost?" behaviour.

The point is that this is NOT a fruit script. It's one rule — ask about the
vaguest thing that was said — so most of these tests are about it working on
topics nobody wrote a branch for.
"""

from __future__ import annotations

import pytest

from app.intelligence.companion import diary_followup as fu


def _model(reply: str):
    async def generate(messages):
        return reply

    return generate


def _boom():
    async def generate(messages):
        raise RuntimeError("ollama is down")

    return generate


# --- the deterministic path -------------------------------------------------


@pytest.mark.parametrize(
    "note,expected",
    [
        ("bought fruits today", "Which fruits?"),
        ("got some vegetables from the market", "Which vegetables?"),
        ("picked up groceries", "What did you pick up?"),
        ("had juice in the evening", "Which juice?"),
        ("bought snacks", "Which snacks?"),
        ("bought some stuff", "What kind of stuff?"),
    ],
)
async def test_a_bag_of_things_gets_asked_about(note, expected):
    assert await fu.next_question(note) == expected


async def test_money_without_an_amount_gets_asked_about():
    assert await fu.next_question("bought a charger today") == "Roughly what did that come to?"


async def test_an_amount_already_given_is_not_asked_for_again():
    assert await fu.next_question("bought a charger for 500") is None
    assert await fu.next_question("bought a charger for ₹500") is None


@pytest.mark.parametrize(
    "note",
    [
        "spent the afternoon at the barber",
        "spent the whole day studying",
        "spent some time with Hori",
        "spent a while walking",
        "spent ages on the assignment",
    ],
)
async def test_spending_time_is_not_spending_money(note):
    # Regression, caught by a test whose premise the bug invalidated: "spent"
    # matched the money rule, so Advary asked what an AFTERNOON cost.
    assert await fu.next_question(note) != "Roughly what did that come to?"


async def test_spending_time_and_money_in_one_note_still_asks_the_price():
    # The time phrase must not become a blanket excuse to miss real spending.
    assert (
        await fu.next_question("spent the afternoon at the barber and bought a comb")
        == "Roughly what did that come to?"
    )


async def test_a_note_with_nothing_vague_is_left_alone():
    # Silence is a perfectly good outcome. A diary that always has a question
    # is a form.
    assert await fu.next_question("felt tired after class") is None


async def test_the_contents_question_comes_before_the_price_one():
    # "bought fruits" is both vague AND unpriced. Naming the things first makes
    # the price question answerable.
    assert await fu.next_question("bought fruits") == "Which fruits?"


# --- the branch (the user's actual example) --------------------------------


async def test_fruits_then_juice_then_amount_without_any_fruit_specific_code():
    """The scenario as described: fruits -> list them -> juice -> amount. Every
    step here comes from the generic rules, not a hardcoded path."""
    note = "went to the market and bought fruits"

    q1 = await fu.next_question(note)
    assert q1 == "Which fruits?"

    details = [{"question": q1, "answer": "apples, mangoes and some juice"}]
    q2 = await fu.next_question(note, details=details)
    # Their ANSWER mentioned juice — which is itself vague, so that's next.
    assert q2 == "Which juice?"

    details.append({"question": q2, "answer": "orange juice"})
    q3 = await fu.next_question(note, details=details)
    # Now nothing is vague, but money moved and no amount was ever named.
    assert q3 == "Roughly what did that come to?"


async def test_the_same_question_is_never_asked_twice():
    note = "bought fruits"
    details = [{"question": "Which fruits?", "answer": "just apples"}]
    assert await fu.next_question(note, details=details) != "Which fruits?"


async def test_questions_are_bounded_so_a_note_is_not_an_interrogation():
    note = "bought fruits and vegetables and snacks and drinks"
    details = [
        {"question": "Which fruits?", "answer": "apples"},
        {"question": "Which vegetables?", "answer": "onions"},
        {"question": "Which snacks?", "answer": "chips"},
    ]
    assert await fu.next_question(note, details=details) is None


# --- the model layer --------------------------------------------------------


async def test_the_model_covers_what_the_rules_cannot_see():
    note = "spent the afternoon at the barber"  # no vague plural, no spend verb
    assert await fu.next_question(note) is None

    q = await fu.next_question(note, generate=_model("How long were you at the barber?"))
    assert q == "How long were you at the barber?"


async def test_a_model_failure_just_means_no_question():
    # Nothing degrades: the diary still saved, we simply don't ask.
    assert await fu.next_question("spent the afternoon at the barber", generate=_boom()) is None


@pytest.mark.parametrize("reply", ["", "NONE", "none", "I think you should save more.", "..."])
async def test_a_model_with_nothing_useful_to_say_stays_quiet(reply):
    assert await fu.next_question("felt tired after class", generate=_model(reply)) is None


# --- grounding: a question may not invent a topic ---------------------------


async def test_a_question_about_something_never_mentioned_is_refused():
    # THE guard. A model that asks "how was the concert?" invents a concert,
    # and the user's answer then gets stored as fact about their life.
    q = await fu.next_question("felt tired after class", generate=_model("How was the concert?"))
    assert q is None


async def test_a_question_about_what_they_wrote_is_allowed():
    q = await fu.next_question("felt tired after class", generate=_model("How was class?"))
    assert q == "How was class?"


async def test_a_question_may_ask_about_their_own_answer_not_just_the_note():
    note = "went to the market"
    details = [{"question": "What did you get?", "answer": "a mango"}]
    q = await fu.next_question(note, details=details, generate=_model("Was the mango any good?"))
    assert q == "Was the mango any good?"


async def test_a_question_that_states_a_number_is_refused():
    # Asking is fine; asserting a figure is not.
    q = await fu.next_question("bought a charger for 500", generate=_model("Was the 500 charger worth it?"))
    assert q is None


async def test_a_rambling_model_reply_is_trimmed_to_one_question():
    q = await fu.next_question(
        "went to the market",
        generate=_model("Sure! Here's a question: What did you get at the market? Let me know!"),
    )
    assert q == "What did you get at the market?"


async def test_an_essay_is_refused_rather_than_shown():
    long_q = "Could you please tell me in as much detail as you possibly can what happened at the market today?"
    assert await fu.next_question("went to the market", generate=_model(long_q)) is None


async def test_a_reply_with_no_question_at_all_is_refused():
    assert await fu.next_question("went to the market", generate=_model("You went to the market.")) is None


# --- grounding helper -------------------------------------------------------


def test_grounding_allows_plural_drift_in_the_users_own_words():
    assert fu._is_grounded("Were the mangoes ripe?", "bought a mango") is True
    assert fu._is_grounded("Were the strawberries ripe?", "bought a mango") is False
