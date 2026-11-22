"""Retrieval layer: INDEX.md validation, extraction, chunking, ids, local and Azure backends, hybrid search, ingestion.
Everything runs on a small fixture KB in a temp folder with FakeProvider embeddings and a fake Azure client: no network."""
import json
import re
from types import SimpleNamespace

import pytest

from retrieval import index_stub
from retrieval.azure_backend import AzureBackend, estimate_bytes
from retrieval.backend import BackendError, department_filter
from retrieval.chunking import chunk_id, chunk_sections, id_prefix, split_text
from retrieval.index_md import build_document, front_matter_yaml, read_index
from retrieval.ingest import ingest, print_report
from retrieval.inspect import format_results
from retrieval.kb import scan_kb
from retrieval.loaders import Section, extract, html_to_markdown, split_markdown
from retrieval.local_backend import LocalBackend, tokenize
from retrieval.model import META_PREFIX, Chunk
from retrieval.search import expand_query, fuse, search, validate_departments
from zenai.config import load_config
from zenai.providers import FakeProvider, ProviderError

DIM = 64
CFG = {
    "providers": {"azure": {"embed_dim": DIM, "embed_model": "embed"}},
    "kb": {"retriever": "local", "chunk": {"target_tokens": 60, "overlap_tokens": 10, "min_chars": 15},
           "search": {"default_k": 8, "candidates": 50, "rrf_k": 60, "aliases": {}},
           "local_dir": ".cache/kb_local",
           "azure_search": {"endpoint_env": "X", "key_env": "Y", "index": "zenai-kb",
                            "vector_field": "content_vector", "storage_limit_mb": 45, "upload_batch": 2}},
}


# ---------------------------------------------------------------- fixture KB

def make_pdf(pages: list[str]) -> bytes:
    """A minimal valid PDF with one line of Helvetica text per line of each page ('' = a page with no text)."""
    n = len(pages)
    font_id = 3 + 2 * n
    objs = [b"<< /Type /Catalog /Pages 2 0 R >>",
            f"<< /Type /Pages /Kids [{' '.join(f'{3 + 2 * i} 0 R' for i in range(n))}] /Count {n} >>".encode()]
    for i, text in enumerate(pages):
        body = " ".join(f"({line}) Tj T*" for line in text.split("\n") if line)
        stream = f"BT /F1 12 Tf 72 720 Td 14 TL {body} ET"
        objs.append((f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents {4 + 2 * i} 0 R "
                     f"/Resources << /Font << /F1 {font_id} 0 R >> >> >>").encode())
        objs.append(f"<< /Length {len(stream)} >>\nstream\n{stream}\nendstream".encode())
    objs.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    out, offsets = b"%PDF-1.4\n", []
    for i, o in enumerate(objs, 1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + o + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
    out += "".join(f"{o:010d} 00000 n \n" for o in offsets).encode()
    return out + f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()


HOSTEL_RULES = """# Hostel rules

## Curfew and in-time
Hostel curfew for residents is ten pm. Students must be back in the hostel before in-time every night.

## Guests
Guests are allowed in the visitor lounge only, until eight pm, with a warden's permission.
"""
LAUNDRY = "The laundry counter accepts clothes from hostel residents between nine and five on working days.\n" * 2
FEES_MD = """# Fee structure

## Tuition
| Year | Tuition fee |
| --- | --- |
| Year 1 | 380000 |
| Year 2 | 390000 |

## Refunds
A tuition fee refund is processed within thirty days of a written request to the finance office.
"""
WIFI_HTML = """<html><head><title>x</title><script>var a = 1;</script></head><body>
<nav>Home | About | Contact | Menu entries that are not content</nav>
<main><h1>Campus wifi</h1><p>Connect to the campus wifi network with your university email address and password.</p>
<h2>Problems</h2><p>If the wifi login fails, reset your password on the IT portal before contacting the helpdesk.</p></main>
<footer>Copyright footer text that is not content</footer></body></html>"""
REFUND_PDF = make_pdf(["Scholarship applications close in July every year for all programmes",
                       "Refund requests need the original receipt and a bank account statement"])
LIBRARY_MD = "# Library hours\n\nThe library reading hall is open until midnight on weekdays for all students and staff.\n"

INDEX = {
    "HOSTEL": [
        {"file": "rules.md", "title": "Hostel rules", "source_url": "https://example.test/hostel",
         "last_updated": "2026-01-10", "public_or_permission": "public", "collector": "tester"},
        {"file": "laundry.txt", "title": "Laundry", "source_url": "https://example.test/laundry",
         "last_updated": "2026-02-01", "public_or_permission": "public", "collector": "tester"},
        {"file": "gone.md", "title": "Listed but missing", "source_url": "https://example.test/gone",
         "last_updated": "2026-02-01", "public_or_permission": "public", "collector": "tester"}],
    "FINANCE": [
        {"file": "fees.md", "title": "Fee structure", "source_url": "https://example.test/fees",
         "last_updated": "2026-03-01", "date_kind": "fetched_on", "public_or_permission": "public",
         "collector": "tester"},
        {"file": "refund.pdf", "title": "Refund policy", "source_url": "https://example.test/refund.pdf",
         "last_updated": "2026-03-02", "public_or_permission": "public", "collector": "tester"},
        {"file": "scan.pdf", "title": "Scanned notice", "source_url": "https://example.test/scan.pdf",
         "last_updated": "2026-03-02", "public_or_permission": "public", "collector": "tester"}],
    "IT": [{"file": "wifi.html", "title": "Campus wifi", "source_url": "https://example.test/wifi",
            "last_updated": "2026-04-01", "public_or_permission": "public", "collector": "tester"}],
    "CAMPUS_SERVICES": [{"file": "library.md", "title": "Library hours",
                         "source_url": "compiled by the team from the library notice board, 2026-05-01",
                         "last_updated": "2026-05-01", "public_or_permission": "team-written", "collector": "tester"}],
}


@pytest.fixture
def kb(tmp_path):
    root = tmp_path / "kb"
    files = {"HOSTEL/rules.md": HOSTEL_RULES, "HOSTEL/laundry.txt": LAUNDRY, "HOSTEL/extra.md": "Not listed anywhere.\n",
             "FINANCE/fees.md": FEES_MD, "IT/wifi.html": WIFI_HTML, "CAMPUS_SERVICES/library.md": LIBRARY_MD,
             "MISC/stray.md": "Unknown folder.\n", "HELPDESK/oops.md": "HELPDESK holds no documents.\n"}
    for rel, text in files.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(text, encoding="utf-8")
    (root / "FINANCE" / "refund.pdf").write_bytes(REFUND_PDF)
    (root / "FINANCE" / "scan.pdf").write_bytes(make_pdf(["", ""]))
    for folder in ("IT", "ACADEMICS", "COURSE_SPECIFIC", "EMPLOYEES", "STUDENT_SUPPORT", "HOSTEL", "FINANCE",
                   "CAMPUS_SERVICES"):
        (root / folder).mkdir(parents=True, exist_ok=True)
        (root / folder / "INDEX.md").write_text(front_matter_yaml(INDEX.get(folder, [])) + "\n# notes\n",
                                                encoding="utf-8")
    return root


@pytest.fixture
def scan(kb):
    return scan_kb(CFG, kb_root=kb)


@pytest.fixture
def local(tmp_path, scan):
    backend = LocalBackend(tmp_path / "local", "embed", DIM)
    backend.upsert(scan.chunks, FakeProvider(dim=DIM).embed([c.search_text() for c in scan.chunks]))
    return backend


def run_search(query, backend, departments=None, k=8, embedder=None):
    return search(query, departments, k, backend=backend, embedder=embedder or FakeProvider(dim=DIM), cfg=CFG)


# ---------------------------------------------------------------- INDEX.md validation

def doc(entry, meta=None):
    return build_document(entry, meta, "kb/X/f.md")


GOOD = {"file": "f.md", "title": "T", "source_url": "https://e.test", "last_updated": "2026-01-01",
        "public_or_permission": "public", "collector": "me"}


def test_valid_entry_builds_a_document():
    d, errors, warnings = doc(GOOD)
    assert errors == [] and warnings == [] and d.title == "T" and d.date_kind == "updated"


@pytest.mark.parametrize("missing, text", [("title", "missing title"), ("source_url", "missing source_url"),
                                           ("last_updated", "missing last_updated"),
                                           ("public_or_permission", "public_or_permission")])
def test_missing_required_field_is_an_error(missing, text):
    d, errors, _ = doc({k: v for k, v in GOOD.items() if k != missing})
    assert d is None and any(text in e for e in errors)


def test_office_provided_may_omit_source_url_and_last_updated_but_not_title():
    entry = {"file": "f.pdf", "title": "T", "public_or_permission": "office-provided", "collector": "me"}
    d, errors, _ = doc(entry)
    assert d is not None and d.source_url == "" and d.last_updated is None
    d, errors, _ = doc({k: v for k, v in entry.items() if k != "title"})
    assert d is None and "missing title" in errors[0]


def test_team_written_must_say_what_it_was_compiled_from():
    d, errors, _ = doc({**GOOD, "public_or_permission": "team-written", "source_url": ""})
    assert d is None and "compiled from" in " ".join(errors)


def test_bad_values_are_errors():
    assert doc({**GOOD, "public_or_permission": "secret"})[0] is None
    assert doc({**GOOD, "last_updated": "10/06/2026"})[0] is None
    assert doc({**GOOD, "date_kind": "whenever"})[0] is None


def test_file_front_matter_fills_only_blank_fields():
    entry = {**GOOD, "title": "", "source_url": "https://index.test"}
    meta = {"title": "From the file", "source_url": "https://file.test", "collector": "someone else"}
    d, errors, _ = doc(entry, meta)
    assert d.title == "From the file"  # blank in INDEX.md: the file fills it
    assert d.source_url == "https://index.test"  # given in INDEX.md: INDEX.md wins
    assert d.collector == "me"


def test_unknown_fields_and_missing_collector_are_warnings():
    _, _, warnings = doc({**GOOD, "colour": "red", "collector": ""}, {"mystery": 1})
    text = " ".join(warnings)
    assert "colour" in text and "mystery" in text and "no collector" in text


def test_index_front_matter_errors(tmp_path):
    (tmp_path / "X").mkdir()
    p = tmp_path / "X" / "INDEX.md"
    with pytest.raises(ValueError, match="does not exist"):
        read_index(p)
    p.write_text("# no front matter\n", encoding="utf-8")
    with pytest.raises(ValueError, match="documents"):
        read_index(p)
    p.write_text("---\ndocuments: [1, 2]\n---\n", encoding="utf-8")
    with pytest.raises(ValueError, match="list of entries"):
        read_index(p)
    p.write_text("---\ndocuments:\n  - file: a.md\n    title: [unclosed\n---\n", encoding="utf-8")
    with pytest.raises(ValueError, match="YAML"):
        read_index(p)


# ---------------------------------------------------------------- scanning the KB folder

def test_scan_ingests_listed_files_and_reports_everything_else(scan):
    assert scan.errors == []
    assert {(d.folder, d.file) for d in scan.documents} == {
        ("HOSTEL", "rules.md"), ("HOSTEL", "laundry.txt"), ("FINANCE", "fees.md"), ("FINANCE", "refund.pdf"),
        ("IT", "wifi.html"), ("CAMPUS_SERVICES", "library.md")}
    text = "\n".join(scan.warnings)
    assert "kb/HOSTEL/gone.md: listed in INDEX.md but the file does not exist" in text  # missing listed file
    assert "kb/HOSTEL/extra.md: present in the folder but not listed" in text  # unlisted file
    assert "kb/MISC is not a knowledge folder" in text  # unknown folder
    assert "HELPDESK holds no documents" in text and "kb/HELPDESK" in text
    assert "kb/FINANCE/scan.pdf" in text and "OCR" in text  # scanned PDF
    skipped = "\n".join(scan.skipped)
    for expected in ("gone.md: missing", "extra.md: unlisted", "MISC/stray.md: unknown folder",
                     "HELPDESK/oops.md: unknown folder", "scan.pdf: scanned PDF"):
        assert expected in skipped


def test_nothing_from_skipped_files_is_chunked(scan):
    files = {c.file for c in scan.chunks}
    assert files == {"rules.md", "laundry.txt", "fees.md", "refund.pdf", "wifi.html", "library.md"}
    assert all(c.content.strip() for c in scan.chunks)


def test_validation_errors_stop_everything(kb):
    index = kb / "HOSTEL" / "INDEX.md"
    entries = [dict(e) for e in INDEX["HOSTEL"]]
    del entries[0]["title"]
    index.write_text(front_matter_yaml(entries), encoding="utf-8")
    scan = scan_kb(CFG, kb_root=kb)
    assert not scan.ok and any("missing title" in e for e in scan.errors)
    report = ingest(CFG, [], scan=scan)
    assert report.backends == [] and not report.ok  # nothing embedded or written


def test_folder_with_files_but_no_index_is_an_error(kb):
    (kb / "IT" / "INDEX.md").unlink()
    assert any("kb/IT has 1 file(s) but no INDEX.md" in e for e in scan_kb(CFG, kb_root=kb).errors)


def test_path_outside_the_folder_and_duplicate_entries_are_errors(kb):
    entries = INDEX["IT"] + [dict(INDEX["IT"][0]), {**INDEX["IT"][0], "file": "../HOSTEL/rules.md"}]
    (kb / "IT" / "INDEX.md").write_text(front_matter_yaml(entries), encoding="utf-8")
    errors = " ".join(scan_kb(CFG, kb_root=kb).errors)
    assert "listed more than once" in errors and "not a path inside the folder" in errors


def test_metadata_in_md_front_matter_fills_blank_index_fields(kb):
    (kb / "IT" / "guide.md").write_text(
        "---\ntitle: Guide from front matter\nsource_url: https://example.test/guide\nlast_updated: 2026-06-01\n"
        "public_or_permission: public\n---\n# Guide\nStudents reset the IT portal password with a one time code.\n",
        encoding="utf-8")
    entries = INDEX["IT"] + [{"file": "guide.md"}]
    (kb / "IT" / "INDEX.md").write_text(front_matter_yaml(entries), encoding="utf-8")
    scan = scan_kb(CFG, kb_root=kb)
    guide = [c for c in scan.chunks if c.file == "guide.md"]
    assert guide and guide[0].title == "Guide from front matter" and guide[0].last_updated == "2026-06-01"
    assert "title:" not in guide[0].content  # front matter is not indexed as text


# ---------------------------------------------------------------- extraction

def test_scanned_pdf_is_detected_and_never_yields_text(kb):
    out = extract(kb / "FINANCE" / "scan.pdf")
    assert out.scanned and out.sections == [] and "OCR" in out.warnings[0]


def test_text_pdf_keeps_page_numbers(kb):
    out = extract(kb / "FINANCE" / "refund.pdf")
    assert not out.scanned and [s.page for s in out.sections] == [1, 2]
    assert "Scholarship" in out.sections[0].text and "Refund" in out.sections[1].text


def test_unreadable_pdf_is_a_loader_error(tmp_path):
    bad = tmp_path / "bad.pdf"
    bad.write_bytes(b"this is not a pdf")
    with pytest.raises(ValueError, match="cannot read PDF"):
        extract(bad)


def test_html_extraction_drops_menus_and_footers_but_keeps_headings(kb):
    sections = extract(kb / "IT" / "wifi.html").sections
    text = "\n".join(s.text for s in sections)
    assert "Menu entries" not in text and "Copyright" not in text and "var a" not in text
    assert [s.heading for s in sections] == [("Campus wifi",), ("Campus wifi", "Problems")]


def test_html_tables_become_markdown_tables():
    md = html_to_markdown("<main><h2>Fees</h2><table><tr><th>Year</th><th>Fee</th></tr>"
                          "<tr><td>1</td><td>100</td></tr></table>" + "<p>text</p>" * 40 + "</main>")
    assert "| Year | Fee |" in md and "| 1 | 100 |" in md


def test_markdown_headings_become_heading_paths():
    sections = split_markdown("intro\n\n# A\ntext a\n## B\ntext b\n```\n# not a heading\n```\n# C\ntext c")
    assert [(s.heading, s.text.split("\n")[0]) for s in sections] == [
        ((), "intro"), (("A",), "text a"), (("A", "B"), "text b"), (("C",), "text c")]


# ---------------------------------------------------------------- chunking

def test_chunk_metadata_is_complete(scan):
    pdf = [c for c in scan.chunks if c.file == "refund.pdf"]
    assert [c.page for c in pdf] == [1, 2]
    c = pdf[1]
    assert (c.department, c.title, c.source_url, c.last_updated, c.provenance) == (
        "FINANCE", "Refund policy", "https://example.test/refund.pdf", "2026-03-02", "public")
    assert c.citation_label() == "Refund policy, p. 2"
    md = [c for c in scan.chunks if c.file == "fees.md"]
    assert md[0].heading_path.startswith("Fee structure > ") and md[0].page is None
    assert all(c.date_kind == "fetched_on" for c in md)  # labelled as the fetch date, not an update date


def test_sections_split_by_heading_first(scan):
    paths = {c.heading_path for c in scan.chunks if c.file == "rules.md"}
    assert paths == {"Hostel rules > Curfew and in-time", "Hostel rules > Guests"}


def test_long_section_splits_to_target_size_with_overlap():
    lines = [f"Line {i}: students must follow hostel instruction number {i} at all times." for i in range(40)]
    chunks = split_text("\n".join(lines), target_tokens=100, overlap_tokens=20)
    assert len(chunks) > 3 and all(len(c) <= 100 * 4 for c in chunks)
    for a, b in zip(chunks, chunks[1:]):
        assert b.split("\n")[0] in a.split("\n")  # the next chunk starts with the end of the previous one
    assert all(line in "\n".join(chunks) for line in lines)


def test_table_header_is_repeated_when_a_table_continues_in_the_next_chunk():
    rows = "\n".join(f"| Year {i} | {i}00000 |" for i in range(60))
    chunks = split_text("| Year | Fee |\n| --- | --- |\n" + rows, target_tokens=80, overlap_tokens=10)
    assert len(chunks) > 2
    assert all(c.startswith("| Year | Fee |\n| --- | --- |") for c in chunks)
    assert all(len(c) <= 80 * 4 for c in chunks)


def test_empty_and_tiny_chunks_are_never_created():
    sections = [Section(""), Section("   \n  "), Section("hi"), Section("This one is long enough to keep.")]
    chunks = chunk_sections(sections, folder="IT", file="a.md", title="T", source_url="u", last_updated="2026-01-01",
                            provenance="public")
    assert [c.content for c in chunks] == ["This one is long enough to keep."]


def test_chunk_ids_are_deterministic_and_stable():
    a = chunk_id("HOSTEL", "rules.md", 3)
    assert a == chunk_id("HOSTEL", "rules.md", 3) and re.fullmatch(r"hostel-[0-9a-f]{10}-0003", a)
    assert a != chunk_id("HOSTEL", "rules.md", 4) and a != chunk_id("FINANCE", "rules.md", 3)
    assert a != chunk_id("HOSTEL", "sub/rules.md", 3)
    assert chunk_id("CAMPUS_SERVICES", "x.md", 0).startswith("campus-services-")
    assert chunk_id("HOSTEL", "rules.md", 0).startswith(id_prefix("HOSTEL", "rules.md"))


def test_scanning_twice_gives_the_same_ids(kb):
    first, second = scan_kb(CFG, kb_root=kb), scan_kb(CFG, kb_root=kb)
    assert [c.id for c in first.chunks] == [c.id for c in second.chunks]
    assert len({c.id for c in first.chunks}) == len(first.chunks)
    assert [c.content for c in first.chunks] == [c.content for c in second.chunks]


def test_the_real_fee_page_chunks_carry_fetched_on_metadata():
    scan = scan_kb(load_config())
    fee = [c for c in scan.chunks if c.file == "bennett-fee-structure.md"]
    assert fee and all(c.department == "FINANCE" and c.date_kind == "fetched_on" for c in fee)
    assert {c.source_url for c in fee} == {"https://www.bennett.edu.in/admission/fee-structure/"}
    assert {c.last_updated for c in fee} == {"2026-10-06"} and {c.provenance for c in fee} == {"public"}
    assert any("B.Tech (Computer Science Engineering)" in c.heading_path for c in fee)


# ---------------------------------------------------------------- team-compiled labelling

def test_team_written_documents_are_labelled_team_compiled(scan):
    lib = next(c for c in scan.chunks if c.file == "library.md")
    assert lib.provenance == "team-written" and lib.team_compiled
    assert lib.citation_label() == "Library hours [team-compiled]"
    cite = lib.citation(1)
    assert cite["team_compiled"] and cite["provenance"] == "team-written" and cite["label"].endswith("[team-compiled]")
    assert cite["office"] == "CAMPUS_SERVICES" and cite["source_url"].startswith("compiled by the team")
    official = next(c for c in scan.chunks if c.file == "rules.md")
    assert not official.team_compiled and "team-compiled" not in official.citation_label()


def test_citation_object_matches_the_api_contract(scan):
    c = next(c for c in scan.chunks if c.file == "refund.pdf" and c.page == 2)
    cite = c.citation(2, snippet_chars=30)
    assert {"n", "title", "source_url", "last_updated", "snippet", "office"} <= set(cite)
    assert cite["n"] == 2 and cite["page"] == 2 and cite["label"] == "Refund policy, p. 2"
    assert len(cite["snippet"]) <= 33


# ---------------------------------------------------------------- local backend and search

def test_tokenizer_handles_abbreviations_and_plurals():
    assert tokenize("B.Tech CSE fees, Ph.D. 1,70,000") == ["btech", "cse", "fee", "phd", "1", "70", "000"]
    assert tokenize("BTech") == tokenize("B.Tech")


def test_hostel_filtered_search_never_returns_other_departments(local):
    for query in ("hostel curfew", "tuition fee refund request", "campus wifi password", "library midnight"):
        results = run_search(query, local, ["HOSTEL"])
        assert results and {r.chunk.department for r in results} == {"HOSTEL"}


def test_filter_to_two_departments(local):
    results = run_search("refund wifi password", local, ["FINANCE", "IT"])
    assert {r.chunk.department for r in results} == {"FINANCE", "IT"}


def test_unfiltered_search_ranks_the_right_department_first(local):
    expected = {"what time is hostel curfew in-time": "HOSTEL", "tuition fee year 2": "FINANCE",
                "wifi login password reset": "IT", "library reading hall open midnight": "CAMPUS_SERVICES",
                "refund original receipt bank statement": "FINANCE"}
    for query, department in expected.items():
        assert run_search(query, local)[0].chunk.department == department, query


def test_scores_are_between_0_and_1_and_sorted(local):
    results = run_search("hostel curfew in-time", local)
    assert all(0 <= r.score <= 1 for r in results)
    assert all(0 <= (r.vector_score or 0) <= 1 and 0 <= (r.keyword_score or 0) <= 1 for r in results)
    assert [r.score for r in results] == sorted((r.score for r in results), reverse=True)
    assert results[0].score > 0.9 and results[0].mode == "hybrid"


def test_k_limits_results_and_unknown_departments_are_refused(local):
    assert len(run_search("hostel", local, k=2)) == 2
    for bad in (["HELPDESK"], ["NOPE"]):
        with pytest.raises(ValueError, match="unknown department"):
            run_search("hostel", local, bad)
    assert run_search("hostel", local, []) == [] and run_search("   ", local) == []
    assert validate_departments(None) is None and validate_departments(["IT", "IT"]) == ["IT"]


def test_search_without_embeddings_falls_back_to_keywords(local):
    class Offline:
        def embed(self, texts):
            raise ProviderError("no network")

    results = run_search("hostel curfew", local, embedder=Offline())
    assert results and results[0].chunk.department == "HOSTEL"
    assert {r.mode for r in results} == {"keyword-only"} and all(r.vector_score is None for r in results)
    assert results[0].score == pytest.approx(1.0)


def test_local_store_persists_and_works_without_any_provider(local, tmp_path):
    reloaded = LocalBackend(tmp_path / "local")  # a new object reading the files: no embedder, no network
    assert reloaded.stats()["documents"] == local.stats()["documents"]
    assert reloaded.keyword("hostel curfew", ["HOSTEL"], 5)
    assert (tmp_path / "local" / "chunks.jsonl").exists() and (tmp_path / "local" / "vectors.npy").exists()
    assert json.loads((tmp_path / "local" / "meta.json").read_text())["embed_model"] == "embed"


def test_alias_expansion_only_touches_the_keyword_query():
    assert expand_query("BTech CSE fees", {"cse": "computer science engineering"}) == \
        "BTech CSE fees computer science engineering"
    assert expand_query("hostel fees", {"cse": "computer science engineering"}) == "hostel fees"
    assert expand_query("x", None) == "x"


def test_fusion_math():
    def chunk(i):
        return Chunk(id=i, department="IT", title="t", source_url="u", content="c")

    kw = [(chunk("a"), 10.0), (chunk("b"), 5.0)]
    vec = [(chunk("b"), 0.9), (chunk("c"), 0.8), (chunk("a"), 0.7)]
    out = {r.chunk.id: r for r in fuse(kw, vec, 10, rrf_k=60)}
    top = 2 / 61
    assert out["b"].score == pytest.approx((1 / 62 + 1 / 61) / top)  # rank 2 keyword + rank 1 vector
    assert out["a"].score == pytest.approx((1 / 61 + 1 / 63) / top)
    assert out["c"].score == pytest.approx((1 / 62) / top) and out["c"].keyword_score is None
    assert out["b"].keyword_score == pytest.approx(0.5) and out["b"].vector_score == 0.9
    assert fuse(kw, None, 1)[0].chunk.id == "a" and fuse(kw, None, 1)[0].score == pytest.approx(1.0)


# ---------------------------------------------------------------- Azure backend (fake service)

class FakeIndexClient:
    """Read-only index management client: any attempt to create or delete an index raises AttributeError."""

    def __init__(self, dims=DIM, key=True, filterable=True, storage=0, docs=None):
        fields = [SimpleNamespace(name=n, key=(n == "id"), filterable=(n == "department" and filterable),
                                  vector_search_dimensions=None) for n in
                  ("id", "content", "department", "title", "source_url")]
        fields.append(SimpleNamespace(name="content_vector", key=False, filterable=False,
                                      vector_search_dimensions=dims))
        if not key:
            fields[0].key = False
        self.index = SimpleNamespace(name="zenai-kb", fields=fields)
        self.storage, self.docs = storage, docs
        self.calls = []

    def get_index(self, name):
        self.calls.append(("get_index", name))
        return self.index

    def get_index_statistics(self, name):
        self.calls.append(("get_index_statistics", name))
        return {"document_count": len(self.docs) if self.docs is not None else 0, "storage_size": self.storage,
                "vector_index_size": 0}


class FakeSearchClient:
    def __init__(self):
        self.docs: dict[str, dict] = {}
        self.upload_batches: list[int] = []
        self.search_calls: list[dict] = []
        self.deleted: list[str] = []

    def get_document_count(self):
        return len(self.docs)

    def merge_or_upload_documents(self, documents):
        self.upload_batches.append(len(documents))
        for d in documents:
            self.docs[d["id"]] = dict(d)
        return [SimpleNamespace(key=d["id"], succeeded=True) for d in documents]

    def delete_documents(self, documents):
        for d in documents:
            self.docs.pop(d["id"], None)
            self.deleted.append(d["id"])

    def search(self, search_text=None, vector_queries=None, filter=None, select=None, top=None, skip=None, **kw):
        self.search_calls.append({"search_text": search_text, "vector_queries": vector_queries, "filter": filter,
                                  "select": select, "top": top, "skip": skip, **kw})
        rows = list(self.docs.values())
        if filter:
            wanted = set(re.search(r"'([^']*)'", filter).group(1).split(","))
            rows = [r for r in rows if r["department"] in wanted]
        if vector_queries:
            q = vector_queries[0]["vector"]
            norm = sum(x * x for x in q) ** 0.5 or 1
            scored = [(r, (1 + sum(a * b for a, b in zip(q, r["content_vector"])) /
                           (norm * (sum(b * b for b in r["content_vector"]) ** 0.5 or 1))) / 2) for r in rows]
        elif search_text and search_text != "*":
            words = set(re.findall(r"\w+", search_text.lower()))
            scored = [(r, float(len(words & set(re.findall(r"\w+", (r["title"] + " " + r["content"]).lower())))))
                      for r in rows]
            scored = [(r, s) for r, s in scored if s > 0]
        else:
            scored = [(r, 1.0) for r in rows]
        scored.sort(key=lambda t: -t[1])
        scored = scored[skip or 0:][: top or 50]
        return [{**{k: r[k] for k in select}, "@search.score": s} for r, s in scored]


def make_azure(index_client=None, client=None):
    client = client or FakeSearchClient()
    index_client = index_client or FakeIndexClient(docs=client.docs)
    backend = AzureBackend(CFG["kb"]["azure_search"], DIM, client=client, index_client=index_client,
                           vector_query=lambda vector, k, field: {"vector": vector, "k": k, "fields": field})
    return backend, client, index_client


def test_azure_document_has_only_the_existing_index_fields(scan):
    chunk = next(c for c in scan.chunks if c.file == "refund.pdf" and c.page == 2)
    d = chunk.to_azure_doc([0.1] * DIM)
    assert set(d) == {"id", "content", "department", "title", "source_url", "content_vector"}
    assert d["department"] == "FINANCE" and d["id"] == chunk.id and d["title"] == "Refund policy"
    assert d["content"].startswith(META_PREFIX) and chunk.content in d["content"]
    first = d["content"].split("\n")[0]
    assert json.loads(first[len(META_PREFIX):]) == {"f": "refund.pdf", "p": 2, "u": "2026-03-02", "v": "public"}


def test_azure_round_trip_preserves_page_heading_date_and_provenance(scan):
    for chunk in scan.chunks:
        back = Chunk.from_azure_doc(chunk.to_azure_doc([0.0] * DIM))
        assert back == chunk
    assert Chunk.from_azure_doc({"id": "x", "content": "plain text", "department": "IT"}).content == "plain text"


def test_azure_upload_batches_and_search_filters(scan):
    backend, client, _ = make_azure()
    vectors = FakeProvider(dim=DIM).embed([c.search_text() for c in scan.chunks])
    assert backend.upsert(scan.chunks, vectors) == len(scan.chunks)
    assert all(n <= 2 for n in client.upload_batches) and len(client.upload_batches) > 1  # upload_batch = 2
    hits = backend.keyword("hostel curfew", ["HOSTEL"], 5)
    assert hits and {c.department for c, _ in hits} == {"HOSTEL"}
    assert client.search_calls[-1]["filter"] == "search.in(department, 'HOSTEL', ',')"
    assert "content_vector" not in client.search_calls[-1]["select"]
    vec = backend.vector(vectors[0], ["FINANCE", "IT"], 5)
    assert {c.department for c, _ in vec} <= {"FINANCE", "IT"}
    assert client.search_calls[-1]["vector_queries"][0]["fields"] == "content_vector"
    assert client.search_calls[-1]["vector_filter_mode"].value == "preFilter"


def test_department_filter_rejects_anything_that_is_not_a_folder_name():
    assert department_filter(None) is None
    assert department_filter(["HOSTEL", "CAMPUS_SERVICES"]) == "search.in(department, 'HOSTEL,CAMPUS_SERVICES', ',')"
    with pytest.raises(ValueError):
        department_filter(["HOSTEL') or (1 eq 1"])


def test_azure_and_local_use_the_same_interface_and_agree(scan, local):
    azure, client, _ = make_azure()
    embedder = FakeProvider(dim=DIM)
    azure.upsert(scan.chunks, embedder.embed([c.search_text() for c in scan.chunks]))
    for query, deps in (("hostel curfew in-time", None), ("tuition fee year 2", ["FINANCE"]), ("wifi password", None)):
        a, b = run_search(query, azure, deps), run_search(query, local, deps)
        assert a and isinstance(a[0].chunk, Chunk) and type(a[0]) is type(b[0])
        assert a[0].chunk == b[0].chunk  # same top chunk, with the same page/heading/date metadata
        assert all(0 <= r.score <= 1 for r in a)
    assert {r.chunk.department for r in run_search("hostel curfew", azure, ["HOSTEL"])} == {"HOSTEL"}


def test_azure_schema_is_only_read_and_checked():
    backend, _, index_client = make_azure()
    backend.verify_schema()
    assert [c[0] for c in index_client.calls] == ["get_index"]
    for bad, message in ((FakeIndexClient(dims=1024), "1024 dimensions"), (FakeIndexClient(key=False), "key field"),
                         (FakeIndexClient(filterable=False), "filterable")):
        with pytest.raises(BackendError, match=message):
            make_azure(index_client=bad)[0].verify_schema()
    missing = FakeIndexClient()
    missing.index.fields = [f for f in missing.index.fields if f.name != "title"]
    with pytest.raises(BackendError, match="no field.*title"):
        make_azure(index_client=missing)[0].verify_schema()
    assert not hasattr(index_client, "create_index") and not hasattr(index_client, "delete_index")


def test_azure_errors_become_backend_errors_without_secrets():
    backend, client, _ = make_azure()

    def boom(**kw):
        raise RuntimeError("service unavailable")

    client.search = boom
    with pytest.raises(BackendError, match="keyword search failed: RuntimeError: service unavailable"):
        backend.keyword("x", None, 3)


# ---------------------------------------------------------------- ingestion

def run_ingest(cfg, scan, backends, **kw):
    return ingest(cfg, backends, embedder=FakeProvider(dim=DIM), scan=scan, say=lambda *_: None, **kw)


def test_ingest_into_local_and_azure_with_the_same_chunks(scan, tmp_path):
    local = LocalBackend(tmp_path / "l", "embed", DIM)
    azure, client, _ = make_azure()
    report = run_ingest(CFG, scan, [local, azure])
    assert report.ok and [b.name for b in report.backends] == ["local", "azure"]
    assert [b.uploaded for b in report.backends] == [len(scan.chunks)] * 2
    assert set(local.list_ids()) == set(client.docs) == {c.id for c in scan.chunks}
    assert all(len(d["content_vector"]) == DIM for d in client.docs.values())
    assert report.backends[1].estimate_bytes > len(scan.chunks) * 4 * DIM


def test_ingest_is_idempotent_and_removes_stale_chunks(kb, tmp_path):
    azure, client, _ = make_azure()
    first = run_ingest(CFG, scan_kb(CFG, kb_root=kb), [azure])
    ids = set(client.docs)
    run_ingest(CFG, scan_kb(CFG, kb_root=kb), [azure])
    assert set(client.docs) == ids  # same ids, replaced not duplicated
    (kb / "HOSTEL" / "rules.md").write_text("# Hostel rules\n\nHostel curfew for residents is ten pm every night.\n",
                                            encoding="utf-8")  # two sections become one chunk
    again = run_ingest(CFG, scan_kb(CFG, kb_root=kb), [azure])
    assert again.backends[0].stale_deleted >= 1 and again.backends[0].foreign == 0
    assert not (set(client.deleted) & {c.id for c in scan_kb(CFG, kb_root=kb).chunks})
    assert len(client.docs) < len(ids) and first.ok


def test_rebuild_clears_documents_but_never_the_index(scan):
    azure, client, index_client = make_azure()
    client.docs["old-chunk-0000"] = {"id": "old-chunk-0000", "content": "x", "department": "IT", "title": "t",
                                     "source_url": "u", "content_vector": [0.0] * DIM}
    messages = []
    report = ingest(CFG, [azure], rebuild=True, embedder=FakeProvider(dim=DIM), scan=scan, say=messages.append)
    assert "old-chunk-0000" not in client.docs and report.backends[0].rebuild_deleted == 1
    assert any("REBUILD" in m and "schema are kept" in m for m in messages)  # reported before it happens
    assert [c[0] for c in index_client.calls if c[0] not in ("get_index", "get_index_statistics")] == []


def test_without_rebuild_unrelated_chunks_are_kept_and_reported(scan):
    azure, client, _ = make_azure()
    client.docs["other-0000"] = {"id": "other-0000", "content": "x", "department": "IT", "title": "t",
                                 "source_url": "u", "content_vector": [0.0] * DIM}
    report = run_ingest(CFG, scan, [azure])
    assert "other-0000" in client.docs and report.backends[0].foreign == 1


def test_azure_upload_stops_before_the_storage_limit(scan):
    azure, client, _ = make_azure(index_client=FakeIndexClient(storage=int(44.999 * 1024 * 1024)))
    report = run_ingest(CFG, scan, [azure])
    assert not report.ok and "over the 45 MB limit" in report.backends[0].blocked
    assert client.docs == {} and report.backends[0].uploaded == 0
    out = []
    print_report(report, say=out.append)
    assert any("stopped before uploading" in line for line in out)


def test_rebuild_ignores_old_storage_in_the_limit_check(scan):
    azure, client, _ = make_azure(index_client=FakeIndexClient(storage=int(44.999 * 1024 * 1024)))
    assert run_ingest(CFG, scan, [azure], rebuild=True).ok and client.docs


def test_estimate_counts_vectors_and_text(scan):
    assert estimate_bytes(scan.chunks, 1536) > len(scan.chunks) * 1536 * 4


def test_dry_run_and_empty_kb_write_nothing(scan, tmp_path):
    local = LocalBackend(tmp_path / "l", "embed", DIM)
    assert run_ingest(CFG, scan, [local], dry_run=True).backends == [] and not (tmp_path / "l").exists()


def test_print_report_lists_warnings_skips_counts_and_storage(scan, tmp_path):
    local = LocalBackend(tmp_path / "l", "embed", DIM)
    out = []
    print_report(run_ingest(CFG, scan, [local]), say=out.append)
    text = "\n".join(out)
    assert "WARNING: kb/HOSTEL/extra.md" in text and f"chunks created: {len(scan.chunks)}" in text
    assert "files skipped:" in text and "[local] chunks uploaded:" in text and "store now:" in text


# ---------------------------------------------------------------- index_stub and inspect

def test_index_stub_lists_every_file_and_prefills_from_front_matter(kb, capsys):
    folder = kb / "IT"
    (folder / "INDEX.md").unlink()
    (folder / "notes").mkdir()
    (folder / "notes" / "faq.md").write_text("---\ntitle: IT FAQ\nsource_url: https://e.test/faq\n---\nbody\n",
                                             encoding="utf-8")
    (folder / "doc.pdf").write_bytes(REFUND_PDF)
    assert index_stub.main([str(folder)]) == 0
    entries = read_index(folder / "INDEX.md")
    assert {e["file"] for e in entries} == {"wifi.html", "notes/faq.md", "doc.pdf"}
    faq = next(e for e in entries if e["file"] == "notes/faq.md")
    assert faq["title"] == "IT FAQ" and faq["source_url"] == "https://e.test/faq" and faq["last_updated"] == ""
    assert all(set(e) >= {"file", "title", "source_url", "last_updated", "public_or_permission", "collector"}
               for e in entries)
    assert "fill in" in capsys.readouterr().out
    errors = scan_kb(CFG, kb_root=kb).errors  # blanks are intentional: ingestion refuses them until filled in
    assert any("missing title" in e for e in errors)


def test_index_stub_never_overwrites_without_force(kb, capsys):
    before = (kb / "IT" / "INDEX.md").read_text(encoding="utf-8")
    assert index_stub.main([str(kb / "IT")]) == 1
    assert (kb / "IT" / "INDEX.md").read_text(encoding="utf-8") == before
    assert "already exists" in capsys.readouterr().out
    assert index_stub.main([str(kb / "IT"), "--force"]) == 0
    assert index_stub.main([str(kb / "MISC")]) == 1


def test_inspect_output_has_department_title_score_page_and_a_short_snippet(local):
    results = run_search("refund original receipt", local, ["FINANCE"])
    text = format_results(results)
    assert "FINANCE  Refund policy" in text and "score " in text and "page: 2" in text
    assert "citation: Refund policy, p. 2" in text
    snippet_lines = [ln.strip() for ln in text.splitlines() if ln.startswith("    ") and "page:" not in ln]
    assert snippet_lines and all(len(ln) <= 203 for ln in snippet_lines)
    assert format_results([]) == "(no chunks found)"
