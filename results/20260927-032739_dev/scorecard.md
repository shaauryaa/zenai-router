# ZEN AI Router scorecard: dev set

Run `20260927-032739_dev` | model `gemini-3.5-flash-lite` | commit `d6ef095622` | config `c91fa669b8e2`

**Routing accuracy: 92% (95% CI 75-98%), n = 25 dev questions (25 composed (team draft, team verified))**

- Routing accuracy, either office (primary or secondary label counts): 96% (95% CI 80-99%), n = 25
- Action accuracy (answer / clarify / handoff / refuse): 78% (95% CI 61-89%), n = 32
- Multi-topic recall (both labelled offices found): 55% (95% CI 28-79%), n = 11
- Auto-route precision: 94% (95% CI 74-99%), n = 18; auto-route coverage: 56% (95% CI 39-72%), n = 32
- Clarify rate: 19% (95% CI 9-35%), n = 32
- Fallback handoff rate (low confidence or unparseable LLM reply): 19% (95% CI 9-35%), n = 32
- Refuse recall on OUT_OF_SCOPE rows: 75% (95% CI 30-95%), n = 4

Routing accuracy and calibration exclude rows labelled clarify (no single correct office). Intervals are 95% Wilson score intervals.

## Baselines (same rows)

| method | routing accuracy | action accuracy |
|---|---|---|
| keyword | 64% (95% CI 45-80%), n = 25 | not defined |
| knn_only | 72% (95% CI 52-86%), n = 25 | not defined |
| llm_only | 92% (95% CI 75-98%), n = 25 | 88% (95% CI 72-95%), n = 32 |
| combined | 92% (95% CI 75-98%), n = 25 | 78% (95% CI 61-89%), n = 32 |

keyword: keyword lists written from the domain descriptions only. knn_only: nearest-example vote on the whole message. llm_only: LLM domain, action from request type alone. combined: the router.

## Breakdowns

### By labelled primary domain

| labelled primary domain | routing accuracy | action accuracy |
|---|---|---|
| ACADEMICS | 80% (95% CI 38-96%), n = 5 | 71% (95% CI 36-92%), n = 7 |
| CAMPUS_SERVICES | 100% (95% CI 57-100%), n = 5 | 100% (95% CI 65-100%), n = 7 |
| FEES | 100% (95% CI 34-100%), n = 2 | 50% (95% CI 15-85%), n = 4 |
| HOSTEL | 100% (95% CI 51-100%), n = 4 | 50% (95% CI 15-85%), n = 4 |
| IT | 100% (95% CI 57-100%), n = 5 | 100% (95% CI 61-100%), n = 6 |
| OUT_OF_SCOPE | 75% (95% CI 30-95%), n = 4 | 75% (95% CI 30-95%), n = 4 |

### By language

| language | routing accuracy | action accuracy |
|---|---|---|
| en | 88% (95% CI 66-97%), n = 17 | 75% (95% CI 55-88%), n = 24 |
| hinglish | 100% (95% CI 68-100%), n = 8 | 88% (95% CI 53-98%), n = 8 |

### By source

| source | routing accuracy | action accuracy |
|---|---|---|
| composed (team draft, team verified) | 92% (95% CI 75-98%), n = 25 | 78% (95% CI 61-89%), n = 32 |

## Calibration (routing accuracy by confidence band)

| confidence band | routing accuracy |
|---|---|
| [0.0, 0.4) | 75% (95% CI 30-95%), n = 4 |
| [0.4, 0.7) | 100% (95% CI 21-100%), n = 1 |
| [0.7, 1.0] | 95% (95% CI 76-99%), n = 20 |

## Confusion matrix (rows: labelled, columns: predicted primary domain)

| labelled \ predicted | IT | FEES | ACADEMICS | HOSTEL | CAMPUS_SERVICES | OUT_OF_SCOPE |
|---|---|---|---|---|---|---|
| IT | 5 | 0 | 0 | 0 | 0 | 0 |
| FEES | 0 | 2 | 0 | 0 | 0 | 0 |
| ACADEMICS | 1 | 0 | 4 | 0 | 0 | 0 |
| HOSTEL | 0 | 0 | 0 | 4 | 0 | 0 |
| CAMPUS_SERVICES | 0 | 0 | 0 | 0 | 5 | 0 |
| OUT_OF_SCOPE | 0 | 0 | 1 | 0 | 0 | 3 |

## Known limits

- Small n: per-domain routing counts below 10: FEES 2, HOSTEL 4, OUT_OF_SCOPE 4, CAMPUS_SERVICES 5, IT 5, ACADEMICS 5. Per-domain intervals are wide; differences between domains are mostly not significant.
- Labels were written by our team (label_status in this set: {'verified': 32}). They are one team's judgement, not an independent gold standard.
- The kNN examples (examples.jsonl) and the dev set were drafted by the team and verified by the team; examples label_status: {'verified': 72}.
- The dev set is used for tuning, so dev numbers are optimistic once thresholds are tuned. Do not quote dev numbers as the router's accuracy.
- One model (gemini-3.5-flash-lite) at temperature 0; results come from cached replies, so a re-run reproduces them exactly but a different model or prompt would not.
