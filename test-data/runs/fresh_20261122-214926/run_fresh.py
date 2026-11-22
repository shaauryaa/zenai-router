"""Fresh 10-question check: the frozen final pipeline and the final test's own scorer on test-data/fresh_questions.csv.

Run from code/:  python <this file>
Reuses, unchanged: helpdesk.pipeline.final_answer, helpdesk.score_p2.score, helpdesk.final_test.passed /
expected_text / actual_text / table_md / short. Only the question file and the output folder differ from
helpdesk/final_test.py; test-data/final_test_table.* are not touched. Stops (nothing saved) on a provider error or if
the run would exceed 40 API calls.
"""
from __future__ import annotations

import csv
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))

from helpdesk import handoff, pipeline, router_v2  # noqa: E402
from helpdesk.final_test import actual_text, expected_text, passed, short, table_md  # noqa: E402
from helpdesk.score_p2 import RUNS, git_info, pct, score  # noqa: E402
from zenai.paths import REPO_ROOT, TEST_DATA  # noqa: E402
from zenai.providers import ProviderError  # noqa: E402

QUESTIONS = TEST_DATA / "fresh_questions.csv"
MAX_CALLS = 40
PER_QUESTION_MAX = 3  # P1 + P2 + P3


def main() -> None:
    with open(QUESTIONS, encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    provider = pipeline.default_provider()
    started = datetime.now()
    records, table = [], []
    for row in rows:
        if provider.stats()["calls_made"] + PER_QUESTION_MAX > MAX_CALLS:
            sys.exit(f"stopped before {row['id']}: call budget of {MAX_CALLS} would be exceeded. Nothing saved.")
        try:
            out = pipeline.final_answer(row["question"], provider)
        except ProviderError as e:
            sys.exit(f"stopped at {row['id']}: {type(e).__name__}: {e}\nNothing saved.")
        s = score(row, out)
        ok = passed(row, s)
        records.append({"id": row["id"], "type": row["type"], "expected_action": row["expected_action"],
                        "key_fact": row["key_fact"], **out, "scores": s, "pass": ok})
        table.append([row["id"], short(row["question"], 60) or "(empty)", row["type"], expected_text(row),
                      actual_text(out), "Pass" if ok else "Fail"])
        print(f"{row['id']}: {out['action']:<9} {'Pass' if ok else 'FAIL'}  {out['reason']}  "
              f"(calls so far {provider.stats()['calls_made']})")

    n_pass = sum(r["pass"] for r in records)
    stats = provider.stats()
    run_id = f"fresh_{started.strftime('%Y%m%d-%H%M%S')}"
    totals = {k: {"k": sum(v for v in (r["scores"][k] for r in records) if v is not None),
                  "n": sum(r["scores"][k] is not None for r in records)} for k in records[0]["scores"]}
    meta = {"run_id": run_id,
            "title": "Fresh check: final pipeline P1 v2 + search routed5_all3 + P2 v2 + quote check + P3 "
                     + pipeline.FINAL["p3"],
            "runner": "run_fresh.py (copy in this folder); same functions as helpdesk/final_test.py, other question file",
            "started": started.isoformat(timespec="seconds"), "finished": datetime.now().isoformat(timespec="seconds"),
            "questions": QUESTIONS.relative_to(REPO_ROOT).as_posix(), "n_questions": len(records),
            "settings": provider.metadata(), "final": pipeline.FINAL,
            "router_prompt_file": router_v2.PROMPT_FILE.relative_to(REPO_ROOT).as_posix(),
            "router_prompt_sha256": router_v2.file_sha256(),
            "p2_prompt_file": pipeline.prompt_path("v2").relative_to(REPO_ROOT).as_posix(),
            "p2_prompt_sha256": pipeline.file_sha256("v2"),
            "p3_prompt_file": handoff.PROMPT_FILE.relative_to(REPO_ROOT).as_posix(),
            "p3_prompt_sha256": handoff.file_sha256(),
            "pass_rule": "action correct, and for rows with a key_fact also key fact found and quote verified",
            "pass": {"k": n_pass, "n": len(records)}, "totals": totals, "git": git_info(),
            "api_calls": stats["calls_made"], "cache_hits": stats["cache_hits"]}

    folder = RUNS / run_id
    folder.mkdir(parents=True)
    with open(folder / "outputs.jsonl", "w", encoding="utf-8", newline="\n") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    (folder / "run_meta.json").write_text(json.dumps(meta, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    header = (f"# Fresh check ({run_id})\n\n{meta['title']}. Model {meta['settings'].get('chat_model')}, "
              f"temperature {meta['settings'].get('temperature')}; commit {meta['git']['commit'][:10]}"
              f"{' (uncommitted changes)' if meta['git']['dirty'] else ''}; API calls {meta['api_calls']}, cache hits "
              f"{meta['cache_hits']}. Questions: `{meta['questions']}`.\n\nPass = {meta['pass_rule']}. "
              f"**Pass: {pct(n_pass, len(records))}**\n\n")
    metrics = "\n\n| Metric | Score |\n|---|---|\n" + "\n".join(
        f"| {k} | {pct(v['k'], v['n'])} |" for k, v in totals.items()) + "\n"
    (folder / "scorecard.md").write_text(header + table_md(table) + metrics, encoding="utf-8")
    with open(folder / "table.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["Test no.", "Input (short)", "Type", "Expected output", "Actual output (short)", "Pass/Fail"])
        w.writerows(table)
    shutil.copyfile(__file__, folder / "run_fresh.py")
    print(f"\nsaved {folder}\nPass {pct(n_pass, len(records))}; API calls {stats['calls_made']}, "
          f"cache hits {stats['cache_hits']}")


if __name__ == "__main__":
    main()
