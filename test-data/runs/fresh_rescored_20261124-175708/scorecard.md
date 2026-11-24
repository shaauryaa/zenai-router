# Offline re-score of fresh_20261124-174736 with the current scorer (fresh_rescored_20261124-175708)

Source `test-data/runs/fresh_20261124-174736`; questions `test-data/fresh_questions.csv` (fresh check 1, now seen (used to choose today's fixes)); commit 128d69b95e; API calls 0.

**Pass: 8/10 (80%) -> 9/10 (90%)**

| Metric | Old | New |
|---|---|---|
| Final action correct | 9/10 (90%) | 9/10 (90%) |
| Key fact found | 6/8 (75%) | 7/8 (88%) |
| Quote verified | 7/8 (88%) | 7/8 (88%) |
| Right document cited | 7/8 (88%) | 7/8 (88%) |
| Valid format (JSON) | 10/10 (100%) | 10/10 (100%) |
| Language matches (Hinglish rows) | 0/1 (0%) | 0/1 (0%) |
| Router office correct | 9/10 (90%) | 9/10 (90%) |
| Topic 2 action correct (two-action rows) | - | n/a |
| Incomplete: answer shown, key fact missing (lower is better) | - | 0/7 (0%) |
| Needs review: answer shown, expected action not answer (lower is better) | - | 0/7 (0%) |

Old "wrong answers shown": F02

## Rows whose scores changed

- F02: key_fact False -> True; pass False -> True

## Rows for a human to read

- Incomplete (answer shown, key fact missing): none
- Needs review (answer shown, expected action not answer): none
