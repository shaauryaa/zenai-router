"""Check test-data/questions.csv against the knowledge base. Prints every failure; exit status 1 if any.

Run (from code/): python -m helpdesk.check_questions [path/to/questions.csv]

For every topic (fields with several topics are ;-separated, in the same order in every column) with a key_fact:
the key_fact must appear word for word (case-sensitive; runs of whitespace such as OCR line breaks count as one
space) in expected_doc on expected_page, or anywhere in the document when expected_page is blank (original .md files
have no pages). Also checks ids, allowed values and that every `answer` topic names a document and a key fact.
"""
from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

from helpdesk.kb_search import read_document, split_pages
from zenai.paths import KB, TEST_DATA

QUESTIONS = TEST_DATA / "questions.csv"
COLUMNS = ["id", "question", "type", "language", "expected_office", "expected_action", "expected_doc",
           "expected_page", "key_fact", "notes"]
TYPES = {"Normal", "Edge", "Invalid"}
LANGUAGES = {"en", "hinglish"}
ACTIONS = {"answer", "not_found", "handoff", "refuse", "clarify"}
OFFICES = {"IT", "FINANCE", "ACADEMICS", "HOSTEL", "CAMPUS_SERVICES", "EMPLOYEES", "STUDENT_SUPPORT", "HELPDESK"}


def _ws(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def page_text(doc: str, page: str) -> str | None:
    path = KB / doc
    if not path.is_file():
        return None
    _, body = read_document(path)
    if not page:
        return body
    return next((t for p, t in split_pages(body) if str(p) == page), None)


def check(path: Path = QUESTIONS) -> list[str]:
    with open(path, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames != COLUMNS:
            return [f"columns are {reader.fieldnames}, expected {COLUMNS}"]
        rows = list(reader)
    errors = []
    for n, row in enumerate(rows, 1):
        rid = row["id"]
        if rid != f"Q{n:02d}":
            errors.append(f"row {n}: id {rid!r}, expected Q{n:02d}")
        if row["type"] not in TYPES or row["language"] not in LANGUAGES:
            errors.append(f"{rid}: type {row['type']!r} or language {row['language']!r} not allowed")
        actions = row["expected_action"].split(";")
        n_topics = len(actions)
        cols = {c: row[c].split(";") if row[c] else [""] * n_topics
                for c in ("expected_office", "expected_doc", "expected_page", "key_fact")}
        for c, values in cols.items():
            if len(values) != n_topics:
                errors.append(f"{rid}: {c} has {len(values)} part(s) for {n_topics} topic(s)")
        if errors and errors[-1].startswith(f"{rid}: ") and "part(s)" in errors[-1]:
            continue
        for t, action in enumerate(actions):
            office, doc, page, fact = (cols[c][t] for c in ("expected_office", "expected_doc", "expected_page",
                                                            "key_fact"))
            label = f"{rid}" + (f" topic {t + 1}" if n_topics > 1 else "")
            if action not in ACTIONS:
                errors.append(f"{label}: expected_action {action!r} not allowed")
            if office and office not in OFFICES:
                errors.append(f"{label}: expected_office {office!r} is not an office")
            if action == "answer" and not (doc and fact):
                errors.append(f"{label}: an answer needs expected_doc and key_fact")
            if not fact:
                continue
            text = page_text(doc, page)
            if text is None:
                errors.append(f"{label}: {doc} page {page or '(whole doc)'} not found")
            elif _ws(fact) not in _ws(text):
                errors.append(f"{label}: key_fact not found word for word in {doc} page {page or '(whole doc)'}: "
                              f"{fact!r}")
    return errors


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = argv if argv is not None else sys.argv[1:]
    path = Path(args[0]) if args else QUESTIONS
    errors = check(path)
    for e in errors:
        print("FAIL", e)
    print(f"{path.name}: {'all checks passed' if not errors else f'{len(errors)} failure(s)'}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
