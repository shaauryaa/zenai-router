"""Final pipeline: P3 handoff draft, refuse/clarify templates, multi-topic note, final test table. No network."""
from helpdesk import final_test, handoff, pipeline
from helpdesk.score_p2 import score
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


def test_multi_topic_note_and_other_topics_kept_one_topic_pipeline():
    fake = FakeProvider(chat_replies=[p1(topic("OUT_OF_SCOPE", "not_campus", text="a"), topic("HOSTEL", text="b"))])
    out = pipeline.final_answer("a and b", fake, config=pipeline.S1_FINAL)
    assert out["multi_topic_note"] == handoff.MULTI_TOPIC_NOTE and out["other_topics"] == ["b"]
    assert "topic_results" not in out and fake.calls_made == 1
    out = pipeline.final_answer("a", FakeProvider(chat_replies=[p1(topic("OUT_OF_SCOPE", "not_campus"))]),
                                config=pipeline.S1_FINAL)
    assert out["multi_topic_note"] == "" and out["other_topics"] == []


P2_FOUND = {"found": True, "answer": "Rs. 1,000.", "quote": "made-up quote that is not in any section",
            "doc_title": "", "page": "", "language": "en"}


def test_final_config_is_two_topics_with_new_search_and_p2_v2():
    assert pipeline.FINAL == {"router": "v2", "search": "routed5_all3_prog", "p2": "v2", "p3": "v2", "topics": 2}


def test_two_info_topics_each_get_their_own_search_and_p2():
    fake = FakeProvider(chat_replies=[
        p1(topic("FEES", text="How much is the late fee?", sq="late registration fee"),
           topic("HOSTEL", text="When must I be back at night?", sq="hostel in-time night")),
        P2_FOUND, DRAFT, P2_NOT_FOUND, DRAFT])  # order: P1, P2 t1, P3 t1, P2 t2, P3 t2
    out = pipeline.final_answer("How much is the late fee? And when must I be back at night?", fake)
    t1, t2 = out["topic_results"]
    assert out["action"] == t1["action"] == "not_found"  # topic 1: quote check failed; top level = topic 1
    assert out["search_query"] == t1["search_query"] == "late registration fee"
    assert t2["search_query"] == "hostel in-time night" and t2["action"] == "not_found"
    assert t2["office"] == "HOSTEL" and t2["p3"]["office"] == "HOSTEL"
    assert any(h["office"] == "HOSTEL" for h in t2["retrieval"])
    # each P2 gets its own topic's text, not the whole message
    p2_prompts = [fake.chat_requests[i][0]["content"] for i in (1, 3)]
    assert "How much is the late fee?" in p2_prompts[0] and "back at night" not in p2_prompts[0].split("STUDENT")[-1]
    assert p2_prompts[1].rstrip().endswith("When must I be back at night?")
    p3_t1 = fake.chat_requests[2][0]["content"]
    assert out["p3"]["office"] == "FINANCE" and "How much is the late fee?" in p3_t1 and "back at night" not in p3_t1
    assert out["multi_topic_note"] == "" and out["other_topics"] == []
    assert out["llm_calls"] == 1 + 1 + 1 + 1 + 1  # P1, P2 x2, P3 for topic 1 (found but unverified), P3 topic 2


def test_second_topic_router_actions():
    fake = FakeProvider(chat_replies=[
        p1(topic("OUT_OF_SCOPE", "not_campus", text="Who won?"),
           topic("FEES", "needs_human", text="Waive my fine", reason="Needs the student's own record.")), DRAFT])
    out = pipeline.final_answer("Who won? Waive my fine", fake)
    t1, t2 = out["topic_results"]
    assert out["action"] == "refuse" and out["reply_text"] == handoff.REFUSE_TEXT and t1["action"] == "refuse"
    assert t2["action"] == "handoff" and t2["p3"]["reason"] == handoff.REASON_RECORD and t2["office"] == "FINANCE"
    fake = FakeProvider(chat_replies=[p1(topic("FEES", "vague", text="fees?"), topic("HOSTEL", "vague", text="room?"))])
    out = pipeline.final_answer("fees? room?", fake)
    t1, t2 = out["topic_results"]
    assert "Finance Office" in t1["reply_text"] and "Hostel" not in t1["reply_text"]
    assert "Hostel Wardens" in t2["reply_text"] and fake.calls_made == 1


def test_three_topics_note_for_the_rest():
    fake = FakeProvider(chat_replies=[p1(topic("OUT_OF_SCOPE", "not_campus", text="a"),
                                         topic("OUT_OF_SCOPE", "not_campus", text="b"),
                                         topic("HOSTEL", text="c"))])
    out = pipeline.final_answer("a b c", fake)
    assert len(out["topic_results"]) == 2 and out["other_topics"] == ["c"]
    assert out["multi_topic_note"] == handoff.MULTI_TOPIC_NOTE_REST and "first two" in out["multi_topic_note"]


def test_one_topic_message_unchanged_in_two_topic_pipeline():
    fake = FakeProvider(chat_replies=[p1(topic(text="part")), P2_NOT_FOUND, DRAFT])
    out = pipeline.final_answer("Is there a fee for the gym?", fake)
    assert len(out["topic_results"]) == 1 and out["topic_results"][0]["action"] == out["action"] == "not_found"
    assert "p2_question" not in out and fake.chat_requests[1][0]["content"].rstrip().endswith("for the gym?")


def test_topic2_metric_and_table_text():
    row = {"expected_action": "answer;answer", "key_fact": "x;y", "expected_doc": "", "language": "en",
           "router_scorable": "no", "v1_domain": ""}
    out = {"action": "answer", "p2_version": "v5", "p2": {}, "quote_check": {}, "first_topic": {},
           "topic_results": [{"action": "answer"}, {"action": "not_found"}]}
    assert score(row, out)["topic2_action"] is False
    out["topic_results"][1]["action"] = "answer"
    assert score(row, out)["topic2_action"] is True
    assert score({**row, "expected_action": "answer"}, out)["topic2_action"] is None
    assert score(row, {k: v for k, v in out.items() if k != "topic_results"})["topic2_action"] is None
    text = final_test.actual_text({"action": "refuse", "reply_text": "no", "topic_results": [
        {"action": "refuse"}, {"action": "clarify", "reply_text": "which office?"}]})
    assert "; topic 2: clarify" in text
    assert final_test.expected_text(row).endswith("; topic 2 expected answer")


def test_final_test_pass_rule():
    row = {"key_fact": "x", "expected_action": "answer"}
    assert final_test.passed(row, {"action": True, "key_fact": True, "quote_verified": True})
    assert not final_test.passed(row, {"action": True, "key_fact": False, "quote_verified": True})
    assert not final_test.passed(row, {"action": True, "key_fact": True, "quote_verified": False})
    assert final_test.passed({"key_fact": "", "expected_action": "refuse"}, {"action": True})
    assert not final_test.passed({"key_fact": "", "expected_action": "refuse"}, {"action": False})
    assert final_test.table_md([["Q1", "a|b", "Edge", "e", "x", "Pass"]]).splitlines()[2] == \
        "| Q1 | a/b | Edge | e | x | Pass |"


def test_key_fact_normalises_pipes_colons_and_whitespace_on_both_sides():
    from helpdesk.score_p2 import fact_norm
    assert fact_norm("Block A | 1,20,000") == fact_norm("Block A: 1,20,000") == "block a 1,20,000"
    row = {"expected_action": "answer", "key_fact": "Block A | 1,20,000", "expected_doc": "", "language": "en",
           "router_scorable": "no", "v1_domain": ""}
    out = {"action": "answer", "p2_version": "v2", "p2": {"answer": "Rs 1,20,000", "quote": "Block  A:\n1,20,000"},
           "quote_check": {"verified": True}}
    s = score(row, out)
    assert s["key_fact"] is True and s["incomplete"] is False and s["needs_review"] is False


def test_incomplete_and_needs_review():
    row = {"expected_action": "answer", "key_fact": "back by 7 pm", "expected_doc": "", "language": "en",
           "router_scorable": "no", "v1_domain": ""}
    out = {"action": "answer", "p2_version": "v2", "p2": {"answer": "Ask the warden.", "quote": "x"},
           "quote_check": {"verified": True}}
    s = score(row, out)
    assert s["incomplete"] is True and s["needs_review"] is False
    s = score({**row, "expected_action": "not_found", "key_fact": ""}, out)
    assert s["incomplete"] is None and s["needs_review"] is True
    s = score(row, {**out, "action": "not_found"})
    assert s["incomplete"] is None and s["needs_review"] is None
