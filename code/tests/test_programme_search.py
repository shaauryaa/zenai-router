"""Programme-aware search (Milestone 2 sprint S1, part B). No network."""
import csv

from helpdesk import kb_search, pipeline
from helpdesk.kb_search import SCSET_PG_FILE, SCSET_UG_FILE, programme_files
from zenai.paths import TEST_DATA
from zenai.providers import FakeProvider

CS = "COURSE_SPECIFIC/"


def test_every_mapped_file_is_a_course_specific_manifest_document():
    with open(TEST_DATA / "kb_manifest.csv", encoding="utf-8", newline="") as f:
        manifest = {r["file"].removeprefix("code/kb/") for r in csv.DictReader(f) if r["office"] == "COURSE_SPECIFIC"}
    mapped = {f for _, _, fs in kb_search.PROGRAMMES for f in fs} | {SCSET_UG_FILE, SCSET_PG_FILE}
    assert mapped == manifest  # every COURSE_SPECIFIC document is reachable, and nothing else


def test_programme_mentions_and_short_forms():
    assert programme_files("btech attendance rule") == [CS + "seas-btech-ordinances-rules.md"]
    assert programme_files("B. Tech attendance") == programme_files("b tech attendance") == programme_files("B.Tech")
    assert programme_files("M.Tech thesis") == [CS + "mtech-ordinances-rules.md"]
    assert programme_files("MBA grading") == [CS + "mba-rules.md"]
    assert programme_files("BA JMC internship") == [CS + "bajmc-rules.md"]
    assert programme_files("BA Liberal Arts minor") == [CS + "ba-liberal-arts-rulebook.md"]
    assert programme_files("BBA exam rules") == [CS + "bba-rules.md"]
    assert programme_files("BBA LLB (Hons) attendance") == [CS + "sol-academic-handbook.md"]
    assert programme_files("BA LL.B moot court") == [CS + "sol-academic-handbook.md"]
    assert programme_files("what is the attendance rule?", "") == []


def test_scset_ug_unless_masters_said():
    assert programme_files("SCSET grading") == [SCSET_UG_FILE]
    assert programme_files("cse backlog rules") == [SCSET_UG_FILE]
    assert programme_files("SCSET master's dissertation") == [SCSET_PG_FILE]
    assert programme_files("cse dual degree") == [SCSET_PG_FILE]
    assert set(programme_files("B.Tech CSE attendance")) == {CS + "seas-btech-ordinances-rules.md", SCSET_UG_FILE}


def test_prog_search_restricts_routed_part_only_for_academics():
    idx = kb_search.default_index()
    hits = idx.search_routed_plus_all_prog("attendance requirement", "ACADEMICS", "MBA attendance?")
    assert len(hits) == 8
    assert sum(h.chunk.file == CS + "mba-rules.md" for h in hits) >= 5
    # no programme, or not ACADEMICS: same as the old search
    for q, d, question in [("attendance requirement", "ACADEMICS", "attendance?"),
                           ("hostel fee mba", "FEES", "MBA hostel fee?")]:
        old = idx.search_routed_plus_all(q, d)
        assert [h.chunk.id for h in idx.search_routed_plus_all_prog(q, d, question)] == [h.chunk.id for h in old]


def test_pipeline_search_options():
    assert pipeline.SEARCHES == ("route5", "routed5_all3", "routed5_all3_prog")
    reply = {"topics": [{"text": "q", "domain": "ACADEMICS", "request_type": "info",
                         "search_query": "attendance requirement", "reason": "r"}]}
    p2 = {"found": False, "answer": "no", "quote": "", "doc_title": "", "page": "", "language": "en"}
    out = pipeline.answer("MBA attendance?", "v2", FakeProvider(chat_replies=[reply, p2]), router="v2",
                          search="routed5_all3_prog")
    assert out["programme_files"] == [CS + "mba-rules.md"] and len(out["retrieval"]) == 8
    out = pipeline.answer("MBA attendance?", "v2", FakeProvider(chat_replies=[reply, p2]), router="v2",
                          search="routed5_all3")
    assert "programme_files" not in out and len(out["retrieval"]) == 8
