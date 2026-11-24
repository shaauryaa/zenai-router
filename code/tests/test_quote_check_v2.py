"""Quote check v2 (Milestone 2 sprint S1): exact rule first, then the near rule against ONE retrieved section.
No network."""
from helpdesk import kb_search, pipeline


def hit(text, cid="X/x.md#p1-1"):
    return kb_search.Hit(kb_search.Chunk(cid, "FINANCE", cid.split("#")[0], "X", 1, "", "", text), 1.0)


FEE_TABLE = hit("#### B.Tech (Example)\n\n| Year | Tuition fee (₹) |\n| --- | --- |\n| Year 1 | 2,10,000 |\n"
                "| Year 2 | 2,20,000 |\n| Year 3 | 2,30,000 |\n| Total Fees (₹) | 6,60,000 |", "F/fees.md#p0-1")
OCR_TABLE = hit("Turnaround Time:\n1 Issuance of Transcript, Character within 48 working\nCertificates, Name change "
                "etc.) hours\nUpdating of Address in within 24 working\nRecords hours", "C/circ.md#p1-1")
OCR_TYPO = hit("Eligibility: a student securing a CGPA of 7.5 and above in any programme, ona scale of 10, shall be eligible to receive "
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
    r = pipeline.verify_quote("a student securing a CGPA of 7.5 and above in any programme, on a scale of 10, shall be eligible to "
                              "receive a merit award equal to 5% of the Tuition Fee.", [OCR_TYPO])
    assert r["verified"] and r["rule"] == "near"


def test_near_rejects_one_number_changed():
    assert not pipeline.check_quote("Year 2: 2,25,000", [FEE_TABLE])[0]
    assert not pipeline.check_quote("a student securing a CGPA of 8.5 and above in any programme, on a scale of 10, shall be eligible "
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


def test_near_needs_every_content_word():
    base = "a student securing a CGPA of 7.5 and above in any programme, on a scale of 10, shall be eligible to receive a merit award"
    assert pipeline.verify_quote(base, [OCR_TYPO])["rule"] == "near"
    r = pipeline.verify_quote(base.replace("merit", "sports"), [OCR_TYPO])  # 1 word of 16 swapped
    assert not r["verified"]


def test_near_negation_words_are_content_words():
    # "not" is a kb_search stop word, but the quote check needs it in the section
    allowed = hit("Visitors including parents are allowed inside the hostel rooms after 8:00 pm.")
    r = pipeline.near_match("Visitors, including parents, are not allowed inside the hostel rooms", allowed.chunk.text)
    assert r == (False, "content words not in section: not")


def test_ocr_typo_next_to_a_number_is_rejected():
    # known cost of the both-neighbours rule: an OCR-merged word right beside a number breaks the number's pair
    typo = hit("a CGPA of 7.5 and above, ona scale of 10, shall be eligible")
    assert not pipeline.verify_quote("a CGPA of 7.5 and above, on a scale of 10, shall be eligible", [typo])["verified"]


SLOTS = hit("Breakfast 7:00 am to 9:00 am. Dinner 8:00 pm to 10:00 pm. Lunch 1:00 pm to 2:30 pm.\n"
            "Minimum length shall be 8 characters; at least 1 characters from each group.", "H/mess.md#p13-1")


def test_near_number_needs_both_neighbours():
    assert pipeline.verify_quote("Dinner: 8:00 pm to 10:00 pm", [SLOTS])["rule"] == "near"
    # 7:00 sits before "am" and "pm" follows 7:00 nowhere: (dinner, 7:00) is not in the section
    assert not pipeline.verify_quote("Dinner: 7:00 pm to 10:00 pm", [SLOTS])["verified"]
    # (1, characters) is in the section, (be, 1) is not: one pair is not enough
    assert not pipeline.verify_quote("Minimum length shall be: 1 characters", [SLOTS])["verified"]
    assert pipeline.verify_quote("Minimum length shall be: 8 characters", [SLOTS])["rule"] == "near"


def test_number_pairs_at_quote_edges_use_one_side():
    assert pipeline.number_pairs(["dinner", "800"]) == [("800", {("dinner", "800")})]
    assert pipeline.number_pairs(["390000"]) == [("390000", set())]


RULES = hit("Hostel rules. Students must not cook food in rooms. Visitors including parents are not allowed to go "
            "inside the hostel rooms. No out pass is required to move out of campus on working days.", "H/rules.md#p2-1")


def test_negation_guard_exact_rule():
    r = pipeline.verify_quote("out pass is required to move out of campus", [RULES])  # drops the leading "No"
    assert not r["verified"] and r["reason"].startswith("dropped negation")
    assert pipeline.verify_quote("No out pass is required to move out of campus", [RULES])["rule"] == "exact"


def test_negation_guard_near_rule_inside_quote():
    r = pipeline.verify_quote("Visitors including parents are allowed to go inside the hostel rooms!", [RULES])
    assert not r["verified"] and r["reason"].startswith("dropped negation")
    ok = pipeline.verify_quote("Visitors, including parents, are not allowed to go inside the hostel rooms!", [RULES])
    assert ok["rule"] == "near"


def test_negation_guard_conservative_on_tied_windows():
    # best windows (3 of the 4 quote words each) tie, one of them holds "never": rejected
    tied = hit("Visitors: park cars at the main gate. Staff: never park cars at the gate.")
    r = pipeline.verify_quote("Visitors park cars at the gate", [tied])
    assert not r["verified"] and r["reason"].startswith("dropped negation")
    # one clearly best window without a negation: accepted
    clear = hit("Visitors: park cars at the main gate. Staff: never park cars at the gate.")
    assert pipeline.verify_quote("Visitors: park cars at the main gate!", [clear])["verified"]


def test_number_abbreviation_is_not_a_negation():
    table = hit("S. No. 1 Issuance of Transcript within 48 working hours")
    assert pipeline.verify_quote("Issuance of Transcript within 48 working hours", [table])["rule"] == "exact"


def test_decide_reason_names_near():
    p2 = {"found": True}
    assert pipeline.decide(p2, True, "", "near")[1] == "P2 found, quote verified (near match, not word for word)"
    assert pipeline.decide(p2, True, "", "exact")[1] == "P2 found, quote verified"
