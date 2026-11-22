"""LLM parsing fallback and end-to-end routing with FakeProvider. Messages here are invented, not dataset text."""
import json

import pytest

from zenai.llm_router import SYSTEM_PROMPT, classify
from zenai.providers import FakeProvider
from zenai.router import Router, decide

CFG = {"knn": {"k": 3}, "confidence": {"w_agree": 0.5, "w_share": 0.5},
       "thresholds": {"t_high": 0.7, "t_low": 0.4}}

EXAMPLES = [
    {"id": "E1", "text": "projector in lab broken", "domain": "CAMPUS_SERVICES"},
    {"id": "E2", "text": "lab projector not working", "domain": "CAMPUS_SERVICES"},
    {"id": "E3", "text": "broken projector lab", "domain": "CAMPUS_SERVICES"},
    {"id": "E4", "text": "canteen menu today", "domain": "CAMPUS_SERVICES"},
    {"id": "E5", "text": "warden permission late entry", "domain": "HOSTEL"},
    {"id": "E6", "text": "late entry warden rules", "domain": "HOSTEL"},
    {"id": "E7", "text": "warden late entry form", "domain": "HOSTEL"},
]


@pytest.fixture
def examples_path(tmp_path):
    path = tmp_path / "examples.jsonl"
    path.write_text("\n".join(json.dumps(e) for e in EXAMPLES), encoding="utf-8")
    return path


def reply(*topics):
    return {"topics": [dict(zip(("text", "domain", "request_type", "reason"), t)) for t in topics]}


# ---- LLM parse / retry / fallback ----

def test_prompt_has_no_example_questions():
    assert "Examples" not in SYSTEM_PROMPT and "e.g." not in SYSTEM_PROMPT


def test_classify_valid_reply_single_call():
    p = FakeProvider([reply(("projector broken", "CAMPUS_SERVICES", "needs_human", "maintenance"))])
    topics, info = classify("projector broken", p)
    assert topics[0].domain == "CAMPUS_SERVICES"
    assert info == {"attempts": 1, "fallback": False}


def test_classify_retries_once_after_invalid_domain():
    p = FakeProvider([reply(("x", "SPORTS", "info", "")), reply(("x", "CAMPUS_SERVICES", "info", ""))])
    topics, info = classify("x", p)
    assert topics[0].domain == "CAMPUS_SERVICES"
    assert info["attempts"] == 2 and not info["fallback"]
    assert "invalid" in p.chat_requests[1][-1]["content"]


def test_classify_retries_after_non_json_text():
    p = FakeProvider(["not json at all", reply(("x", "IT", "info", ""))])
    topics, info = classify("x", p)
    assert topics[0].domain == "IT" and info["attempts"] == 2
    assert p.chat_requests[1][-2] == {"role": "assistant", "content": "not json at all"}


def test_classify_two_failures_fall_back_to_null_domain():
    p = FakeProvider(["garbage", {"topics": []}])
    topics, info = classify("some message", p)
    assert len(topics) == 1 and topics[0].domain is None and topics[0].text == "some message"
    assert info["fallback"] is True


# ---- end to end ----

def test_route_multi_topic(examples_path):
    p = FakeProvider([reply(("lab projector broken", "CAMPUS_SERVICES", "needs_human", "fix"),
                            ("warden late entry rules", "HOSTEL", "info", "rules"))])
    r = Router(CFG, p, examples_path).route("lab projector broken and warden late entry rules?")
    assert [t.action for t in r.topics] == ["handoff", "answer"]
    assert all(t.agree and t.confidence == 1.0 for t in r.topics)
    assert (r.primary_domain, r.secondary_domain, r.action, r.auto_routed) == \
           ("CAMPUS_SERVICES", "HOSTEL", "handoff", True)
    assert {n.id for n in r.topics[1].neighbours} == {"E5", "E6", "E7"}


def test_route_llm_fallback_hands_off(examples_path):
    p = FakeProvider(["garbage", "more garbage"])
    r = Router(CFG, p, examples_path).route("lab projector broken")
    assert r.action == "handoff" and r.primary_domain is None and r.signals["llm"]["fallback"]


def test_route_all_refuse(examples_path):
    p = FakeProvider([reply(("who wins the cricket match", "OUT_OF_SCOPE", "not_campus", "sport opinion"))])
    r = Router(CFG, p, examples_path).route("who wins the cricket match")
    assert (r.action, r.primary_domain) == ("refuse", "OUT_OF_SCOPE")


def test_decide_recomputes_offline_with_new_thresholds(examples_path):
    # LLM says HOSTEL but the neighbours are CAMPUS_SERVICES -> share 0, confidence 0
    p = FakeProvider([reply(("lab projector broken", "HOSTEL", "info", "wrong on purpose"))])
    router = Router(CFG, p, examples_path)
    result = router.route("lab projector broken")
    assert result.action == "handoff"

    calls_before = p.calls_made
    lenient = {**CFG, "thresholds": {"t_high": 0.0, "t_low": 0.0}}
    redo = decide(result.message, result.signals, lenient)
    assert redo.action == "answer"
    assert p.calls_made == calls_before  # no new provider calls
