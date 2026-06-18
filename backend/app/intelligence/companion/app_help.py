"""App how-to help — the companion teaches the app (no menus, no manual).

Deterministic intent layer: when the user asks "how do I…/where do I…" about a
*feature* (add an expense, set a budget, plan a purchase, mark an event, lend
money, talk by voice, change currency, rename me), answer with concise steps and
the route to open. Also detects "show me around / give me a tour" to (re)launch the
guided tour.

Wired into the chat advisor; because voice routes spoken queries through the same
chat advisor, this answers by voice too.
"""

from __future__ import annotations

from dataclasses import dataclass

# How-to phrasing that signals the user wants *instructions*, not a number.
_HOWTO_TRIGGERS = (
    "how do i", "how do you", "how to", "how can i", "how would i", "how i can",
    "where do i", "where can i", "where is", "where's", "where do you",
    "show me how", "teach me how", "help me add", "help me set", "help me plan",
    "help me record", "help me log", "how does this work",
)

# Phrasing that asks for the whole walkthrough.
_TOUR_TRIGGERS = (
    "show me around", "give me a tour", "take the tour", "start the tour",
    "walk me through", "how does this app work", "how do i use this app",
    "how do i use the app", "show me the app", "guide me through", "tour the app",
    "explain the app", "what is this app", "show me how the app works",
)


@dataclass(frozen=True)
class HelpAnswer:
    title: str
    message: str
    route: str | None       # go_router path the client can offer to open


# (feature keywords, answer). First match wins, so order from most specific to least.
_HOW_TO: list[tuple[tuple[str, ...], HelpAnswer]] = [
    (("expense", "spent", "log a cost", "record a cost", "log spending", "spending on"),
     HelpAnswer("Add an expense",
                "From Home, tap the day you spent → Add expense → enter the amount and "
                "pick a category → Save. Your spending analysis updates right away.",
                "/home")),
    (("income", "salary", "got paid", "received money", "earned", "got money", "paycheck"),
     HelpAnswer("Record income",
                "From Home, tap the day you got paid → Add income → enter the amount → "
                "Save. It keeps your projections accurate.",
                "/home")),
    (("plan a purchase", "plan to buy", "planning to buy", "planned expense", "budget plan",
      "save up for", "saving for", "buy a", "big purchase"),
     HelpAnswer("Plan a purchase",
                "Open Budget Setup → add a planned purchase with its cost and roughly "
                "when → Save. I'll tell you whether it fits and how to reach it.",
                "/budget-setup")),
    (("budget", "monthly limit", "spending limit", "set a limit", "monthly cap", "yearly budget"),
     HelpAnswer("Set a budget",
                "Open Budget Setup → set how much you want to spend each month (or year) "
                "→ Save. I'll warn you as you get close to it.",
                "/budget-setup")),
    (("event", "mark a day", "note on", "reminder on", "mark something", "put something on",
      "add a note", "remember a day"),
     HelpAnswer("Mark an event or note",
                "On your Home calendar, tap the date → Add event → give it a title → "
                "Save. It shows on that day so you don't forget.",
                "/home")),
    (("lend", "lent", "loan to", "borrowed from me", "i gave", "owes me", "money i'm owed"),
     HelpAnswer("Record money you lent",
                "Tap the date you lent it on Home → Add lent → who and how much → Save. "
                "I'll track repayment and remind you when it's due.",
                "/home")),
    (("future me", "see my forecast", "see the future", "future projection", "where i'm headed",
      "where am i headed"),
     HelpAnswer("See Future Me",
                "Open Future Me to see your projected balance and how small changes today "
                "play out — or just ask me \"what if I save more?\" and I'll run it.",
                "/future-me")),
    (("talk to you", "talk with you", "use voice", "voice message", "speak to you", "the mic",
      "by voice", "voice command"),
     HelpAnswer("Talk to me",
                "Tap the mic anywhere to talk to me, or open the chat to type. I answer "
                "questions and can even add expenses or income for you by voice.",
                "/advisor")),
    (("currency", "convert", "exchange rate", "base currency", "change money"),
     HelpAnswer("Currency & conversion",
                "Open the Currency screen to convert amounts and see rates. To change the "
                "currency everything is shown in, go to Settings → base currency.",
                "/convert")),
    (("your name", "rename you", "call you", "change your name", "your personality",
      "change your style", "your voice", "name you"),
     HelpAnswer("Make me yours",
                "Open Settings → Companion name to rename me, Companion style to change my "
                "personality, and Voice to turn speaking on or off.",
                "/settings")),
]


def _norm(text: str | None) -> str:
    return (text or "").lower().strip()


def wants_tour(text: str | None) -> bool:
    t = _norm(text)
    return any(k in t for k in _TOUR_TRIGGERS)


def how_to(text: str | None) -> HelpAnswer | None:
    """Return step-by-step help when the user asks how to use a feature, else None
    (so financial/forecast intents still get their turn)."""
    t = _norm(text)
    if not any(k in t for k in _HOWTO_TRIGGERS):
        return None
    for keys, ans in _HOW_TO:
        if any(k in t for k in keys):
            return ans
    return None
