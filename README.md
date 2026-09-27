# ZEN AI Router

**One front door for every campus question.** ZEN AI Router reads a student's message (English or Hinglish),
splits it into topics, sends each topic to the right campus office, and decides what should happen next:
**answer**, **clarify**, **handoff** to a person, or **refuse**.

Built for Microsoft Innovate 2026, Problem Statement 18, *"One Front Door for Everything"*.
This repository is the routing prototype and its evaluation; it does not answer questions itself.

```
$ python -m zenai.route "AC kharab hai aur mujhe room change karna hai"

#  topic                            LLM              kNN (share)             conf  action
1  AC kharab hai                    CAMPUS_SERVICES  CAMPUS_SERVICES (0.43)  0.71  handoff
2  aur mujhe room change karna hai  HOSTEL           HOSTEL (0.57)           0.79  handoff

MESSAGE -> action=handoff  primary=CAMPUS_SERVICES  secondary=HOSTEL  auto_routed=True
```

## Offices and actions

| Domain | Covers |
|---|---|
| IT | ERP, college email/Outlook, LMS, university laptops, network accounts and wifi connectivity |
| FEES | fee structure, payments, receipts, scholarships, refunds, fee deadlines |
| ACADEMICS | exams, academic calendar and holidays, attendance, faculty contacts, registrar documents, courses and batches, placements, clubs and fests |
| HOSTEL | room change and allotment, curfew/in-time, leave and outing, guests, hostel rules, laundry |
| CAMPUS_SERVICES | maintenance and cleaning, mess and food outlets, transport, sports facilities, library, lost and found |
| OUT_OF_SCOPE | not a campus question, jokes, opinions, or anyone's private records |

Actions: **answer** (an official document can answer it), **clarify** (ask the student a follow-up),
**handoff** (needs a person: the student's own records, a fix, a complaint), **refuse** (out of scope).

## How it works

1. **Signal A: LLM classifier.** One chat call splits the message into topics and labels each with a domain
   and a request type (info, needs_human, vague, not_campus). The prompt contains only the domain
   descriptions above, no example questions.
2. **Signal B: nearest-neighbour vote.** Each topic is embedded and compared with 72 labelled example
   questions; the 7 most similar vote for their domain.
3. **Confidence** = 0.5 × (the two signals agree) + 0.5 × (share of neighbours that voted for the LLM's domain).
4. **Decision rules:** out of scope → refuse; vague → clarify; confidence ≥ 0.7 → answer (info) or handoff
   (needs a person); 0.4 to 0.7 → clarify; below 0.4 → handoff. The message takes the strictest topic action.

Every model call goes through a disk cache, so re-running an evaluation costs no API calls and gives
identical results. Raw signals are saved per question, so thresholds can be re-tested offline.

## Results (v1, frozen thresholds)

Model: `gemini-3.5-flash-lite` (temperature 0) with `gemini-embedding-2`. Thresholds were tuned on the dev
set only, then frozen before the test set was run once. Every figure below is copied from a scorecard in
[`results/`](results/); intervals are 95% Wilson intervals.

**Test set** ([scorecard](results/20260927-032804_test/scorecard.md)):
**Routing accuracy: 85% (95% CI 74-92%), n = 60 test questions (53 real student questions (survey), 7 composed (multi-topic, written by team))**

| Metric | Test | Simulated variants ([scorecard](results/20260927-033305_simulated/scorecard.md)) |
|---|---|---|
| Routing accuracy | 85% (74-92%), n = 60 | 84% (78-88%), n = 178 |
| Routing accuracy, either office | 93% (84-97%), n = 60 | 91% (86-94%), n = 178 |
| Action accuracy | 69% (57-78%), n = 70 | 66% (59-72%), n = 206 |
| Multi-topic recall | 29% (13-53%), n = 17 | 45% (33-57%), n = 65 |
| Auto-route precision | 78% (63-88%), n = 41 | 79% (70-86%), n = 109 |
| Auto-route coverage | 59% (47-69%), n = 70 | 53% (46-60%), n = 206 |

Baselines on the same test rows:

| Method | Routing accuracy | Action accuracy |
|---|---|---|
| Keyword matching | 65% (52-76%) | not defined |
| Nearest-neighbour vote only | 50% (38-62%) | not defined |
| LLM only | 85% (74-92%) | 74% (63-83%) |
| Full router (LLM + neighbour confidence) | 85% (74-92%) | 69% (57-78%) |

**What this shows.** The LLM classifier routes clearly better than keyword matching. The
nearest-neighbour confidence layer, as built in v1, did not improve decisions: its action accuracy is below
the LLM alone on both dev and test, and low-confidence questions were not more likely to be wrong. Most
routing errors on test are wifi faults, which our labels send to CAMPUS_SERVICES but the domain
description assigns to IT. Splitting multi-topic messages is the weakest area.

## Quickstart

Requires Python 3.11 and a Gemini API key.

```bash
python -m venv .venv
.venv/Scripts/activate            # Windows; use `source .venv/bin/activate` on macOS/Linux
pip install -r requirements.txt
cp .env.example .env              # then set GEMINI_API_KEY=...

python -m zenai.route "wifi aur mess dono bekaar hai"
python -m zenai.route --json "fees"
pytest
```

## Web demo

```bash
uvicorn zenai.api:app --reload    # then open http://127.0.0.1:8000
```

Type a message (or click a sample from the dev set). Each topic appears as a card with its office, a
confidence bar marked with the frozen thresholds, the action, a one-line reason, and a "Why?" panel showing
the LLM's choice, the nearest-neighbour vote and the 3 closest example questions. The footer shows the model
and thresholds the demo is running. `/?q=<message>` routes a message on page load, for shareable links.
API: `POST /route {"message": "..."}`, `GET /health`, `GET /samples`.

## Evaluation workflow

```bash
python -m evaluation.check_data                    # validate labels in data/
python -m evaluation.run_eval --set dev --baselines
python -m evaluation.tune --write                  # grid search on saved dev signals, freeze thresholds
python -m evaluation.sync_simulated                # re-derive simulated labels from test labels
python -m evaluation.run_eval --set test --baselines
python -m evaluation.run_eval --set simulated
```

Each run writes `results/<timestamp>_<set>/`: `scorecard.md`, `scorecard.json`, `predictions.csv`,
`errors.csv`, a confusion matrix, a confidence-band chart, a leakage report and `run_meta.json` (commit,
config hash, data hashes, model, API call counts).

## Evaluation rules

- **Dev data is for tuning; test data is only for measuring.** Prompts, examples, keywords and thresholds
  never use `test_set.csv` or the simulated set. A leakage check runs before every evaluation.
- **Test runs need frozen thresholds** and each one is logged in
  [`results/test_runs.log`](results/test_runs.log), so the number of looks at the test set is on record.
- **Numbers come only from files in `results/`.** Nothing there is hand-edited; see
  [`results/CHANGELOG.md`](results/CHANGELOG.md) for anything that affects how runs should be read.

## Data

| File | Rows | What it is |
|---|---|---|
| `data/test_set.csv` | 70 | 62 real student questions from a survey + 8 multi-topic questions written by the team |
| `data/simulated_v1.csv` | 206 | LLM-generated variants of test questions (paraphrase, Hinglish, SMS typos, vaguer, merged), team verified |
| `data/dev_set.csv` | 32 | Tuning set, team drafted and verified |
| `data/examples.jsonl` | 72 | Labelled examples for the nearest-neighbour vote, 12 per domain |

## Known limits

- Small samples: some offices have only 4-5 test questions, so per-office intervals are wide.
- Labels are one team's judgement, not an independent gold standard.
- Results are for one model at temperature 0; another model or prompt needs a new evaluation.
- The test set has now been seen. A v2 router should be measured on fresh questions.

## Repository layout

```
zenai/        router: providers (cached Gemini client), llm_router, knn, confidence, router, CLI
evaluation/   data check, leakage check, simulated sync, run_eval, metrics, baselines, tuning, report
tests/        pytest suite (no network)
data/         labelled datasets
results/      one folder per evaluation run, test run log, changelog
config.yaml   provider, kNN, confidence weights, frozen thresholds
```
