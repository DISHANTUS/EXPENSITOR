"""Companion styles (Sprint 4c-B1, pure).

Same facts, different personality. Styles flavor the salutation/encouragement and
(in 4c-B2) the Ollama prompt. Never judgmental in any style.
"""

from __future__ import annotations

STYLES = ("balanced", "cheerful", "professional", "anime", "minimal")
DEFAULT = "balanced"


def normalize(style: str | None) -> str:
    return style if style in STYLES else DEFAULT


def salutation(base: str, style: str) -> str:
    """Flavor a base salutation ('Good morning') for the chosen style."""
    style = normalize(style)
    if style == "minimal":
        # Drop the leading "Good ".
        return base.replace("Good ", "").capitalize()
    if style == "anime":
        return base.replace(".", "~")
    if style == "cheerful":
        return base
    return base  # balanced / professional keep it plain


def flair(style: str) -> str:
    """A trailing emoji flair appended to celebratory lines."""
    return {"cheerful": " 😊", "anime": " ✨"}.get(normalize(style), "")


def encouragements(style: str) -> list[str]:
    style = normalize(style)
    pools = {
        "balanced": ["Have a good one.", "Hope today goes well.", "I’m here if you need me."],
        "cheerful": ["Let’s make today a good one!", "You’ve got this!", "Cheering you on!"],
        "professional": ["Have a productive day.", "Let me know if you need anything.", "Wishing you a steady day."],
        "anime": ["Do your best today~", "I’ll be right here cheering for you ✨", "Ganbatte!"],
        "minimal": ["Have a good day.", "Take care.", ""],
    }
    return pools[style]
