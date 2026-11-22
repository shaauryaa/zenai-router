# Scorecard: P1 v2 + search route5 + P2 v2 (step2_P1v2_P2v2_20261122-190814)

Model gemini-3.5-flash-lite, temperature 0, reasoning_effort minimal; prompt `prompts/v2/P2_grounded_answer.md` sha256 0e45708c06c8; router prompt `prompts/v2/P1_router.md` sha256 0d8fd3c7a1bf; commit c4089da567 (uncommitted changes); API calls 34, cache hits 15.

Router: helpdesk/router_v2.py classify() (P1 v2, prompts/v2/P1_router.md). Retrieval: helpdesk.kb_search.search_for_route(question, first topic domain, k=5). Quote check: pipeline.check_quote with quote_forms(): ** and __ removed, OCR line-end hyphens joined, whitespace collapsed, lowercased.

| Metric | Score |
|---|---|
| Final action correct | 21/24 (88%) |
| Key fact found | 11/16 (69%) |
| Quote verified | 13/16 (81%) |
| Right document cited | 13/16 (81%) |
| Valid format (JSON) | 18/18 (100%) |
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
| Q06 | answer | answer | - | P2 found, quote verified |
| Q07 | answer | not_found | action, key_fact, quote_verified, doc_cited | P2 found=false |
| Q08 | answer | answer | - | P2 found, quote verified |
| Q09 | answer | not_found | action, key_fact, quote_verified, doc_cited | P2 found=false |
| Q10 | answer | answer | key_fact | P2 found, quote verified |
| Q11 | answer | answer | - | P2 found, quote verified |
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
