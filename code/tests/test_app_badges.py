"""Honest source badges in the Streamlit app (code/app.py): number check, programme check, older-document tag.
Display-only checks: they never change the pipeline's result. No LLM call."""
import app


# 1. Number check
def test_number_missing_from_quote_is_flagged():
    answer = "You need a minimum attendance of 70% in a course during a semester."
    assert app.numbers_not_in_quote(answer, "A student must have a minimum attendance of") == ["70"]


def test_every_number_in_quote_is_not_flagged():
    answer = ("For withdrawal requests received after 30 September 2026 and up to 31 October 2026, you will not get a "
              "full refund; the refund will be processed after deducting a processing fee of up to Rs. 1,000.")
    quote = ("For Withdrawal/Cancellation requests received after 30 September 2026 and up to 31 October 2026, the "
             "refund shall be processed after deduction of a processing fee, which shall not exceed Rs. 1,000.")
    assert app.numbers_not_in_quote(answer, quote) == []


def test_number_formats_and_duplicates():
    assert app.numbers_not_in_quote("Rs. 1000 within 45 days", "a fee of Rs. 1,000") == ["45"]
    assert app.numbers_not_in_quote("45 days, then 45 more", "no numbers here") == ["45"]
    assert app.numbers_not_in_quote("Laundry takes 3-4 days.", "Normal turn-around time is 3-4 days.") == []
    assert app.numbers_not_in_quote("No numbers at all.", "") == []


# 2. Programme check
def test_btech_question_with_masters_source_is_a_mismatch():
    assert (app.programme_mismatch("What is the minimum attendance I need in a course in B.Tech?",
                                   "SCSET Academic Rules for Master's Programme") == "Master's programmes")


def test_matching_or_generic_programme_is_not_a_mismatch():
    assert app.programme_mismatch("I'm doing my btech, what is the pass mark?", "B.Tech Academic Regulations") is None
    assert app.programme_mismatch("MBA, what grade counts as pass?", "Rules for Master's Programme") is None
    assert app.programme_mismatch("Undergraduate attendance rule?", "B.Tech Academic Regulations") is None


def test_no_programme_on_either_side_is_not_a_mismatch():
    assert app.programme_mismatch("How do I get my security deposit back?", "Fee Refund Policy 2026-27") is None
    assert app.programme_mismatch("What is the attendance rule?", "SCSET Academic Rules for Master's Programme") is None
    assert app.programme_mismatch("B.Tech attendance rule?", "Student Handbook, Academic Year 2019-20") is None


def test_specific_mismatch_names_the_source_programme():
    assert app.programme_mismatch("Is there a supplementary exam in MBA?", "BBA Programme Rules") == "BBA"
    assert app.programme_mismatch("PhD coursework credits?", "M.Tech Regulations") == "M.Tech"


def test_programme_words_inside_other_words_do_not_count():
    assert app.programmes_in("biotechnology at the embassy, a combat sport") == []
    assert app.programmes_in("M.Tech and MBA") == [("M.Tech", "pg"), ("MBA", "pg")]


# 3. Older document
def test_older_document_year():
    assert app.older_year("07/2019") == 2019
    assert app.older_year("2019-20") == 2019
    assert app.older_year("2021-2022") is None  # an academic year counts by its later year
    assert app.older_year("03/2022") is None
    assert app.older_year("2026-2027") is None
    assert app.older_year("unknown") is None
    assert app.older_year(None) is None
