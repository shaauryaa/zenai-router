# Fresh check (fresh_20261124-181523)

Final pipeline: P1 v2 + search routed5_all3_prog + P2 v2 + quote check v2 (tightened) + P3 v2, 2 topics answered. Questions: fresh check 1, now seen (used to choose today's fixes). Model gemini-3.5-flash-lite, temperature 0; commit 7188b9c5e9 (uncommitted changes); API calls 0, cache hits 23. Questions: `test-data/fresh_questions.csv`.

Pass = action correct, and for rows with a key_fact also key fact found and quote verified. Two-topic rows are scored on topic 1. **Pass: 9/10 (90%)**

| Test no. | Input (short) | Type | Expected output | Actual output (short) | Pass/Fail |
|---|---|---|---|---|---|
| F01 | How much are the examination charges each year, and how d... | Normal | answer; key fact "Examination Charges: ₹12,000 per academic year, payable i...", quote verified | not_found; draft to finance@zenai-demo.example: "Inquiry regarding annual examination charges an..." | Fail |
| F02 | What is the tuition fee for the second year of B.Tech Com... | Normal | answer; key fact "Year 2 / 3,90,000", quote verified | answer: "The tuition fee for the second year of B.Tech Computer Science Engi..." [Bennett University fee structure p.-; quote verified (near match)] | Pass |
| F03 | What are the dinner timings for hostel residents? | Normal | answer; key fact "Dinner 8:00 pm to 10:00 pm", quote verified | answer: "Dinner is served from 8:00 pm to 10:00 pm in the dining areas." [Student Handbook, Academic Year 2019-20 p.13; quote verified] | Pass |
| F04 | Which items am I allowed to keep in my hostel room? | Normal | answer; key fact "Only the following items are permitted in the hostel room...", quote verified | answer: "Only specific items like computers/laptops, mobile chargers, person..." [Student Handbook, Academic Year 2019-20 p.13; quote verified] | Pass |
| F05 | What is the minimum length of my university login password? | Normal | answer; key fact "Minimum Password length shall be set to 8 characters", quote verified | answer: "The minimum length of your university login password is 8 characters." [IT Policy p.144; quote verified] | Pass |
| F06 | I'm a BA Liberal Arts student. When are the supplementary... | Normal | answer; key fact "in January for Odd semester and June/July for Even semester", quote verified | answer: "Supplementary exams are held for each commiserating semester in Jan..." [Rules and Regulations for Undergradua... p.17; quote verified] | Pass |
| F07 | bonafide certificate banwane mein kitna time lagta hai? | Edge | answer; key fact "within 24 working hours", quote verified | answer: "Bonafide certificates are issued within 24 working hours." [Circular: Online Helpdesk for Student... p.1; quote verified (near match)] | Pass |
| F08 | waht is the hostl fee for a triple sharing room per year? | Edge | answer; key fact "Triple Sharing / ₹ 1,70,000 PA", quote verified | answer: "The hostel fee for a triple sharing room is ₹ 1,70,000 per annum." [Bennett University fee structure p.-; quote verified] | Pass |
| F09 | When is the convocation ceremony this year? | Edge | not_found; handoff draft | not_found; draft to academics@zenai-demo.example: "Inquiry regarding this year's convocation ceremony" | Pass |
| F10 | What are the library opening hours on weekends? | Edge | not_found; handoff draft | not_found; draft to services@zenai-demo.example: "Library opening hours on weekends" | Pass |

| Metric | Score |
|---|---|
| action | 9/10 (90%) |
| key_fact | 7/8 (88%) |
| quote_verified | 7/8 (88%) |
| doc_cited | 7/8 (88%) |
| format_valid | 10/10 (100%) |
| language | 0/1 (0%) |
| router_office | 9/10 (90%) |
| topic2_action | n/a |
| incomplete | 0/7 (0%) |
| needs_review | 0/7 (0%) |

## Rows for a human to read

- Incomplete (answer shown, key fact missing): none
- Needs review (answer shown, expected action not answer): none
