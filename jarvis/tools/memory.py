"""Let Jarvis remember and forget things about you."""

from __future__ import annotations

from . import tool


@tool(
    "Remember a fact about the user for the future (their name, preferences, "
    "birthdays, where they study or work...). Use it when the user says "
    "'remember that...' or shares something worth keeping.",
    {"fact": {"type": "string", "description": "The fact, written as a full sentence"}},
)
def remember(ctx, fact: str) -> str:
    ctx.memory.add(fact)
    return f"Saved to memory: {fact}"


@tool(
    "Forget remembered facts that contain some text.",
    {"text": {"type": "string", "description": "Words that appear in the fact to forget"}},
)
def forget(ctx, text: str) -> str:
    removed = ctx.memory.forget(text)
    if not removed:
        return f"Nothing in memory mentions '{text}'."
    return "Forgot: " + "; ".join(removed)
