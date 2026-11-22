# Fresh check (fresh_20261122-214926)

Fresh check: the frozen final pipeline (P1 v2 + search routed5_all3 + P2 v2 + quote check + P3 v2) on 10 questions the
team wrote after the prompts and search were frozen (`test-data/fresh_questions_draft.txt` -> `test-data/fresh_questions.csv`,
committed in a2d3d54 "Add fresh check questions" before the run). Model gemini-3.5-flash-lite, temperature 0; commit
a2d3d54a81 (the only uncommitted file was the untracked team draft); API calls 30, cache hits 0. Prompt sha256 equal to
the final run's: P1 0d8fd3c7a1bf, P2 0e45708c06c8, P3 v2 43865836044b. One run, no re-run, no re-labelling, no tuning
after the results.

The run reuses `pipeline.final_answer` and the final test's scorer unchanged (`score_p2.score`, `final_test.passed`);
only the question file and the output folder differ from `python -m helpdesk.final_test` (runner copied to
`test-data/runs/fresh_20261122-214926/run_fresh.py`).

Pass = action correct, and for rows with a key_fact also key fact found and quote verified. **Pass: 6/10 (60%)**
(final test on the 24 seen questions: 21/24, 88%).

| Test no. | Input (short) | Type | Expected output | Actual output (short) | Pass/Fail |
|---|---|---|---|---|---|
| F01 | How much are the examination charges each year, and how d... | Normal | answer; key fact "Examination Charges: ₹12,000 per academic year, payable i...", quote verified | not_found; draft to finance@zenai-demo.example: "Inquiry regarding annual examination charges an..." | Fail |
| F02 | What is the tuition fee for the second year of B.Tech Com... | Normal | answer; key fact "Year 2 / 3,90,000", quote verified | not_found; draft to finance@zenai-demo.example: "Inquiry regarding second year B.Tech CSE tuitio..." | Fail |
| F03 | What are the dinner timings for hostel residents? | Normal | answer; key fact "Dinner 8:00 pm to 10:00 pm", quote verified | answer: "Dinner is served from 8:00 pm to 10:00 pm in the dining areas." [Student Handbook, Academic Year 2019-20 p.13; quote verified] | Pass |
| F04 | Which items am I allowed to keep in my hostel room? | Normal | answer; key fact "Only the following items are permitted in the hostel room...", quote verified | answer: "Only specific items like computers/laptops, mobile chargers, person..." [Student Handbook, Academic Year 2019-20 p.13; quote verified] | Pass |
| F05 | What is the minimum length of my university login password? | Normal | answer; key fact "Minimum Password length shall be set to 8 characters", quote verified | answer: "The minimum length of your university login password is 8 characters." [IT Policy p.144; quote verified] | Pass |
| F06 | I'm a BA Liberal Arts student. When are the supplementary... | Normal | answer; key fact "in January for Odd semester and June/July for Even semester", quote verified | not_found; draft to academics@zenai-demo.example: "Inquiry regarding supplementary exams schedule" | Fail |
| F07 | bonafide certificate banwane mein kitna time lagta hai? | Edge | answer; key fact "within 24 working hours", quote verified | not_found; draft to academics@zenai-demo.example: "Inquiry regarding processing time for bonafide..." | Fail |
| F08 | waht is the hostl fee for a triple sharing room per year? | Edge | answer; key fact "Triple Sharing / ₹ 1,70,000 PA", quote verified | answer: "The hostel fee for a triple sharing room is ₹ 1,70,000 per annum." [Bennett University fee structure p.-; quote verified] | Pass |
| F09 | When is the convocation ceremony this year? | Edge | not_found; handoff draft | not_found; draft to academics@zenai-demo.example: "Inquiry regarding this year's convocation ceremony" | Pass |
| F10 | What are the library opening hours on weekends? | Edge | not_found; handoff draft | not_found; draft to services@zenai-demo.example: "Library opening hours on weekends" | Pass |

(In the table a `|` inside a key fact is shown as `/`, as in final_test_table.md.)

Other metrics from the run's scorecard: key fact found 5/8, quote verified 4/8, right document cited 6/8, valid JSON
10/10, Hinglish reply 0/1 (F07), router office 9/10 (F03 routed to CAMPUS_SERVICES, still answered from the HOSTEL
handbook through the all-folders part of the search).

## Failures (cause read from `outputs.jsonl` and the retrieved chunk ids, no re-run)

- F01: P2 returned found=false although 5 of the 8 retrieved chunks contain the exact "Examination Charges: ₹12,000 per
  academic year..." line; the fee page also lists ₹7,000 and ₹2,500 examination charges for other programmes and the
  question names no programme. Cause: P2 (generation) declined; the label assumes the ₹12,000 programmes.
- F02: search found the right chunk (B.Tech CSE table, `bennett-fee-structure.md#p0-2`) and P2 answered correctly
  (₹3,90,000), but quoted the table row as "Year 2: 3,90,000" instead of "| Year 2 | 3,90,000 |", so the word-for-word
  quote check rejected it and the answer became not_found. Cause: quote check on table text.
- F06: search miss: BA Liberal Arts rulebook p.17 (the supplementary exam rule) was not in the top 8 (only its p.15
  was); the one retrieved chunk with the rule was another programme's (SCSET PG), which P2 correctly did not use.
  Cause: search.
- F07: search found the right chunk (circular p.1) and P2 answered correctly in English ("within 24 working hours"),
  but its quote joined two OCR table lines in an order that is not in the source ("...etc.) within 24 working
  hours"), so the quote check rejected it. Cause: quote check on OCR table text (the team's note expected this risk).

No row gave a wrong or invented answer: every failure ended as not_found with a handoff draft, and the F09/F10 drafts
contain no dates or hours. F08's answer gives the ₹1,70,000 fee but not the "up to 7%" increase in the team's expected
answer; the pass rule does not require it.

Raw run: `test-data/runs/fresh_20261122-214926/` (outputs.jsonl, run_meta.json, scorecard.md, table.csv, run_fresh.py).
