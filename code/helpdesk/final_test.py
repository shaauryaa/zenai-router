"""Final test table: the final pipeline (helpdesk.pipeline.final_answer with pipeline.FINAL: P1 -> search -> P2 ->
quote check -> P3 handoff draft / templates, two topics) on all 24 rows of test-data/questions.csv.

Run (from code/):  python -m helpdesk.final_test [--no-table] [--max-calls N]
--no-table saves only the run folder (test-data/final_test_table.* untouched); --max-calls stops (nothing saved)
before a question that could take the run past N API calls (3 per topic: P1, P2, P3).

Writes test-data/final_test_table.csv and test-data/final_test_table.md with the columns
    Test no. | Input (short) | Type | Expected output | Actual output (short) | Pass/Fail
and saves the raw run in test-data/runs/final_<timestamp>/ (outputs.jsonl, run_meta.json, scorecard.md with the
same table and the score_p2 metrics).

Pass = final action == expected action, and for rows with a key_fact also key fact found (score_p2 metric key_fact)
and quote verified (score_p2 metric quote_verified). Two-topic rows (Q16) are scored on topic 1, as in every other
run; the two-topic pipeline's second topic is the separate metric topic2_action (not part of Pass). Expected values are read from questions.csv as they are; nothing is changed to make a row pass.
A provider error (daily quota, network) stops the run and nothing is saved.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime

from helpdesk import handoff, pipeline, router_v2
from helpdesk.score_p2 import QUESTIONS, QUOTE_CHECK_TEXT, RUNS, first, git_info, pct, read_rows, score
from zenai.paths import REPO_ROOT, TEST_DATA
from zenai.providers import ProviderError

COLUMNS = ["Test no.", "Input (short)", "Type", "Expected output", "Actual output (short)", "Pass/Fail"]
TABLE_CSV = TEST_DATA / "final_test_table.csv"
TABLE_MD = TEST_DATA / "final_test_table.md"


def short(text: str, n: int = 70) -> str:
    text = " ".join((text or "").split())
    return text if len(text) <= n else text[:n - 3].rstrip() + "..."


def expected_text(row: dict) -> str:
    action, fact = first(row["expected_action"]), first(row["key_fact"])
    text = action + (" (topic 1 of 2)" if ";" in row["expected_action"] else "")
    if fact:
        text += f'; key fact "{short(fact, 60)}", quote verified'
    elif action in ("not_found", "handoff"):
        text += "; handoff draft"
    if ";" in row["expected_action"]:
        text += f"; topic 2 expected {row['expected_action'].split(';')[1]}"
    return text


def actual_text(out: dict) -> str:
    text = topic_text(out)
    results = out.get("topic_results") or []
    if len(results) > 1:
        text += f"; topic 2: {topic_text(results[1])}"
    if out.get("multi_topic_note"):
        text += f"; multi-topic note ({len(out['other_topics'])} more topic)"
    return text


def topic_text(out: dict) -> str:
    """The short actual output for one topic (a pipeline result or one of its topic_results)."""
    action = out["action"]
    if action == "answer":
        p2 = out["p2"] or {}
        page = f" p.{p2['page']}" if p2.get("page") else ""
        near = " (near match)" if (out.get("quote_check") or {}).get("rule") == "near" else ""
        text = (f'answer: "{short(p2.get("answer", ""), 70)}" [{short(p2.get("doc_title", ""), 40)}{page}; '
                f'quote verified{near}]')
    elif action in ("not_found", "handoff"):
        p3 = out.get("p3") or {}
        d = p3.get("draft")
        text = (f'{action}; draft to {p3.get("office_email")}: "{short(d["subject"], 50)}"' if d
                else f"{action}; draft failed ({p3.get('error')})")
    else:
        text = f'{action}: "{short(out.get("reply_text", ""), 60)}"'
    return text


def passed(row: dict, s: dict) -> bool:
    if not s["action"]:
        return False
    if first(row["key_fact"]):
        return bool(s["key_fact"]) and bool(s["quote_verified"])
    return True


def md_cell(text: str) -> str:
    return str(text).replace("|", "/").replace("\n", " ")


def table_md(rows: list[list[str]]) -> str:
    lines = ["| " + " | ".join(COLUMNS) + " |", "|" + "---|" * len(COLUMNS)]
    lines += ["| " + " | ".join(md_cell(c) for c in r) + " |" for r in rows]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="python -m helpdesk.final_test")
    ap.add_argument("--no-table", action="store_true", help="save only the run folder, not test-data/final_test_table.*")
    ap.add_argument("--max-calls", type=int, help="stop (nothing saved) before a question that could exceed N API calls")
    args = ap.parse_args(argv)
    provider = pipeline.default_provider()
    per_question = 3 * pipeline.FINAL.get("topics", 1)
    started = datetime.now()
    records, table = [], []
    for row in read_rows():
        if args.max_calls is not None and provider.stats()["calls_made"] + per_question > args.max_calls:
            sys.exit(f"stopped before {row['id']}: the budget of {args.max_calls} API calls could be exceeded. "
                     "Nothing saved.")
        try:
            out = pipeline.final_answer(row["question"], provider)
        except ProviderError as e:
            sys.exit(f"stopped at {row['id']}: {type(e).__name__}: {e}\nNothing saved; no error recorded as an answer.")
        s = score(row, out)
        ok = passed(row, s)
        records.append({"id": row["id"], "type": row["type"], "expected_action": row["expected_action"],
                        "key_fact": row["key_fact"], **out, "scores": s, "pass": ok})
        table.append([row["id"], short(row["question"], 60) or "(empty)", row["type"], expected_text(row),
                      actual_text(out), "Pass" if ok else "Fail"])
        t2 = (out.get("topic_results") or [None, None])[1:2]
        print(f"{row['id']}: {out['action']:<9} {'Pass' if ok else 'FAIL'}  {out['reason']}"
              + (f"  | topic 2: {t2[0]['action']} ({t2[0]['reason']})" if t2 and t2[0] else "")
              + f"  (calls so far {provider.stats()['calls_made']})")

    n_pass = sum(r["pass"] for r in records)
    stats = provider.stats()
    run_id = f"final_{started.strftime('%Y%m%d-%H%M%S')}"
    totals = {k: {"k": sum(v for v in (r["scores"][k] for r in records) if v is not None),
                  "n": sum(r["scores"][k] is not None for r in records)} for k in records[0]["scores"]}
    fin = pipeline.FINAL
    meta = {"run_id": run_id,
            "title": (f"Final pipeline: P1 {fin['router']} + search {fin['search']} + P2 {fin['p2']} + quote check "
                      f"v2 (tightened) + P3 {fin['p3']}"
                      + (f", {fin['topics']} topics answered" if fin.get("topics", 1) > 1 else "")),
            "started": started.isoformat(timespec="seconds"), "finished": datetime.now().isoformat(timespec="seconds"),
            "questions": QUESTIONS.relative_to(REPO_ROOT).as_posix(), "n_questions": len(records),
            "settings": provider.metadata(), "final": pipeline.FINAL,
            "router_prompt_file": router_v2.PROMPT_FILE.relative_to(REPO_ROOT).as_posix(),
            "router_prompt_sha256": router_v2.file_sha256(),
            "p2_prompt_file": pipeline.prompt_path(fin["p2"]).relative_to(REPO_ROOT).as_posix(),
            "p2_prompt_sha256": pipeline.file_sha256(fin["p2"]), "quote_check": QUOTE_CHECK_TEXT,
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
    header = (f"# Final test table ({run_id})\n\n{meta['title']}. Model {meta['settings'].get('chat_model')}, "
              f"temperature {meta['settings'].get('temperature')}; commit {meta['git']['commit'][:10]}"
              f"{' (uncommitted changes)' if meta['git']['dirty'] else ''}; API calls {meta['api_calls']}, cache hits "
              f"{meta['cache_hits']}. Questions: `{meta['questions']}`.\n\nPass = {meta['pass_rule']}. Two-topic rows "
              f"are scored on topic 1. **Pass: {pct(n_pass, len(records))}**\n\n")
    metrics = "\n\n| Metric | Score |\n|---|---|\n" + "\n".join(
        f"| {k} | {pct(v['k'], v['n'])} |" for k, v in totals.items()) + "\n"
    (folder / "scorecard.md").write_text(header + table_md(table) + metrics, encoding="utf-8")
    with open(folder / "table.csv", "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(COLUMNS)
        w.writerows(table)
    if args.no_table:
        print(f"\nsaved {folder} (test-data/final_test_table.* not touched)\nPass {pct(n_pass, len(records))}; "
              f"API calls {stats['calls_made']}, cache hits {stats['cache_hits']}")
        return
    TABLE_MD.write_text(header + table_md(table) + f"\n\nRaw run: `test-data/runs/{run_id}/`.\n", encoding="utf-8")
    with open(TABLE_CSV, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(COLUMNS)
        w.writerows(table)
    print(f"\nsaved {folder}\nPass {pct(n_pass, len(records))}; API calls {stats['calls_made']}, "
          f"cache hits {stats['cache_hits']}")


if __name__ == "__main__":
    main()
