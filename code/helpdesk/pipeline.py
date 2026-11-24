"""Milestone 2 helpdesk pipeline: router (P1) -> KB search -> grounded answer (P2) -> quote check.

answer(question, p2_version) returns a dict holding every intermediate step:
  a. empty or whitespace input -> action clarify, no LLM call
  b. P1 = the frozen v1 router's classify() (zenai/llm_router.py, unchanged). The first topic decides; all topics are
     recorded. request_type not_campus -> refuse, vague -> clarify, needs_human -> handoff, info -> continue
     (an unusable router reply, request_type None, -> handoff)
  c. kb_search.search_for_route(question, first topic's domain, k=5)
  d. P2: prompts/<version>/P2_grounded_answer.md (the text after TEMPLATE_MARKER) with {question} and {sections}
     filled in, sent as one user message. v1 is plain text (chat_text), v2 and later JSON mode (chat_json)
  e. quote check v2 (code, no LLM, verify_quote): rule "exact" = the quote appears in one retrieved section after
     normalising both sides (quote_forms: markdown ** and __ removed, OCR line-end hyphens joined, whitespace
     collapsed, case-insensitive). If not, rule "near" accepts it against ONE section when every content word of the
     quote (negation words kept) is in that section, every number has the same tokens on both sides as in the
     section, it has >= 4 content words, and the best-matching part of the section has as many negations as the
     quote (table rows reformatted, OCR lines reordered, OCR typos such as "ona scale"). Both
     rules reject a quote that drops a negation standing just before the matched text in the source.
     quote_check["rule"] records which rule verified it.
     If P2 says found but the check fails, action becomes not_found and the reason is kept
  f. found = false -> action not_found (the handoff for not_found comes later)

Options (Milestone 2 steps; the defaults are the original pipeline):
  router="v1" frozen zenai/llm_router.py | "v2" helpdesk/router_v2.py (P1 v2, prompts/v2/P1_router.md)
  search="route5" search_for_route(question, domain, k=5)
       | "routed5_all3" search_routed_plus_all(first topic's search_query, or the question if empty, domain): top 5
         from the routed folder + top 3 from all folders
       | "routed5_all3_prog" the same, but for an ACADEMICS question that names a programme (kb_search.programme_files
         on the question and the search_query) the top 5 routed come only from that programme's COURSE_SPECIFIC file(s)
       | "dual_prog" kb_search.search_dual_prog: the search_query AND the topic's own text (P1 topic "text", else
         the question) each ranked by BM25, merged by reciprocal rank fusion, then the same 5 routed + 3 all split
         and programme filter as routed5_all3_prog
  own_topic_text=True (final pipeline with two topics): when P1 finds two or more topics, P2 gets the first topic's
  own text instead of the whole message. Steps c-f for one topic are answer_topic(); final_answer() runs it for
  topic 2 too (config FINAL["topics"] == 2) and returns both in out["topic_results"].

Provider errors (quota, network) are raised, never turned into answers.
"""
from __future__ import annotations

import hashlib
import re
from collections import Counter

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
SEARCHES = ("route5", "routed5_all3", "routed5_all3_prog", "dual_prog")

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


# Quote check v2, "near" rule (Milestone 2 sprint S1). Numbers: digits with , . : separators (3,90,000 / 8.5 / 8:00);
# a % sign or a Rs/₹ prefix is not part of the match, commas are dropped (3,90,000 == 390000).
NUMBER = re.compile(r"\d+(?:[.,:]\d+)*")
TABLE_MARKUP = re.compile(r"\||^\s*#+\s*|^\s*-{3,}\s*$|`", re.M)  # table pipes, heading marks, rules, backticks
NEAR_MIN_WORDS = 4
# Not stop words for the quote check (kb_search drops "no", "not" and "nor" from search tokens).
NEGATIONS = frozenset({"no", "not", "never", "nor", "cannot", "without"})
NEGATION_WINDOW = 3
NUMBER_ABBREV = re.compile(r"\bno\.", re.I)  # "S. No.", "Enrollment No.": the abbreviation of number, not a negation
NEAR_TOKEN = re.compile(r"\d+(?:[.,:]\d+)*|[a-z0-9]+")  # a number with its separators is one token


def _plain(text: str) -> str:
    """Lowercased, without markdown emphasis, table pipes, heading marks and rules."""
    return TABLE_MARKUP.sub(" ", MARKDOWN_EMPHASIS.sub("", text or "")).lower()


def content_words(text: str) -> list[str]:
    """kb_search tokens (lowercased letter/digit runs minus STOP_WORDS) after removing table pipes and markdown."""
    return kb_search.tokenize(TABLE_MARKUP.sub(" ", MARKDOWN_EMPHASIS.sub("", text or "")))


def check_words(text: str) -> list[str]:
    """Content words for the near rule: content_words() with the NEGATIONS kept."""
    return [t for t in kb_search.TOKEN.findall(_plain(text)) if t not in kb_search.STOP_WORDS or t in NEGATIONS]


def number_stream(text: str) -> list[str]:
    """Content tokens in order, a number as one token without commas (3,90,000 -> 390000), NEGATIONS kept."""
    toks = [t.replace(",", "") if t[0].isdigit() else t for t in NEAR_TOKEN.findall(_plain(text))]
    return [t for t in toks if t not in kb_search.STOP_WORDS or t in NEGATIONS]


def number_pairs(stream: list[str]) -> list[tuple[str, set[tuple[str, str]]]]:
    """[(number, {(token before, number), (number, token after)})] for every number token of a stream."""
    out = []
    for i, t in enumerate(stream):
        if t[0].isdigit():
            pairs = set()
            if i > 0:
                pairs.add((stream[i - 1], t))
            if i + 1 < len(stream):
                pairs.add((t, stream[i + 1]))
            out.append((t, pairs))
    return out


def raw_tokens(text: str) -> list[str]:
    """Every lowercased letter/digit run, stop words included (for the negation window)."""
    return kb_search.TOKEN.findall(_plain(NUMBER_ABBREV.sub(" ", text or "")))


def dropped_negation(source_before: str, quote: str) -> bool:
    """True when the NEGATION_WINDOW tokens of the source right before the match hold a negation word and the
    first NEGATION_WINDOW tokens of the quote do not."""
    before = raw_tokens(source_before)[-NEGATION_WINDOW:]
    return any(t in NEGATIONS for t in before) and not any(t in NEGATIONS for t in raw_tokens(quote)[:NEGATION_WINDOW])


def best_windows(q_words: list[str], sources: set[str]) -> list[tuple[list[str], list[str]]]:
    """The windows of the chunk that best match the quote: every run of len(q_words) consecutive content tokens
    (stop words dropped, negations kept) of every source form, scored by how many of the quote's content words it
    holds (repeats counted). Returns [(window tokens, the raw tokens before the window)] for every window with the
    best score."""
    need = Counter(q_words)
    scored = []
    for s in sources:
        raw = raw_tokens(s)
        pos = [i for i, t in enumerate(raw) if t not in kb_search.STOP_WORDS or t in NEGATIONS]
        size = len(q_words)
        for start in range(max(1, len(pos) - size + 1)):
            window = [raw[i] for i in pos[start:start + size]]
            before = raw[:pos[start]] if pos else raw
            scored.append((sum((Counter(window) & need).values()), window, before))
    if not scored:
        return []
    top = max(score for score, _, _ in scored)
    return [(window, before) for score, window, before in scored if score == top]


def near_match(quote: str, chunk_text: str) -> tuple[bool, str]:
    """The near rule against ONE chunk: (accepted, why not). All must hold:
    a. every content word of the quote (check_words: negations kept) is in the chunk;
    b. every number of the quote is in the chunk next to the same tokens as in the quote: both its pair with the token
       right before it and its pair with the token right after it (only one where the number starts or ends the
       quote), pipes and punctuation removed;
    c. the quote has >= NEAR_MIN_WORDS content words;
    d. negations: in every chunk window that best matches the quote (best_windows; conservative: all tied windows
       must agree), the window holds the same number of negation words as the quote, and no negation stands in the
       NEGATION_WINDOW tokens just before the window unless the quote starts with one."""
    (q,) = quote_forms(quote, source=False)
    words = check_words(q)
    if len(words) < NEAR_MIN_WORDS:
        return False, f"{len(words)} content words (< {NEAR_MIN_WORDS})"
    sources = quote_forms(chunk_text, source=True)  # both line-end hyphen joins
    vocab = set().union(*(check_words(s) for s in sources))
    missing = sorted({w for w in words if w not in vocab})
    if missing:
        return False, f"content words not in section: {', '.join(missing)}"
    chunk_pairs = set()
    for s in sources:
        for _, pairs in number_pairs(number_stream(s)):
            chunk_pairs |= pairs
    for num, pairs in number_pairs(number_stream(q)):
        if not pairs <= chunk_pairs:
            return False, f"number {num} not next to the same words as in the section"
    q_neg = sum(w in NEGATIONS for w in words)
    q_starts_negated = any(t in NEGATIONS for t in raw_tokens(q)[:NEGATION_WINDOW])
    for window, before in best_windows(words, sources):
        if sum(t in NEGATIONS for t in window) != q_neg:
            return False, "dropped negation: the matching part of the section has a different number of negations"
        if any(t in NEGATIONS for t in before[-NEGATION_WINDOW:]) and not q_starts_negated:
            return False, "dropped negation: the section has a negation just before the quoted text"
    return True, ""


def verify_quote(quote: str, hits: list[kb_search.Hit]) -> dict:
    """Quote check v2: {"verified", "chunk_id", "reason", "rule"}. rule "exact": the quote appears in one retrieved
    section after quote_forms() normalising (the original check, always tried first). rule "near": no exact match,
    but near_match() accepts it against one section. rule None: not verified. Both rules reject a match that drops a
    negation of the source (dropped_negation)."""
    (q,) = quote_forms(quote, source=False)
    if not q:
        return {"verified": False, "chunk_id": None, "reason": "empty quote", "rule": None}
    exact_dropped = False
    for h in hits:
        for form in quote_forms(h.chunk.text, source=True):
            start = form.find(q)
            while start != -1:
                if not dropped_negation(form[:start], q):
                    return {"verified": True, "chunk_id": h.chunk.id, "reason": "", "rule": "exact"}
                exact_dropped = True
                start = form.find(q, start + 1)
    why_near = []
    for h in hits:
        ok, why = near_match(quote, h.chunk.text)
        if ok:
            return {"verified": True, "chunk_id": h.chunk.id, "reason": "", "rule": "near"}
        why_near.append(why)
    if exact_dropped or any(w.startswith("dropped negation") for w in why_near):
        reason = "dropped negation: the source has a negation just before the quoted text"
    else:
        reason = "quote not found in the retrieved sections"
        if why_near and why_near[0].endswith(f"(< {NEAR_MIN_WORDS})"):
            reason += f"; near rule not applicable: {why_near[0]}"
        elif why_near:
            reason += " (exact or near)"
    return {"verified": False, "chunk_id": None, "reason": reason, "rule": None}


def check_quote(quote: str, hits: list[kb_search.Hit]) -> tuple[bool, str | None, str]:
    """(verified, chunk id the quote was found in, reason): verify_quote() without the rule name."""
    r = verify_quote(quote, hits)
    return r["verified"], r["chunk_id"], r["reason"]


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


def answer(question: str, p2_version: str, provider=None, router: str = "v1", search: str = "route5",
           own_topic_text: bool = False) -> dict:
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
    p2_question = question
    if own_topic_text and len(topics) > 1:
        p2_question = (getattr(first, "text", "") or "").strip() or question
        out["p2_question"] = p2_question

    # c-f for the first topic
    r = answer_topic(out["router"]["topics"][0], p2_question, p2_version, provider, search)
    out["llm_calls"] += r.pop("llm_calls")
    out.update({k: v for k, v in r.items() if k not in ("topic", "question")})
    return out


TOPIC_FIELDS = ("action", "reason", "search_query", "retrieval", "p2_prompt_sha256", "p2_raw", "p2", "quote_check")


def answer_topic(topic: dict, question: str, p2_version: str, provider, search: str = "route5") -> dict:
    """Steps c-f for ONE router topic (a dict as in out["router"]["topics"]): its request_type decides refuse /
    clarify / handoff, an info topic gets its own search (its search_query, else `question`, and its domain), P2 on
    `question` and the quote check. Returns {"topic", "question", "llm_calls", "programme_files" (prog search only),
    *TOPIC_FIELDS}."""
    r: dict = {"topic": topic, "question": question, "llm_calls": 0, **{k: None for k in TOPIC_FIELDS}}
    r.update(reason="", retrieval=[])
    rt, domain = topic.get("request_type"), topic.get("domain")
    if rt is None:
        r.update(action="handoff", reason="router reply unusable")
        return r
    if rt in ROUTER_ACTIONS:
        r.update(action=ROUTER_ACTIONS[rt], reason=f"router request_type {rt}")
        return r

    # c. search
    if search == "route5":
        query = question
        hits = kb_search.search_for_route(query, domain, k=5)
    else:
        query = (topic.get("search_query") or "").strip() or question
        if search == "routed5_all3":
            hits = kb_search.search_routed_plus_all(query, domain, routed_k=5, all_k=3)
        elif search == "dual_prog":
            r["programme_files"] = kb_search.programme_files(question, query) if domain == "ACADEMICS" else []
            r["topic_text_query"] = (topic.get("text") or "").strip() or question
            hits = kb_search.search_dual_prog(query, r["topic_text_query"], domain, question, routed_k=5, all_k=3)
        else:
            r["programme_files"] = kb_search.programme_files(question, query) if domain == "ACADEMICS" else []
            hits = kb_search.search_routed_plus_all_prog(query, domain, question, routed_k=5, all_k=3)
    r["search_query"] = query
    r["retrieval"] = [{"id": h.chunk.id, "file": h.chunk.file, "title": h.chunk.title, "office": h.chunk.office,
                       "page": h.chunk.page, "score": h.score} for h in hits]

    # d. P2
    prompt = fill(load_template(p2_version), question, format_sections(hits))
    r["p2_prompt_sha256"] = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    messages = [{"role": "user", "content": prompt}]
    r["llm_calls"] += 1
    if p2_version in PLAIN_TEXT_VERSIONS:
        raw = provider.chat_text(messages)
        r["p2_raw"] = raw
        p2 = parse_plain(raw)
    else:
        try:
            reply = provider.chat_json(messages)
            r["p2_raw"] = reply
            p2 = parse_json(reply)
        except JSONParseError as e:  # the model's reply was not JSON: a format failure, not a provider error
            r["p2_raw"] = e.raw
            p2 = {"found": False, "answer": e.raw, "quote": "", "doc_title": "", "page": "", "language": "",
                  "format_valid": False, "format_error": str(e)}
    r["p2"] = p2

    # e. quote check
    r["quote_check"] = qc = verify_quote(p2["quote"], hits)

    # f. decision
    r["action"], r["reason"] = decide(p2, qc["verified"], qc["reason"], qc["rule"])
    return r


# The final pipeline (Milestone 2 sprint S3, frozen 24 Nov): P1 v2 + programme-aware search + P2 v2 + quote check v2
# (tightened) + P3 v2, and the first two topics of a message each answered on their own. P2 v5 was tried and rejected
# (run test-data/runs/final_20261124-173053); prompts/v5/ is kept as a recorded version.
# Sprint S4: search dual_prog (search_query + topic text, reciprocal rank fusion) replaced routed5_all3_prog after
# test-data/runs/search_recall_dual_20261124-180009: no labelled topic lost its expected page, Q16 topic 2 gained it.
FINAL = {"router": "v2", "search": "dual_prog", "p2": "v2", "p3": "v2", "topics": 2}
# The 22 Nov final pipeline as re-scored from the cache in sprint S1 (one topic, old search, P2 v2).
S1_FINAL = {"router": "v2", "search": "routed5_all3", "p2": "v2", "p3": "v2", "topics": 1}


def final_answer(question: str, provider=None, config: dict | None = None) -> dict:
    """The final pipeline (config, default FINAL): P1 -> search -> P2 -> quote check, then helpdesk/handoff.py: a P3
    handoff draft for not_found and handoff, fixed template text for refuse and clarify.
    config["topics"] == 1: only the first topic is handled; the multi-topic note lists the others.
    config["topics"] == 2: with two or more topics, topics 1 and 2 are each handled on their own (P2 and P3 get the
    topic's own text) and out["topic_results"] lists both; the top-level fields stay topic 1's; a note lists any
    topic after the second. A one-topic message is handled exactly as with topics == 1, plus topic_results."""
    from helpdesk import handoff  # local import: handoff.py does not import this module

    cfg = config or FINAL
    provider = provider or default_provider()
    n = cfg.get("topics", 1)
    out = answer(question, cfg["p2"], provider, router=cfg["router"], search=cfg["search"], own_topic_text=n >= 2)
    out = handoff.finish(out, provider, answered=n)
    if n < 2:
        return out
    topics = (out.get("router") or {}).get("topics") or []
    results = [{"topic": topics[0] if topics else None, "question": out.get("p2_question") or question,
                "llm_calls": out["llm_calls"],
                **{k: out.get(k) for k in (*TOPIC_FIELDS, "programme_files", "topic_text_query", "office", "office_name", "reply_text",
                                           "p3")}}]
    for t in topics[1:n]:
        q = (t.get("text") or "").strip() or question
        r = handoff.finish_topic(answer_topic(t, q, cfg["p2"], provider, cfg["search"]), provider)
        out["llm_calls"] += r["llm_calls"]
        results.append(r)
    out["topic_results"] = results
    return out


def decide(p2: dict, verified: bool, why: str, rule: str | None = None) -> tuple[str, str]:
    """Step f: (action, reason) from P2's parsed reply and the quote check."""
    if not p2["found"]:
        return "not_found", "P2 found=false" + (f" (invalid format: {p2['format_error']})"
                                                if p2.get("format_valid") is False else "")
    if not verified:
        return "not_found", f"P2 said found but quote check failed: {why}"
    return "answer", "P2 found, quote verified" + (" (near match, not word for word)" if rule == "near" else "")
