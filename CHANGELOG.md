# Changelog

## 2026-11-22

Milestone 2 started. Repository reorganised into the course layout (code/, prompts/, test-data/, docs/). No files
removed; earlier state tagged pre-m2.

Data files (.csv, .jsonl) are kept with LF line endings (.gitattributes).

Helpdesk knowledge base added: 24 documents from the team's files converted to Markdown under code/kb/<OFFICE>/ (OCR
text for scanned PDFs, pdftotext for text PDFs, two original .md files), plus the existing fee structure page: 25
documents in 7 office folders, listed in test-data/kb_manifest.csv. Excluded by team decision: PhD ordinances,
finance/guidelines.pdf, punctualiti.pdf, the fee payment guidelines .docx, the admission withdrawal form, hostel warden
contacts, the HR manual and processed-data/. PDFs are not committed. Student details (8 entries) and staff personal
mobile numbers and emails are redacted; names, roles, office landlines and role mailboxes are kept. INDEX.md entries
gain a free-text `date` field (the date exactly as the team's source list gives it). New BM25 search:
`python -m helpdesk.kb_search "query" --office HOSTEL --k 4`.

KB build tools committed (`python -m tools.build_kb`; it reproduces the committed kb/ byte for byte). The late-fee
annexure, the Room Partner manual and the anti-ragging/ICC contacts file are marked `public_or_permission: unverified`
(new provenance value, also in docs/API.md).

Grounded-answer prompt P2, versions v1-v3 (prompts/v1..v3/P2_grounded_answer.md; final copy in prompts/final/, with
the frozen v1 router prompt copied to prompts/final/P1_router.md). New pipeline `code/helpdesk/pipeline.py` (router P1
-> kb_search -> P2 -> code quote check) and runner/scorer `python -m helpdesk.score_p2 <version>`, which saves
test-data/runs/P2_<version>_<timestamp>/ (outputs.jsonl, scorecard.md, run_meta.json). Recorded runs on
test-data/questions.csv, final action correct: v1 17/24, v2 17/24, v3 16/24 (v3 fixed one quote, regressed two
answers into refusals). Details and per-question errors in docs/iteration_log.md. zenai/llm_router.py unchanged.

Router P1 v2, search and quote check (Milestone 2 steps 1-4; each step re-ran all 24 questions in
test-data/questions.csv, runs in test-data/runs/, details in docs/iteration_log.md):
1. Quote check normalisation in `code/helpdesk/pipeline.py`: markdown `**`/`__` removed, OCR line-end hyphens joined
   (hyphen kept or dropped), whitespace collapsed, on quote and sections. The saved P2 v2 run re-scored offline
   (`python -m helpdesk.score_p2 --rescore`): final action 17/24 -> 19/24.
2. Router P1 v2 (`prompts/v2/P1_router.md`, `code/helpdesk/router_v2.py`): STUDENT_SUPPORT domain, request_type rule
   (policy questions are info), new `search_query` field. `zenai/llm_router.py` (v1) unchanged. With P2 v2: 21/24.
   P1 v2 alone on test-data/test_set.csv (seen set, `python -m helpdesk.route_eval`): routing 50/60 (83%) vs v1's 85%.
3. Search `kb_search.search_routed_plus_all`: P1 v2's search_query, top 5 from the routed folder + top 3 from all
   folders (k=8); STUDENT_SUPPORT mapped to its kb folder. With P2 v2: 22/24.
4. P2 v4 (`prompts/v4/`) = v2 + one Hinglish rule: 21/24 (Q09 regressed), so the final P2 stays v2.
Final prompts: `prompts/final/P1_router.md` = P1 v2, `prompts/final/P2_grounded_answer.md` = P2 v2; P1 v1 kept in
`prompts/v1/P1_router.md`. `score_p2` gains `--router`, `--search`, `--name`, `--rescore`. code/CLAUDE.md now says
Milestone 2 runs go in test-data/runs/. The 24 questions were used both to choose and to measure these changes, so
the numbers are optimistic; a fresh question set is planned for Milestone 3.
