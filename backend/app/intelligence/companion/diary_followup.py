"""Branching follow-ups for a diary entry — Advary asking the one useful next
question about what you wrote, instead of running a fixed script.

The generalisation matters. "You said fruits — which ones?" then "apples and
mangoes" then "what did that come to?" is NOT a hardcoded fruit→juice→amount
path; it's one rule applied repeatedly: **find the vaguest thing that was said,
and ask about that**. A branch per topic would collapse the moment someone wrote
about something we never anticipated, which is most of the time.

Rules first (offline, instant, always available), the local model only for what
the rules can't see. Any model failure just means no question — silence is a
perfectly good outcome here, so nothing degrades.

Grounding rule: a question may only ask about words the user actually wrote.
The model gets an allow-list of ordinary question vocabulary; any other content
word must appear in the entry. Without that, a model that "helpfully" asks "how
was the concert?" invents a concert the user never went to and then stores their
answer as fact.
"""

from __future__ import annotations

import re
from typing import Awaitable, Callable

# Words that name a bag of things without naming the things. Seeing one of these
# is the strongest signal we have that there's a more specific answer available.
_VAGUE_PLURALS: dict[str, str] = {
    "fruits": "Which fruits?",
    "fruit": "Which fruit?",
    "vegetables": "Which vegetables?",
    "veggies": "Which vegetables?",
    "groceries": "What did you pick up?",
    "snacks": "Which snacks?",
    "sweets": "Which sweets?",
    "drinks": "What did you drink?",
    "juice": "Which juice?",
    "food": "What did you eat?",
    "lunch": "What did you have for lunch?",
    "dinner": "What did you have for dinner?",
    "breakfast": "What did you have for breakfast?",
    "clothes": "What did you get?",
    "books": "Which books?",
    "games": "Which games?",
    "medicines": "What did you need?",
    "supplies": "What did you pick up?",
    "stuff": "What kind of stuff?",
    "things": "What sort of things?",
    "shopping": "What did you buy?",
}

# Saying money happened without saying how much.
_SPEND_VERBS = (
    "bought", "buy", "purchased", "paid", "spent", "got", "picked up",
    "ordered", "grabbed", "booked",
)

# You spend money and you spend time, and only one of them has a price. Without
# this, "spent the afternoon at the barber" gets answered with "roughly what did
# that come to?" — Advary asking what an afternoon cost.
_TIME_OBJECTS = (
    "morning", "afternoon", "evening", "night", "day", "days", "hour", "hours",
    "minute", "minutes", "time", "week", "weekend", "while", "ages", "years",
)

_AMOUNT_RE = re.compile(r"[₹$€£¥]\s*\d|(?<![a-z])\d+(?:[.,]\d+)?\s*(?:k|rs|rupees|bucks|dollars)?", re.IGNORECASE)

# Ordinary question words the model may use freely. Anything outside this list
# has to come from the user's own text — that's the whole guard.
_QUESTION_VOCAB = frozenset(
    """
    a an the and or but so is are was were do does did done have has had
    you your yours it its that this these those they them their there here
    what which who whom whose when where why how much many more most
    cost costs price paid pay spend spent buy bought get got kind sort type
    any else other another one ones some all about roughly around each
    for from with at on in of to by up out off over into
    like enjoy enjoyed favourite favorite usual usually often
    day days today yesterday time times again still yet just only
    did'you go went make made take took come came
    """.split()
)

_MAX_QUESTIONS = 3  # a note is not an interrogation

_SYSTEM = """You are helping someone keep a short diary. Given their note, ask ONE short,
natural follow-up question about something they mentioned but left vague.

Rules:
- Ask about something THEY wrote. Never introduce a topic, place, person or
  thing they did not mention.
- One question. Under 12 words. End with "?".
- Never state or guess a number, price or date.
- If nothing in the note is worth asking about, reply with exactly: NONE

Reply with the question only, or NONE. No prose, no quotes."""


def _tokens(text: str) -> list[str]:
    return re.findall(r"[a-z']+", text.lower())


def _has_amount(text: str) -> bool:
    return bool(_AMOUNT_RE.search(text))


def _spends_time_not_money(text: str) -> bool:
    """"spent the afternoon", "spent a while", "spent time" — the verb is the
    same, the price is not."""
    low = text.lower()
    # Up to three words of padding between the verb and the time noun, so "spent
    # the whole day" and "spent a couple of hours" both read as time. Bounded
    # rather than open-ended: "spent the money I saved last week" must NOT count
    # as time just because a week turns up five words later.
    pattern = r"\bspent\s+(?:\w+\s+){0,3}(?:" + "|".join(_TIME_OBJECTS) + r")\b"
    return bool(re.search(pattern, low))


def _mentions_spending(text: str) -> bool:
    low = f" {text.lower()} "
    if not any(f" {v} " in low or low.startswith(f"{v} ") for v in _SPEND_VERBS):
        return False
    # "spent the afternoon at the barber and bought a comb" still spends money;
    # only bail when the ONLY money-ish verb is a time one.
    if _spends_time_not_money(text):
        others = [v for v in _SPEND_VERBS if v != "spent"]
        return any(f" {v} " in low or low.startswith(f"{v} ") for v in others)
    return True


def _deterministic_question(text: str, asked: set[str]) -> str | None:
    """The fast path. Returns None when the rules see nothing worth asking —
    which is a fine answer, not a failure."""
    tokens = set(_tokens(text))

    # 1. A bag of things was named but not its contents. Most specific win
    #    available, so it goes first.
    for word, question in _VAGUE_PLURALS.items():
        if word in tokens and question not in asked:
            return question

    # 2. Money changed hands but no amount was ever given.
    if _mentions_spending(text) and not _has_amount(text):
        question = "Roughly what did that come to?"
        if question not in asked:
            return question

    return None


def _echoes(token: str, corpus_tokens: set[str]) -> bool:
    """Allows plural/tense drift against what they wrote ("mango"/"mangoes")."""
    return any(t == token or t[:4] == token[:4] for t in corpus_tokens)


def _is_grounded(question: str, corpus: str) -> bool:
    """A question must be about something the user actually wrote.

    The rule is "at least one substantive word echoes their text", NOT "every
    word is on an approved list". The strict version rejected "Were the mangoes
    ripe?" because "ripe" wasn't in the vocabulary — and no list can enumerate
    ordinary English, so that version blocked almost every natural question and
    made the whole model layer dead weight.

    A question made only of ordinary question words ("How was it?") is fine: it
    can't invent anything, because it names nothing.

    Residual hole, accepted knowingly: "How was class and the concert?" passes
    on the strength of "class". Narrowing that needs real part-of-speech
    tagging to tell an invented noun from an adjective — a dependency and a lot
    of machinery for a case the prompt already forbids and the length cap makes
    unlikely."""
    corpus_tokens = set(_tokens(corpus))
    substantive = [t for t in _tokens(question) if len(t) >= 3 and t not in _QUESTION_VOCAB]
    if not substantive:
        return True
    return any(_echoes(t, corpus_tokens) for t in substantive)


def _clean_model_question(raw: str, corpus: str) -> str | None:
    if not raw:
        return None
    line = raw.strip().strip('"').strip()
    if not line or line.upper().startswith("NONE"):
        return None
    # Take the first question it produced, ignore any extra chatter.
    match = re.search(r"[^.?!\n]*\?", line)
    if not match:
        return None
    question = match.group(0).strip()
    # Models like to introduce themselves ("Sure! Here's a question: What did
    # you get?"). Everything before the last colon is preamble, not the question.
    if ":" in question:
        question = question.rsplit(":", 1)[1].strip()
    if len(question) > 90 or len(question.split()) > 14:
        return None
    # A follow-up must never assert a figure — asking is fine, claiming is not.
    if re.search(r"\d", question):
        return None
    if not _is_grounded(question, corpus):
        return None
    return question[0].upper() + question[1:]


def corpus_of(text: str, details: list[dict[str, str]] | None) -> str:
    """Everything the user has said about this entry — the note plus their own
    answers. Their answers are fair game to ask about ("apples and mangoes" ->
    "what did the mangoes cost?"); Advary's own questions are not."""
    parts = [text or ""]
    for d in details or []:
        answer = (d or {}).get("answer")
        if answer:
            parts.append(str(answer))
    return " ".join(parts)


async def next_question(
    text: str,
    *,
    details: list[dict[str, str]] | None = None,
    generate: Callable[[list[dict[str, str]]], Awaitable[str]] | None = None,
) -> str | None:
    """The next thing worth asking about this entry, or None to stop.

    `generate` is an injected callable (messages -> str), same contract as
    llm_router.route / judge_sufficiency / planning_intent.interpret."""
    details = details or []
    if len(details) >= _MAX_QUESTIONS:
        return None  # stop before a diary becomes a form

    asked = {str((d or {}).get("question") or "") for d in details}
    corpus = corpus_of(text, details)

    fast = _deterministic_question(corpus, asked)
    if fast is not None:
        return fast

    if generate is None:
        return None

    prompt = f"Note: {text.strip()}"
    for d in details:
        q, a = (d or {}).get("question"), (d or {}).get("answer")
        if q and a:
            prompt += f'\nYou asked: {q}\nThey said: {a}'
    messages = [{"role": "system", "content": _SYSTEM}, {"role": "user", "content": prompt}]
    try:
        question = _clean_model_question(await generate(messages), corpus)
    except Exception:  # noqa: BLE001 — any model/transport failure => just don't ask
        return None
    if question is None or question in asked:
        return None
    return question
