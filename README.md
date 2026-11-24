# ZEN AI: Campus Helpdesk

**Problem C1.** Bennett University students ask the same questions every day (fee refunds, scholarships, hostel
rules, attendance, wifi) and the answers are spread across dozens of official PDFs owned by different offices.
ZEN AI Helpdesk answers a student's question **only from the official documents**, shows the exact sentence it used
with the document, page and link, and when it cannot answer it **hands off**: it drafts a short email to the right
office for the student to send.

**Prototype:** https://zenai-campusdesk.streamlit.app/

## Features

- **Every answer quotes its source.** An answer is shown only after code finds its quote in an official document;
  the student sees the exact sentence, the document, the page and a link.
- **English and Hinglish**, and up to **two questions in one message**, each answered on its own.
- **Safety card**: a student who reports ragging or harassment sees official contacts at once, copied word for word
  from the documents, then a draft to Student Support.
- **Email draft to the right office** when the documents don't cover a question. Draft only: nothing is ever sent.
- **Source badges** that help the student double-check: a number in the answer that the quote doesn't show, another
  programme's rules, or a document from before 2022.
- **"How ZEN AI decided"** panel: router output, retrieved sections, raw answer JSON and the quote check, per answer.
- Chat interface with suggestion cards and office shortcuts; no login, no chats stored.

## Results at a glance

| Result | Number | Source |
|---|---|---|
| Fake (mutated) quotes accepted by quote check v2 | **0 of 59** (26 of 59 before tightening) | `test-data/runs/quote_check_v2_tight_20261124-172251` |
| Seen test set (24 questions) | **22/24 (92%)** | `test-data/runs/final_20261124-181511` |
| Unseen fresh check 2 (18 questions, written after the freeze) | **11/18 (61%)**: one question 5/10, two questions 3/4, safety 2/2, follow-ups 1/2 | `test-data/runs/fresh_20261124-183516` |
| Wrong answers shown on unseen questions (human-checked) | **1 of 18** (F15) | `test-data/fresh2_check.md` |
| Software tests | **284 passed** | `cd code && pytest -q` |

Milestone 2 documents: [docs/M2_PE-B81-26_ZENAIHelpdesk.pdf](docs/M2_PE-B81-26_ZENAIHelpdesk.pdf) and the Business
Model Canvas [docs/codingwoofs_BMC.pdf](docs/codingwoofs_BMC.pdf).

**Team:** codingwoofs (Team ID PE-B81-26). SCSE4041 Prompt Engineering, problem C1, batch B81-93, faculty: Indrajeet Gupta.

| Member | Enrollment no. | Main task |
|---|---|---|
| Shaurya Nigam (team leader) | S24CSEU0497 | Prompt design (P1, P2, P3), prompt iterations and testing, knowledge base, Streamlit prototype, documentation |
| Saksham Chandel | S24CSEU0448 | Reel voice-over and narration of the demo |

## How to use it

1. Open the prototype link. No login; don't enter personal details.
2. Type a question in English or Hinglish, or click one of the four examples.
3. Read the result card. It is one of:
   - **Answer**: the answer, the quote from the document in a quote block, the document title, page, date and a link
     to the source, and a green "Quote verified in source" badge (the quote was found in the retrieved text by code).
   - **Not found / needs a person**: a short explanation plus an email draft to the right office, with
     `[Your name]` and `[Enrollment no.]` placeholders. Draft only: nothing is sent.
   - **Out of scope / needs more detail**: a fixed message saying what ZEN AI can help with, or one short question.
4. Open **"How ZEN AI decided"** to see every step: the router's office, request type and search query, the
   retrieved sections with their scores, the raw answer JSON, the quote check result and the handoff draft checks.

A message with two questions gets both answered, each on its own (a third topic is listed with a note asking the
student to send it separately). A student who reports something happening to them (ragging, harassment, threats)
first sees a card of official contacts copied from the documents, then a draft to Student Support. After a
"needs more detail" reply, a short answer (8 words or fewer) is joined to the previous question. Each browser session
can ask 20 questions.

## How it works: the prompt chain

```
student message  (after a clarify, a short reply is joined to the previous question: clarify follow-up)
  -> P1 router (LLM, prompts/final/P1_router.md = P1 v2)
       office, request type (info / needs_human / vague / not_campus), English search query, one entry per topic
  -> for each of the first two topics, on its own text (two topics; a third is listed in a note):
       safety report (STUDENT_SUPPORT + needs_human, or an English incident pattern) -> safety card + P3 draft
       not_campus -> refuse (fixed text)   vague or empty -> clarify (fixed text)   needs_human -> handoff
  -> programme-aware search (code, BM25 over code/kb/): top 5 sections from the routed office's folder (for an
       ACADEMICS question naming a programme, only from that programme's rules file) + top 3 from all folders
  -> P2 grounded answer (LLM, prompts/final/P2_grounded_answer.md = P2 v2)
       JSON {found, answer, quote, doc_title, page, language}, using only the retrieved sections
  -> quote check v2 (code, no LLM): exact (after removing ** and OCR line-end hyphens, whitespace and case) or
       near (one section; every content word, every number next to the same word, negations kept, >= 4 words)
       verified -> answer        found = false or not verified -> not_found
  -> P3 handoff draft (LLM, prompts/final/P3_handoff.md = P3 v2), for not_found, handoff and safety
       JSON {to, subject, body}: polite, English, under 120 words, placeholders, no invented facts
```

The safety card is fixed text plus lines copied word for word from
`code/kb/STUDENT_SUPPORT/anti-ragging-and-sexual-harassment-contacts.md` (no LLM writes a phone number or email). The
prompt chain has 9 saved prompt versions (P1 v1, v2; P2 v1 to v5; P3 v1, v2); see [docs/iteration_log.md](docs/iteration_log.md).

Model: `gemini-3.5-flash-lite`, temperature 0. Every LLM call goes through one cached, rate-limited client
(`code/zenai/providers.py`), so re-running a test costs no API calls and gives the same output. Office email
addresses in drafts are demo addresses on the reserved `zenai-demo.example` domain; the app never sends email.

## Results

All numbers come from saved runs in `test-data/runs/`. Three question sets:

| Set | n | Status | Pass | Run |
|---|---|---|---|---|
| `test-data/questions.csv` | 24 | seen: used to choose every change | **22/24 (92%)** | `final_20261124-181511` |
| `test-data/fresh_questions.csv` (fresh check 1) | 10 | now seen: its failures were used to choose the 24 Nov fixes | 9/10 (90%) | `fresh_20261124-181523` |
| `test-data/fresh2_questions.csv` (fresh check 2) | 18 | **unseen**: written after the freeze, labels committed before the run | **11/18 (61%)** | `fresh_20261124-183516` |

Pass = correct action, and for answerable rows also the key fact present and the quote verified. Fresh check 2 adds
row types with their own rules, fixed in `test-data/README.md` before the run: two questions in one message (both
parts must be right), safety reports (safety card with contacts) and two-turn follow-ups (clarify, then a passing
answer).

**Final test table** ([test-data/final_test_table.md](test-data/final_test_table.md), run
`test-data/runs/final_20261124-181511`, the frozen pipeline): **22/24 pass (92%)**. The 22 Nov table (21/24) is kept in
`test-data/final_test_table_22nov.md`.

| Metric (final pipeline, 24 seen questions) | Score |
|---|---|
| Final action correct | 23/24 (96%) |
| Key fact found | 14/16 (88%) |
| Quote verified in source | 15/16 (94%) |
| Right document cited | 15/16 (94%) |
| Valid JSON from P2 | 18/18 (100%) |
| Hinglish answer for Hinglish question | 2/2 |
| Router office correct | 17/17 (100%) |

The two failures: Q10 (answered from page 3 of the anti-ragging rules, not page 5, so the expected key fact is
missing) and Q16 (the two-question wifi/curfew message: the wifi part's search missed IT Policy p.11 and the curfew
part also ended as not_found).

**Fresh check 2 on unseen questions** ([test-data/fresh2_check.md](test-data/fresh2_check.md)): **11/18 (61%)**:
one-question rows 5/10, two-question rows 3/4, safety rows 2/2, follow-up rows 1/2. Failures: P2 declined with the
rule retrieved (F13); P2 answered "90 days" from the 2019-20 handbook instead of 45 days from the IT Policy, with a
verified quote (F15); router request type sent a question to a person (F16) or answered a vague turn 1 (F28); the
same rule quoted from another page (F17); a search miss (F18); a correct answer rejected by the quote check on OCR
text (F22 part 2). No price or fee was invented. On the 34 earlier questions the pipeline scored 22/24 and 9/10; on
unseen questions it scores 61%, which is the number to trust.

**Wrong answers shown (human-checked): 1/18, F15** ("90 days"; IT Policy p.144 says 45 days). A person read every
row the scorer listed as "incomplete" (answer shown, key fact missing): F17 and F28 are true answers missing the key
fact's wording, F15 contradicts the documents. The automatic scorer filed F15 as incomplete, so its count does not
separate wrong answers from incomplete ones. The run was retried once: the first attempt stopped at F23 on an HTTP
503 from the provider and saved nothing, and in the retry F11-F22 came back identical from the cache.

How each prompt version and pipeline step moved these numbers is in [docs/iteration_log.md](docs/iteration_log.md).

## Roadmap (Milestone 3)

Each item comes from a measured failure in the runs above (error analysis: [docs/iteration_log.md](docs/iteration_log.md),
"Error analysis: fresh check 2"). None is built yet; the pipeline stays frozen at tag `m2-final-24nov`.

- **Prefer the newest official document when two documents conflict** (F15): rank retrieved sections by the document
  date in `INDEX.md`, so the 2024 IT Policy (45 days) wins over the 2019-20 handbook (90 days). A verified quote proves
  the sentence is in a document, so the next check is whether it is the current one.
- **Ask which programme a student is in when rules differ by programme** (F28 turn 1, F01): route ACADEMICS and fee
  questions that name no programme to a clarify. (P2 v5 tried to list every programme's value in the answer and
  lowered the seen pass rate from 22/24 to 19/24, so the fix moves to the router.)
- **Extend the quote to the full sentence so it always shows the number quoted in the answer**: widen the matched span
  to sentence boundaries in the quote check (today a quote can stop at "...minimum attendance of", and the app flags it
  with a "number not in quote" badge).
- **Accept correct quotes from OCR and table text** (F22 part 2): strip OCR replacement characters and bullets before
  the quote check.
- **Lift recall without moving the right page down** (F18, Q16): re-rank the top 8 rather than widen the search (the
  dual-query search raised page hit@8 from 13/16 to 14/16 but lowered the seen pass rate from 22/24 to 19/24, so it
  was rejected).
- **Sharpen the router and P2 on two known rows** (F16: a rules question sent to a person; F13: P2 declined with the
  rule retrieved), and add Hinglish incident patterns to the safety trigger (Hinglish reports rely on the router today).
- **Measure on new unseen questions** after each change: the 24 seen questions and fresh check 1 were used to choose
  changes, so fresh check 2 (11/18) is the number to beat.
- **Staff side**: the FastAPI server, case approval and email sending, staff queues and the Next.js web app
  (`code/server/`, `code/web/`, `code/answer/` are placeholders; `docs/API.md` is the planned contract). The prototype
  is the Streamlit app above.

## Run it locally

Requires Python 3.11 and a Gemini API key.

```bash
python -m venv .venv
.venv/Scripts/activate                 # Windows; source .venv/bin/activate on macOS/Linux
pip install -r code/requirements.txt
cp .env.example .env                   # then set GEMINI_API_KEY=...

streamlit run code/app.py              # the helpdesk app, from the repo root

cd code
pytest -q                              # tests, no network
python -m helpdesk.final_test          # final test table on the 24 questions (cached: 0 new calls on a re-run)
python -m helpdesk.kb_search "hostel in-time" --office HOSTEL --k 4   # try the search alone
```

For Streamlit Community Cloud the key goes in the app's secrets as `GEMINI_API_KEY = "..."`.

## Folder map

| Folder | What is in it |
|---|---|
| `code/` | All code. `app.py` (Streamlit app), `helpdesk/` (pipeline, router P1 v2, search, P3 handoff, scorers, `final_test.py`), `kb/` (the official documents as Markdown, one folder per office, with an `INDEX.md` each), `zenai/` (cached LLM client and the earlier router), `config/` (offices and demo mailboxes), `tests/` |
| `prompts/` | Every prompt version with its settings and the reason for each change: `v1/` to `v5/`, and `final/` (P1 router, P2 grounded answer, P3 handoff) |
| `test-data/` | `questions.csv` (the 24 test questions with expected action, document, page and key fact), `final_test_table.csv/.md` (24 Nov; `_22nov` the earlier table), `fresh_questions.csv` and `fresh_check.md` (fresh check 1), `fresh2_questions.csv` and `fresh2_check.md` (fresh check 2, 18 unseen questions), `runs/` (one folder per recorded run: outputs, scorecard, settings), `kb_manifest.csv` (every document and its source) |
| `docs/` | `M2_PE-B81-26_ZENAIHelpdesk.pdf` (Milestone 2 document), `codingwoofs_BMC.pdf` (Business Model Canvas), `diagrams/` (the five design diagrams and `draw_diagrams.py`), `iteration_log.md` (prompt iterations and errors), `POLICY.md` (routing rules), `RETRIEVAL.md`, `API.md` |

Builds on our earlier routing prototype (Sept to Oct 2026); its code and results are kept in code/ and test-data/results/.
