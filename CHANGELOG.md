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
`prompts/v1/P1_router.md`. `score_p2` gains `--router`, `--search`, `--name`, `--rescore`. The project rules file in code/ now says
Milestone 2 runs go in test-data/runs/. The 24 questions were used both to choose and to measure these changes, so
the numbers are optimistic; a fresh question set is planned for Milestone 3.

Handoff prompt P3, Streamlit app and final test table:
- P3 handoff draft, one version (`prompts/final/P3_handoff.md`, same file in `prompts/v1/`), in
  `code/helpdesk/handoff.py`: input question, office, reason (not found in documents / needs the student's own record
  / needs someone to act) and a demo office address (`<tag from config/mailbox_map.yaml>@zenai-demo.example`, a
  reserved domain); output JSON {to, subject, body} with `[Your name]` and `[Enrollment no.]` placeholders. Code
  records checks (keys, `to`, body under 120 words, placeholders) and always sets `to` to the demo address.
- `pipeline.final_answer()`: the frozen final pipeline (P1 v2, search routed5_all3, P2 v2, quote check; prompts and
  search unchanged) plus P3 for not_found and handoff, fixed template text (no LLM call) for refuse and clarify, and
  a note naming the other topics when P1 finds two or more ("I answered the first one; please ask the other
  separately").
- Streamlit app `code/app.py` (`streamlit run code/app.py` from the repo root): question box, 4 example buttons
  (new wording, not from any question set), result card per action, "How ZEN AI decided" expander, 20 questions per
  session, cached index and answers, friendly error messages (`.streamlit/config.toml` hides error details).
  `streamlit==1.58.0` added to `code/requirements.txt`.
- Final test table `python -m helpdesk.final_test`: test-data/final_test_table.csv/.md, raw run
  test-data/runs/final_20261122-201923/. Pass (action correct, and key fact found and quote verified where a key fact
  is set): 21/24. Failures Q10 (key fact missing: answered from anti-ragging rules p.3, expected p.5), Q15 (quote
  check: OCR "ona scale"), Q16 (search missed IT Policy p.11). 5 API calls (the 5 P3 drafts), 41 cache hits.
- README.md rewritten for evaluators.

App polish and P3 v2:
- Streamlit app look (UI only; pipeline, prompts P1/P2, search and scoring unchanged): theme for light and dark in
  `.streamlit/config.toml` (system font, blue accent, softer radii; developer toolbar items hidden; error details
  still hidden), question box first and example buttons below in a wrapping row (readable at phone width), trust
  badges under the title, a coloured status badge per action, the quote shown with its source, page, date and link
  and the "Quote verified in source" badge, "Draft only. Nothing is sent." as a badge above the handoff draft, a
  progress bar for questions left. A few lines of scoped CSS in `code/app.py` for heading tracking, the quote block
  and button press feedback (off under reduced motion). The four example buttons give the same results as before.
- Hinglish example button: the old example ("cooler ya heater") was answered in English. New example (not from any
  question set): "kya main hostel room mein apna pet, jaise ek billi, rakh sakta hoon?", answered in Hinglish with a
  verified quote (Standing Orders for Hostel p.2).
- P3 handoff draft v2 (`prompts/v2/P3_handoff.md`, now also `prompts/final/P3_handoff.md`; v1 kept in `prompts/v1/`):
  the Q19 draft repeated itself ("because it needs my own record, could you please check my own record"). Two rule
  lines changed; details in docs/iteration_log.md. New `python -m helpdesk.final_handoff_rerun --base <final run>`
  re-runs only the rows that get a P3 draft and rewrites those rows of test-data/final_test_table.csv/.md; it stops
  without saving if any action or Pass/Fail changes. Run `test-data/runs/final_p3v2_20261122-212027/` (Q15-Q19,
  0 API calls: P1/P2 and P3 replies from the cache). Pass stays 21/24. `pipeline.FINAL["p3"]` is now "v2".

Fresh check: 10 new team-written questions (test-data/fresh_questions.csv, committed before the run) on the frozen final pipeline, run test-data/runs/fresh_20261122-214926/ (30 API calls): pass 6/10 (60%) vs 21/24 on the seen set; failures F01 (P2 found=false), F02 and F07 (quote check on table/OCR text), F06 (search miss); details in test-data/fresh_check.md. Prompts, search and code unchanged.
