questions.csv: reviewed by team on 22/11/2026

Milestone 2 helpdesk files:
- `questions.csv`: the 24 test questions (12 Normal, 8 Edge, 4 Invalid) with expected office, action, document, page and key fact. Also used to choose prompt changes, so it is a seen set.
- `final_test_table.md` / `.csv`: the final test table on questions.csv (21/24).
- `fresh_questions_draft.txt`: the team's 10 fresh questions, written after the prompts and search were frozen. `fresh_questions.csv` is the same 10 in the questions.csv columns (ids F01-F10), committed before the run.
- `fresh_check.md`: the fresh check result (6/10) with the cause of each failure.
- `runs/`: one folder per Milestone 2 run (outputs.jsonl, scorecard.md, run_meta.json with model, prompt sha256 and commit).
- `kb_manifest.csv`: every knowledge-base document and its source.

Milestone 1 routing files (kept unchanged): `dev_set.csv`, `test_set.csv`, `examples.jsonl`, `simulated_v1.csv`, `simulated_synced.csv`, and `results/` (one folder per routing run).
