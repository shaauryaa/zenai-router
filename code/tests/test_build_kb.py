"""tools.build_kb / tools.kb_index: the KB build table matches kb/, and cleaning/redaction behave as documented.
All personal data below is invented (example.test addresses, 90000 numbers, made-up enrolment numbers)."""
import re
from pathlib import Path

import yaml

from retrieval.index_md import read_index
from tools import build_kb
from tools.build_kb import DOCS, clean, redact
from tools.kb_index import render_index
from zenai.paths import KB

NOT_BUILT = {"FINANCE/bennett-fee-structure.md"}  # fetched from the web page earlier, not from the team's zip


def test_build_table_matches_the_kb_folder():
    built = {f"{d.office}/{d.slug}.md" for d in DOCS}
    on_disk = {f"{p.parent.name}/{p.name}" for p in KB.glob("*/*.md") if p.name != "INDEX.md"}
    assert len(built) == len(DOCS) and built == on_disk - NOT_BUILT


def test_index_provenance_matches_the_build_table():
    for d in DOCS:
        entry = next(e for e in read_index(KB / d.office / "INDEX.md") if e["file"] == f"{d.slug}.md")
        assert entry["public_or_permission"] == d.provenance, d.slug
        assert str(entry["date"]) == d.date and entry["source_url"] == d.source_url
    assert {d.slug for d in DOCS if d.provenance == "unverified"} == {
        "late-fee-payment-rules", "room-partner-user-manual", "anti-ragging-and-sexual-harassment-contacts"}


def test_tools_take_paths_as_arguments_not_machine_paths():
    for name in ("build_kb.py", "kb_index.py"):
        src = (Path(build_kb.__file__).parent / name).read_text(encoding="utf-8")
        assert not re.search(r"(?<![A-Za-z])[A-Za-z]:[\\/]|/Users/|/home/|Downloads|scratchpad", src), name


def test_clean_drops_only_junk():
    header = "UNIVERSITY BANNER LINE"
    rules = ["Students must sign in.", "Carry the ID card.", "Pay fees on time.", "Return library books."]
    pages = [f"{header}\n{rule}\n.....\n{i}" for i, rule in enumerate(rules, 1)]  # the same banner on every page
    out, removed = clean(pages)
    assert out == rules  # only the banner, the symbol line and the page number are gone
    assert sum(removed.values()) == 12 and removed["page number"] == 4  # banner and '.....' repeat on every page
    assert clean(["Name ________ Date\n# not a heading"])[0] == ["Name   Date\n\\# not a heading"]


def test_redact_students_and_personal_contacts_but_keep_roles_and_landlines():
    text = ("(i) | Ms Test Person, Enrol No E99ABC123\n"
            "Mr Staff Member, 0120-0000000, 9000012345, staff.member@example.test\n"
            "Write to registrar@example.test\n"
            "or call at 9000054321")
    out, n = redact(text, "some-doc")
    assert "Test Person" not in out and "E99ABC123" not in out and "(i) | [student details removed]" in out
    assert "9000012345" not in out and "staff.member@" not in out and "0120-0000000" in out
    assert "registrar@example.test" in out and "or call at 9000054321" in out
    assert n == {"student (enrolment no.)": 1, "personal email": 1, "mobile number": 1}


def test_render_index_replaces_built_entries_and_keeps_the_rest():
    index = ("---\ndocuments:\n- file: z-kept.md\n  title: Kept\n- file: a-old.md\n  title: Old\n---\n\n# prose\n")
    out = render_index(index, [{"file": "a-old.md", "title": "New"}])
    meta = yaml.safe_load(out.split("---\n")[1])
    assert [d["file"] for d in meta["documents"]] == ["a-old.md", "z-kept.md"]
    assert meta["documents"][0]["title"] == "New" and out.endswith("\n# prose\n")
