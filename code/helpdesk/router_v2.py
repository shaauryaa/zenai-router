"""Router P1 v2 (Milestone 2 step 2): prompts/v2/P1_router.md.

Same JSON shape as the frozen v1 router (zenai/llm_router.py, unchanged) plus one field per topic, `search_query`,
and one more domain, STUDENT_SUPPORT. Same call pattern as v1: system prompt + "Student message: <message>", JSON
mode, one retry with the error on an unusable reply, then a fallback topic with domain and request_type None
(-> handoff). Provider errors (quota, network) are raised.
"""
from __future__ import annotations

import hashlib
import json
from typing import Literal

from pydantic import BaseModel, Field, ValidationError, model_validator

from zenai.paths import PROMPTS
from zenai.providers import JSONParseError

TEMPLATE_MARKER = "<!-- TEMPLATE -->"
PROMPT_FILE = PROMPTS / "v2" / "P1_router.md"

DomainV2 = Literal["IT", "FEES", "ACADEMICS", "HOSTEL", "CAMPUS_SERVICES", "STUDENT_SUPPORT", "OUT_OF_SCOPE"]
RequestType = Literal["info", "needs_human", "vague", "not_campus"]


class TopicV2(BaseModel):
    text: str = Field(min_length=1)
    domain: DomainV2 | None
    request_type: RequestType | None
    search_query: str = ""
    reason: str = ""


class TopicsV2(BaseModel):
    topics: list[TopicV2] = Field(min_length=1)

    @model_validator(mode="after")
    def labels_present(self):
        for t in self.topics:
            if t.domain is None or t.request_type is None:
                raise ValueError("every topic needs a domain and a request_type")
        return self


def system_prompt() -> str:
    text = PROMPT_FILE.read_text(encoding="utf-8")
    if TEMPLATE_MARKER not in text:
        raise ValueError(f"{PROMPT_FILE} has no {TEMPLATE_MARKER} line")
    return text.split(TEMPLATE_MARKER, 1)[1].strip() + "\n"


def file_sha256() -> str:
    return hashlib.sha256(PROMPT_FILE.read_bytes()).hexdigest()


def _messages(message: str) -> list[dict]:
    return [{"role": "system", "content": system_prompt()},
            {"role": "user", "content": f"Student message: {message}"}]


def _parse(provider, messages: list[dict]) -> tuple[list[TopicV2] | None, str, str]:
    try:
        reply = provider.chat_json(messages)
    except JSONParseError as e:
        return None, e.raw, str(e)
    raw = json.dumps(reply, ensure_ascii=False)
    try:
        return TopicsV2.model_validate(reply).topics, raw, ""
    except ValidationError as e:
        return None, raw, str(e).splitlines()[0]


def classify(message: str, provider) -> tuple[list[TopicV2], dict]:
    """Split and label a message with P1 v2. On two unusable replies, return one unlabelled topic (-> handoff)."""
    messages = _messages(message)
    topics, raw, error = _parse(provider, messages)
    if topics is not None:
        return topics, {"attempts": 1, "fallback": False}
    retry = messages + [
        {"role": "assistant", "content": raw},
        {"role": "user", "content": f"That reply was invalid ({error}). Reply again with only the JSON object "
                                    "in the required format, using only the listed domain and request type names."},
    ]
    topics, _, error2 = _parse(provider, retry)
    if topics is not None:
        return topics, {"attempts": 2, "fallback": False, "first_error": error}
    fallback = TopicV2(text=message, domain=None, request_type=None, reason="LLM reply could not be parsed")
    return [fallback], {"attempts": 2, "fallback": True, "first_error": error, "error": error2}
