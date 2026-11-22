"""Helpdesk knowledge base (code/kb/) and its BM25 search (helpdesk.kb_search)."""
import re

import pytest

from helpdesk.kb_search import KBIndex, kb_files, read_document, split_pages, split_text, tokenize
from zenai.paths import KB

REQUIRED = ("title", "office", "source_url", "date", "text_source", "original_file")
TEXT_SOURCES = {"ocr", "pdf text", "original md", "html"}
# Left out on purpose (team decision): PhD ordinances, finance/guidelines.pdf, punctualiti.pdf, the fee payment
# guidelines .docx, the admission withdrawal form, warden contacts, the HR manual, and the processed-data/ folder.
EXCLUDED = {"ORDINANCES-RULES-AND-REGULATIONS-FOR-PH.D.-PROGRAMS-28-May-24.pdf", "guidelines.pdf", "punctualiti.pdf",
            "Guidelines for Fee Payment and Registration AY 2026-27 Odd Semester.docx",
            "Admission-withdrawal-form-updated-1_.pdf", "hostel_warden_contacts.md", "BU_HR_Manual_.pdf",
            "department_mapping.csv", "duplicates.csv", "manifest.csv", "manifest.json", "preprocess_report.md",
            "retrieval_checks.json", "search.sqlite3"}
DOCS = [(p, *read_document(p)) for p in kb_files()]


@pytest.fixture(scope="module")
def index(tmp_path_factory):
    return KBIndex.load(cache_dir=tmp_path_factory.mktemp("kb_search"))


def test_every_kb_file_has_the_required_header_fields():
    assert len(DOCS) >= 25
    for path, meta, body in DOCS:
        label = f"{path.parent.name}/{path.name}"
        for field in REQUIRED:
            assert str(meta.get(field) or "").strip(), f"{label}: missing {field}"
        assert meta["office"] == path.parent.name, label
        assert meta["text_source"] in TEXT_SOURCES, label
        if meta["text_source"] in ("ocr", "pdf text"):
            assert split_pages(body) and all(p is not None for p, _ in split_pages(body)), f"{label}: no page headings"


def test_no_excluded_file_is_present_and_the_handbook_is_only_in_hostel():
    originals = [str(meta.get("original_file")) for _, meta, _ in DOCS]
    assert not EXCLUDED & set(originals)
    names = " ".join(p.stem.lower() for p, _, _ in DOCS)
    for word in ("phd", "ph-d", "hr-manual", "punctualiti", "warden", "withdrawal", "guidelines"):
        assert word not in names, word
    handbooks = [p for p, meta, _ in DOCS if meta.get("original_file") == "studentHandbookBennett.pdf"]
    assert [p.parent.name for p in handbooks] == ["HOSTEL"]
    # only Markdown is committed: no PDF or other original file in kb/
    assert all(p.suffix == ".md" for p in KB.rglob("*") if p.is_file() and not p.name.startswith("."))


def test_no_student_details_or_personal_contacts_in_the_kb():
    roles = {"registrar", "registerar", "icc", "dsa", "finance", "ithelpdesk", "thelpdesk", "helpdesk", "info",
             "registry.comm", "ops-helpdesk", "netid"}
    for path, _, body in DOCS:
        label = f"{path.parent.name}/{path.name}"
        assert not re.search(r"\b[A-Z]{1,2}\d{2}[A-Z]{2,6}\d{2,4}\b", body), f"{label}: enrolment number"
        for email in re.findall(r"\b([\w.+-]+)@[\w-]+(?:\.[\w-]+)+", body):
            assert email.lower() in roles, f"{label}: personal email"
        for line in body.splitlines():
            if not line.lower().startswith("or call at"):  # the handbook's institutional number
                assert not re.search(r"(?<!\d)[6-9]\d{4}[\s-]?\d{5}(?!\d)|(?<!\d)[6-9]\d{3}[\s-]\d{6}(?!\d)", line), \
                    f"{label}: mobile number"


def test_chunks_are_small_and_carry_their_metadata(index):
    assert index.chunks
    for c in index.chunks:
        assert c.title and c.office and c.source_url and c.date and c.text.strip()
        assert len(c.text.split()) <= 350, c.id
    assert len({c.id for c in index.chunks}) == len(index.chunks)


def test_split_text_keeps_short_pages_whole_and_splits_long_ones():
    assert split_text("one two three") == ["one two three"]
    long_para = " ".join(f"w{i}" for i in range(800))
    parts = split_text(f"short para\n\n{long_para}", max_words=350)
    assert all(len(p.split()) <= 350 for p in parts) and " ".join(parts).split() == ["short", "para"] + long_para.split()


def test_cache_round_trip(tmp_path):
    first = KBIndex.load(cache_dir=tmp_path)
    assert (tmp_path / "index.json").exists()
    second = KBIndex.load(cache_dir=tmp_path)
    assert [c.id for c in second.chunks] == [c.id for c in first.chunks]
    assert second.search("refund", k=3) == first.search("refund", k=3)


def test_refund_in_finance_finds_the_fee_refund_policy(index):
    hits = index.search("refund", k=3, office="FINANCE")
    assert all(h.chunk.office == "FINANCE" for h in hits)
    assert "FINANCE/fee-refund-policy-2026-27.md" in [h.chunk.file for h in hits]


def test_password_in_it_finds_the_it_policy(index):
    hits = index.search("password", k=3, office="IT")
    assert hits and "IT/it-policy.md" in [h.chunk.file for h in hits]


def test_stop_words_are_dropped_from_english_and_hinglish():
    assert tokenize("Kya hostel ka in-time hai?") == ["hostel", "time"]
    assert tokenize("How do I reset my password pls") == ["reset", "password"]


def test_report_ragging_finds_the_anti_ragging_rules(index):
    assert "STUDENT_SUPPORT/anti-ragging.md" in [h.chunk.file for h in index.search("how do I report ragging", k=3)]


def test_search_for_route_mixes_the_domain_folder_with_all_folders(index):
    hits = index.search_for_route("refund", "FEES", k=5)
    assert len(hits) == 5 and [h.score for h in hits] == sorted((h.score for h in hits), reverse=True)
    assert sum(h.chunk.office == "FINANCE" for h in hits) >= 3
    # a ragging question routed to HOSTEL by v1 still reaches STUDENT_SUPPORT through the all-folders slots
    assert "STUDENT_SUPPORT" in {h.chunk.office for h in index.search_for_route("report ragging", "HOSTEL")}
    assert index.search_for_route("refund", None) == index.search("refund", k=5)
    assert index.search_for_route("refund", "OUT_OF_SCOPE") == index.search("refund", k=5)
    with pytest.raises(ValueError):
        index.search_for_route("refund", "FINANCE")  # a kb folder, not a v1 domain


def test_empty_or_unmatched_query_returns_nothing(index):
    assert index.search("") == [] and index.search("zzzqqqxxv") == []
