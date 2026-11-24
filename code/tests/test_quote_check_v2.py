"""Quote check v2 (Milestone 2 sprint S1): exact rule first, then the near rule against ONE retrieved section.
No network."""
from helpdesk import kb_search, pipeline


def hit(text, cid="X/x.md#p1-1"):
    return kb_search.Hit(kb_search.Chunk(cid, "FINANCE", cid.split("#")[0], "X", 1, "", "", text), 1.0)


FEE_TABLE = hit("#### B.Tech (Example)\n\n| Year | Tuition fee (₹) |\n| --- | --- |\n| Year 1 | 2,10,000 |\n"
                "| Year 2 | 2,20,000 |\n| Year 3 | 2,30,000 |\n| Total Fees (₹) | 6,60,000 |", "F/fees.md#p0-1")
OCR_TABLE = hit("Turnaround Time:\n1 Issuance of Transcript, Character within 48 working\nCertificates, Name change "
                "etc.) hours\nUpdating of Address in within 24 working\nRecords hours", "C/circ.md#p1-1")
OCR_TYPO = hit("Eligibility: a student securing a CGPA of 7.5 and above, ona scale of 10, shall be eligible to receive "
               "a merit award equal to 5% of the Tuition Fee.", "F/award.md#p3-1")
OTHER = hit("Visitors including parents are not allowed inside the hostel rooms after 8:00 pm.", "H/hostel.md#p2-1")


def test_exact_rule_still_first_and_recorded():
    r = pipeline.verify_quote("a CGPA of 7.5 and above", [OCR_TYPO])
    assert r == {"verified": True, "chunk_id": "F/award.md#p3-1", "reason": "", "rule": "exact"}


def test_near_accepts_table_row_reformatted():  # F02-style
    r = pipeline.verify_quote("Year 2: 2,20,000", [OTHER, FEE_TABLE])
    assert r["verified"] and r["rule"] == "near" and r["chunk_id"] == "F/fees.md#p0-1"


def test_near_accepts_ocr_lines_in_other_order():  # F07-style
    r = pipeline.verify_quote("Issuance of Transcript, Character Certificates, Name change etc.) within 48 working hours",
                              [OCR_TABLE])
    assert r["verified"] and r["rule"] == "near"


def test_near_accepts_ocr_typo():  # Q15-style
    r = pipeline.verify_quote("a student securing a CGPA of 7.5 and above, on a scale of 10, shall be eligible to "
                              "receive a merit award equal to 5% of the Tuition Fee.", [OCR_TYPO])
    assert r["verified"] and r["rule"] == "near"


def test_near_rejects_one_number_changed():
    assert not pipeline.check_quote("Year 2: 2,25,000", [FEE_TABLE])[0]
    assert not pipeline.check_quote("a student securing a CGPA of 8.5 and above, on a scale of 10, shall be eligible "
                                    "to receive a merit award equal to 5% of the Tuition Fee.", [OCR_TYPO])[0]


def test_near_rejects_quote_from_a_different_chunk():
    # the words are in OTHER, the retrieved sections are the fee table and the OCR circular
    q = "Visitors including parents are not allowed inside the hostel rooms after 8:00 pm."
    assert pipeline.verify_quote(q, [OTHER])["rule"] == "exact"
    assert not pipeline.check_quote(q, [FEE_TABLE, OCR_TABLE, OCR_TYPO])[0]


def test_near_needs_all_conditions_in_one_section():
    # numbers from one section, words from another: not accepted
    q = "Year 2: 2,20,000 within 24 working hours"
    assert not pipeline.check_quote(q, [FEE_TABLE, OCR_TABLE])[0]


def test_near_rejects_invented_sentence():
    r = pipeline.verify_quote("Students may pay the tuition fee in twelve monthly instalments without any penalty.",
                              [FEE_TABLE, OCR_TABLE, OCR_TYPO, OTHER])
    assert not r["verified"] and r["rule"] is None and r["chunk_id"] is None


def test_near_needs_four_content_words():
    r = pipeline.verify_quote("Year 3", [FEE_TABLE])  # short, but word for word: the exact rule still accepts it
    assert r["verified"] and r["rule"] == "exact"
    r = pipeline.verify_quote("Year: 3", [FEE_TABLE])  # 2 content words, not word for word: near does not apply
    assert not r["verified"] and "near rule not applicable" in r["reason"]


def test_near_word_share_threshold():
    base = "a student securing a CGPA of 7.5 and above shall be eligible to receive a merit award"
    assert pipeline.verify_quote(base.replace("merit", "sports"), [OCR_TYPO])["verified"]  # 10/11 words = 91%
    assert not pipeline.verify_quote(base.replace("merit award", "sports prize"), [OCR_TYPO])["verified"]  # 82%


def test_decide_reason_names_near():
    p2 = {"found": True}
    assert pipeline.decide(p2, True, "", "near")[1] == "P2 found, quote verified (near match, not word for word)"
    assert pipeline.decide(p2, True, "", "exact")[1] == "P2 found, quote verified"
