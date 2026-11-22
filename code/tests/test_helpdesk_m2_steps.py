"""Milestone 2 steps 1-4: quote normalisation, router P1 v2, 5+3 search, P2 v4 template. FakeProvider: no network."""
from types import SimpleNamespace

from helpdesk import kb_search, pipeline, route_eval, router_v2
from zenai.providers import FakeProvider


def hit(text):
    return kb_search.Hit(kb_search.Chunk("x#p1-1", "HOSTEL", "HOSTEL/x.md", "X", 1, "", "", text), 1.0)


# step 1: quote check normalisation
def test_quote_check_ignores_markdown_emphasis():
    ok, _, _ = pipeline.check_quote("a late registration fee of ₹1,000.", [hit("a **late registration fee of ₹1,000**.")])
    assert ok
    assert pipeline.check_quote("the __rule__ applies", [hit("the rule applies")])[0]


def test_quote_check_joins_line_end_hyphens_both_ways():
    h = [hit("members of the Anti-\nRagging Committee and the exam-\nination cell")]
    assert pipeline.check_quote("members of the Anti-Ragging Committee", h)[0]
    assert pipeline.check_quote("members of the Anti- Ragging Committee", h)[0]
    assert pipeline.check_quote("the examination cell", h)[0]


def test_quote_check_still_rejects_other_text():
    assert not pipeline.check_quote("members of the Discipline Committee", [hit("members of the Anti-\nRagging")])[0]
    assert pipeline.check_quote("", [hit("anything")])[2] == "empty quote"


# step 2: router P1 v2
def v2_reply(domain="STUDENT_SUPPORT", rt="info", sq="anti ragging complaint procedure"):
    return {"topics": [{"text": "q", "domain": domain, "request_type": rt, "search_query": sq, "reason": "r"}]}


def test_router_v2_prompt_and_schema():
    prompt = router_v2.system_prompt()
    assert "STUDENT_SUPPORT" in prompt and "search_query" in prompt and "<!-- TEMPLATE -->" not in prompt
    topics, meta = router_v2.classify("q", FakeProvider(chat_replies=[v2_reply()]))
    assert topics[0].domain == "STUDENT_SUPPORT" and topics[0].search_query and meta["attempts"] == 1


def test_router_v2_retries_then_falls_back():
    topics, meta = router_v2.classify("q", FakeProvider(chat_replies=[{"topics": []}, {"bad": 1}]))
    assert meta["fallback"] and topics[0].domain is None


def test_pipeline_router_v2_student_support_reaches_p2():
    q = "Who do I report ragging to?"
    hits = kb_search.search_for_route(q, "STUDENT_SUPPORT", k=5)
    assert any(h.chunk.office == "STUDENT_SUPPORT" for h in hits)
    p2 = {"found": False, "answer": "no", "quote": "", "doc_title": "", "page": "", "language": "en"}
    out = pipeline.answer(q, "v2", FakeProvider(chat_replies=[v2_reply(), p2]), router="v2")
    assert out["router_version"] == "v2" and out["search_query"] == q and out["action"] == "not_found"


# step 3: search with search_query, top 5 routed + top 3 all
def test_search_routed_plus_all_shape():
    hits = kb_search.search_routed_plus_all("hostel visitors parents rooms", "HOSTEL")
    assert len(hits) == 8 and sum(h.chunk.office == "HOSTEL" for h in hits) >= 5
    assert [h.score for h in hits] == sorted((h.score for h in hits), reverse=True)
    assert len({h.chunk.id for h in hits}) == 8
    assert len(kb_search.search_routed_plus_all("hostel visitors", None)) == 8


def test_pipeline_uses_search_query_and_falls_back_to_question():
    p2 = {"found": False, "answer": "no", "quote": "", "doc_title": "", "page": "", "language": "en"}
    out = pipeline.answer("kitne din?", "v2", FakeProvider(chat_replies=[v2_reply("FEES", sq="fee refund days"), p2]),
                          router="v2", search="routed5_all3")
    assert out["search_query"] == "fee refund days" and len(out["retrieval"]) == 8
    out = pipeline.answer("fee refund days", "v2", FakeProvider(chat_replies=[v2_reply("FEES", sq=""), p2]),
                          router="v2", search="routed5_all3")
    assert out["search_query"] == "fee refund days"


# step 4: P2 v4 = v2 plus one line
def test_p2_v4_is_v2_plus_hinglish_rule():
    v2, v4 = pipeline.load_template("v2").splitlines(), pipeline.load_template("v4").splitlines()
    added = [line for line in v4 if line not in v2]
    assert [line for line in v2 if line not in v4] == [] and len(added) == 1 and "Hinglish" in added[0]


def test_route_eval_primary_and_action():
    t = lambda d, rt: SimpleNamespace(domain=d, request_type=rt)  # noqa: E731
    assert route_eval.primary_and_action([t("OUT_OF_SCOPE", "not_campus")]) == ("OUT_OF_SCOPE", "refuse")
    assert route_eval.primary_and_action([t("OUT_OF_SCOPE", "not_campus"), t("IT", "info")]) == ("IT", "answer")
    assert route_eval.primary_and_action([t("IT", "info"), t("HOSTEL", "needs_human")]) == ("IT", "handoff")
    assert route_eval.primary_and_action([t(None, None)]) == ("", "handoff")
