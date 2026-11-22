"""test-data/questions.csv: every key_fact is word for word on its expected kb page (helpdesk.check_questions)."""
import csv

from helpdesk.check_questions import QUESTIONS, check


def test_question_set_passes_the_checks():
    assert check() == []


def test_question_set_mix():
    rows = list(csv.DictReader(open(QUESTIONS, encoding="utf-8", newline="")))
    assert len(rows) == 24
    assert [sum(r["type"] == t for r in rows) for t in ("Normal", "Edge", "Invalid")] == [12, 8, 4]
    assert sum(r["language"] == "hinglish" for r in rows) == 2
