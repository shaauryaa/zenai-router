"""helpdesk.pipeline with FakeProvider: no network."""
from helpdesk import pipeline
from zenai.providers import FakeProvider


def route(domain="HOSTEL", request_type="info"):
    return {"topics": [{"text": "q", "domain": domain, "request_type": request_type, "reason": "r"}]}


def test_empty_input_clarifies_without_llm():
    p = FakeProvider()
    out = pipeline.answer("   ", "v2", p)
    assert out["action"] == "clarify" and p.calls_made == 0


def test_router_request_types_map_to_actions():
    for rt, action in [("not_campus", "refuse"), ("vague", "clarify"), ("needs_human", "handoff")]:
        out = pipeline.answer("hello", "v2", FakeProvider(chat_replies=[route("OUT_OF_SCOPE", rt)]))
        assert out["action"] == action and out["p2"] is None


def test_templates_load_from_files():
    for v in ("v1", "v2"):
        t = pipeline.load_template(v)
        assert t.startswith("You are ZEN AI") and "{sections}" in t and "{question}" in t


def test_verified_quote_answers_and_bad_quote_is_not_found():
    q = "Can parents visit the hostel rooms?"
    hits = pipeline.kb_search.search_for_route(q, "HOSTEL", k=5)
    real = " ".join(hits[0].chunk.text.split()[:12])
    good = {"found": True, "answer": "a", "quote": real.upper(), "doc_title": "t", "page": "1", "language": "en"}
    out = pipeline.answer(q, "v2", FakeProvider(chat_replies=[route(), good]))
    assert out["action"] == "answer" and out["quote_check"]["verified"]
    bad = dict(good, quote="parents may stay overnight in rooms")
    out = pipeline.answer(q, "v2", FakeProvider(chat_replies=[route(), bad]))
    assert out["action"] == "not_found" and "quote check failed" in out["reason"]


def test_v1_plain_text_parsing():
    p = pipeline.parse_plain('I couldn\u2019t find this in the official documents. Contact "Hostel".')
    assert p["found"] is False
    p = pipeline.parse_plain('Yes. "Visitors are not allowed" (Standing Orders, page 2)')
    assert p["found"] is True and p["quote"] == "Visitors are not allowed"


def test_json_format_validation():
    assert pipeline.parse_json({"found": "yes"})["format_valid"] is False
    ok = pipeline.parse_json({k: "" for k in pipeline.JSON_KEYS} | {"found": False})
    assert ok["format_valid"] is True
