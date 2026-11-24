"""Re-score a saved final-test or fresh-check run with the current scorer. Offline: no API call, no pipeline step is
re-run; only helpdesk.score_p2.score and helpdesk.final_test.passed are applied again to the saved outputs.

Run (from code/):  python -m helpdesk.rescore_run ../test-data/runs/final_20261124-174710 --name final_rescored

Saves test-data/runs/<name>_<timestamp>/ (the source folder is not touched) with outputs.jsonl (each record with
the new scores and pass plus old_scores and old_pass), run_meta.json and scorecard.md: every metric old vs new,
the rows whose scores changed, and the rows for a human to read (incomplete, needs_review).
"Old wrong answers shown" is the earlier single column: action answer and (expected action not answer, or key fact
missing under the old scores).
"""
from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime
from pathlib import Path

from helpdesk.final_test import passed, review_md
from helpdesk.score_p2 import METRICS, RUNS, first, git_info, pct, score
from zenai.paths import REPO_ROOT

RECORD_ONLY = ("id", "type", "expected_action", "key_fact", "scores", "pass")


def old_wrong_shown(rec: dict) -> bool:
    s = rec["scores"]
    return rec["action"] == "answer" and (first(rec["expected_action"]) != "answer" or s.get("key_fact") is False)


def tally(records: list[dict], field: str) -> dict:
    out = {}
    for key, _ in METRICS:
        vals = [r[field][key] for r in records if r[field].get(key) is not None]
        out[key] = {"k": sum(vals), "n": len(vals)}
    return out


def rescore(source: Path, name: str) -> Path:
    source = Path(source).resolve()
    src_meta = json.loads((source / "run_meta.json").read_text(encoding="utf-8"))
    with open(REPO_ROOT / src_meta["questions"], encoding="utf-8", newline="") as f:
        rows = {r["id"]: r for r in csv.DictReader(f)}
    started = datetime.now()
    records = []
    for line in (source / "outputs.jsonl").read_text(encoding="utf-8").splitlines():
        old = json.loads(line)
        row = rows[old["id"]]
        out = {k: v for k, v in old.items() if k not in RECORD_ONLY}
        new = score(row, out)
        records.append({**old, "scores": new, "pass": passed(row, new), "old_scores": old["scores"],
                        "old_pass": old["pass"], "old_wrong_shown": old_wrong_shown(old)})

    run_id = f"{name}_{started.strftime('%Y%m%d-%H%M%S')}"
    old_t, new_t = tally(records, "old_scores"), tally(records, "scores")
    n = len(records)
    meta = {"run_id": run_id, "title": f"Offline re-score of {src_meta['run_id']} with the current scorer",
            "rescored_from": source.relative_to(REPO_ROOT).as_posix(), "questions": src_meta["questions"],
            "question_status": src_meta.get("question_status", ""), "n_questions": n,
            "started": started.isoformat(timespec="seconds"), "git": git_info(), "api_calls": 0,
            "old_pass": {"k": sum(r["old_pass"] for r in records), "n": n},
            "pass": {"k": sum(r["pass"] for r in records), "n": n},
            "old_wrong_shown": [r["id"] for r in records if r["old_wrong_shown"]],
            "old_totals": old_t, "totals": new_t}

    folder = RUNS / run_id
    folder.mkdir(parents=True)
    with open(folder / "outputs.jsonl", "w", encoding="utf-8", newline="\n") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    (folder / "run_meta.json").write_text(json.dumps(meta, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    lines = [f"# {meta['title']} ({run_id})", "",
             f"Source `{meta['rescored_from']}`; questions `{meta['questions']}`"
             + (f" ({meta['question_status']})" if meta["question_status"] else "")
             + f"; commit {meta['git']['commit'][:10]}; API calls 0.", "",
             f"**Pass: {pct(meta['old_pass']['k'], n)} -> {pct(meta['pass']['k'], n)}**", "",
             "| Metric | Old | New |", "|---|---|---|"]
    for key, label in METRICS:
        o = old_t.get(key, {"k": 0, "n": 0})
        lines.append(f"| {label} | {pct(o['k'], o['n']) if o['n'] else '-'} | {pct(new_t[key]['k'], new_t[key]['n'])} |")
    lines += ["", f"Old \"wrong answers shown\": {', '.join(meta['old_wrong_shown']) or 'none'}", "",
              "## Rows whose scores changed", ""]
    changed = [r for r in records
               if any(r["old_scores"].get(k) != v for k, v in r["scores"].items() if k in r["old_scores"])
               or r["old_pass"] != r["pass"]]
    lines += [f"- {r['id']}: " + ", ".join(f"{k} {r['old_scores'].get(k)} -> {v}" for k, v in r["scores"].items()
                                           if k in r["old_scores"] and r["old_scores"][k] != v)
              + f"; pass {r['old_pass']} -> {r['pass']}" for r in changed] or ["none"]
    (folder / "scorecard.md").write_text("\n".join(lines) + "\n" + review_md(records), encoding="utf-8")
    return folder


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="python -m helpdesk.rescore_run")
    ap.add_argument("source", type=Path, help="saved run folder (final_test or fresh check)")
    ap.add_argument("--name", required=True, help="new run folder name before the timestamp")
    args = ap.parse_args(argv)
    folder = rescore(args.source, args.name)
    print((folder / "scorecard.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
