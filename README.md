# ZEN AI: Campus Helpdesk

**Problem C1.** Bennett University students ask the same questions every day (fee refunds, scholarships, hostel
rules, attendance, wifi) and the answers are spread across dozens of official PDFs owned by different offices.
ZEN AI Helpdesk answers a student's question **only from the official documents**, shows the exact sentence it used
with the document, page and link, and when it cannot answer it **hands off**: it drafts a short email to the right
office for the student to send.

**Prototype:** [PROTOTYPE_LINK]

**Team:** [TEAM]

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

A message with two questions gets the first one answered and a clear note asking the student to send the other
separately. Each browser session can ask 20 questions.

## How it works: the prompt chain

```
student question
  -> P1 router (LLM, prompts/final/P1_router.md = P1 v2)
       office, request type (info / needs_human / vague / not_campus), English search query, one entry per topic
       not_campus -> refuse (fixed text)   vague or empty -> clarify (fixed text)   needs_human -> handoff
  -> search (code, BM25 over code/kb/): top 5 sections from the routed office's folder + top 3 from all folders
  -> P2 grounded answer (LLM, prompts/final/P2_grounded_answer.md = P2 v2)
       JSON {found, answer, quote, doc_title, page, language}, using only the retrieved sections
  -> quote check (code, no LLM): the quote must appear in a retrieved section; if not, the answer is not shown
       verified -> answer        found = false or not verified -> not_found
  -> P3 handoff draft (LLM, prompts/final/P3_handoff.md = P3 v1), for not_found and handoff only
       JSON {to, subject, body}: polite, English, under 120 words, placeholders, no invented facts
```

Model: `gemini-3.5-flash-lite`, temperature 0. Every LLM call goes through one cached, rate-limited client
(`code/zenai/providers.py`), so re-running a test costs no API calls and gives the same output. Office email
addresses in drafts are demo addresses on the reserved `zenai-demo.example` domain; the app never sends email.

## Results

All numbers come from saved runs in `test-data/runs/` on the 24-question set `test-data/questions.csv`
(16 answerable, 2 not in the documents, 1 needs the student's record, 2 vague/empty, 3 off-topic or unsafe;
English, Hinglish, typos and a two-question message).

**Final test table** ([test-data/final_test_table.md](test-data/final_test_table.md), run
`test-data/runs/final_20261122-201923`): **21/24 pass (88%)**. Pass = correct action, and for answerable rows
also the key fact present and the quote verified.

| Metric (final pipeline) | Score |
|---|---|
| Final action correct | 22/24 (92%) |
| Key fact found | 14/16 (88%) |
| Quote verified in source | 14/16 (88%) |
| Right document cited | 14/16 (88%) |
| Valid JSON from P2 | 18/18 (100%) |
| Hinglish answer for Hinglish question | 2/2 |
| Router office correct | 17/17 (100%) |

The three failures: Q10 (answered from a different page of the anti-ragging rules, so the expected key fact is
missing), Q15 (correct answer rejected by the quote check because the scanned source reads "ona scale"), Q16 (the
search query for the wifi part missed the password page). How each prompt version and pipeline step moved these
numbers (P2 v1 to v4, router v1 to v2, search, quote check) is in [docs/iteration_log.md](docs/iteration_log.md).

**Limitation.** The same 24 questions were used to choose each change and to measure it, so these numbers are
optimistic. A fresh, unseen question set is planned for the next milestone.

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
| `prompts/` | Every prompt version with its settings and the reason for each change: `v1/` to `v4/`, and `final/` (P1 router, P2 grounded answer, P3 handoff) |
| `test-data/` | `questions.csv` (the 24 test questions with expected action, document, page and key fact), `final_test_table.csv/.md`, `runs/` (one folder per recorded run: outputs, scorecard, settings), `kb_manifest.csv` (every document and its source) |
| `docs/` | `iteration_log.md` (prompt iterations and errors), `POLICY.md` (routing rules), `RETRIEVAL.md`, `API.md` |

Builds on our earlier routing prototype (Sept to Oct 2026); its code and results are kept in code/ and test-data/results/.
