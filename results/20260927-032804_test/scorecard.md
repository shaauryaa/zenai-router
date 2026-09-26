# ZEN AI Router scorecard: test set

Run `20260927-032804_test` | model `gemini-3.5-flash-lite` | commit `d6ef095622 (uncommitted changes)` | config `c91fa669b8e2`

**Routing accuracy: 85% (95% CI 74-92%), n = 60 test questions (53 real student questions (survey), 7 composed (multi-topic, written by team))**

- Routing accuracy, either office (primary or secondary label counts): 93% (95% CI 84-97%), n = 60
- Action accuracy (answer / clarify / handoff / refuse): 69% (95% CI 57-78%), n = 70
- Multi-topic recall (both labelled offices found): 29% (95% CI 13-53%), n = 17
- Auto-route precision: 78% (95% CI 63-88%), n = 41; auto-route coverage: 59% (95% CI 47-69%), n = 70
- Clarify rate: 9% (95% CI 4-17%), n = 70
- Fallback handoff rate (low confidence or unparseable LLM reply): 29% (95% CI 19-40%), n = 70
- Refuse recall on OUT_OF_SCOPE rows: 80% (95% CI 38-96%), n = 5

Routing accuracy and calibration exclude rows labelled clarify (no single correct office). Intervals are 95% Wilson score intervals.

## Baselines (same rows)

| method | routing accuracy | action accuracy |
|---|---|---|
| keyword | 65% (95% CI 52-76%), n = 60 | not defined |
| knn_only | 50% (95% CI 38-62%), n = 60 | not defined |
| llm_only | 85% (95% CI 74-92%), n = 60 | 74% (95% CI 63-83%), n = 70 |
| combined | 85% (95% CI 74-92%), n = 60 | 69% (95% CI 57-78%), n = 70 |

keyword: keyword lists written from the domain descriptions only. knn_only: nearest-example vote on the whole message. llm_only: LLM domain, action from request type alone. combined: the router.

## Breakdowns

### By labelled primary domain

| labelled primary domain | routing accuracy | action accuracy |
|---|---|---|
| ACADEMICS | 95% (95% CI 76-99%), n = 20 | 48% (95% CI 30-67%), n = 25 |
| CAMPUS_SERVICES | 76% (95% CI 55-89%), n = 21 | 75% (95% CI 55-88%), n = 24 |
| FEES | 100% (95% CI 57-100%), n = 5 | 67% (95% CI 30-90%), n = 6 |
| HOSTEL | 100% (95% CI 51-100%), n = 4 | 100% (95% CI 51-100%), n = 4 |
| IT | 60% (95% CI 23-88%), n = 5 | 100% (95% CI 61-100%), n = 6 |
| OUT_OF_SCOPE | 80% (95% CI 38-96%), n = 5 | 80% (95% CI 38-96%), n = 5 |

### By language

| language | routing accuracy | action accuracy |
|---|---|---|
| en | 82% (95% CI 69-91%), n = 45 | 69% (95% CI 55-79%), n = 54 |
| hinglish | 93% (95% CI 70-99%), n = 15 | 69% (95% CI 44-86%), n = 16 |

### By source

| source | routing accuracy | action accuracy |
|---|---|---|
| composed (multi-topic, written by team) | 71% (95% CI 36-92%), n = 7 | 75% (95% CI 41-93%), n = 8 |
| survey | 87% (95% CI 75-93%), n = 53 | 68% (95% CI 55-78%), n = 62 |

## Calibration (routing accuracy by confidence band)

| confidence band | routing accuracy |
|---|---|
| [0.0, 0.4) | 100% (95% CI 82-100%), n = 18 |
| [0.4, 0.7) | 100% (95% CI 21-100%), n = 1 |
| [0.7, 1.0] | 78% (95% CI 63-88%), n = 41 |

## Confusion matrix (rows: labelled, columns: predicted primary domain)

| labelled \ predicted | IT | FEES | ACADEMICS | HOSTEL | CAMPUS_SERVICES | OUT_OF_SCOPE |
|---|---|---|---|---|---|---|
| IT | 3 | 2 | 0 | 0 | 0 | 0 |
| FEES | 0 | 5 | 0 | 0 | 0 | 0 |
| ACADEMICS | 0 | 1 | 19 | 0 | 0 | 0 |
| HOSTEL | 0 | 0 | 0 | 4 | 0 | 0 |
| CAMPUS_SERVICES | 5 | 0 | 0 | 0 | 16 | 0 |
| OUT_OF_SCOPE | 0 | 0 | 1 | 0 | 0 | 4 |

## Known limits

- Small n: per-domain routing counts below 10: HOSTEL 4, IT 5, OUT_OF_SCOPE 5, FEES 5. Per-domain intervals are wide; differences between domains are mostly not significant.
- Labels were written by our team (label_status in this set: {'verified': 70}). They are one team's judgement, not an independent gold standard.
- The kNN examples (examples.jsonl) and the dev set were drafted by the team and verified by the team; examples label_status: {'verified': 72}.
- 8 of 70 test questions were written by the team, not students.
- One model (gemini-3.5-flash-lite) at temperature 0; results come from cached replies, so a re-run reproduces them exactly but a different model or prompt would not.
