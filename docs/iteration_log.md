# Iteration log: P2 grounded answer

Every number below is read from the run folders under `test-data/runs/` (scorecard.md, run_meta.json). All runs:
test-data/questions.csv (24 questions), router P1 = frozen v1 `classify()`, retrieval `kb_search.search_for_route(question, first topic domain, k=5)`, model gemini-3.5-flash-lite, temperature 0, reasoning_effort minimal. Metric definitions: `code/helpdesk/score_p2.py`.

| Version | What changed | Why | Result after the change |
|---|---|---|---|
| v1 | Milestone 1 baseline prompt, unchanged; plain-text reply. Code reads not_found from the fixed sentence and the quote from the first pair of double quotes. | Baseline to measure against. | final action correct 17/24 (71%); key fact found 8/16 (50%); quote verified 9/16 (56%); right document cited 11/16 (69%); language matches 1/2 (50%); router office correct 17/17 (100%) (run `P2_v1_20261122-184456`) |
| v2 | Same rules; reply is one JSON object {found, answer, quote, doc_title, page, language} in JSON mode. Not-found case: found=false, empty quote/doc/page. | v1's free text has to be guessed at (fixed sentence, first quoted text). Fields make found/quote/document checkable. | final action correct 17/24 (71%); key fact found 9/16 (56%); quote verified 9/16 (56%); right document cited 11/16 (69%); valid format 15/15 (100%); language matches 1/2 (50%); router office correct 17/17 (100%) (run `P2_v2_20261122-184902`) |
| v3 | (1) quote copied as one short unbroken passage, character for character, keeping `**` and line-end hyphens; (2) Hinglish question matched to English documents by meaning; (3) reply in the question's language also when not found; (4) two worked examples (one Hinglish answer, one refusal) on an invented drone club. | From v2's failures: Q03 quote dropped `**` marks and Q10 joined an OCR hyphen ('Anti- Ragging'), so both failed the quote check; Q14 (Hinglish) refused although page 1 was retrieved, and refused in English. No injection rule: Q24 is refused by the router before P2. | final action correct 16/24 (67%); key fact found 8/16 (50%); quote verified 8/16 (50%); right document cited 9/16 (56%); valid format 15/15 (100%); language matches 1/2 (50%); router office correct 17/17 (100%) (run `P2_v3_20261122-185126`) |

## Scorecards side by side

| Metric | v1 | v2 | v3 |
|---|---|---|---|
| Final action correct | 17/24 (71%) | 17/24 (71%) | 16/24 (67%) |
| Key fact found | 8/16 (50%) | 9/16 (56%) | 8/16 (50%) |
| Quote verified | 9/16 (56%) | 9/16 (56%) | 8/16 (50%) |
| Right document cited | 11/16 (69%) | 11/16 (69%) | 9/16 (56%) |
| Valid format (JSON) | n/a | 15/15 (100%) | 15/15 (100%) |
| Language matches (Hinglish rows) | 1/2 (50%) | 1/2 (50%) | 1/2 (50%) |
| Router office correct | 17/17 (100%) | 17/17 (100%) | 17/17 (100%) |
| API calls (cache hits) | 44 (0) | 18 (23) | 20 (23) |

What happened: v2 kept every v1 decision and made the reply machine-checkable (15/15 valid JSON, key fact +1). v3 fixed Q03 (quote now verified) but did not fix Q10 (the hyphen is still joined) or Q14 (still refuses), and it turned two v2 answers into refusals (Q01, Q16), most likely because the added refusal example makes the model refuse sooner. v3 is therefore lower than v2 on action, key fact, quote and document. Three router (P1) errors (Q06, Q09 needs_human; Q11 not_campus) stop those questions before P2 in every version; P1 is frozen.

## v3: errors by question

| id | expected | got | wrong metrics | cause |
|---|---|---|---|---|
| Q01 | answer | not_found | action, key_fact, quote_verified, doc_cited | P2 regression: found=false although the refund page 1 was retrieved (answered correctly by v2) |
| Q06 | answer | handoff | action, key_fact, quote_verified, doc_cited | P1 router labelled it needs_human -> handoff; P2 never ran |
| Q07 | answer | not_found | action, key_fact, quote_verified, doc_cited | retrieval: guest wifi SOP (IT Policy p.189) not in the top 5; P2 rightly said not found |
| Q09 | answer | handoff | action, key_fact, quote_verified, doc_cited | P1 router labelled it needs_human -> handoff; P2 never ran |
| Q10 | answer | not_found | action, key_fact, quote_verified | retrieval: page 5 not in the top 5; P2 used a page 7 passage and joined the OCR hyphen, so the quote check failed |
| Q11 | answer | refuse | action, key_fact, quote_verified, doc_cited | P1 router labelled it not_campus -> refuse; P2 never ran |
| Q14 | answer | not_found | action, key_fact, quote_verified, doc_cited, language | P2: Hinglish question refused although page 1 holds the answer; refusal text in English |
| Q16 | answer | not_found | action, key_fact, quote_verified, doc_cited | P2 regression: refused both topics; retrieval also lacked IT Policy p.11 and Standing Orders p.3 |

Q16 is a two-topic row: it is scored on topic 1 (IT); topic 2 (HOSTEL in-time) is noted in each scorecard.

## Full text of v1

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

## Full text of v2

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

## Full text of v3

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
