"""Safety card (Milestone 2 sprint S4; docs/POLICY.md section 5). No LLM call.

A topic is `safety` when
  a. the router gives domain STUDENT_SUPPORT with request_type needs_human, or
  b. its text REPORTS an incident: someone being ragged, harassed, threatened, assaulted, attacked, abused, bullied
     or stalked (an incident verb aimed at a person: "seniors are ragging me", "I was harassed", "getting threats"),
     or self-harm ("hurt myself", "suicide").
A general question about a policy ("Who can I report ragging to?", "How do I file a harassment complaint?") names
the incident but reports none: it stays an ordinary info question. Trigger b is English only: a Hinglish report is
caught by trigger a (the router) or not at all.

The student first sees a fixed card: CARD_INTRO, then lines copied word for word from CONTACTS_FILE (card_lines:
from each CARD_SECTIONS section, its lines before the first person, and every person block that has a contact line
that is not redacted, keeping the block's heading, designation and unredacted contact lines; a lead-in line ending
in "reach out to:**" only if such a person follows), the document's title and path as the source, and
CARD_FALLBACK. If no contact line is found, the card is only CARD_FALLBACK: no address or number is ever written from
memory. Then the P3 draft to the Student Support office (helpdesk/handoff.py).
"""
from __future__ import annotations

import re

from helpdesk.kb_search import read_document
from zenai.paths import KB

CONTACTS_FILE = KB / "STUDENT_SUPPORT" / "anti-ragging-and-sexual-harassment-contacts.md"
OFFICE = "STUDENT_SUPPORT"
CARD_SECTIONS = ("Anti Ragging Committee", "Policy Against Sexual Harassment")  # "## " headings in CONTACTS_FILE
CARD_INTRO = ("This sounds serious. You can contact these people at Bennett University directly. "
              "The contacts below are copied from the official list:")
CARD_FALLBACK = "You can also contact the Student Support office directly."

_VERBS = (r"(?:rag(?:ged|ging)|harass(?:ed|ing)?|threaten(?:ed|ing)?|assault(?:ed|ing)?|attack(?:ed|ing)?|"
          r"abus(?:ed|ing)|bull(?:ied|ying)|stalk(?:ed|ing)|beat(?:ing)?|beaten|hitting)")
_PARTICIPLES = r"(?:ragged|harassed|threatened|assaulted|attacked|abused|bullied|stalked|beaten|molested)"
_PERSON = r"(?:me|us|him|her|them|my\s+\w+|our\s+\w+|a\s+(?:friend|junior|classmate|roommate)\w*)"
INCIDENT = re.compile(
    rf"\b{_VERBS}\s+{_PERSON}\b"                                                # "they are ragging me"
    rf"|\b(?:i|we|he|she|they|my\s+\w+)\s+(?:am|are|is|was|were|got|get|have\s+been|has\s+been|keeps?\s+getting)"
    rf"\s+(?:being\s+)?{_PARTICIPLES}\b"                                        # "I was harassed"
    rf"|\bi'?m\s+(?:being\s+)?{_PARTICIPLES}\b"                                  # "I'm being ragged"
    r"|\b(?:got|getting|receiv(?:ed|ing))\s+(?:a\s+)?(?:death\s+)?threats?\b"   # "getting threats"
    r"|\bself[-\s]?harm\w*|\b(?:hurt|hurting|kill|killing|harm|harming)\s+myself\b|\bsuicid\w*"
    r"|\bwant(?:s|ing)?\s+to\s+die\b|\bend\s+my\s+life\b",
    re.I)


def trigger(topic: dict, text: str) -> str:
    """The reason this topic is safety, or "" when it is not."""
    if topic.get("domain") == OFFICE and topic.get("request_type") == "needs_human":
        return "safety: router STUDENT_SUPPORT / needs_human"
    m = INCIDENT.search(" ".join((text or "").replace("’", "'").split()))
    return f"safety: incident reported ({m.group(0)!r})" if m else ""


def is_contact(line: str) -> bool:
    return line.startswith(("- **Email:**", "- **Phone:**")) and "removed]" not in line


def card_lines(body: str) -> list[str]:
    """The card's lines, each a stripped line of `body`, unchanged (see the module docstring)."""
    out: list[str] = []
    lead: list[str] = []
    block: list[str] = []
    section = None

    def flush() -> None:
        if block and any(is_contact(x) for x in block):
            out.extend(lead)
            lead.clear()
            out.extend(x for x in block if x.startswith(("### ", "- **Designation:**")) or is_contact(x))
        block.clear()

    for raw in body.splitlines():
        line = raw.strip()
        if line.startswith(("# ", "## ")) or line == "---":
            flush()
            lead.clear()
            section = line[3:] if line.startswith("## ") and line[3:] in CARD_SECTIONS else None
            if section:
                out.append(line)
        elif section is None or not line:
            continue
        elif line.startswith("### "):
            flush()
            block.append(line)
        elif block:
            block.append(line)
        elif line.endswith("reach out to:**"):
            lead.append(line)
        else:
            out.append(line)
    flush()
    return out


def card() -> dict:
    """{"intro", "lines" (word for word from the source; [] when no contact is found), "fallback", "source_title",
    "source_file", "verified"}."""
    meta, body = read_document(CONTACTS_FILE)
    lines = card_lines(body)
    present = {line.strip() for line in body.splitlines()}
    verified = any("@" in x for x in lines) and all(x in present for x in lines)
    return {"intro": CARD_INTRO, "lines": lines if verified else [], "fallback": CARD_FALLBACK,
            "source_title": str(meta.get("title") or ""),
            "source_file": CONTACTS_FILE.relative_to(KB.parent).as_posix(), "verified": verified}


def card_markdown(c: dict) -> str:
    """The card as Markdown: intro, the copied lines as a quote (heading marks dropped), the source, the fallback."""
    if not c["lines"]:
        return c["fallback"]
    quoted = "  \n".join("> " + re.sub(r"^#+\s*", "", line) for line in c["lines"])
    return (f"{c['intro']}\n\n{quoted}\n\nSource: *{c['source_title']}* (`{c['source_file']}`)\n\n"
            f"{c['fallback']}")
