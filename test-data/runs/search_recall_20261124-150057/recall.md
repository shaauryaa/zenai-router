# Search recall: routed5_all3 (old) vs routed5_all3_prog (new) (search_recall_20261124-150057)

Search query and domain: P1 v2's first topic as saved in `test-data/runs/final_20261122-201923`, `test-data/runs/fresh_20261122-214926` (no API call). Rows with an expected_doc only; first topic. Metric definitions: docstring of `code/helpdesk/search_recall.py`. The fresh rows are now seen: they were used to choose this fix.

Old search reproduces the saved retrieval: yes, every row that searched.

| Set | Rows | Doc hit@8 old | Doc hit@8 new | Page hit@8 old | Page hit@8 new | Fact hit@8 old | Fact hit@8 new |
|---|---|---|---|---|---|---|---|
| seen | 16 | 15/16 (94%) | 16/16 (100%) | 12/15 (80%) | 13/15 (87%) | 14/16 (88%) | 14/16 (88%) |
| fresh | 8 | 8/8 (100%) | 8/8 (100%) | 4/5 (80%) | 5/5 (100%) | 7/8 (88%) | 7/8 (88%) |

## Rows whose result changed

| Row | Programme files | Doc old -> new | Page old -> new | Fact old -> new |
|---|---|---|---|---|
| Q09 | COURSE_SPECIFIC/scset-academic-rules-ug.md | miss -> hit | miss -> hit | hit -> hit |
| F06 | COURSE_SPECIFIC/ba-liberal-arts-rulebook.md | hit -> hit | miss -> hit | hit -> hit |

## Rows where the new search restricted the routed part to programme files

- Q08 (seen): COURSE_SPECIFIC/seas-btech-ordinances-rules.md; search_query `minimum attendance requirement policy for B.Tech courses`
- Q09 (seen): COURSE_SPECIFIC/scset-academic-rules-ug.md; search_query `make-up exam policy and eligibility for missed end-sem exams due to illness`
- F06 (fresh): COURSE_SPECIFIC/ba-liberal-arts-rulebook.md; search_query `supplementary exams schedule academic calendar`
