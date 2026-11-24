"""Re-run the final pipeline from the LLM cache only, and compare with a saved run (Milestone 2 sprint S1, part D).

Run (from code/):  python -m helpdesk.cached_rerun seen     (test-data/questions.csv, base final_20261122-201923)
                   python -m helpdesk.cached_rerun fresh    (test-data/fresh_questions.csv, base fresh_20261122-214926)

Same pipeline.final_answer() and the final test's scorer (final_test.passed / expected_text / actual_text) as
helpdesk/final_test.py, with the current code (current quote check, search routed5_all3). The provider may not send any
request: a cache miss raises CacheOnlyError, the run stops and nothing is saved. Saves
test-data/runs/<seen: final_qv2tight | fresh: fresh_qv2tight>_<timestamp>/ (outputs.jsonl, run_meta.json, scorecard.md,
table.csv). Existing run folders and test-data/final_test_table.* are not touched.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime

from helpdesk import handoff, pipeline, router_v2
from helpdesk.final_test import COLUMNS, actual_text, expected_text, passed, short, table_md
from helpdesk.score_p2 import QUOTE_CHECK_TEXT, RUNS, git_info, pct, score
from zenai.paths import REPO_ROOT, TEST_DATA
from zenai.providers import ProviderError

SETS = {"seen": {"questions": TEST_DATA / "questions.csv", "base": "final_20261122-201923", "prefix": "final_qv2tight",
                 "label": "24 seen questions"},
        "fresh": {"questions": TEST_DATA / "fresh_questions.csv", "base": "fresh_20261122-214926",
                  "prefix": "fresh_qv2tight", "label": "10 fresh questions, now seen (used to choose the fix)"}}


class CacheOnlyError(ProviderError):
    pass


def cache_only(provider):
    """The provider with its network paths replaced: cache hits work, any request raises CacheOnlyError."""
    def blocked(*args, **kwargs):
        raise CacheOnlyError("cache miss: this call would go to the API")
    provider._chat_network = blocked
    provider._request = blocked
    return provider


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="python -m helpdesk.cached_rerun")
    ap.add_argument("set", choices=SETS)
    cfg = SETS[ap.parse_args(argv).set]
    with open(cfg["questions"], encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    base = {}
    for line in (RUNS / cfg["base"] / "outputs.jsonl").read_text(encoding="utf-8").splitlines():
        rec = json.loads(line)
        base[rec["id"]] = rec
    provider = cache_only(pipeline.default_provider())
    started = datetime.now()
    records, table, changes = [], [], []
    for row in rows:
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
        old = base[row["id"]]
        if (old["action"], old["pass"]) != (out["action"], ok):
            changes.append({"id": row["id"], "old_action": old["action"], "new_action": out["action"],
                            "old_pass": old["pass"], "new_pass": ok, "rule": (out.get("quote_check") or {}).get("rule"),
                            "reason": out["reason"]})
        print(f"{row['id']}: {out['action']:<9} {'Pass' if ok else 'FAIL'}  {out['reason']}")

    stats = provider.stats()
    if stats["calls_made"]:
        sys.exit(f"{stats['calls_made']} API calls counted although the network was blocked. Nothing saved.")
    n_pass, n_old = sum(r["pass"] for r in records), sum(base[r["id"]]["pass"] for r in records)
    run_id = f"{cfg['prefix']}_{started.strftime('%Y%m%d-%H%M%S')}"
    totals = {k: {"k": sum(v for v in (r["scores"][k] for r in records) if v is not None),
                  "n": sum(r["scores"][k] is not None for r in records)} for k in records[0]["scores"]}
    meta = {"run_id": run_id,
            "title": f"Cache-only re-run, quote check v2, old search routed5_all3: {cfg['label']}",
            "runner": "code/helpdesk/cached_rerun.py", "base_run": cfg["base"],
            "started": started.isoformat(timespec="seconds"), "finished": datetime.now().isoformat(timespec="seconds"),
            "questions": cfg["questions"].relative_to(REPO_ROOT).as_posix(), "n_questions": len(records),
            "question_status": "seen (used to choose the fix)" if cfg["prefix"].startswith("fresh") else "seen",
            "settings": provider.metadata(), "final": pipeline.FINAL, "quote_check": QUOTE_CHECK_TEXT,
            "router_prompt_sha256": router_v2.file_sha256(), "p2_prompt_sha256": pipeline.file_sha256("v2"),
            "p3_prompt_file": handoff.PROMPT_FILE.relative_to(REPO_ROOT).as_posix(),
            "p3_prompt_sha256": handoff.file_sha256(),
            "pass_rule": "action correct, and for rows with a key_fact also key fact found and quote verified",
            "pass": {"k": n_pass, "n": len(records)}, "base_pass": {"k": n_old, "n": len(records)},
            "changed_rows": changes, "totals": totals, "git": git_info(),
            "api_calls": stats["calls_made"], "cache_hits": stats["cache_hits"]}

    folder = RUNS / run_id
    folder.mkdir(parents=True)
    with open(folder / "outputs.jsonl", "w", encoding="utf-8", newline="\n") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    (folder / "run_meta.json").write_text(json.dumps(meta, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    with open(folder / "table.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(COLUMNS)
        w.writerows(table)
    change_lines = ["| Row | Old action | New action | Old | New | Quote rule | Reason |", "|---|---|---|---|---|---|---|"]
    change_lines += [f"| {c['id']} | {c['old_action']} | {c['new_action']} | {'Pass' if c['old_pass'] else 'Fail'} | "
                     f"{'Pass' if c['new_pass'] else 'Fail'} | {c['rule'] or '-'} | {c['reason'].replace('|', '/')} |"
                     for c in changes]
    header = (f"# {meta['title']} ({run_id})\n\nModel {meta['settings'].get('chat_model')}, temperature "
              f"{meta['settings'].get('temperature')}; commit {meta['git']['commit'][:10]}"
              f"{' (uncommitted changes)' if meta['git']['dirty'] else ''}; API calls {meta['api_calls']} (network "
              f"blocked), cache hits {meta['cache_hits']}. Questions: `{meta['questions']}` "
              f"({meta['question_status']}). Base run: `test-data/runs/{cfg['base']}`.\n\nPass = {meta['pass_rule']}. "
              f"**Pass: {pct(n_pass, len(records))}** (base run {pct(n_old, len(records))}).\n\n## Rows that changed\n\n"
              + ("\n".join(change_lines) if changes else "None.") + "\n\n## Table\n\n")
    metrics = "\n\n| Metric | Score |\n|---|---|\n" + "\n".join(
        f"| {k} | {pct(v['k'], v['n'])} |" for k, v in totals.items()) + "\n"
    (folder / "scorecard.md").write_text(header + table_md(table) + metrics, encoding="utf-8")
    print(f"\nsaved {folder.relative_to(REPO_ROOT).as_posix()}\nPass {pct(n_pass, len(records))} (base "
          f"{pct(n_old, len(records))}); API calls {stats['calls_made']}, cache hits {stats['cache_hits']}")


if __name__ == "__main__":
    main()
