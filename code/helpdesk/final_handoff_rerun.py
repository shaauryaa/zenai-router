"""Re-run only the handoff-draft rows of the final test table after a P3 change, and update those rows in place.

Run (from code/):  python -m helpdesk.final_handoff_rerun --base final_20261122-201923

The rows re-run are the ones whose saved action in the base run is not_found or handoff (the rows that get a P3
draft). They go through the same pipeline.final_answer() as helpdesk.final_test; P1 and P2 replies come from the
provider cache, so only the P3 call is new. The run is saved in test-data/runs/final_p3<version>_<timestamp>/
(outputs.jsonl, run_meta.json, scorecard.md); the base run folder is never touched. In
test-data/final_test_table.csv/.md only the re-run rows are rewritten, and the .md header names both runs.

The script stops without saving anything if a re-run row's action or Pass/Fail differs from the base run: a P3
change must not change any decision or score.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime

from helpdesk import final_test, handoff, pipeline
from helpdesk.final_test import COLUMNS, TABLE_CSV, TABLE_MD, actual_text, passed, short, table_md
from helpdesk.score_p2 import RUNS, git_info, pct, read_rows, score
from zenai.paths import REPO_ROOT
from zenai.providers import ProviderError

HANDOFF_ACTIONS = ("not_found", "handoff")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True, help="final run folder name in test-data/runs/")
    args = ap.parse_args()
    base_dir = RUNS / args.base
    base = {}
    with open(base_dir / "outputs.jsonl", encoding="utf-8") as f:
        for line in f:
            rec = json.loads(line)
            base[rec["id"]] = rec
    ids = [i for i, rec in base.items() if rec["action"] in HANDOFF_ACTIONS]
    rows = {r["id"]: r for r in read_rows()}

    provider = pipeline.default_provider()
    started = datetime.now()
    records, table = [], {}
    for i in ids:
        row = rows[i]
        try:
            out = pipeline.final_answer(row["question"], provider)
        except ProviderError as e:
            sys.exit(f"stopped at {i}: {type(e).__name__}: {e}\nNothing saved.")
        s = score(row, out)
        ok = passed(row, s)
        if out["action"] != base[i]["action"] or ok != base[i]["pass"]:
            sys.exit(f"{i}: action/pass changed ({base[i]['action']}/{base[i]['pass']} -> {out['action']}/{ok}). "
                     "Nothing saved.")
        records.append({"id": i, "type": row["type"], "expected_action": row["expected_action"],
                        "key_fact": row["key_fact"], **out, "scores": s, "pass": ok})
        table[i] = [i, short(row["question"], 60) or "(empty)", row["type"], final_test.expected_text(row),
                    actual_text(out), "Pass" if ok else "Fail"]
        print(f"{i}: {out['action']:<9} {'Pass' if ok else 'FAIL'}  {out['p3']['draft']['subject'] if out['p3'] and out['p3']['draft'] else '-'}")

    stats = provider.stats()
    version = pipeline.FINAL["p3"]
    run_id = f"final_p3{version}_{started.strftime('%Y%m%d-%H%M%S')}"
    meta = {"run_id": run_id, "title": f"Final test table, handoff-draft rows only, re-run with P3 {version}",
            "base_run": args.base, "rows": ids,
            "started": started.isoformat(timespec="seconds"), "finished": datetime.now().isoformat(timespec="seconds"),
            "settings": provider.metadata(), "final": pipeline.FINAL,
            "p3_prompt_file": handoff.PROMPT_FILE.relative_to(REPO_ROOT).as_posix(),
            "p3_prompt_sha256": handoff.file_sha256(),
            "pass_rule": "same as the base run; every re-run row keeps its base action and Pass/Fail",
            "git": git_info(), "api_calls": stats["calls_made"], "cache_hits": stats["cache_hits"]}

    # Rebuild the table: base rows from the current table file, re-run rows replaced.
    with open(TABLE_CSV, encoding="utf-8", newline="") as f:
        current = list(csv.reader(f))[1:]
    merged = [table.get(r[0], r) for r in current]
    n_pass = sum(r[5] == "Pass" for r in merged)

    folder = RUNS / run_id
    folder.mkdir(parents=True)
    with open(folder / "outputs.jsonl", "w", encoding="utf-8", newline="\n") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    (folder / "run_meta.json").write_text(json.dumps(meta, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    (folder / "scorecard.md").write_text(
        f"# {meta['title']} ({run_id})\n\nBase run `test-data/runs/{args.base}/`. Rows: {', '.join(ids)}. "
        f"API calls {stats['calls_made']}, cache hits {stats['cache_hits']}.\n\n"
        + table_md([table[i] for i in ids]) + "\n", encoding="utf-8")

    md = TABLE_MD.read_text(encoding="utf-8")
    head, rest = md.split("| " + " | ".join(COLUMNS) + " |", 1)
    note = (f"Handoff-draft rows {', '.join(ids)} re-run with P3 {version} in `test-data/runs/{run_id}/` (P1 and P2 "
            f"replies from the cache, so actions and Pass/Fail are unchanged; only the drafts are new). Every other "
            f"row is from `test-data/runs/{args.base}/`. **Pass: {pct(n_pass, len(merged))}**\n\n")
    if "Handoff-draft rows" in head:
        head = head.split("Handoff-draft rows", 1)[0]
    TABLE_MD.write_text(head + note + table_md(merged) + "\n\nRaw runs: `test-data/runs/" + args.base
                        + "/`, `test-data/runs/" + run_id + "/`.\n", encoding="utf-8")
    with open(TABLE_CSV, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(COLUMNS)
        w.writerows(merged)
    print(f"\nsaved {folder}\nPass {pct(n_pass, len(merged))}; API calls {stats['calls_made']}, "
          f"cache hits {stats['cache_hits']}")


if __name__ == "__main__":
    main()
