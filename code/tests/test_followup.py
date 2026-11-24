"""Clarify follow-up (Milestone 2 sprint S4): a short reply after a clarify is joined to the previous question."""
from helpdesk import followup, pipeline
from zenai.providers import FakeProvider


def topic(domain, rt, text, sq=""):
    return {"text": text, "domain": domain, "request_type": rt, "search_query": sq, "reason": "r"}


DRAFT = {"to": "x", "subject": "Question about the refund",
         "body": "Dear Finance Office,\nI could not find this.\n[Your name]\n[Enrollment no.]"}
P2_NOT_FOUND = {"found": False, "answer": "", "quote": "", "doc_title": "", "page": "", "language": "en"}


def test_two_turns_clarify_then_short_reply_runs_on_both():
    fake = FakeProvider(chat_replies=[
        {"topics": [topic("FEES", "vague", "how do I get it back")]},                      # turn 1: P1
        {"topics": [topic("FEES", "info", "how do I get my caution money back", "caution money refund")]},  # turn 2
        P2_NOT_FOUND, DRAFT])
    first_q = "how do I get it back"
    run_on, previous = followup.resolve(None, first_q)
    assert (run_on, previous) == (first_q, "")
    out1 = pipeline.final_answer(run_on, fake)
    assert out1["action"] == "clarify"
    last = followup.remember(out1, run_on)

    run_on, previous = followup.resolve(last, "the caution money")
    assert run_on == "how do I get it back the caution money" and previous == first_q
    out2 = pipeline.final_answer(run_on, fake)
    assert "how do I get it back the caution money" in fake.chat_requests[1][-1]["content"]  # P1 saw both turns
    assert out2["question"] == run_on and out2["action"] == "not_found"
    assert followup.FOLLOWUP_NOTE.format(previous=previous) == "Using your previous message: “how do I get it back”"


def test_no_join_when_long_or_not_after_clarify():
    clarify = {"question": "is it open", "action": "clarify"}
    assert followup.resolve(clarify, "one two three four five six seven eight") == (
        "is it open one two three four five six seven eight", "is it open")
    long_msg = "one two three four five six seven eight nine"
    assert followup.resolve(clarify, long_msg) == (long_msg, "")
    assert followup.resolve({"question": "is it open", "action": "answer"}, "the library") == ("the library", "")
    assert followup.resolve({"question": "", "action": "clarify"}, "the library") == ("the library", "")
    assert followup.resolve(clarify, "   ") == ("", "")
