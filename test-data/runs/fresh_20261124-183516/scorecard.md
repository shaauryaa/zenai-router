# Fresh check (fresh_20261124-183516)

Final pipeline: P1 v2 + search routed5_all3_prog + P2 v2 + quote check v2 (tightened) + P3 v2, 2 topics answered. Questions: fresh check 2, unseen (written after the freeze). Model gemini-3.5-flash-lite, temperature 0; commit 6a4c847679; API calls 27, cache hits 31. Questions: `test-data/fresh2_questions.csv`.

Pass = action correct, and for rows with a key_fact also key fact found and quote verified; two-question, safety and follow-up rows by the rules in test-data/README.md. **Pass: 11/18 (61%)**

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

| Metric | Score |
|---|---|
| action | 14/18 (78%) |
| key_fact | 8/14 (57%) |
| quote_verified | 10/14 (71%) |
| doc_cited | 9/14 (64%) |
| format_valid | 15/15 (100%) |
| language | 0/1 (0%) |
| router_office | 9/10 (90%) |
| topic2_action | 3/4 (75%) |
| incomplete | 3/11 (27%) |
| needs_review | 0/11 (0%) |
| turn1_clarify | 1/2 (50%) |
| safety_card | 2/2 (100%) |
| two_question_row | 3/4 (75%) |
| safety_row | 2/2 (100%) |
| followup_row | 1/2 (50%) |

## Rows for a human to read

- Incomplete (answer shown, key fact missing): F15 (expected answer): "Your university login password expires after 90 days."; F17 (expected answer): "There are no limits on internet bandwidth or data usage for valid academic purposes, bu..."; F28 (expected answer): "For the MBA program, a 'D' grade is considered the minimum passing grade."
- Needs review (answer shown, expected action not answer): none
