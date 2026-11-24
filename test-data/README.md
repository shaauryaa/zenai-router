questions.csv: reviewed by team on 22/11/2026

Milestone 2 helpdesk files:
- `questions.csv`: the 24 test questions (12 Normal, 8 Edge, 4 Invalid) with expected office, action, document, page and key fact. Also used to choose prompt changes, so it is a seen set.
- `final_test_table.md` / `.csv`: the final test table on questions.csv (21/24).
- `fresh_questions_draft.txt`: the team's 10 fresh questions, written after the prompts and search were frozen. `fresh_questions.csv` is the same 10 in the questions.csv columns (ids F01-F10), committed before the run.
- `fresh_check.md`: the fresh check result (6/10) with the cause of each failure.
- `fresh2_questions_draft.txt`: the team's fresh check 2: part 1 F11-F20 (one question each) and part 2 F21-F28 (two-question messages, safety reports, two-turn follow-ups), written after the pipeline was frozen. `fresh2_questions.csv` is the same 18 rows in the questions.csv columns plus `turn2_question` and `turn1_expected_action`, committed with the scoring rules below before the run.
- `runs/`: one folder per Milestone 2 run (outputs.jsonl, scorecard.md, run_meta.json with model, prompt sha256 and commit).
- `kb_manifest.csv`: every knowledge-base document and its source.

Milestone 1 routing files (kept unchanged): `dev_set.csv`, `test_set.csv`, `examples.jsonl`, `simulated_v1.csv`, `simulated_synced.csv`, and `results/` (one folder per routing run).

## Fresh check 2 (fresh2_questions.csv): labels and scoring rules

Written on 24/11/2026, before fresh check 2 was run. The rules are fixed here first; the runner
(`python -m helpdesk.final_test --questions test-data/fresh2_questions.csv`) applies them, and no expected value is
changed after the run.

Labels:
- Two-question rows (F21-F24): as Q16 in questions.csv, `expected_office`, `expected_action`, `expected_doc`,
  `expected_page` and `key_fact` hold one value per part, `;`-separated in part order. An empty part (F24 part 2,
  not_found) has no document, page or key fact.
- Safety rows (F25, F26): `expected_action` is `safety`, `expected_office` STUDENT_SUPPORT, no document or key fact.
- Follow-up rows (F27, F28): `question` is turn 1, `turn1_expected_action` its expected action (clarify),
  `turn2_question` the student's short reply. `expected_office`, `expected_action`, `expected_doc`, `expected_page`
  and `key_fact` describe turn 2.
- F21-F28 have `router_scorable` = no and no `v1_domain`: the team gave no v1 routing labels for them.

Pass rules:
- One-question rows (F11-F20): as in every final run. Pass if the action is right and, for a row with a key fact,
  the key fact is found and the quote verified.
- Two-question rows: Pass only if BOTH parts have the right action (part 1 = topic 1, part 2 = topic 2 of the
  two-topic pipeline; a missing topic 2 is a wrong action), and every answered part (expected action answer) has its
  key fact and a verified quote.
- Safety rows: Pass if the action is safety and the card shows the contacts (the safety card is verified and has at
  least one email or phone line copied from the knowledge base).
- Follow-up rows: Pass if turn 1 is clarify and turn 2, run through the same follow-up function the app uses
  (`helpdesk.followup.resolve` / `remember`: the reply is joined to turn 1 after a clarify), passes like a normal row.

Metrics: for a two-question row, action, key fact, quote verified and right document hold only if they hold for
every part they apply to, and incomplete / needs_review count the row if any part is incomplete / needs review. For
a follow-up row the metrics are turn 2's. The row-type metrics (two-question rows, safety rows, follow-up rows) are
each the Pass count of that row type.

The team's draft also asks for things these rules leave out of Pass: the afternoon slot "2:00 PM to 4:00 PM" (F22),
a handoff draft for F24 part 2, and for safety rows the card first and then a Student Support draft. They are shown
in the run's table and outputs, not scored.
