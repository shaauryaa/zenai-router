# Search recall: routed5_all3_prog (old) vs dual_prog (new) (search_recall_dual_20261124-180009)

P1 v2 topics as saved in `test-data/runs/final_20261124-174710`, `test-data/runs/fresh_20261124-174736` (no API call). Every topic with an expected_doc, both topics of two-topic rows. Both sets are seen. Definitions: docstring of `code/helpdesk/search_recall_dual.py`.

Old search reproduces the saved retrieval: yes, every topic that searched.

| Set | Topics | Page hit@8 old | Page hit@8 new | Doc hit@8 old | Doc hit@8 new | Fact hit@8 old | Fact hit@8 new |
|---|---|---|---|---|---|---|---|
| seen | 17 | 13/16 (81%) | 14/16 (88%) | 17/17 (100%) | 17/17 (100%) | 14/17 (82%) | 15/17 (88%) |
| fresh 1 | 8 | 5/5 (100%) | 5/5 (100%) | 8/8 (100%) | 8/8 (100%) | 7/8 (88%) | 7/8 (88%) |

Topics that lose their expected page: none. Topics that gain it: Q16 t2.

**Decision: adopt dual_prog** (rule: adopt only if no topic loses its expected page).

## Topics whose result changed

| Topic | Page old -> new | Doc old -> new | Fact old -> new | search_query | topic text |
|---|---|---|---|---|---|
| Q16 t2 | miss -> hit | hit -> hit | miss -> hit | hostel curfew in-time rules | And what time do we have to be back on campus at night? |
