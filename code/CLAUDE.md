# ZEN AI Router

Routing-only prototype for a campus assistant (Microsoft Innovate 2026, Problem Statement 18 "One Front Door for Everything").
It does not answer questions. It takes one student message (English or Hinglish), splits it into topics, picks a campus
domain for each topic, scores confidence, and decides: answer, clarify, handoff or refuse.

The sentences above describe v1 (tag `v1-routing-frozen`), which is frozen: its results in `test-data/results/` are
the official routing numbers. The project is now growing into the full ZEN AI prototype (retrieval, grounded answers,
case handoffs, staff queues, a web app) around it. See "ZEN AI full prototype" below.

## Rules (must follow)

- Domains: IT, FEES, ACADEMICS, HOSTEL, CAMPUS_SERVICES, OUT_OF_SCOPE. Actions: answer, clarify, handoff, refuse.
- test-data/test_set.csv and test-data/simulated_v1.csv are TEST data. Never use them to write prompts, pick examples, choose keywords or tune thresholds. Only test-data/dev_set.csv may be used for tuning. Never copy any test question text into code, prompts or examples.
- Never invent or hand-edit results. Every number must come from a file in test-data/results/.
- Every LLM and embedding call goes through the cached provider in zenai/providers.py.

## Layout

Repo root (Milestone 2 course layout): `code/` (this folder), `test-data/`, `docs/`, `prompts/`, plus `README.md`,
`CHANGELOG.md`, `.env.example` and the git-ignored `.env`, `.cache/`, `.data/`. Every path constant is in
`zenai/paths.py`. Run commands from `code/`. Paths below are relative to `code/` unless they name `test-data/`,
`docs/`, `prompts/` or say "at the repo root".

- `zenai/`: router package
- `evaluation/`: testing agent (evaluator, baselines, tuning); `python -m evaluation.check_data` validates test-data/
- `tests/`: pytest (`cd code && pytest -q`)
- `test-data/`: datasets (dev_set.csv, test_set.csv, examples.jsonl, simulated_*.csv), do not edit
- `test-data/results/`: run outputs, one folder per run, committed to git
- `.cache/`: LLM/embedding response cache, gitignored, at the repo root
- `config.yaml`: provider, kNN, confidence weights, thresholds

## ZEN AI full prototype

The v1 rules above still apply to everything below. v1 code paths (`zenai/router.py`, `zenai/llm_router.py`,
`zenai/knn.py`, `evaluation/`, `static/index.html`, `zenai/api.py`) stay reproducible: do not change their behaviour,
and never touch an existing folder in `test-data/results/`. The v1 demo is served at `/v1` by the new server.

Layout added on top of the v1 layout:

- `kb/`: the knowledge base. `kb/<FOLDER>/` holds the original files (PDF, md, txt, html) and one `INDEX.md` listing
  the metadata of every file in it. Folders are exactly IT, FINANCE, ACADEMICS, COURSE_SPECIFIC, HOSTEL,
  CAMPUS_SERVICES, EMPLOYEES, STUDENT_SUPPORT. There is no `kb/HELPDESK`: HELPDESK is an office that holds no documents.
- `retrieval/`: ingestion and search over `kb/` (`python -m retrieval.ingest`, `python -m retrieval.inspect`; see
  `docs/RETRIEVAL.md`). Backends: `local` (BM25 + numpy, `.cache/kb_local/` at the repo root) and `azure` (the existing `zenai-kb` index,
  whose schema this project never changes). KB chunks and queries are embedded with Azure `embed` only; the router's
  Gemini vectors are never mixed with them. Every `kb/<FOLDER>/INDEX.md` must list every file in the folder
- `zenai/v2/`: routing v2 (`zenai/router.py` stays v1)
- `answer/`: grounded answers and handoff drafts
- `server/`: FastAPI app (chat, cases, email, staff). Its contract is `docs/API.md`
- `web/`: Next.js app
- `config/offices.yaml`, `config/mailbox_map.yaml`: offices, required fields and demo mailboxes (loaded by `zenai/offices.py`)
- `docs/POLICY.md`: the single source of truth for routing. Change a rule there first; prompts, evaluation labels,
  `config/` and `docs/API.md` follow it
- `docs/API.md`: the HTTP contract the server and the web app both build against. Change it before changing the code
- `.data/`: runtime state (cases, outbox), gitignored, at the repo root
- `prompts/`: prompt versions for the course (`v1/` to `v4/`, `final/`)

Rules for the full prototype (must follow):

- v2 vocabulary: offices IT, FINANCE, ACADEMICS, HOSTEL, CAMPUS_SERVICES, EMPLOYEES, STUDENT_SUPPORT, HELPDESK; actions
  answer, not_found, clarify, handoff, refuse, safety; intents are listed in `docs/POLICY.md`. The v1 domain and action
  names above stay valid for v1 code and results.
- Answers must cite retrieved chunks or say they can't answer. Never answer from model memory. A course-specific
  question is answered only from `kb/COURSE_SPECIFIC`, never from general documents.
- The LLM can never send email. Only `POST /api/cases/{id}/approve` with a valid one-time approval token sends.
- Demo students only (`student1`, `student2`). No real student data anywhere: not in code, data, logs or results.
- Keys and passwords live only in `.env` (this repo is public, `.env` is gitignored). `.env.example` has names only.
  Never put a key, password or real email address (including the demo Gmail) in any tracked file.
- Provider is chosen by `LLM_PROVIDER` in `.env` (gemini or azure), overriding `provider.name` in `config.yaml`. Both go
  through `zenai/providers.py` with the same cache, rate limiter and daily caps. Switching the provider changes the
  cache keys, so v1 evaluation numbers are reproduced with `LLM_PROVIDER=gemini` (or unset).
- New numbers go in new folders under `test-data/results/`, with their config and commit recorded. Never edit or
  overwrite an existing run folder; note anything that changes how runs are read in `test-data/results/CHANGELOG.md`.
- The test-data rule applies to v2 too: prompts, examples, keywords and thresholds for routing v2 come from
  `test-data/dev_set.csv` and new team-written data only, never from the test or simulated sets.
