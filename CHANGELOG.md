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
