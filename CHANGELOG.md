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
