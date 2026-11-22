# Scorecard: P1 v2 + search routed5_all3 + P2 v4 (step4_P1v2_search8_P2v4_20261122-193227)

Model gemini-3.5-flash-lite, temperature 0, reasoning_effort minimal; prompt `prompts/v4/P2_grounded_answer.md` sha256 73ef90487f07; router prompt `prompts/v2/P1_router.md` sha256 0d8fd3c7a1bf; commit c4089da567 (uncommitted changes); API calls 19, cache hits 23.

Router: helpdesk/router_v2.py classify() (P1 v2, prompts/v2/P1_router.md). Retrieval: helpdesk.kb_search.search_routed_plus_all(first topic search_query or question, first topic domain): top 5 from the routed folder + top 3 from all folders (k=8). Quote check: pipeline.check_quote with quote_forms(): ** and __ removed, OCR line-end hyphens joined, whitespace collapsed, lowercased.

| Metric | Score |
|---|---|
| Final action correct | 21/24 (88%) |
| Key fact found | 11/16 (69%) |
| Quote verified | 13/16 (81%) |
| Right document cited | 13/16 (81%) |
| Valid format (JSON) | 18/18 (100%) |
| Language matches (Hinglish rows) | 2/2 (100%) |
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
| Q06 | answer | answer | key_fact, doc_cited | P2 found, quote verified |
| Q07 | answer | answer | - | P2 found, quote verified |
| Q08 | answer | answer | - | P2 found, quote verified |
| Q09 | answer | not_found | action, key_fact, quote_verified, doc_cited | P2 found=false |
| Q10 | answer | answer | key_fact | P2 found, quote verified |
| Q11 | answer | answer | - | P2 found, quote verified |
| Q12 | answer | answer | key_fact | P2 found, quote verified |
| Q13 | answer | answer | - | P2 found, quote verified |
| Q14 | answer | answer | - | P2 found, quote verified |
| Q15 | answer | not_found | action, quote_verified | P2 said found but quote check failed: quote not found in the retrieved sections |
| Q16 | answer | not_found | action, key_fact, quote_verified, doc_cited | P2 found=false |
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
