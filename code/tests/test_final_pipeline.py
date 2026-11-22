"""Final pipeline: P3 handoff draft, refuse/clarify templates, multi-topic note, final test table. No network."""
from helpdesk import final_test, handoff, pipeline
from zenai.paths import PROMPTS
from zenai.providers import FakeProvider


def topic(domain="FEES", rt="info", sq="fee refund", text="q", reason="r"):
    return {"text": text, "domain": domain, "request_type": rt, "search_query": sq, "reason": reason}


def p1(*topics):
    return {"topics": list(topics) or [topic()]}


P2_NOT_FOUND = {"found": False, "answer": "I couldn't find this in the official documents.", "quote": "",
                "doc_title": "", "page": "", "language": "en"}
DRAFT = {"to": "x", "subject": "Question about the fee refund",
         "body": "Dear Finance Office,\nI could not find this.\n[Your name]\n[Enrollment no.]"}


def test_p3_prompt_final_is_v2_and_v1_is_kept():
    t = handoff.load_template()
    assert t == handoff.load_template(PROMPTS / "v2" / "P3_handoff.md")
    v1 = handoff.load_template(handoff.PROMPT_FILE_V1)
    assert t != v1
    for template in (t, v1):
        for name in ("{question}", "{office}", "{office_email}", "{reason}", "[Your name]", "[Enrollment no.]"):
            assert name in template
        assert '{"to": "...", "subject": "...", "body": "..."}' in template
    assert pipeline.FINAL["p3"] == "v2"


def test_office_mapping_and_demo_addresses():
    assert handoff.office_for("FEES") == "FINANCE" and handoff.office_for("OUT_OF_SCOPE") == "HELPDESK"
    assert handoff.office_for(None) == "HELPDESK"
    assert handoff.office_email("FINANCE") == "finance@zenai-demo.example"
    assert handoff.office_email("CAMPUS_SERVICES") == "services@zenai-demo.example"


def test_handoff_reason():
    assert handoff.handoff_reason("not_found") == handoff.REASON_NOT_FOUND
    assert handoff.handoff_reason("handoff", "Depends on the student's own fee record.") == handoff.REASON_RECORD
    assert handoff.handoff_reason("handoff", "Someone must fix the AC.") == handoff.REASON_ACT


def test_not_found_gets_a_p3_draft_with_demo_address_and_checks():
    fake = FakeProvider(chat_replies=[p1(), P2_NOT_FOUND, DRAFT])
    out = pipeline.final_answer("Is there a fee for the gym?", fake)
    assert out["action"] == "not_found" and out["llm_calls"] == 3
    p3 = out["p3"]
    assert p3["reason"] == handoff.REASON_NOT_FOUND and p3["office"] == "FINANCE"
    assert p3["draft"]["to"] == "finance@zenai-demo.example"  # code sets `to`, whatever the model wrote
    assert p3["checks"] == {"keys_present": True, "to_matches": False, "body_words": 12, "under_120_words": True,
                            "placeholders_present": True}
    prompt = fake.chat_requests[2][0]["content"]
    assert "Is there a fee for the gym?" in prompt and "Finance Office" in prompt and "{reason}" not in prompt


def test_handoff_gets_a_p3_draft():
    fake = FakeProvider(chat_replies=[p1(topic(rt="needs_human", reason="Needs the student's own record.")), DRAFT])
    out = pipeline.final_answer("my dues?", fake)
    assert out["action"] == "handoff" and out["p3"]["reason"] == handoff.REASON_RECORD and out["llm_calls"] == 2


def test_p3_non_json_reply_is_recorded_not_raised():
    out = pipeline.final_answer("x", FakeProvider(chat_replies=[p1(topic(rt="needs_human")), "no json here"]))
    assert out["p3"]["draft"] is None and out["p3"]["error"]


def test_refuse_and_clarify_use_templates_without_llm_call():
    fake = FakeProvider(chat_replies=[p1(topic("OUT_OF_SCOPE", "not_campus"))])
    out = pipeline.final_answer("Who won the match?", fake)
    assert out["action"] == "refuse" and out["reply_text"] == handoff.REFUSE_TEXT and fake.calls_made == 1
    fake = FakeProvider(chat_replies=[p1(topic("FEES", "vague"))])
    out = pipeline.final_answer("refund?", fake)
    assert out["action"] == "clarify" and "Finance Office" in out["reply_text"] and fake.calls_made == 1
    assert out["reply_text"].count("?") == 1
    out = pipeline.final_answer("   ", FakeProvider())
    assert out["action"] == "clarify" and out["reply_text"] == handoff.CLARIFY_EMPTY and out["p3"] is None


def test_clarify_names_two_offices():
    text = handoff.clarify_text([topic("FEES", "vague"), topic("HOSTEL", "vague")])
    assert "Finance Office" in text and "Hostel Wardens" in text


def test_multi_topic_note_and_other_topics_kept():
    fake = FakeProvider(chat_replies=[p1(topic("OUT_OF_SCOPE", "not_campus", text="a"), topic("HOSTEL", text="b"))])
    out = pipeline.final_answer("a and b", fake)
    assert out["multi_topic_note"] == handoff.MULTI_TOPIC_NOTE and out["other_topics"] == ["b"]
    out = pipeline.final_answer("a", FakeProvider(chat_replies=[p1(topic("OUT_OF_SCOPE", "not_campus"))]))
    assert out["multi_topic_note"] == "" and out["other_topics"] == []


def test_final_test_pass_rule():
    row = {"key_fact": "x", "expected_action": "answer"}
    assert final_test.passed(row, {"action": True, "key_fact": True, "quote_verified": True})
    assert not final_test.passed(row, {"action": True, "key_fact": False, "quote_verified": True})
    assert not final_test.passed(row, {"action": True, "key_fact": True, "quote_verified": False})
    assert final_test.passed({"key_fact": "", "expected_action": "refuse"}, {"action": True})
    assert not final_test.passed({"key_fact": "", "expected_action": "refuse"}, {"action": False})
    assert final_test.table_md([["Q1", "a|b", "Edge", "e", "x", "Pass"]]).splitlines()[2] == \
        "| Q1 | a/b | Edge | e | x | Pass |"
