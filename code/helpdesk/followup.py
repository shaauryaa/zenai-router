"""Clarify follow-up (Milestone 2 sprint S4). No LLM call.

The app keeps the last turn in session state as {"question": the text the pipeline ran on, "action": its action}.
If the last action was clarify and the new message is short (MAX_WORDS words or fewer), the pipeline runs on
"<previous question> <new message>" and the app shows FOLLOWUP_NOTE. Otherwise the new message runs on its own.
A clarify for an empty message has no previous question to join, so the next message runs on its own.
"""
from __future__ import annotations

MAX_WORDS = 8
FOLLOWUP_NOTE = "Using your previous message: “{previous}”"


def resolve(last: dict | None, message: str) -> tuple[str, str]:
    """(the question to run, the previous question it was joined to, or "" when it was not joined)."""
    message = (message or "").strip()
    previous = ((last or {}).get("question") or "").strip()
    if (last or {}).get("action") == "clarify" and previous and message and len(message.split()) <= MAX_WORDS:
        return f"{previous} {message}", previous
    return message, ""


def remember(result: dict, question: str) -> dict:
    """The last turn to keep: the question the pipeline ran on and its (topic 1) action."""
    return {"question": question, "action": result.get("action")}
