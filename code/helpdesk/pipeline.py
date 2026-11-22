"""Milestone 2 helpdesk pipeline: router (P1) -> KB search -> grounded answer (P2) -> quote check.

answer(question, p2_version) returns a dict holding every intermediate step:
  a. empty or whitespace input -> action clarify, no LLM call
  b. P1 = the frozen v1 router's classify() (zenai/llm_router.py, unchanged). The first topic decides; all topics are
     recorded. request_type not_campus -> refuse, vague -> clarify, needs_human -> handoff, info -> continue
     (an unusable router reply, request_type None, -> handoff)
  c. kb_search.search_for_route(question, first topic's domain, k=5)
  d. P2: prompts/<version>/P2_grounded_answer.md (the text after TEMPLATE_MARKER) with {question} and {sections}
     filled in, sent as one user message. v1 is plain text (chat_text), v2 and later JSON mode (chat_json)
  e. quote check (code, no LLM): the quote must appear in one retrieved section after normalising both sides
     (quote_forms: markdown ** and __ removed, OCR line-end hyphens joined, whitespace collapsed, case-insensitive).
     If P2 says found but the check fails, action becomes not_found and the reason is kept
  f. found = false -> action not_found (the handoff for not_found comes later)

Options (Milestone 2 steps; the defaults are the original pipeline):
  router="v1" frozen zenai/llm_router.py | "v2" helpdesk/router_v2.py (P1 v2, prompts/v2/P1_router.md)
  search="route5" search_for_route(question, domain, k=5)
       | "routed5_all3" search_routed_plus_all(first topic's search_query, or the question if empty, domain): top 5
         from the routed folder + top 3 from all folders

Provider errors (quota, network) are raised, never turned into answers.
"""
from __future__ import annotations

import hashlib
import re

from helpdesk import kb_search, router_v2
from zenai.config import load_config
from zenai.llm_router import classify
from zenai.paths import PROMPTS
from zenai.providers import JSONParseError, Provider

TEMPLATE_MARKER = "<!-- TEMPLATE -->"
PLAIN_TEXT_VERSIONS = {"v1"}  # every other version replies in JSON mode
NOT_FOUND_TEXT = re.compile(r"couldn['’]?t find this in the official documents", re.I)
FIRST_QUOTE = re.compile(r"[\"“](.+?)[\"”]", re.S)
JSON_KEYS = ("found", "answer", "quote", "doc_title", "page", "language")
ROUTER_ACTIONS = {"not_campus": "refuse", "vague": "clarify", "needs_human": "handoff"}
ROUTERS = ("v1", "v2")
SEARCHES = ("route5", "routed5_all3")

_PROVIDER: Provider | None = None


def default_provider() -> Provider:
    global _PROVIDER
    if _PROVIDER is None:
        _PROVIDER = Provider(load_config())
    return _PROVIDER


def prompt_path(version: str):
    return PROMPTS / version / "P2_grounded_answer.md"


def load_template(version: str) -> str:
    """The template text of a prompt file: everything after the marker line."""
    text = prompt_path(version).read_text(encoding="utf-8")
    if TEMPLATE_MARKER not in text:
        raise ValueError(f"{prompt_path(version)} has no {TEMPLATE_MARKER} line")
    return text.split(TEMPLATE_MARKER, 1)[1].lstrip("\r\n").rstrip() + "\n"


def file_sha256(version: str) -> str:
    return hashlib.sha256(prompt_path(version).read_bytes()).hexdigest()


def format_sections(hits: list[kb_search.Hit]) -> str:
    parts = []
    for n, h in enumerate(hits, 1):
        c = h.chunk
        page = c.page if c.page is not None else "-"
        parts.append(f"[Section {n}] Document: {c.title} | Office: {c.office} | Page: {page} | "
                     f"Source: {c.source_url or '-'}\n{c.text}")
    return "\n\n".join(parts) if parts else "(no matching sections)"


def fill(template: str, question: str, sections: str) -> str:
    # str.replace, not str.format: the JSON templates contain braces
    return template.replace("{sections}", sections).replace("{question}", question)


def norm(text: str) -> str:
    """Whitespace and line breaks collapsed to one space, lowercased."""
    return re.sub(r"\s+", " ", text or "").strip().lower()


MARKDOWN_EMPHASIS = re.compile(r"\*\*|__")
LINE_END_HYPHEN = re.compile(r"(\w)-[ \t]*\r?\n\s*(\w)")  # "Anti-\nRagging", "exam-\nination"
SPACED_HYPHEN = re.compile(r"(\w)- +(\w)")  # a line-end hyphen after the model turned the break into a space


def quote_forms(text: str, *, source: bool) -> set[str]:
    """Normalised forms of a text for the quote check (Milestone 2 step 1): markdown ** and __ removed, a word split
    by an OCR line-end hyphen joined, whitespace collapsed, lowercased. A line-end hyphen is ambiguous (a real compound
    "Anti-Ragging" or a split word "exam-ination"), so a source section gets both joins: hyphen kept and hyphen dropped.
    In a quote, "word- word" is read as the same line-end hyphen (hyphen kept)."""
    text = MARKDOWN_EMPHASIS.sub("", text or "")
    if source:
        forms = {LINE_END_HYPHEN.sub(r"\1-\2", text), LINE_END_HYPHEN.sub(r"\1\2", text)}
    else:
        forms = {SPACED_HYPHEN.sub(r"\1-\2", text)}
    return {norm(f) for f in forms}


def check_quote(quote: str, hits: list[kb_search.Hit]) -> tuple[bool, str | None, str]:
    """(verified, chunk id the quote was found in, reason). Both sides are normalised by quote_forms()."""
    (q,) = quote_forms(quote, source=False)
    if not q:
        return False, None, "empty quote"
    for h in hits:
        if any(q in form for form in quote_forms(h.chunk.text, source=True)):
            return True, h.chunk.id, ""
    return False, None, "quote not found in the retrieved sections"


def parse_plain(reply: str) -> dict:
    """v1: not_found if the reply says it couldn't find the answer; quote = text in the first pair of double quotes."""
    m = FIRST_QUOTE.search(reply)
    return {"found": not NOT_FOUND_TEXT.search(reply), "answer": reply.strip(), "quote": m.group(1).strip() if m else "",
            "doc_title": "", "page": "", "language": "", "format_valid": None, "format_error": ""}


def parse_json(reply: dict) -> dict:
    missing = [k for k in JSON_KEYS if k not in reply]
    error = f"missing keys {missing}" if missing else ""
    if not error and not isinstance(reply["found"], bool):
        error = f"found is {reply['found']!r}, not true/false"
    out = {k: ("" if reply.get(k) is None else str(reply.get(k))) for k in JSON_KEYS if k != "found"}
    out["found"] = reply.get("found") is True
    out.update(format_valid=not error, format_error=error)
    return out


def answer(question: str, p2_version: str, provider=None, router: str = "v1", search: str = "route5") -> dict:
    if router not in ROUTERS or search not in SEARCHES:
        raise ValueError(f"router must be one of {ROUTERS}, search one of {SEARCHES}")
    out: dict = {"question": question, "p2_version": p2_version, "router_version": router, "search": search,
                 "action": None, "reason": "", "router": None, "first_topic": None, "search_query": None,
                 "retrieval": [], "p2_prompt_sha256": None, "p2_raw": None, "p2": None, "quote_check": None,
                 "llm_calls": 0}
    if not (question or "").strip():
        out.update(action="clarify", reason="empty input: no LLM call")
        return out
    provider = provider or default_provider()

    # b. P1 router (frozen v1, or P1 v2)
    topics, router_meta = (classify if router == "v1" else router_v2.classify)(question, provider)
    out["router"] = {"topics": [t.model_dump() for t in topics], "meta": router_meta}
    first = topics[0]
    out["first_topic"] = {"domain": first.domain, "request_type": first.request_type}
    out["llm_calls"] += router_meta["attempts"]
    if first.request_type is None:
        out.update(action="handoff", reason="router reply unusable")
        return out
    if first.request_type in ROUTER_ACTIONS:
        out.update(action=ROUTER_ACTIONS[first.request_type], reason=f"router request_type {first.request_type}")
        return out

    # c. search
    if search == "route5":
        query = question
        hits = kb_search.search_for_route(query, first.domain, k=5)
    else:
        query = (getattr(first, "search_query", "") or "").strip() or question
        hits = kb_search.search_routed_plus_all(query, first.domain, routed_k=5, all_k=3)
    out["search_query"] = query
    out["retrieval"] = [{"id": h.chunk.id, "file": h.chunk.file, "title": h.chunk.title, "office": h.chunk.office,
                         "page": h.chunk.page, "score": h.score} for h in hits]

    # d. P2
    prompt = fill(load_template(p2_version), question, format_sections(hits))
    out["p2_prompt_sha256"] = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    messages = [{"role": "user", "content": prompt}]
    out["llm_calls"] += 1
    if p2_version in PLAIN_TEXT_VERSIONS:
        raw = provider.chat_text(messages)
        out["p2_raw"] = raw
        p2 = parse_plain(raw)
    else:
        try:
            reply = provider.chat_json(messages)
            out["p2_raw"] = reply
            p2 = parse_json(reply)
        except JSONParseError as e:  # the model's reply was not JSON: a format failure, not a provider error
            out["p2_raw"] = e.raw
            p2 = {"found": False, "answer": e.raw, "quote": "", "doc_title": "", "page": "", "language": "",
                  "format_valid": False, "format_error": str(e)}
    out["p2"] = p2

    # e. quote check
    verified, chunk_id, why = check_quote(p2["quote"], hits)
    out["quote_check"] = {"verified": verified, "chunk_id": chunk_id, "reason": why}

    # f. decision
    out["action"], out["reason"] = decide(p2, verified, why)
    return out


def decide(p2: dict, verified: bool, why: str) -> tuple[str, str]:
    """Step f: (action, reason) from P2's parsed reply and the quote check."""
    if not p2["found"]:
        return "not_found", "P2 found=false" + (f" (invalid format: {p2['format_error']})"
                                                if p2.get("format_valid") is False else "")
    if not verified:
        return "not_found", f"P2 said found but quote check failed: {why}"
    return "answer", "P2 found, quote verified"
