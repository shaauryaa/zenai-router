"""Fresh check 2 row types in helpdesk/final_test.py (rules in test-data/README.md). No API call."""
from helpdesk import final_test, safety

BASE = {"type": "Edge", "language": "en", "notes": "", "router_scorable": "no", "v1_domain": "",
        "expected_page": "", "turn2_question": "", "turn1_expected_action": ""}
FACT1, FACT2 = "Lockout Duration shall be set to 30 minutes", "10:00 AM to 1:00 PM"


def row(**k):
    return {**BASE, "id": "F99", "question": "q", "expected_office": "", "expected_doc": "", "key_fact": "", **k}


def topic(action, answer="", verified=True):
    return {"action": action, "p2": {"answer": answer, "quote": "", "doc_title": "", "format_valid": True},
            "quote_check": {"verified": verified}}


def out_of(*topics):
    return {**topics[0], "p2_version": "v2", "topic_results": list(topics)}


TWO = row(expected_action="answer;answer", expected_office="IT;CAMPUS_SERVICES", key_fact=f"{FACT1};{FACT2}")
TWO_NF = row(expected_action="answer;not_found", key_fact=f"{FACT1};")


def test_row_kind():
    assert final_test.row_kind(TWO) == "two"
    assert final_test.row_kind(row(expected_action="safety")) == "safety"
    assert final_test.row_kind(row(expected_action="answer", turn2_question="MBA?")) == "followup"
    assert final_test.row_kind(row(expected_action="not_found")) == "one"
    assert final_test.row_kind({"expected_action": "answer"}) == "one"  # fresh check 1 has no turn2 column


def test_part_rows_split_in_order():
    parts = final_test.part_rows(TWO_NF)
    assert [p["expected_action"] for p in parts] == ["answer", "not_found"]
    assert [p["key_fact"] for p in parts] == [FACT1, ""]


def test_two_question_needs_both_parts():
    good = out_of(topic("answer", FACT1), topic("answer", FACT2))
    s, ok, parts = final_test.score_row("two", TWO, good)
    assert ok and s["two_question_row"] and s["action"] and s["key_fact"] and len(parts) == 2
    # part 2 wrong action
    s, ok, _ = final_test.score_row("two", TWO, out_of(topic("answer", FACT1), topic("not_found")))
    assert not ok and s["action"] is False and s["two_question_row"] is False
    # part 2 answered without its key fact
    s, ok, _ = final_test.score_row("two", TWO, out_of(topic("answer", FACT1), topic("answer", "9 to 5")))
    assert not ok and s["key_fact"] is False and s["incomplete"] is True
    # part 1 quote not verified
    _, ok, _ = final_test.score_row("two", TWO, out_of(topic("answer", FACT1, False), topic("answer", FACT2)))
    assert not ok
    # only one topic found by the router
    s, ok, parts = final_test.score_row("two", TWO, out_of(topic("answer", FACT1)))
    assert not ok and parts[1]["action"] is False


def test_two_question_not_found_part():
    _, ok, _ = final_test.score_row("two", TWO_NF, out_of(topic("answer", FACT1), topic("not_found")))
    assert ok
    s, ok, _ = final_test.score_row("two", TWO_NF, out_of(topic("answer", FACT1), topic("answer", "Rs 500")))
    assert not ok and s["needs_review"] is True


def test_safety_row_needs_card_with_contacts():
    r = row(expected_action="safety", expected_office="STUDENT_SUPPORT")
    card = safety.card()
    s, ok, _ = final_test.score_row("safety", r, {**topic("safety"), "p2": None, "p2_version": "v2",
                                                 "safety_card": card})
    assert ok and s["safety_card"] and s["safety_row"]
    _, ok, _ = final_test.score_row("safety", r, {**topic("safety"), "p2": None, "p2_version": "v2",
                                                 "safety_card": {**card, "lines": [], "verified": False}})
    assert not ok
    s, ok, _ = final_test.score_row("safety", r, {**topic("answer", "POSH process"), "p2_version": "v2"})
    assert not ok and s["safety_card"] is False


def test_followup_row():
    r = row(expected_action="answer", key_fact=FACT1, turn2_question="how long?", turn1_expected_action="clarify")
    out2 = {**topic("answer", FACT1), "p2_version": "v2"}
    s, ok, _ = final_test.score_row("followup", r, out2, turn1={"action": "clarify"})
    assert ok and s["turn1_clarify"] and s["followup_row"]
    s, ok, _ = final_test.score_row("followup", r, out2, turn1={"action": "answer"})
    assert not ok and s["turn1_clarify"] is False
    _, ok, _ = final_test.score_row("followup", r, {**topic("not_found"), "p2_version": "v2"},
                                    turn1={"action": "clarify"})
    assert not ok


def test_run_followup_joins_after_clarify(monkeypatch):
    seen = []

    def fake(question, provider):
        seen.append(question)
        return {"action": "clarify" if len(seen) == 1 else "answer"}

    monkeypatch.setattr(final_test.pipeline, "final_answer", fake)
    r = row(question="fees?", turn2_question="hostel fee rise yearly", turn1_expected_action="clarify",
            expected_action="answer")
    out1, out2, previous = final_test.run_followup(r, None)
    assert seen == ["fees?", "fees? hostel fee rise yearly"] and previous == "fees?"
    assert out1["action"] == "clarify" and out2["action"] == "answer"


def test_every_row_has_the_same_score_keys():
    keys = {tuple(final_test.score_row(k, r, o, t)[0]) for k, r, o, t in [
        ("two", TWO, out_of(topic("answer", FACT1), topic("answer", FACT2)), None),
        ("safety", row(expected_action="safety"), {**topic("refuse"), "p2": None, "p2_version": "v2"}, None),
        ("followup", row(expected_action="answer", turn1_expected_action="clarify", turn2_question="x"),
         {**topic("answer"), "p2_version": "v2"}, {"action": "clarify"}),
        ("one", row(expected_action="not_found"), {**topic("not_found"), "p2_version": "v2"}, None)]}
    assert len(keys) == 1
