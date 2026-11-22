"""Signal A: the LLM splits a message into topics and labels each with a domain and request type.

The prompt contains domain descriptions only. Example questions live only in the kNN index (knn.py).
"""
import json

from pydantic import ValidationError

from .providers import JSONParseError
from .schemas import LLMTopics, Topic

SYSTEM_PROMPT = """\
You are the routing step of a university campus helpdesk. You never answer the student's question.
You read one student message, written in English or Hinglish (Hindi in Latin script), and decide which
campus team each part of it belongs to.

Domains:
- IT: ERP, college email/Outlook, LMS, university laptops, network accounts and wifi connectivity.
- FEES: fee structure, payments, receipts, scholarships, refunds, fee deadlines.
- ACADEMICS: exams, academic calendar and holidays, attendance, faculty and their contacts, registrar documents, courses and batches, placements, clubs and fests.
- HOSTEL (wardens): room change and allotment, curfew/in-time, leave and outing, guests, hostel rules, laundry.
- CAMPUS_SERVICES (Punctualiti helpdesk): maintenance and cleaning (electrical, plumbing, AC), mess and food outlets, transport, sports facilities, library, lost and found.
- OUT_OF_SCOPE: not a campus question, jokes, opinions, or anyone's private records.

Request types:
- info: an official document could answer it for everyone.
- needs_human: needs the student's own records, a fix, a complaint, or faculty-specific info.
- vague: cannot be routed without asking.
- not_campus: out of scope.

Instructions:
1. Split the message into topics, one per distinct request, in the order they appear. A message about one thing is one topic.
2. For each topic give "text" (the part of the message about that topic, in the student's own words),
   "domain" (exactly one domain name from the list above), "request_type" (exactly one request type from
   the list above) and "reason" (one short sentence explaining the choice).
3. If a topic is OUT_OF_SCOPE, its request_type is not_campus.
4. If a topic is too unclear to route, still give the most likely domain and set request_type to vague.

Reply with only this JSON object:
{"topics": [{"text": "...", "domain": "...", "request_type": "...", "reason": "..."}]}
"""


def _messages(message: str) -> list[dict]:
    return [{"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Student message: {message}"}]


def _parse(provider, messages: list[dict]) -> tuple[list[Topic] | None, str, str]:
    """Return (topics, raw_reply, error). topics is None if the reply was unusable."""
    try:
        reply = provider.chat_json(messages)
    except JSONParseError as e:
        return None, e.raw, str(e)
    raw = json.dumps(reply, ensure_ascii=False)
    try:
        return LLMTopics.model_validate(reply).topics, raw, ""
    except ValidationError as e:
        return None, raw, str(e).splitlines()[0]


def classify(message: str, provider) -> tuple[list[Topic], dict]:
    """Split and label a message. On two unusable replies, return one unlabelled topic (-> handoff).

    Provider errors (quota, network) are raised, not swallowed, so an evaluation run cannot silently
    record them as routing decisions.
    """
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

    fallback = Topic(text=message, domain=None, request_type=None, reason="LLM reply could not be parsed")
    return [fallback], {"attempts": 2, "fallback": True, "first_error": error, "error": error2}
