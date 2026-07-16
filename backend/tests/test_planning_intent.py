"""Planning-intent extractor: rules, model escalation, and the grounding rule.

The point of this layer is that the Planning flow is NOT a fixed script — it has
to cope with however someone happens to phrase things. So the bulk of this file
is a wide sweep of real phrasings rather than a couple of happy paths.
"""

from __future__ import annotations

from datetime import date

import pytest

from app.intelligence.companion import planning_intent

TODAY = date(2026, 7, 16)  # a Thursday, mid-month, mid-year


async def _interpret(text: str, generate=None):
    return await planning_intent.interpret(text, today=TODAY, generate=generate)


def _fake_model(reply: str):
    async def generate(messages):
        return reply

    return generate


def _exploding_model():
    async def generate(messages):
        raise RuntimeError("ollama is down")

    return generate


# --- kind detection across phrasings -------------------------------------


@pytest.mark.parametrize(
    "text,kind",
    [
        ("am planning to buy a new headphone", "buy"),
        ("I want to buy headphones", "buy"),
        ("thinking of getting a bike", "buy"),
        ("need a new laptop", "buy"),
        ("planning to purchase a washing machine", "buy"),
        ("I want to start a netflix subscription", "subscription"),
        ("thinking about subscribing to spotify", "subscription"),
        ("gym membership from next month", "subscription"),
        ("I want to save for a trip to japan", "save"),
        ("saving up for an emergency fund", "save"),
        ("want to set aside money each month", "save"),
        ("my friend owes me money", "other"),
        ("", "other"),
    ],
)
async def test_kind_is_read_from_natural_phrasing(text, kind):
    assert (await _interpret(text))["kind"] == kind


async def test_subscription_beats_a_buy_verb_in_the_same_sentence():
    # "get a netflix subscription" has both a buy verb and a subscription noun.
    assert (await _interpret("want to get a netflix subscription"))["kind"] == "subscription"


async def test_saving_toward_a_thing_is_saving_not_buying():
    assert (await _interpret("I want to save for a phone"))["kind"] == "save"


# --- amounts --------------------------------------------------------------


@pytest.mark.parametrize(
    "text,amount",
    [
        ("buy headphones for 3000", 3000),
        ("buy headphones for ₹3,000", 3000),
        ("buy headphones for 3k", 3000),
        ("buy headphones for 3 thousand", 3000),
        ("save 2 lakhs for a car", 200000),
        ("netflix for $15 a month", 15),
        ("buy a laptop for 45000 rupees", 45000),
        ("buy shoes for 2499.50", 2499.50),
        ("am planning to buy a new headphone", None),
    ],
)
async def test_amount_extraction(text, amount):
    assert (await _interpret(text))["amount"] == amount


@pytest.mark.parametrize(
    "text",
    [
        "thinking of finally pulling the trigger on a switch 2",
        "want to buy an iphone 15",
        "planning to get a pixel 9",
        "buy a ps5",
    ],
)
async def test_a_number_inside_a_product_name_is_not_a_price(text):
    # Regression, caught by running the real model: "switch 2" was read as a ₹2
    # purchase. A number only counts as money when something frames it as money
    # (a symbol, a currency word, "for"/"costs"). Asking "how much?" beats
    # inventing a ₹2 goal.
    assert (await _interpret(text))["amount"] is None


async def test_a_bare_number_needs_a_cue_to_count_as_money():
    assert (await _interpret("buy a laptop 45000"))["amount"] is None       # no cue -> ask
    assert (await _interpret("buy a laptop for 45000"))["amount"] == 45000  # "for" -> money
    assert (await _interpret("the gym is 1200 a month"))["amount"] == 1200  # "is" -> money


async def test_a_year_is_not_mistaken_for_a_price():
    # Regression guard: "by 2027" is a bare 4-digit number and would otherwise
    # be read as a ₹2027 price — planting a fake cost into a real savings goal.
    result = await _interpret("planning to buy a bike by 2027-03-01")
    assert result["amount"] is None
    assert result["target_date"] == date(2027, 3, 1)


async def test_a_price_that_looks_like_a_year_still_parses_when_marked():
    assert (await _interpret("buy a phone for ₹2050"))["amount"] == 2050
    assert (await _interpret("buy a phone for 2050 rupees"))["amount"] == 2050


async def test_amount_and_date_in_the_same_sentence_dont_collide():
    result = await _interpret("buy headphones for 3000 by december")
    assert result["amount"] == 3000
    assert result["target_date"] == date(2026, 12, 31)


# --- dates ----------------------------------------------------------------


@pytest.mark.parametrize(
    "text,expected",
    [
        ("buy a bike by december", date(2026, 12, 31)),
        ("buy a bike by march", date(2027, 3, 31)),          # already past -> next year
        ("buy a bike by july", date(2026, 7, 31)),           # this month -> this year
        ("buy a bike next month", date(2026, 8, 16)),
        ("buy a bike next year", date(2027, 7, 16)),
        ("buy a bike next week", date(2026, 7, 23)),
        ("buy a bike in 3 months", date(2026, 10, 16)),
        ("buy a bike in 2 weeks", date(2026, 7, 30)),
        ("buy a bike by end of the month", date(2026, 7, 31)),
        ("buy a bike by 2026-09-30", date(2026, 9, 30)),
        ("buy a bike", None),
    ],
)
async def test_date_extraction(text, expected):
    assert (await _interpret(text))["target_date"] == expected


async def test_month_end_clamps_on_a_short_month():
    assert (await _interpret("buy a bike by february"))["target_date"] == date(2027, 2, 28)


async def test_an_invalid_iso_date_doesnt_crash_the_parse():
    result = await _interpret("buy a bike by 2026-13-45")
    assert result["kind"] == "buy"  # the rest of the sentence still reads fine


# --- items ----------------------------------------------------------------


@pytest.mark.parametrize(
    "text,item",
    [
        ("am planning to buy a new headphone", "headphone"),
        ("I want to buy headphones for 3000 by december", "headphones"),
        ("thinking of getting a washing machine", "washing machine"),
        ("save for a trip to japan", "trip to japan"),
        ("want to get a netflix subscription", "netflix subscription"),
        ("need a new laptop", "laptop"),
        ("buy a bike next month", "bike"),          # timing is not part of the name
        ("buy a bike by end of the month", "bike"),
    ],
)
async def test_item_extraction_drops_filler_price_and_date(text, item):
    assert (await _interpret(text))["item"] == item


@pytest.mark.parametrize(
    "text",
    [
        "my headphone died",              # no verb naming an intent
        "something came up and I need one",  # names only a pronoun
        "the thing costs 4500 and I want it",
    ],
)
async def test_item_extraction_returns_none_rather_than_a_guess(text):
    # Being wrong here is worse than being silent: a guessed item becomes the
    # name of a real goal, and a non-None item also suppresses the model
    # escalation that would have worked it out.
    assert (await _interpret(text))["item"] is None


# --- what the flow still has to ask for -----------------------------------


async def test_missing_lists_exactly_what_is_still_needed():
    result = await _interpret("am planning to buy a new headphone")
    assert result["item"] == "headphone"
    assert result["missing"] == ["amount", "target_date"]


async def test_a_complete_sentence_leaves_nothing_to_ask():
    result = await _interpret("buy headphones for 3000 by december")
    assert result["missing"] == []


async def test_a_subscription_never_asks_for_a_target_date():
    # A subscription is open-ended — asking "by when?" makes no sense.
    result = await _interpret("start a netflix subscription for 649")
    assert result["missing"] == []


# --- the model layer ------------------------------------------------------


async def test_rules_alone_need_no_model():
    result = await _interpret("buy headphones for 3000 by december", generate=_exploding_model())
    # A fully-understood sentence never round-trips to the model, so the
    # exploding one is never even called.
    assert result["source"] == "rules"
    assert result["amount"] == 3000


async def test_the_model_widens_what_we_understand():
    # No buy/save/subscription keyword anywhere — the rules can't classify this.
    text = "my old phone finally died so I need to replace it"
    assert (await _interpret(text))["kind"] == "other"

    result = await _interpret(text, generate=_fake_model('{"kind": "buy", "item": "phone", "amount": null}'))
    assert result["kind"] == "buy"
    assert result["item"] == "phone"
    assert result["source"] == "model"


async def test_a_model_failure_falls_back_to_the_rules():
    result = await _interpret("planning to buy something nice", generate=_exploding_model())
    assert result["kind"] == "buy"
    assert result["source"] == "rules"


@pytest.mark.parametrize("reply", ["", "not json at all", "{broken", '{"kind": "nonsense"}', "[]", "null"])
async def test_garbage_model_replies_never_corrupt_the_result(reply):
    result = await _interpret("planning to buy a thing", generate=_fake_model(reply))
    assert result["kind"] == "buy"
    assert result["amount"] is None


async def test_deterministic_values_win_over_the_model():
    # The user wrote 3000; the model claims 9999. The user's number wins,
    # because the rules were confident and the model only fills gaps.
    result = await _interpret(
        "grab a netflix plan for 3000",
        generate=_fake_model('{"kind": "buy", "item": "netflix", "amount": 9999}'),
    )
    assert result["amount"] == 3000
    assert result["kind"] == "subscription"


# --- grounding: the model may not invent facts ----------------------------


async def test_a_model_invented_price_is_dropped():
    # THE important guard. The user never said a number; a model that helpfully
    # "knows" headphones cost 5000 would otherwise plant a fake price into a
    # real savings goal the user is then told to fund.
    result = await _interpret(
        "my headphone broke, need another",
        generate=_fake_model('{"kind": "buy", "item": "headphone", "amount": 5000}'),
    )
    assert result["amount"] is None
    assert result["missing"] == ["amount", "target_date"]


async def test_a_model_amount_that_is_in_the_text_is_kept():
    result = await _interpret(
        "the thing costs 4500 and I want it",
        generate=_fake_model('{"kind": "buy", "item": "thing", "amount": 4500}'),
    )
    assert result["amount"] == 4500


def test_a_shorthand_amount_still_counts_as_grounded():
    # 3000 never appears literally in "about 3k", but it IS what the user said —
    # tested directly, since the rules would resolve "3k" before the model ran.
    assert planning_intent._grounded_amount(3000, "want it, about 3k") == 3000
    assert planning_intent._grounded_amount(5000, "want it, about 3k") is None


async def test_a_model_invented_item_is_dropped():
    result = await _interpret(
        "something came up and I need one",
        generate=_fake_model('{"kind": "buy", "item": "playstation 5", "amount": null}'),
    )
    assert result["item"] is None


async def test_a_model_item_that_echoes_the_user_survives_plural_drift():
    result = await _interpret(
        "my headphone died",
        generate=_fake_model('{"kind": "buy", "item": "headphones", "amount": null}'),
    )
    assert result["item"] == "headphones"


async def test_a_negative_or_zero_model_amount_is_dropped():
    for bad in ("-500", "0"):
        result = await _interpret(
            "need one soon",
            generate=_fake_model(f'{{"kind": "buy", "item": "one", "amount": {bad}}}'),
        )
        assert result["amount"] is None
