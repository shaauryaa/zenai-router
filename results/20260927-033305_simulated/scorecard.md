# ZEN AI Router scorecard: simulated set

Run `20260927-033305_simulated` | model `gemini-3.5-flash-lite` | commit `d6ef095622 (uncommitted changes)` | config `c91fa669b8e2`

**Routing accuracy: 84% (95% CI 78-88%), n = 178 simulated variants**

- Routing accuracy, either office (primary or secondary label counts): 91% (95% CI 86-94%), n = 178
- Action accuracy (answer / clarify / handoff / refuse): 66% (95% CI 59-72%), n = 206
- Multi-topic recall (both labelled offices found): 45% (95% CI 33-57%), n = 65
- Auto-route precision: 79% (95% CI 70-86%), n = 109; auto-route coverage: 53% (95% CI 46-60%), n = 206
- Clarify rate: 15% (95% CI 11-21%), n = 206
- Fallback handoff rate (low confidence or unparseable LLM reply): 32% (95% CI 26-39%), n = 206
- Refuse recall on OUT_OF_SCOPE rows: 80% (95% CI 49-94%), n = 10

Routing accuracy and calibration exclude rows labelled clarify (no single correct office). Intervals are 95% Wilson score intervals.

## Breakdowns

### By labelled primary domain

| labelled primary domain | routing accuracy | action accuracy |
|---|---|---|
| ACADEMICS | 96% (95% CI 88-99%), n = 57 | 45% (95% CI 34-57%), n = 71 |
| CAMPUS_SERVICES | 70% (95% CI 58-80%), n = 64 | 73% (95% CI 61-82%), n = 73 |
| FEES | 100% (95% CI 81-100%), n = 16 | 68% (95% CI 46-85%), n = 19 |
| HOSTEL | 100% (95% CI 78-100%), n = 14 | 93% (95% CI 69-99%), n = 14 |
| IT | 65% (95% CI 41-83%), n = 17 | 89% (95% CI 69-97%), n = 19 |
| OUT_OF_SCOPE | 80% (95% CI 49-94%), n = 10 | 80% (95% CI 49-94%), n = 10 |

### By language

| language | routing accuracy | action accuracy |
|---|---|---|
| en | 83% (95% CI 75-89%), n = 102 | 71% (95% CI 62-79%), n = 118 |
| hinglish | 84% (95% CI 74-91%), n = 76 | 59% (95% CI 49-69%), n = 88 |

### By source

| source | routing accuracy | action accuracy |
|---|---|---|
| simulated (Claude draft, team verified) | 84% (95% CI 78-88%), n = 178 | 66% (95% CI 59-72%), n = 206 |

### By variant type

| variant type | routing accuracy | action accuracy |
|---|---|---|
| language_switch | 83% (95% CI 72-91%), n = 60 | 63% (95% CI 51-73%), n = 70 |
| merge | 80% (95% CI 61-91%), n = 25 | 76% (95% CI 57-89%), n = 25 |
| paraphrase | 83% (95% CI 72-91%), n = 60 | 64% (95% CI 53-74%), n = 70 |
| typo_sms | 88% (95% CI 73-95%), n = 33 | 64% (95% CI 47-78%), n = 33 |
| vaguer | n/a (n = 0) | 88% (95% CI 53-98%), n = 8 |

## Calibration (routing accuracy by confidence band)

| confidence band | routing accuracy |
|---|---|
| [0.0, 0.4) | 89% (95% CI 79-95%), n = 57 |
| [0.4, 0.7) | 100% (95% CI 80-100%), n = 15 |
| [0.7, 1.0] | 78% (95% CI 70-85%), n = 106 |

## Confusion matrix (rows: labelled, columns: predicted primary domain)

| labelled \ predicted | IT | FEES | ACADEMICS | HOSTEL | CAMPUS_SERVICES | OUT_OF_SCOPE |
|---|---|---|---|---|---|---|
| IT | 11 | 6 | 0 | 0 | 0 | 0 |
| FEES | 0 | 16 | 0 | 0 | 0 | 0 |
| ACADEMICS | 0 | 2 | 55 | 0 | 0 | 0 |
| HOSTEL | 0 | 0 | 0 | 14 | 0 | 0 |
| CAMPUS_SERVICES | 17 | 0 | 1 | 1 | 45 | 0 |
| OUT_OF_SCOPE | 0 | 0 | 2 | 0 | 0 | 8 |

## Known limits

- Small n: per-domain routing counts below 10: none. Per-domain intervals are wide; differences between domains are mostly not significant.
- Labels were written by our team (label_status in this set: {'verified': 206}). They are one team's judgement, not an independent gold standard.
- The kNN examples (examples.jsonl) and the dev set were drafted by the team and verified by the team; examples label_status: {'verified': 72}.
- The simulated set was drafted by an LLM (Claude) from test seeds and verified by the team; its labels are re-derived from the current seed labels by rule (evaluation/sync_simulated.py).
- One model (gemini-3.5-flash-lite) at temperature 0; results come from cached replies, so a re-run reproduces them exactly but a different model or prompt would not.
