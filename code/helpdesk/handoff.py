"""Final-pipeline step after P2: what the student sees when ZEN AI does not answer.

- not_found / handoff -> P3 handoff draft (prompts/final/P3_handoff.md, one LLM call, JSON mode). Draft only: nothing
  is ever sent from here.
- refuse / clarify    -> fixed template text, no LLM call.
- a message with two or more topics -> the original pipeline answers the first and MULTI_TOPIC_NOTE tells the student
  to ask the rest separately; the two-topic final pipeline answers the first two (finish_topic for topic 2) and
  MULTI_TOPIC_NOTE_REST covers a third or later topic. Other topics are listed, never dropped silently.

The office comes from P1 v2's first-topic domain (FEES -> FINANCE, OUT_OF_SCOPE or none -> HELPDESK). Office email
addresses are demo addresses built from the tags in config/mailbox_map.yaml on a reserved, non-deliverable domain,
so no real address ever reaches a prompt, a run file or the app.

Provider errors (quota, network) are raised, never turned into a draft.
"""
from __future__ import annotations

import hashlib
import re

import yaml

from zenai.paths import CONFIG_DIR, PROMPTS
from zenai.providers import JSONParseError

TEMPLATE_MARKER = "<!-- TEMPLATE -->"
PROMPT_FILE = PROMPTS / "final" / "P3_handoff.md"
PROMPT_FILE_V1 = PROMPTS / "v1" / "P3_handoff.md"
DEMO_DOMAIN = "zenai-demo.example"  # .example is reserved (RFC 2606): never deliverable
MAX_BODY_WORDS = 120
PLACEHOLDERS = ("[Your name]", "[Enrollment no.]")
DRAFT_KEYS = ("to", "subject", "body")

REASON_NOT_FOUND = "not found in documents"
REASON_RECORD = "needs the student's own record"
REASON_ACT = "needs someone to act"

DOMAIN_TO_OFFICE = {"FEES": "FINANCE", "IT": "IT", "ACADEMICS": "ACADEMICS", "HOSTEL": "HOSTEL",
                    "CAMPUS_SERVICES": "CAMPUS_SERVICES", "STUDENT_SUPPORT": "STUDENT_SUPPORT"}
DEFAULT_OFFICE = "HELPDESK"

MULTI_TOPIC_NOTE = ("Your message has more than one question. I answered the first one; please ask the other "
                    "separately.")
MULTI_TOPIC_NOTE_REST = ("Your message has more than two questions. I answered the first two; please ask the rest "
                         "separately.")
REFUSE_TEXT = ("Sorry, I can't help with that. ZEN AI answers questions about Bennett University from its official "
               "documents: fees, refunds and scholarships; exams, attendance and academic rules; hostel rules; IT, "
               "email and wifi; campus services; and student support such as anti-ragging and harassment policies. "
               "I can't share anyone's personal records. Please ask a question about one of these.")
CLARIFY_EMPTY = ("Please type your question. Is it about fees, exams, the hostel, IT or campus services?")


def _yaml(name: str) -> dict:
    with open(CONFIG_DIR / name, encoding="utf-8") as f:
        return yaml.safe_load(f)


def office_for(domain: str | None) -> str:
    return DOMAIN_TO_OFFICE.get(domain or "", DEFAULT_OFFICE)


def office_name(office: str) -> str:
    return _yaml("offices.yaml")["offices"][office]["display_name"]


def office_email(office: str) -> str:
    """Demo address from the office's tag in config/mailbox_map.yaml, e.g. finance@zenai-demo.example."""
    return f"{_yaml('mailbox_map.yaml')['offices'][office]}@{DEMO_DOMAIN}"


def clarify_text(topics: list[dict]) -> str:
    """One short question naming the likely offices (from P1's vague topics); a generic question when P1 gave none."""
    offices: list[str] = []
    for t in topics:
        if t.get("request_type") == "vague" and t.get("domain") in DOMAIN_TO_OFFICE:
            name = office_name(office_for(t["domain"]))
            if name not in offices:
                offices.append(name)
    if not offices:
        return CLARIFY_EMPTY
    which = (f"the {offices[0]} or a different office" if len(offices) == 1
             else f"the {', the '.join(offices[:-1])} or the {offices[-1]}")
    return f"Is your question for {which}? Please add a few words about what you need."


def handoff_reason(action: str, first_topic_reason: str = "") -> str:
    """not_found -> not found in documents; handoff -> own record if P1 v2's reason sentence mentions a record
    (P1 v2 defines needs_human as "the student's own record ... or someone must act"), else someone must act."""
    if action == "not_found":
        return REASON_NOT_FOUND
    return REASON_RECORD if re.search(r"\brecords?\b", first_topic_reason or "", re.I) else REASON_ACT


def load_template(path=PROMPT_FILE) -> str:
    text = path.read_text(encoding="utf-8")
    if TEMPLATE_MARKER not in text:
        raise ValueError(f"{path} has no {TEMPLATE_MARKER} line")
    return text.split(TEMPLATE_MARKER, 1)[1].lstrip("\r\n").rstrip() + "\n"


def file_sha256() -> str:
    return hashlib.sha256(PROMPT_FILE.read_bytes()).hexdigest()


def fill(template: str, question: str, office: str, email: str, reason: str) -> str:
    # str.replace, not str.format: the template contains JSON braces. {question} last, so text inside it is not
    # treated as a placeholder.
    return (template.replace("{office}", office).replace("{office_email}", email).replace("{reason}", reason)
            .replace("{question}", question))


def check_draft(reply: dict, email: str) -> dict:
    body = str(reply.get("body") or "")
    words = len(body.split())
    return {"keys_present": all(k in reply for k in DRAFT_KEYS), "to_matches": str(reply.get("to") or "") == email,
            "body_words": words, "under_120_words": words < MAX_BODY_WORDS,
            "placeholders_present": all(p in body for p in PLACEHOLDERS)}


def draft(question: str, office: str, reason: str, provider) -> dict:
    """P3: {"office", "office_name", "reason", "prompt_sha256", "raw", "draft" {to, subject, body} or None, "checks",
    "error"}. `to` is always set to the office's demo address."""
    email, name = office_email(office), office_name(office)
    prompt = fill(load_template(), question, name, email, reason)
    out = {"office": office, "office_name": name, "office_email": email, "reason": reason,
           "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(), "raw": None, "draft": None,
           "checks": None, "error": ""}
    try:
        reply = provider.chat_json([{"role": "user", "content": prompt}])
    except JSONParseError as e:  # the reply was not JSON: a format failure, not a provider error
        out.update(raw=e.raw, error=str(e))
        return out
    out["raw"] = reply
    out["checks"] = check_draft(reply, email)
    out["draft"] = {"to": email, "subject": str(reply.get("subject") or ""), "body": str(reply.get("body") or "")}
    return out


def _reply(r: dict, topic: dict, clarify_topics: list[dict], question: str, provider) -> dict:
    office = office_for(topic.get("domain"))
    r.update(office=office, office_name=office_name(office), reply_text="", p3=None)
    action = r["action"]
    if action == "refuse":
        r["reply_text"] = REFUSE_TEXT
    elif action == "clarify":
        r["reply_text"] = clarify_text(clarify_topics)
    elif action in ("not_found", "handoff"):
        reason = handoff_reason(action, topic.get("reason", ""))
        r["p3"] = draft(question, office, reason, provider)
        r["llm_calls"] += 1
    return r


def finish(out: dict, provider, answered: int = 1) -> dict:
    """Add what the student sees to a pipeline.answer() result (topic 1): office, reply text or P3 draft, and the
    multi-topic note when P1 found more topics than `answered` (1: the original pipeline, 2: topics 1 and 2 answered,
    the rest listed). With answered >= 2 and several topics, topic 1's clarify names only topic 1's office and its P3
    draft is written for topic 1's own text (out["p2_question"])."""
    topics = (out.get("router") or {}).get("topics") or []
    first = topics[0] if topics else {}
    own = answered >= 2 and len(topics) > 1
    _reply(out, first, [first] if own else topics, out.get("p2_question") or out["question"], provider)
    rest = topics[answered:]
    note = MULTI_TOPIC_NOTE if answered == 1 else MULTI_TOPIC_NOTE_REST
    out.update(other_topics=[t.get("text", "") for t in rest], multi_topic_note=note if rest else "")
    return out


def finish_topic(r: dict, provider) -> dict:
    """What the student sees for one pipeline.answer_topic() result (topic 2 and later): office, reply text or a P3
    draft for the topic's own text."""
    topic = r.get("topic") or {}
    return _reply(r, topic, [topic], r["question"], provider)
