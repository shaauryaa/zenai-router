# Fresh check 2 (fresh_20261124-183516)

Fresh check 2: the frozen final pipeline (P1 v2 + programme-aware search routed5_all3_prog + P2 v2 + quote check v2
(tightened) + P3 v2, two topics answered, safety card, clarify follow-up) on 18 questions the team wrote after the
pipeline was frozen (`test-data/fresh2_questions_draft.txt` -> `test-data/fresh2_questions.csv`). F11-F20 are one
question each; F21-F28 are two-question messages (F21-F24), safety reports (F25, F26) and two-turn follow-ups (F27,
F28). The labels and the scoring rules (`test-data/README.md`) were committed before the run in 41506e1 "Add fresh
check 2 questions F21-F28 and scoring rules"; the runner change that applies them is 6a4c847 (tag `m2-final-24nov`).
Model gemini-3.5-flash-lite, temperature 0; commit 6a4c847679, no uncommitted changes. Prompt sha256 equal to the 24
Nov final run's: P1 0d8fd3c7a1bf, P2 0e45708c06c8, P3 v2 43865836044b. No re-labelling and no tuning after the results.

API calls: 79 in total. The first attempt stopped at F23 on a provider error (HTTP 503, "model is currently
experiencing high demand") after 52 calls and saved nothing, as the runner does on any provider error. The same
command was then run again: F11-F22 came from the response cache (temperature 0, identical replies, the same
Pass/Fail as printed by the first attempt) and F23-F28 made 27 new calls. The run folder records that second
invocation (API calls 27, cache hits 31).

Run: `python -m helpdesk.final_test --questions test-data/fresh2_questions.csv --label "fresh check 2, unseen
(written after the freeze)" --max-calls 100` (second invocation `--max-calls 48`, the budget left).

Pass rules (from `test-data/README.md`): one-question rows as in every final run (action correct, and key fact found
and quote verified where a key fact is set); two-question rows only if both parts have the right action and every
answered part has its key fact and a verified quote; safety rows if the action is safety and the card shows the
contacts; follow-up rows if turn 1 is clarify and turn 2, run through the app's follow-up function, passes like a
normal row. **Pass: 11/18 (61%)**

| Row type | Pass |
|---|---|
| One question (F11-F20) | 5/10 |
| Two questions in one message (F21-F24) | 3/4 |
| Safety reports (F25, F26) | 2/2 |
| Two-turn follow-ups (F27, F28) | 1/2 |
| **All** | **11/18 (61%)** |

| Test no. | Input (short) | Type | Expected output | Actual output (short) | Pass/Fail |
|---|---|---|---|---|---|
| F11 | I'm paying my fee after the late registration window has... | Normal | answer; key fact "late registration fee of ₹5,000", quote verified | answer: "Fee payment after 29 July 2026 requires prior approval from the Reg..." [Annexure I: Rules for Late Fee Payment p.-; quote verified] | Pass |
| F12 | My brother is already studying at Bennett. Can I get a sc... | Normal | answer; key fact "A scholarship amount of 10% is offered to the eligible st...", quote verified | answer: "Yes, you can get a 10% scholarship called the Sibling Scholarship i..." [Scholarship Policy, Academic Year 202... p.3; quote verified] | Pass |
| F13 | Can I use an electric iron in my hostel room? | Normal | answer; key fact "Electrical appliances like electrical irons, heaters", quote verified | not_found; draft to hostel@zenai-demo.example: "Inquiry regarding use of electric iron in hoste..." | Fail |
| F14 | If the university cancels my hostel allotment because I b... | Normal | answer; key fact "NO REFUND of fees is permissible", quote verified | answer: "No, if your hostel allocation is cancelled due to a breach of the c..." [Fee Refund Policy, Academic Year 2026-27 p.3; quote verified] | Pass |
| F15 | After how many days does my university login password exp... | Normal | answer; key fact "Maximum Password age shall be set to 45 days", quote verified | answer: "Your university login password expires after 90 days." [Student Handbook, Academic Year 2019-20 p.17; quote verified] | Fail |
| F16 | I'm a BBA student and I was debarred for low attendance.... | Normal | answer; key fact "shall not be allowed to take the supplementary Examination", quote verified | handoff; draft to academics@zenai-demo.example: "Inquiry regarding supplementary exam eligibilit..." | Fail |
| F17 | hostel mein wifi ki data limit hoti hai kya? | Edge | answer; key fact "There is no limit on the bandwidth or data usage for vali...", quote verified | answer: "There are no limits on internet bandwidth or data usage for valid a..." [Student Handbook, Academic Year 2019-20 p.17; quote verified] | Fail |
| F18 | can i keep a pet dog in the hostle? | Edge | answer; key fact "keep pets", quote verified | not_found; draft to hostel@zenai-demo.example: "Inquiry regarding keeping a pet dog in the hostel" | Fail |
| F19 | How much does it cost to apply for re-evaluation of my an... | Edge | not_found; handoff draft | not_found; draft to academics@zenai-demo.example: "Inquiry regarding answer sheet re-evaluation ap..." | Pass |
| F20 | What does a cup of coffee cost at the campus cafe? | Edge | not_found; handoff draft | not_found; draft to services@zenai-demo.example: "Inquiry regarding campus cafe coffee price" | Pass |
| F21 | How do I get my security deposit back when I leave, and h... | Edge | part 1 answer; key fact "No-dues certificate shall be required for refun...", quote verified / part 2 answer; key fact "Normal turn-around time for the laundry is 3-4...", quote verified | answer: "To get your security deposit back, you need a no-dues certificate,..." [Fee Refund Policy, Academic Year 2026-27 p.1; quote verified]; topic 2: answer: "The normal turn-around time for the laundry is 3-4 days." [Student Handbook, Academic Year 2019-20 p.22; quote verified] | Pass |
| F22 | My login got locked after I typed the wrong password too... | Edge | part 1 answer; key fact "Lockout Duration shall be set to 30 minutes", quote verified / part 2 answer; key fact "10:00 AM to 1:00 PM", quote verified | answer: "Your login lockout lasts for 30 minutes." [IT Policy p.144; quote verified]; topic 2: not_found; draft to academics@zenai-demo.example: "Inquiry regarding Registrar helpdesk counter ti..." | Fail |
| F23 | I'm a BBA student. What CGPA do I need to be promoted to... | Edge | part 1 answer; key fact "minimum CGPA of 3 on 10-point scale to be promo...", quote verified / part 2 answer; key fact "Rs.1 lakh cashless medical insurance", quote verified | answer: "To be promoted to the second year, you need to obtain a minimum CGP..." [Rules and Regulations for Bachelor of... p.25; quote verified]; topic 2: answer: "Yes, the University provides Rs.1 lakh cashless medical insurance t..." [Student Handbook, Academic Year 2019-20 p.14; quote verified] | Pass |
| F24 | What happens to my scholarship if I hide some information... | Edge | part 1 answer; key fact "all such financial support will be recovered by...", quote verified / part 2 not_found; handoff draft | answer: "If an applicant conceals, suppresses, or distorts information that..." [Scholarship Policy, Academic Year 202... p.6; quote verified (near match)]; topic 2: not_found; draft to services@zenai-demo.example: "Inquiry regarding gym membership cost" | Pass |
| F25 | Some seniors in my hostel make me clean their rooms every... | Edge | safety; contacts card copied from the KB, then a draft to Student Support | safety (contacts card); draft to studentsupport@zenai-demo.example: "Urgent assistance needed regarding hostel haras..."; card: 1 contact lines from kb/STUDENT_SUPPORT/anti-ragging-and-sexual-harassment-contacts.md | Pass |
| F26 | ek professor mujhe raat ko baar baar messages bhej raha h... | Edge | safety; contacts card copied from the KB, then a draft to Student Support | safety (contacts card); draft to studentsupport@zenai-demo.example: "Urgent assistance needed regarding professor me..."; card: 1 contact lines from kb/STUDENT_SUPPORT/anti-ragging-and-sexual-harassment-contacts.md | Pass |
| F27 | T1 "fees?" / T2 "how much does hostel fee rise ye..." | Edge | turn 1 clarify; turn 2 answer; key fact "The Hostel fee is subject to an annual increase of upto 7%", quote verified | turn 1 clarify: "Is your question for the Finance Office or a different of..."; turn 2 (joined to "fees?"): answer: "The hostel fee is subject to an annual increase of up to 7%." [Bennett University fee structure p.-; quote verified] | Pass |
| F28 | T1 "exam rules" / T2 "MBA, what grade counts as pass?" | Edge | turn 1 clarify; turn 2 answer; key fact "pass (D and above) grade", quote verified | turn 1 answer: "As a general guideline, there shall be two written examinations, sp..." [Rules and Regulations for Undergradua... p.13; quote verified]; turn 2 (not joined): answer: "For the MBA program, a 'D' grade is considered the minimum passing..." [Academic Rules Master of Business Adm... p.20; quote verified] | Fail |

(In the table a `|` inside a cell is shown as `/`, as in final_test_table.md.)

Other metrics from the run's scorecard (for a two-question row a metric holds only if it holds for every part; for a
follow-up row they are turn 2's): final action correct 14/18, key fact found 8/14, quote verified 10/14, right
document cited 9/14, valid JSON 15/15, Hinglish reply 0/1 (F17), router office 9/10 (F14 routed to FINANCE), topic 2
action 3/4, turn 1 clarify 1/2, safety card with contacts 2/2. Incomplete (answer shown, key fact missing): 3/11
(F15, F17, F28). Needs review (answer shown, expected action not answer): 0/11.

## Wrong answers shown (human-checked)

The scorer never decides that an answer is wrong; it lists rows for a person to read. A person read every
"incomplete" row against the documents (no re-run, no label change):

| Row | Verdict | Answer shown | What the documents say |
|---|---|---|---|
| F15 | **WRONG** (contradicts the documents) | "Your university login password expires after 90 days." Quote: "Changing passwords every 90 days." (Student Handbook 2019-20, 07/2019, p.17) | IT Policy (06/2024) p.144: "Maximum Password age shall be set to 45 days" |
| F17 | INCOMPLETE (true, key fact missing) | "There are no limits on internet bandwidth or data usage for valid academic purposes, but large consumption requires faculty approval, and you can buy the Bennett Mobile Plan for non-academic usage." | Handbook p.17: "There are no restrictions on the use of internet bandwidth and/or data downloads for valid academic purposes." and "Large consumption of bandwidth or data will be permitted upon approvals from the respective faculty."; p.34 (key fact): "There is no limit on the bandwidth or data usage for valid academic reasons." Same rule, other page |
| F28 (turn 2) | INCOMPLETE (true, key fact missing) | "For the MBA program, a 'D' grade is considered the minimum passing grade." | MBA rules p.20: "it is the minimum passing grade in any course" (also p.25); key fact on p.15: "pass (D and above) grade". The quote was matched to the same sentence in the SEAS B.Tech rules |

**Wrong answers shown (human-checked): 1/18, F15.** The automatic scorer filed F15 as *incomplete* (answer shown, key
fact missing), the same as the two true answers, so the "incomplete" count alone does not separate wrong answers
from incomplete ones. F28's turn 1 ("two written examinations i.e Mid Term and an End Term Examination", from the BA
Journalism rules) is a real rule, not contradicted by the documents, but it answers a question that named no
programme from one programme's rulebook; it is counted as a failure (turn 1 not clarify), not as a wrong answer.

The run was retried once: the first attempt stopped at F23 on HTTP 503 and saved nothing; in the second, F11-F22 came
back identical from the cache (see the top of this file).

## Failures (cause read from `outputs.jsonl` and the retrieved chunk ids, no re-run)

- F13 (electric iron): the chunk with the rule (`hostel-standing-orders.md#p1-2`, "Electrical appliances like
  electrical irons, heaters...") was retrieved, but P2 returned found=false. Cause: P2 (generation) declined.
- F15 (password expiry): the expected IT Policy p.144 was the top retrieved chunk, but P2 answered "90 days" from the
  Student Handbook 2019-20 p.17 ("Changing passwords every 90 days."), also retrieved through the all-folders part
  of the search. The quote is real and verified, so the wrong number was shown as an answer. Cause: P2 picked the
  wrong source; the quote check cannot catch it.
- F16 (BBA supplementary exam after debarment): P1 gave request_type needs_human, so the row became a handoff with no
  search. Cause: router request_type.
- F17 (Hinglish, hostel wifi data limit): routed to IT; P2 answered correctly in substance from the Student Handbook
  p.17 ("There are no restrictions on the use of internet bandwidth and/or data downloads for valid academic
  purposes."), not the expected p.34 (retrieved, but not used), so the key fact "There is no limit on the bandwidth
  or data usage..." is missing. The reply is in English. Cause: key fact on a different page (same rule, other
  wording).
- F18 (pet dog, typo "hostle"): search miss: Standing Orders p.2 ("keep pets") was not in the top 8 for the query
  "pet policy in hostel"; P2 correctly said not found. Cause: search.
- F22 (lockout + Registrar counter): part 1 passed (30 minutes, IT Policy p.144). Part 2 was routed to ACADEMICS
  (expected CAMPUS_SERVICES), but the search still retrieved the circular p.1 and P2's answer was right ("10:00 AM to
  1:00 PM and from 2:00 PM to 4:00 PM"). Its quote joined the two OCR lines with a "�" character that is not in the
  source, so the quote check rejected it and the part became not_found, with a draft to Academics. Cause: quote check
  on OCR text (P2 quote copying).
- F28 (follow-up "exam rules" -> "MBA, what grade counts as pass?"): turn 1 was not clarify: P1 treated "exam rules"
  as an info question and P2 answered from the BA (Journalism & Mass Communication) rules p.13 (a real, verified
  sentence, but from one programme chosen at random). Because turn 1 was not clarify, turn 2 ran on its own (not
  joined); it was answered from the MBA rules ("a 'D' grade is considered the minimum passing grade"), but its quote
  was matched to the SEAS B.Tech rules p.24 chunk (the same sentence is in the MBA rules p.20) and the key fact
  "pass (D and above) grade" (MBA p.15) is missing. Cause: router request_type (turn 1 should be vague); turn 2 is
  incomplete by the key-fact rule.

## Passes worth a note

- F14 passed, but from the Fee Refund Policy p.3 (routed to FINANCE), not the expected hostel refund policy p.1; the
  key fact "NO REFUND of fees is permissible" is in both (right document cited: no).
- F21, F23 and F24: both parts handled on their own; F23 part 1 came from the BBA rules (programme-aware search), and
  F24 part 2 (gym price) became not_found with a draft to Campus Services, no amount invented. F24 part 1's quote was
  verified by the near rule.
- F25 and F26: both safety by trigger a (P1 gave STUDENT_SUPPORT / needs_human; the Hinglish F26 has no English
  incident words). The card shows 1 contact line copied from
  `kb/STUDENT_SUPPORT/anti-ragging-and-sexual-harassment-contacts.md`, then a draft to Student Support.
- F27: turn 1 "fees?" was clarify; the reply was joined ("fees? how much does hostel fee rise yearly") and answered
  with the "upto 7%" line from the fee structure page.

No row shows an invented price or fee: F19, F20 and F24 part 2 ended as not_found with a handoff draft. One wrong
answer was shown with a verified quote (F15, 90 days instead of 45), found by a person, not by the scorer.

Error categories and planned fixes (none built): `docs/iteration_log.md`, "Error analysis: fresh check 2".

Raw run: `test-data/runs/fresh_20261124-183516/` (outputs.jsonl, run_meta.json, scorecard.md, table.csv).
