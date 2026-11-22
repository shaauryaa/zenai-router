# Router P1 v2 on the seen set (P1_v2_seen_test_set_20261122-192440)

SEEN set: test-data/test_set.csv. v1's errors on it were studied before P1 v2 was written, so this is not a clean test. Definitions: docstring of code/helpdesk/route_eval.py (same as v1's llm_only).

Model gemini-3.5-flash-lite, temperature 0; router prompt `prompts/v2/P1_router.md` sha256 0d8fd3c7a1bf; commit c4089da567 (uncommitted changes); API calls 51, cache hits 25.

| Metric | P1 v1 (frozen, `20260927-032804_test`) | P1 v2 (this run) |
|---|---|---|
| Routing accuracy | 85% (n = 60) | 50/60 (83%) |
| Routing accuracy, either office | 93% (n = 60) | 55/60 (92%) |
| Action accuracy (from request_type, llm_only) | 74% (n = 70) | 53/70 (76%) |

P1 v2 predicted STUDENT_SUPPORT as the primary office on 0 routing rows (always wrong here: the labels have no STUDENT_SUPPORT).

## Routing errors

| id | labelled primary | labelled secondary | predicted |
|---|---|---|---|
| S004 | CAMPUS_SERVICES | IT | IT |
| S006 | IT | FEES | FEES |
| S008 | CAMPUS_SERVICES | IT | IT |
| S025 | OUT_OF_SCOPE | - | ACADEMICS |
| S029 | CAMPUS_SERVICES | - | IT |
| S030 | CAMPUS_SERVICES | IT | IT |
| S034 | CAMPUS_SERVICES | - | IT |
| S053 | CAMPUS_SERVICES | - | ACADEMICS |
| C002 | IT | ACADEMICS | FEES |
| C006 | ACADEMICS | FEES | FEES |
