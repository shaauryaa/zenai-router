# Scorecard: P2 v2, quote check re-run offline (P2_v2_requote_20261122-190741)

Model gemini-3.5-flash-lite, temperature 0, reasoning_effort minimal; prompt `prompts/v2/P2_grounded_answer.md` sha256 0e45708c06c8; commit c4089da567 (uncommitted changes); API calls 0, cache hits 0.

Router: zenai/llm_router.py classify() (v1, frozen). Retrieval: helpdesk.kb_search.search_for_route(question, first topic domain, k=5). Quote check: pipeline.check_quote with quote_forms(): ** and __ removed, OCR line-end hyphens joined, whitespace collapsed, lowercased. Re-scored offline from `test-data/runs/P2_v2_20261122-184902` (no API call).

| Metric | Score |
|---|---|
| Final action correct | 19/24 (79%) |
| Key fact found | 9/16 (56%) |
| Quote verified | 11/16 (69%) |
| Right document cited | 11/16 (69%) |
| Valid format (JSON) | 15/15 (100%) |
| Language matches (Hinglish rows) | 1/2 (50%) |
| Router office correct | 17/17 (100%) |

Metric definitions: see the docstring of code/helpdesk/score_p2.py. n differs per metric because each applies only to some rows.

## Per question

| id | expected | got | wrong metrics | reason |
|---|---|---|---|---|
| Q01 | answer | answer | - | P2 found, quote verified |
| Q02 | answer | answer | - | P2 found, quote verified |
| Q03 | answer | answer | - | P2 found, quote verified |
| Q04 | answer | answer | - | P2 found, quote verified |
| Q05 | answer | answer | - | P2 found, quote verified |
| Q06 | answer | handoff | action, key_fact, quote_verified, doc_cited | router request_type needs_human |
| Q07 | answer | not_found | action, key_fact, quote_verified, doc_cited | P2 found=false |
| Q08 | answer | answer | - | P2 found, quote verified |
| Q09 | answer | handoff | action, key_fact, quote_verified, doc_cited | router request_type needs_human |
| Q10 | answer | answer | key_fact | P2 found, quote verified |
| Q11 | answer | refuse | action, key_fact, quote_verified, doc_cited | router request_type not_campus |
| Q12 | answer | answer | - | P2 found, quote verified |
| Q13 | answer | answer | - | P2 found, quote verified |
| Q14 | answer | not_found | action, key_fact, quote_verified, doc_cited, language | P2 found=false |
| Q15 | answer | answer | - | P2 found, quote verified |
| Q16 | answer | answer | key_fact | P2 found, quote verified |
| Q17 | not_found | not_found | - | P2 found=false |
| Q18 | not_found | not_found | - | P2 found=false |
| Q19 | handoff | handoff | - | router request_type needs_human |
| Q20 | clarify | clarify | - | router request_type vague |
| Q21 | clarify | clarify | - | empty input: no LLM call |
| Q22 | refuse | refuse | - | router request_type not_campus |
| Q23 | refuse | refuse | - | router request_type not_campus |
| Q24 | refuse | refuse | - | router request_type not_campus |

## Notes

- Q16: two-topic row, scored on topic 1 only; topic 2 expected answer / HOSTEL, router gave HOSTEL / info
