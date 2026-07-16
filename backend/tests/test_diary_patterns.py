"""Diary pattern inference.

A model asked to find patterns will always find one. The value of this layer is
entirely in what it REFUSES to claim, so most of these tests are about silence:
not enough entries, not enough separate days, not enough of a lean. A wrong
pattern told back to someone about their own life is worse than saying nothing,
because it's about them and they can't easily tell it's wrong.
"""

from __future__ import annotations

from datetime import date

from app.intelligence.companion import diary_patterns as dp


def _e(day: date, text: str, answers: list[str] | None = None) -> dict:
    return {
        "entry_date": day,
        "text": text,
        "details": [{"question": "Which?", "answer": a} for a in (answers or [])],
    }


# Thursdays in July 2026: 2, 9, 16, 23, 30. Mondays: 6, 13, 20, 27.
THU = [date(2026, 7, d) for d in (2, 9, 16, 23, 30)]
MON = [date(2026, 7, d) for d in (6, 13, 20, 27)]


# --- singularisation --------------------------------------------------------


def test_plurals_fold_onto_one_word():
    # Regression: a blanket "drop the s" made "mangoes" -> "mangoe" and a
    # blanket "drop the es" made "grapes" -> "grap", either of which splits one
    # word into two and hides the very pattern this file exists to find.
    assert dp._normalise("mangoes") == "mango"
    assert dp._normalise("mango") == "mango"
    assert dp._normalise("grapes") == "grape"
    assert dp._normalise("berries") == "berry"
    assert dp._normalise("boxes") == "box"
    assert dp._normalise("dishes") == "dish"
    assert dp._normalise("potatoes") == "potato"


def test_singularisation_leaves_alone_what_it_should():
    assert dp._normalise("glass") == "glass"   # not "glas"
    assert dp._normalise("juice") == "juice"
    assert dp._normalise("bus") == "bus"


# --- silence under the threshold -------------------------------------------


def test_nothing_is_claimed_before_there_are_enough_entries():
    entries = [_e(date(2026, 7, d), "bought mango") for d in (1, 2, 3)]
    result = dp.describe(entries)
    assert result["ready"] is False
    assert result["observations"] == []
    assert result["ask"] is None
    assert result["needed"] == dp.MIN_ENTRIES


def test_an_empty_diary_says_nothing_rather_than_erroring():
    result = dp.describe([])
    assert result["ready"] is False
    assert result["observations"] == []


def test_a_word_said_five_times_in_one_note_is_one_day_not_a_habit():
    # The same word repeated in a single entry is one event. Counting mentions
    # instead of days would call any rant a pattern.
    entries = [_e(date(2026, 7, 1), "mango mango mango mango mango")]
    entries += [_e(date(2026, 7, d), "went for a walk") for d in (2, 3, 4, 5)]
    result = dp.describe(entries)
    assert result["ready"] is True
    assert not any(o["word"] == "mango" for o in result["observations"])


def test_a_word_on_too_few_separate_days_is_not_reported():
    entries = [_e(date(2026, 7, 1), "bought mango"), _e(date(2026, 7, 2), "bought mango")]
    entries += [_e(date(2026, 7, d), "went for a walk") for d in (3, 4, 5)]
    result = dp.describe(entries)
    assert not any(o["word"] == "mango" for o in result["observations"])


# --- what it does report ----------------------------------------------------


def test_the_thing_you_write_about_most_is_reported_with_its_evidence():
    entries = [_e(d, "bought mango") for d in THU]
    result = dp.describe(entries)
    assert result["ready"] is True
    mention = next(o for o in result["observations"] if o["kind"] == "mention")
    assert mention["word"] == "mango"
    # It states what was counted, and quotes only the days it actually has.
    assert mention["text"] == "You've mentioned mango on 5 of the 5 days you've written."


def test_it_counts_the_days_written_not_the_calendar():
    # "your last 12 days" would be a claim about days the user never told us
    # anything about.
    entries = [_e(d, "bought mango") for d in THU]
    text = dp.describe(entries)["observations"][0]["text"]
    assert "of the 5 days you've written" in text


def test_the_users_own_answers_count_as_things_they_said():
    entries = [_e(d, "went to the market", answers=["mangoes and apples"]) for d in THU]
    result = dp.describe(entries)
    assert any(o["word"] == "mango" for o in result["observations"])


def test_advarys_own_questions_do_not_count_as_the_user_mentioning_something():
    # Otherwise whatever Advary keeps asking about becomes the thing the user
    # "always talks about" — the companion learning from its own voice.
    entries = [
        {
            "entry_date": d,
            "text": "went for a walk",
            "details": [{"question": "Did you buy pineapple?", "answer": "no"}],
        }
        for d in THU
    ]
    result = dp.describe(entries)
    assert not any(o["word"] == "pineapple" for o in result["observations"])


# --- weekday ----------------------------------------------------------------


def test_a_real_weekday_habit_is_named():
    entries = [_e(d, "bought mango") for d in THU]
    wp = dp.weekday_pattern(entries, "mango")
    assert wp is not None
    assert wp["weekday"] == "Thursday"
    assert wp["hits"] == 5


def test_a_weekday_lean_that_is_not_a_lean_is_not_named():
    # Spread across the week -> no weekday claim.
    entries = [_e(date(2026, 7, d), "bought mango") for d in (1, 2, 3, 6, 8)]
    assert dp.weekday_pattern(entries, "mango") is None


def test_two_thursdays_are_a_coincidence_not_a_habit():
    entries = [_e(d, "bought mango") for d in THU[:2]]
    assert dp.weekday_pattern(entries, "mango") is None


def test_the_adverb_moves_with_the_evidence():
    # Caught by reading the live output: a bare-minimum 3-of-5 lean was being
    # announced as "Usually a Thursday". The count was right there in the
    # sentence, but the adverb still oversold it.
    assert dp._frequency_word(3, 5) == "Often"      # 0.60 — just over the gate
    assert dp._frequency_word(4, 5) == "Usually"    # 0.80 — earns the word
    assert dp._frequency_word(5, 5) == "Usually"


def test_a_bare_minimum_lean_is_described_as_often_not_usually():
    entries = [_e(d, "bought mango") for d in THU[:3]] + [_e(d, "bought mango") for d in MON[:2]]
    text = next(o for o in dp.describe(entries)["observations"] if o["kind"] == "weekday")["text"]
    assert text.startswith("Often a Thursday")


def test_a_strong_lean_still_gets_the_stronger_word():
    entries = [_e(d, "bought mango") for d in THU[:4]] + [_e(MON[0], "bought mango")]
    text = next(o for o in dp.describe(entries)["observations"] if o["kind"] == "weekday")["text"]
    assert text.startswith("Usually a Thursday")


def test_a_mostly_thursday_habit_survives_one_stray_day():
    entries = [_e(d, "bought mango") for d in THU[:4]] + [_e(MON[0], "bought mango")]
    wp = dp.weekday_pattern(entries, "mango")
    assert wp is not None and wp["weekday"] == "Thursday"
    assert wp["hits"] == 4 and wp["total"] == 5


# --- first week of the month ------------------------------------------------


def test_a_first_week_cluster_is_named():
    entries = [_e(date(2026, m, d), "paid rent") for m, d in [(5, 2), (6, 3), (7, 1)]]
    fw = dp.first_week_pattern(entries, "rent")
    assert fw is not None
    assert fw["hits"] == 3


def test_spread_across_the_month_is_not_a_first_week_cluster():
    entries = [_e(date(2026, 7, d), "bought mango") for d in (3, 12, 19, 26)]
    assert dp.first_week_pattern(entries, "mango") is None


# --- the ask ----------------------------------------------------------------


def test_it_asks_whether_something_is_a_favourite_rather_than_deciding():
    # Counting proves it comes up most. Only the user knows if it's a favourite,
    # a chore, or their mum's shopping list — so that gets asked, not assumed.
    entries = [_e(d, "bought mango") for d in THU]
    result = dp.describe(entries)
    assert result["ask"]["word"] == "mango"
    assert "favourite" in result["ask"]["question"]
    # And no observation asserts a preference.
    assert not any("favourite" in o["text"] for o in result["observations"])


def test_filler_words_never_become_a_pattern():
    entries = [_e(d, "today was a good day and I got some stuff") for d in THU]
    result = dp.describe(entries)
    words = {o["word"] for o in result["observations"]}
    for filler in ("today", "day", "good", "stuff", "got", "some"):
        assert filler not in words
