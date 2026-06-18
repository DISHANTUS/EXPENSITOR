"""First-launch guided tour — the companion (Advary) walks a brand-new user through
the whole app, screen by screen.

Deterministic content (NOT calculation, NOT an LLM): an ordered list of steps, each
naming the real screen/route the client navigates to while the companion narrates.
Style-aware (reuses the same companion styles as greetings) and TTS-ready
(`spoken_text` is plain, emoji-free). Never persisted.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.intelligence.mood import styles


@dataclass(frozen=True)
class TourStep:
    key: str
    route: str          # go_router path the client navigates to for this step
    icon: str           # emoji shown on the step card
    title: str
    narration: str      # shown on the card (may be a little more expressive)
    spoken_text: str    # plain, emoji-free — what TTS reads aloud


def _name(companion_name: str | None) -> str:
    return (companion_name or "Advary").strip() or "Advary"


def build_tour(style: str | None, companion_name: str | None) -> list[TourStep]:
    """The ordered walkthrough. `style` flavors the opening/closing lines only —
    the facts about each screen never change."""
    style = styles.normalize(style)
    name = _name(companion_name)
    close = (styles.encouragements(style)[0] or "Let's get started.").strip()

    intro = {
        "anime": f"Hi, I'm {name}~ I'll be right by your side. Let me show you around — it only takes a minute.",
        "professional": f"Hello, I'm {name}, your financial companion. Let me give you a quick tour of the app.",
        "minimal": f"I'm {name}. Quick tour.",
    }.get(style, f"Hi, I'm {name} — your companion here. Let me show you around. It'll only take a minute.")

    steps = [
        TourStep(
            "welcome", "/home", "👋", f"Meet {name}",
            intro, intro,
        ),
        TourStep(
            "home", "/home", "🗓️", "Your Home",
            "This is your home — a calendar of your money. Tap any date to add an "
            "expense, income, an event, or just a note for that day.",
            "This is your home, a calendar of your money. Tap any date to add an "
            "expense, income, an event, or just a note for that day.",
        ),
        TourStep(
            "budget_setup", "/budget-setup", "🎯", "Budget Setup",
            "Here's Budget Setup. Set how much you want to spend each month or year — "
            "and if you're planning to buy something, set a budget plan for it and I'll "
            "tell you whether it fits.",
            "Here is Budget Setup. Set how much you want to spend each month or year. "
            "And if you are planning to buy something, set a budget plan for it and I "
            "will tell you whether it fits.",
        ),
        TourStep(
            "plan_today", "/plan-today", "✅", "Plan Today",
            "Plan Today helps you decide what to do with today's money. I'll suggest a "
            "simple plan based on what's coming up.",
            "Plan Today helps you decide what to do with today's money. I will suggest "
            "a simple plan based on what is coming up.",
        ),
        TourStep(
            "timeline", "/timeline", "📖", "Your Timeline",
            "Your Timeline is your story — past income, expenses, goals, and the "
            "moments that mattered, all in one place.",
            "Your Timeline is your story: past income, expenses, goals, and the "
            "moments that mattered, all in one place.",
        ),
        TourStep(
            "future_me", "/future-me", "🔮", "Future Me",
            "Future Me shows where you're headed. I project your balance and show how "
            "small changes today change tomorrow.",
            "Future Me shows where you are headed. I project your balance and show how "
            "small changes today change tomorrow.",
        ),
        TourStep(
            "advisor", "/advisor", "💬", "Just ask me",
            "Anytime you're unsure, just ask me. Type here or tap the mic and talk — "
            "things like \"how do I set a budget?\", \"who owes me money?\", or "
            "\"can I afford a trip in October?\".",
            "Anytime you are unsure, just ask me. Type here, or tap the mic and talk. "
            "Try: how do I set a budget? Who owes me money? Can I afford a trip in October?",
        ),
        TourStep(
            "relationships", "/relationships", "🤝", "Relationships",
            "Relationships keeps track of the people in your money life — who you've "
            "lent to, who you share costs with, and the memories around them.",
            "Relationships keeps track of the people in your money life: who you have "
            "lent to, who you share costs with, and the memories around them.",
        ),
        TourStep(
            "settings", "/settings", "⚙️", "Make me yours",
            "And Settings is where you set your currency, give me a name, pick my "
            "personality, and turn my voice on or off.",
            "And Settings is where you set your currency, give me a name, pick my "
            "personality, and turn my voice on or off.",
        ),
        TourStep(
            "done", "/home", "✨", "You're all set",
            f"That's the tour. I'll be right here on every screen. If you ever forget "
            f"something, just ask me \"how do I…\" or tap the mic. {close}",
            f"That is the tour. I will be right here on every screen. If you ever "
            f"forget something, just ask me how do I, or tap the mic. {close}",
        ),
    ]
    return steps
