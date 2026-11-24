"""Dual-query search (Milestone 2 sprint S4): search_query + topic text, reciprocal rank fusion. No network."""
from helpdesk import kb_search, pipeline
from helpdesk.kb_search import Chunk, KBIndex
from zenai.providers import FakeProvider


def tiny_index() -> KBIndex:
    texts = [("FINANCE", "late fee penalty for fee payment after the due date"),
             ("FINANCE", "scholarship renewal needs a minimum grade"),
             ("HOSTEL", "hostel in-time is 10 pm for all residents"),
             ("HOSTEL", "mess timings breakfast lunch dinner"),
             ("IT", "wifi password must not be shared")]
    chunks = [Chunk(id=f"c{i}", file=f"{o}/d{i}.md", title=f"doc {i}", office=o, page=1, text=t,
                    source_url="", date="")
              for i, (o, t) in enumerate(texts)]
    return KBIndex(chunks, [kb_search.tokenize(c.text) for c in chunks])


def test_fusion_ranks_chunks_found_by_either_query():
    idx = tiny_index()
    ids = [idx.chunks[i].id for _, i in idx._fused(["late fee penalty", "dinner timings"])]
    assert {"c0", "c3"} <= set(ids[:2])
    # one query, or the same query twice: the BM25 order is kept
    assert [i for _, i in idx._fused(["hostel in-time"])] == [i for _, i in idx._ranked("hostel in-time")]
    assert idx._fused(["hostel in-time", "Hostel  in-time"]) == idx._fused(["hostel in-time"])
    assert idx._fused(["", "  "]) == []


def test_dual_search_keeps_routed_split():
    idx = tiny_index()
    hits = idx.search_dual_prog("fee", "when is dinner", "FEES", routed_k=1, all_k=1)
    assert len(hits) == 2 and sum(h.chunk.office == "FINANCE" for h in hits) == 1
    assert any(h.chunk.id == "c3" for h in hits)  # the topic text found the dinner chunk
    assert idx.search_dual_prog("fee", "dinner", None, routed_k=1, all_k=1)  # all folders


def test_dual_search_programme_filter_same_as_prog_search():
    idx = kb_search.default_index()
    hits = idx.search_dual_prog("attendance requirement", "How much attendance do I need?", "ACADEMICS",
                                "MBA attendance?")
    assert len(hits) == 8
    assert sum(h.chunk.file == "COURSE_SPECIFIC/mba-rules.md" for h in hits) >= 5


def test_pipeline_dual_prog_records_both_queries():
    p1 = {"topics": [{"domain": "HOSTEL", "request_type": "info", "intent": "", "confidence": 0.9,
                      "text": "When is dinner served?", "search_query": "mess dinner timings"}]}
    p2 = {"found": False, "answer": "", "quote": "", "doc_title": "", "page": "", "language": "en"}
    fake = FakeProvider(chat_replies=[p1, p2])
    out = pipeline.answer("When is dinner served?", "v2", fake, router="v2", search="dual_prog")
    assert out["search_query"] == "mess dinner timings" and out["topic_text_query"] == "When is dinner served?"
    assert len(out["retrieval"]) == 8
