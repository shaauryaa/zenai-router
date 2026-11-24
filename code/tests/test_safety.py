"""Safety card (Milestone 2 sprint S4). No network."""
import csv
import json

from helpdesk import final_test, pipeline, safety
from helpdesk.kb_search import read_document
from helpdesk.score_p2 import RUNS
from zenai.paths import TEST_DATA
from zenai.providers import FakeProvider


def topic(domain="STUDENT_SUPPORT", rt="info", text="q", sq="anti ragging"):
    return {"text": text, "domain": domain, "request_type": rt, "search_query": sq, "reason": "r"}


DRAFT = {"to": "x", "subject": "Need help urgently",
         "body": "Dear Student Support,\nI need help.\n[Your name]\n[Enrollment no.]"}
P2_FOUND = {"found": True, "answer": "a", "quote": "q", "doc_title": "", "page": "", "language": "en"}


def test_card_lines_are_word_for_word_from_the_contacts_file():
    c = safety.card()
    _, body = read_document(safety.CONTACTS_FILE)
    present = {line.strip() for line in body.splitlines()}
    assert c["verified"] and c["lines"]
    assert all(line in present for line in c["lines"])
    assert sum("@" in line for line in c["lines"]) >= 2  # one anti-ragging, one harassment address
    assert not any("removed]" in line for line in c["lines"])  # redacted lines are never shown
    assert c["source_file"].endswith("STUDENT_SUPPORT/anti-ragging-and-sexual-harassment-contacts.md")
    md = safety.card_markdown(c)
    assert c["source_title"] in md and md.startswith(safety.CARD_INTRO)


def test_card_without_any_contact_is_only_the_fallback():
    body = "## Anti Ragging Committee\n\n### Someone\n- **Designation:** X\n- **Email:** [contact removed]\n"
    assert safety.card_lines(body) == ["## Anti Ragging Committee"]
    assert safety.card_markdown({**safety.card(), "lines": []}) == safety.CARD_FALLBACK


def test_router_trigger_student_support_needs_human():
    fake = FakeProvider(chat_replies=[{"topics": [topic(rt="needs_human", text="something happened")]}, DRAFT])
    out = pipeline.final_answer("something happened in my hostel", fake)
    assert out["action"] == "safety" and "needs_human" in out["reason"]
    assert out["safety_card"]["verified"] and out["reply_text"].startswith(safety.CARD_INTRO)
    assert out["office"] == "STUDENT_SUPPORT" and out["p3"]["office"] == "STUDENT_SUPPORT"
    assert out["retrieval"] == [] and out["p2"] is None
    assert out["llm_calls"] == 2  # P1 and P3 only: no P2
    assert final_test.topic_text(out).startswith("safety (contacts card); draft to ")


def test_incident_trigger_from_the_text_even_when_routed_elsewhere():
    fake = FakeProvider(chat_replies=[{"topics": [topic(domain="HOSTEL", text="Seniors in my block keep ragging me "
                                                                               "at night")]}, DRAFT])
    out = pipeline.final_answer("Seniors in my block keep ragging me at night", fake)
    assert out["action"] == "safety" and "incident reported" in out["reason"]
    assert out["office"] == "STUDENT_SUPPORT"
    for text in ("I was harassed by a classmate", "I keep getting threats on chat", "my roommate got assaulted",
                 "I want to hurt myself", "thinking about suicide"):
        assert safety.trigger(topic(domain="HOSTEL"), text), text


def test_policy_questions_are_not_safety():
    for text in ("Whom should students report ragging to?", "What is the punishment for ragging?",
                 "What is the process for a sexual harassment complaint?", "Is there a helpline for harassment?"):
        assert safety.trigger(topic(), text) == "", text
    fake = FakeProvider(chat_replies=[{"topics": [topic(text="What is the anti-ragging policy?")]}, P2_FOUND])
    out = pipeline.answer("What is the anti-ragging policy?", "v2", fake, router="v2", search="dual_prog")
    assert out["action"] != "safety" and len(out["retrieval"]) == 8


def test_q10_q11_stay_info_with_their_saved_router_topics():
    """Q10 and Q11 (general policy questions, expected answer) must not trigger the card: their text and the topics
    P1 v2 gave them in the checkpoint run (read from files, not copied here)."""
    with open(TEST_DATA / "questions.csv", encoding="utf-8", newline="") as f:
        rows = {r["id"]: r for r in csv.DictReader(f) if r["id"] in ("Q10", "Q11")}
    saved = {}
    for line in (RUNS / "final_20261124-174710" / "outputs.jsonl").read_text(encoding="utf-8").splitlines():
        rec = json.loads(line)
        saved[rec["id"]] = rec
    for qid, row in rows.items():
        assert row["expected_action"] == "answer"
        t = saved[qid]["router"]["topics"][0]
        assert safety.trigger(t, t.get("text") or row["question"]) == "", qid
        assert safety.trigger(t, row["question"]) == "", qid
