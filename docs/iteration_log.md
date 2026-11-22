# Iteration log: P1 router, P2 grounded answer and P3 handoff draft

Every number below is read from the run folders under `test-data/runs/` (scorecard.md, run_meta.json). All runs use
test-data/questions.csv (24 questions), model gemini-3.5-flash-lite, temperature 0, reasoning_effort minimal. Metric
definitions are in `code/helpdesk/score_p2.py`. Commands: `python -m helpdesk.score_p2 <P2 version> --router v1|v2
--search route5|routed5_all3 --name <name>`, `--rescore <run> --name <name>` (offline) and `python -m helpdesk.route_eval`.

## Limitations

The same 24 questions were used to pick each change (by reading the errors of the previous run) and to measure its
effect. The final numbers are therefore optimistic: they show that the changes fix the failures they were aimed at,
not how the pipeline does on new questions. A fresh, unseen question set is planned for Milestone 3. Each row is one
run at temperature 0, so a single question flipping (for example Q09 between step 3 and step 4) is within run-to-run
sensitivity to prompt wording and is not strong evidence on its own. The P1 v2 routing number on test_set.csv is on a
seen set (see below).

## Table 1: P2 versions

| Version | What changed | Why | Setup | Action | Key fact | Quote verified | Doc cited | Valid JSON | Language (Hinglish) | Router office | Run |
|---|---|---|---|---|---|---|---|---|---|---|---|
| v1 | Milestone 1 baseline prompt; plain-text reply. Code reads not_found from the fixed sentence and the quote from the first pair of double quotes. | Baseline. | P1 v1, search route5, original quote check | 17/24 (71%) | 8/16 (50%) | 9/16 (56%) | 11/16 (69%) | n/a | 1/2 | 17/17 | `P2_v1_20261122-184456` |
| v2 | Same rules; reply is one JSON object {found, answer, quote, doc_title, page, language}. | v1's free text has to be guessed at; fields make found/quote/document checkable. | same as v1 | 17/24 (71%) | 9/16 (56%) | 9/16 (56%) | 11/16 (69%) | 15/15 | 1/2 | 17/17 | `P2_v2_20261122-184902` |
| v3 | v2 + quote copied character for character (keep `**`, line-end hyphens); Hinglish matched by meaning; reply in the question's language also when not found; two worked examples (Hinglish answer, refusal). | v2 failures Q03 (`**` dropped), Q10 (OCR hyphen joined), Q14 (Hinglish refused, in English). | same as v1 | 16/24 (67%) | 8/16 (50%) | 8/16 (50%) | 9/16 (56%) | 15/15 | 1/2 | 17/17 | `P2_v3_20261122-185126` |
| v4 | v2 + one rule only: "The documents are in English. If the question is in Hinglish, match it to the documents by meaning and reply in Hinglish, including when you can't find the answer." No examples. | Q14 (Hinglish) refused although its page was retrieved. v3's refusal example was left out because it turned Q01 into a refusal. | P1 v2, search routed5_all3, new quote check (step 4) | 21/24 (88%) | 11/16 (69%) | 13/16 (81%) | 13/16 (81%) | 18/18 | 2/2 | 17/17 | `step4_P1v2_search8_P2v4_20261122-193227` |

v1-v3 share one setup and compare directly. v4 was only run in the step 4 setup; its fair comparison is v2 in the
same setup (step 3: 22/24 actions, 14/16 key fact, 14/16 quote, 14/16 document, 2/2 language). On identical retrieved
chunks (step 3 and step 4 retrieve exactly the same chunks for every question), v4 turned Q09 from a correct answer
into found=false and worded Q06 and Q12 so that the key fact no longer appears verbatim. Q14, the question v4 was
written for, was already answered in Hinglish by v2 in step 3: its answer sentence is in the second chunk of refund
policy page 1 (`fee-refund-policy-2026-27.md#p1-2`), which no run before step 3 retrieved (they had only `#p1-1`). So
Q14 was a search miss, not a Hinglish failure; the earlier diagnosis "page 1 was retrieved" (v3 error table below)
was wrong at chunk level.
**Best P2: v2**, copied to `prompts/final/P2_grounded_answer.md`.

## Table 2: pipeline steps

Starting point: the prompt-4 error analysis of v3's 8 errors (3 router request_type, 3 search missed the page, 1
Hinglish, 1 v3 refusal example; the Hinglish one, Q14, later turned out to be a search miss, see the note under
Table 1). Each step changes one thing and re-runs all 24 questions. P2 = v2 in steps 1-3.

| Step | Change | P1 | Search | P2 | Action | Key fact | Quote verified | Doc cited | Valid JSON | Language (Hinglish) | Router office | API calls (cache hits) | Run |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Baseline | P2 v2 run as recorded | v1 | route5 | v2 | 17/24 (71%) | 9/16 (56%) | 9/16 (56%) | 11/16 (69%) | 15/15 | 1/2 | 17/17 | 18 (23) | `P2_v2_20261122-184902` |
| 1 | Quote check normalisation: strip `**` and `__`, join OCR line-end hyphens ("-\n"; the section is matched with the hyphen kept and with it dropped), collapse whitespace, on quote and sections. Baseline re-scored offline. | v1 | route5 | v2 | 19/24 (79%) | 9/16 (56%) | 11/16 (69%) | 11/16 (69%) | 15/15 | 1/2 | 17/17 | 0 (offline) | `P2_v2_requote_20261122-190741` |
| 2 | Router P1 v2: STUDENT_SUPPORT domain; request_type rule (policy questions are info); new `search_query` field (not used for search yet) | v2 | route5 | v2 | 21/24 (88%) | 11/16 (69%) | 13/16 (81%) | 13/16 (81%) | 18/18 | 1/2 | 17/17 | 34 (15) | `step2_P1v2_P2v2_20261122-190814` |
| 3 | Search with P1 v2's search_query (fallback: the question); top 5 from the routed folder + top 3 from all folders (k=8) | v2 | routed5_all3 | v2 | **22/24 (92%)** | **14/16 (88%)** | **14/16 (88%)** | **14/16 (88%)** | 18/18 | 2/2 | 17/17 | 23 (23) | `step3_P1v2_search8_P2v2_20261122-192957` |
| 4 | P2 v4 (v2 + one Hinglish rule) | v2 | routed5_all3 | v4 | 21/24 (88%) | 11/16 (69%) | 13/16 (81%) | 13/16 (81%) | 18/18 | 2/2 | 17/17 | 19 (23) | `step4_P1v2_search8_P2v4_20261122-193227` |

What each step did (from the per-question tables in each scorecard.md):

- Step 1 (no API call): Q03 (quote without the source's `**`) and Q10 ("Anti-Ragging" vs "Anti-\nRagging") now
  pass the quote check, so both become answers. Q10's quote is a real passage from page 7 of the anti-ragging rules,
  not the expected page 5, and its key fact is still missing.
- Step 2: Q06 and Q11 are now routed correctly and answered; Q10 is routed to STUDENT_SUPPORT and answered. Q09 is now
  info (correct) but reaches P2 without the SCSET page 9 in the top 5 and becomes not_found. Q07 (guest wifi page not
  retrieved) and Q14 (Hinglish refused) remain.
- Step 3: the English search_query and wider search bring in IT Policy p.189 (Q07) and the refund chunk `#p1-2`
  for Q14, which is now answered in Hinglish. Q09 becomes a correct action with the right rule ("No makeup
  examination is allowed for end semester examination"), but from the SCSET rules for Master's programmes p.9, not
  the expected SCSET undergraduate rules p.9 (doc cited = wrong); the UG page is still not retrieved. Two new errors: Q15 (P2's longer quote writes "on a scale"
  where the OCR text has "ona scale", so the quote check rejects a correct 8.0 CGPA answer) and Q16 (search_query
  "wifi network account sharing policy" lacks "password", so IT Policy p.11 is not retrieved).
- Step 4: no retrieval change; Q09 regresses to not_found (see Table 1).

Final configuration: P1 v2 + search routed5_all3 + P2 v2 (step 3). P1 v2 is in `prompts/final/P1_router.md`, P1 v1
stays in `prompts/v1/P1_router.md` and `code/zenai/llm_router.py`.

## Questions still wrong in the final configuration (step 3)

| id | expected | got | cause |
|---|---|---|---|
| Q15 | answer | not_found | quote check: the OCR source has "ona scale"; P2 quoted "on a scale". Answer itself correct (8.0) |
| Q16 | answer | not_found | search: P1 v2's search_query omits "password", IT Policy p.11 not retrieved (topic 1 of a two-topic row) |
| Q09 | answer | answer (scored correct) | wrong document: the same rule quoted from the SCSET Master's rules p.9; the UG rules page is not retrieved. Counted under "doc cited" only |

## P1 v2 on the 60-question routing set (seen set)

`python -m helpdesk.route_eval` ran P1 v2 alone on test-data/test_set.csv. This is a **seen set**: v1's errors on it
were studied before P1 v2 was written, so it is not a clean test of v2 (the prompt itself was written from
questions.csv failures; no test_set text was used). Same definitions as v1's llm_only baseline.

| Metric | P1 v1 (frozen, `test-data/results/20260927-032804_test`) | P1 v2 (`test-data/runs/P1_v2_seen_test_set_20261122-192440`) |
|---|---|---|
| Routing accuracy (n = 60) | 85% | 50/60 (83%) |
| Routing accuracy, either office (n = 60) | 93% | 55/60 (92%) |
| Action accuracy from request_type (n = 70) | 74% (llm_only) | 53/70 (76%) |

P1 v2 does not improve office routing on this set (one row lower, within noise for n = 60). Of its 10 errors, 5
pick the labelled secondary office of a two-office row and 2 more are CAMPUS_SERVICES rows routed to IT. It predicted STUDENT_SUPPORT on
no row. Its request_type rule gives +2 points of action accuracy.

## P3 handoff draft: v1 -> v2

P3 v1 was the only P3 version in the final run `final_20261122-201923` (pass 21/24). Reading its five drafts showed
one wording problem, in Q19 (action handoff, reason `needs the student's own record`):

> I am writing to ask how much fee is still pending on my account for this semester. Since ZEN AI could not answer
> this because it needs my own record, could you please check my own record and reply?

The model copied the reason phrase into the email and then followed the record rule, so the request appears twice,
and the email talks about ZEN AI although the student sends it. P3 v2 (`prompts/v2/P3_handoff.md`, now also
`prompts/final/P3_handoff.md`; v1 kept in `prompts/v1/`) changes two lines of the Rules: the record rule asks the
office to "look up the student's account or details and reply", and a new rule says to state the question once and
the request once, not to copy the "why" phrase word for word, and not to mention ZEN AI. Inputs, placeholders and
JSON format are unchanged.

Only the five rows that get a P3 draft were re-run (`python -m helpdesk.final_handoff_rerun --base
final_20261122-201923`, run `final_p3v2_20261122-212027`). P1 and P2 replies came from the cache, so actions and
Pass/Fail are unchanged (the script stops without saving if either changes). Pass stays 21/24.

| id | action | P3 v1 subject | P3 v2 subject |
|---|---|---|---|
| Q15 | not_found | Inquiry regarding SCSET 10% academic scholarship CGPA requirement | Query regarding SCSET 10% academic scholarship CGPA requirement |
| Q16 | not_found | Inquiry regarding WiFi login sharing and campus curfew | Inquiry regarding WiFi login sharing and campus curfew |
| Q17 | not_found | Inquiry regarding swimming pool timings on Sundays | Inquiry regarding Sunday swimming pool timings |
| Q18 | not_found | Inquiry regarding college bus availability after 9 pm | Inquiry regarding college bus availability to Pari Chowk metro |
| Q19 | handoff | Inquiry regarding pending fee for this semester | Inquiry regarding pending semester fee |

Q19 body with P3 v2:

> I would like to know how much fee is still pending on my account for this semester. Could you please look up my
> account details and let me know the status?

The four not_found drafts keep the same content (question, "could not find the answer in the official university
documents", a request to answer). This is a wording fix checked by reading five drafts, not a measured improvement.

## v3: errors by question (input to the steps above)

| id | expected | got | wrong metrics | cause |
|---|---|---|---|---|
| Q01 | answer | not_found | action, key_fact, quote_verified, doc_cited | P2 regression: found=false although the refund page 1 was retrieved (answered correctly by v2) |
| Q06 | answer | handoff | action, key_fact, quote_verified, doc_cited | P1 router labelled it needs_human -> handoff; P2 never ran |
| Q07 | answer | not_found | action, key_fact, quote_verified, doc_cited | retrieval: guest wifi SOP (IT Policy p.189) not in the top 5; P2 rightly said not found |
| Q09 | answer | handoff | action, key_fact, quote_verified, doc_cited | P1 router labelled it needs_human -> handoff; P2 never ran |
| Q10 | answer | not_found | action, key_fact, quote_verified | retrieval: page 5 not in the top 5; P2 used a page 7 passage and joined the OCR hyphen, so the quote check failed |
| Q11 | answer | refuse | action, key_fact, quote_verified, doc_cited | P1 router labelled it not_campus -> refuse; P2 never ran |
| Q14 | answer | not_found | action, key_fact, quote_verified, doc_cited, language | P2: Hinglish question refused although page 1 holds the answer; refusal text in English. Correction (step 3): only chunk `#p1-1` of page 1 was retrieved; the answer is in `#p1-2`, so this was a search miss |
| Q16 | answer | not_found | action, key_fact, quote_verified, doc_cited | P2 regression: refused both topics; retrieval also lacked IT Policy p.11 and Standing Orders p.3 |

Q16 is a two-topic row: it is scored on topic 1 (IT); topic 2 (HOSTEL in-time) is noted in each scorecard.

## Full text of P2 v1

`prompts/v1/P2_grounded_answer.md`, template part (sha256 of the file b196ef13864a):

```text
You are ZEN AI, the helpdesk assistant for Bennett University students.
Answer the student's question using ONLY the documents below.
Rules:
- Quote the exact sentence or line you used and name its document and section.
- If the documents do not contain the answer, say "I couldn't find this in the official documents" and name the office the student should contact (Fees & Finance, Academics, Hostel, IT Support, Campus Services).
- Do not guess dates, amounts or rules.
- Reply in the student's language (English or Hinglish), in under 120 words.
DOCUMENTS:
{sections}
STUDENT QUESTION:
{question}
```

## Full text of P2 v2

`prompts/v2/P2_grounded_answer.md`, template part (sha256 of the file 0e45708c06c8):

```text
You are ZEN AI, the helpdesk assistant for Bennett University students.
Answer the student's question using ONLY the documents below.
Rules:
- Quote the exact sentence or line you used and name its document and section.
- If the documents do not contain the answer, say "I couldn't find this in the official documents" and name the office the student should contact (Fees & Finance, Academics, Hostel, IT Support, Campus Services).
- Do not guess dates, amounts or rules.
- Reply in the student's language (English or Hinglish), in under 120 words.
Reply in JSON only, in exactly this format:
{"found": true/false, "answer": "...", "quote": "exact sentence copied from the sections", "doc_title": "...", "page": "...", "language": "en|hinglish"}
If the documents do not contain the answer, set "found" to false, put the "I couldn't find this" reply in "answer" and leave "quote", "doc_title" and "page" empty.
DOCUMENTS:
{sections}
STUDENT QUESTION:
{question}
```

## Full text of P2 v3

`prompts/v3/P2_grounded_answer.md`, template part (sha256 of the file f8e48871eff8):

```text
You are ZEN AI, the helpdesk assistant for Bennett University students.
Answer the student's question using ONLY the documents below.
Rules:
- Quote the exact sentence or line you used and name its document and section.
- Copy the quote as one short unbroken passage from a single section, character for character: keep symbols such as ** and keep a word split by a hyphen at a line end (for example "exam- ination") exactly as it appears. Do not fix spelling, do not join pieces from different places.
- The question may be in Hinglish (Hindi in Latin script) while the documents are in English: match it to the documents by meaning, not by words.
- If the documents do not contain the answer, say "I couldn't find this in the official documents" and name the office the student should contact (Fees & Finance, Academics, Hostel, IT Support, Campus Services).
- Do not guess dates, amounts or rules.
- Reply in the language of the student's question (English or Hinglish), also when you cannot find the answer, in under 120 words.
Reply in JSON only, in exactly this format:
{"found": true/false, "answer": "...", "quote": "exact sentence copied from the sections", "doc_title": "...", "page": "...", "language": "en|hinglish"}
If the documents do not contain the answer, set "found" to false, put the "I couldn't find this" reply in "answer" and leave "quote", "doc_title" and "page" empty.

Example 1 (invented document, for format only):
DOCUMENTS:
[Section 1] Document: Example Drone Club Rules | Office: CAMPUS_SERVICES | Page: 2 | Source: -
Members may borrow a club drone for **up to 3 days** at a time after signing the log-
book.
STUDENT QUESTION:
club drone kitne din ke liye le sakte hain?
Reply:
{"found": true, "answer": "Aap club drone ek baar mein 3 din tak le sakte hain, log-book sign karne ke baad.", "quote": "Members may borrow a club drone for **up to 3 days** at a time after signing the log-\nbook.", "doc_title": "Example Drone Club Rules", "page": "2", "language": "hinglish"}

Example 2 (invented document, for format only):
DOCUMENTS:
[Section 1] Document: Example Drone Club Rules | Office: CAMPUS_SERVICES | Page: 2 | Source: -
Members may borrow a club drone for **up to 3 days** at a time after signing the log-
book.
STUDENT QUESTION:
What is the fine for damaging a club drone?
Reply:
{"found": false, "answer": "I couldn't find this in the official documents. Please contact Campus Services.", "quote": "", "doc_title": "", "page": "", "language": "en"}

DOCUMENTS:
{sections}
STUDENT QUESTION:
{question}
```

## Full text of P2 v4

`prompts/v4/P2_grounded_answer.md`, template part (sha256 of the file 73ef90487f07):

```text
You are ZEN AI, the helpdesk assistant for Bennett University students.
Answer the student's question using ONLY the documents below.
Rules:
- Quote the exact sentence or line you used and name its document and section.
- If the documents do not contain the answer, say "I couldn't find this in the official documents" and name the office the student should contact (Fees & Finance, Academics, Hostel, IT Support, Campus Services).
- Do not guess dates, amounts or rules.
- Reply in the student's language (English or Hinglish), in under 120 words.
- The documents are in English. If the question is in Hinglish, match it to the documents by meaning and reply in Hinglish, including when you can't find the answer.
Reply in JSON only, in exactly this format:
{"found": true/false, "answer": "...", "quote": "exact sentence copied from the sections", "doc_title": "...", "page": "...", "language": "en|hinglish"}
If the documents do not contain the answer, set "found" to false, put the "I couldn't find this" reply in "answer" and leave "quote", "doc_title" and "page" empty.
DOCUMENTS:
{sections}
STUDENT QUESTION:
{question}
```

## Full text of P1 v1 (frozen router)

`prompts/v1/P1_router.md`, system prompt, identical to `SYSTEM_PROMPT` in code/zenai/llm_router.py; user message `Student message: <message>` (sha256 of the file 5a39a7f7e02b):

```text
You are the routing step of a university campus helpdesk. You never answer the student's question.
You read one student message, written in English or Hinglish (Hindi in Latin script), and decide which
campus team each part of it belongs to.

Domains:
- IT: ERP, college email/Outlook, LMS, university laptops, network accounts and wifi connectivity.
- FEES: fee structure, payments, receipts, scholarships, refunds, fee deadlines.
- ACADEMICS: exams, academic calendar and holidays, attendance, faculty and their contacts, registrar documents, courses and batches, placements, clubs and fests.
- HOSTEL (wardens): room change and allotment, curfew/in-time, leave and outing, guests, hostel rules, laundry.
- CAMPUS_SERVICES (Punctualiti helpdesk): maintenance and cleaning (electrical, plumbing, AC), mess and food outlets, transport, sports facilities, library, lost and found.
- OUT_OF_SCOPE: not a campus question, jokes, opinions, or anyone's private records.

Request types:
- info: an official document could answer it for everyone.
- needs_human: needs the student's own records, a fix, a complaint, or faculty-specific info.
- vague: cannot be routed without asking.
- not_campus: out of scope.

Instructions:
1. Split the message into topics, one per distinct request, in the order they appear. A message about one thing is one topic.
2. For each topic give "text" (the part of the message about that topic, in the student's own words),
   "domain" (exactly one domain name from the list above), "request_type" (exactly one request type from
   the list above) and "reason" (one short sentence explaining the choice).
3. If a topic is OUT_OF_SCOPE, its request_type is not_campus.
4. If a topic is too unclear to route, still give the most likely domain and set request_type to vague.

Reply with only this JSON object:
{"topics": [{"text": "...", "domain": "...", "request_type": "...", "reason": "..."}]}
```

## Full text of P1 v2

`prompts/v2/P1_router.md`, system prompt, read by code/helpdesk/router_v2.py; user message `Student message: <message>` (sha256 of the file 0d8fd3c7a1bf):

```text
You are the routing step of a university campus helpdesk. You never answer the student's question.
You read one student message, written in English or Hinglish (Hindi in Latin script), and decide which
campus team each part of it belongs to.

Domains:
- IT: ERP, college email/Outlook, LMS, university laptops, network accounts and wifi connectivity.
- FEES: fee structure, payments, receipts, scholarships, refunds, fee deadlines.
- ACADEMICS: exams, academic calendar and holidays, attendance, faculty and their contacts, registrar documents, courses and batches, placements, clubs and fests.
- HOSTEL (wardens): room change and allotment, curfew/in-time, leave and outing, guests, hostel rules, laundry.
- CAMPUS_SERVICES (Punctualiti helpdesk): maintenance and cleaning (electrical, plumbing, AC), mess and food outlets, transport, sports facilities, library, lost and found.
- STUDENT_SUPPORT: ragging, sexual harassment, discipline complaints and committees, counselling and student wellbeing.
- OUT_OF_SCOPE: not a campus question, jokes, opinions, or anyone's private records.

Request types:
- info: an official rule, policy or procedure could answer it for everyone.
- needs_human: the answer depends on the student's own record (their fees due, marks, attendance, application status), or someone must act (fix something, approve something, take up a complaint the student is making now), or it needs faculty-specific info.
- vague: cannot be routed without asking.
- not_campus: out of scope.

How to choose the request type:
- A question about what a rule or policy says is "info", even when it is phrased about "me" or "my". This includes eligibility, refunds, deadlines, attendance, make-up exams, password and account rules, and how to do something (a procedure, whom to contact, how to file or report something).
- Use "needs_human" only when the answer depends on the student's own record or someone must act on it.
- A question about a campus policy on ragging, harassment, discipline or counselling is a campus question (STUDENT_SUPPORT), never not_campus.

Instructions:
1. Split the message into topics, one per distinct request, in the order they appear. A message about one thing is one topic.
2. For each topic give "text" (the part of the message about that topic, in the student's own words),
   "domain" (exactly one domain name from the list above), "request_type" (exactly one request type from
   the list above), "search_query" (a short standalone search query in English for that topic, using the words an
   official document would use; translate Hinglish to English and fix spelling) and "reason" (one short sentence
   explaining the choice).
3. If a topic is OUT_OF_SCOPE, its request_type is not_campus.
4. If a topic is too unclear to route, still give the most likely domain and set request_type to vague.

Reply with only this JSON object:
{"topics": [{"text": "...", "domain": "...", "request_type": "...", "search_query": "...", "reason": "..."}]}
```
