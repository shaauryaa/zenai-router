"""Final test table: the frozen final pipeline (P1 v2 -> search routed5_all3 -> P2 v2 -> quote check -> P3 handoff
draft / templates, helpdesk.pipeline.final_answer) on all 24 rows of test-data/questions.csv.

Run (from code/):  python -m helpdesk.final_test

Writes test-data/final_test_table.csv and test-data/final_test_table.md with the columns
    Test no. | Input (short) | Type | Expected output | Actual output (short) | Pass/Fail
and saves the raw run in test-data/runs/final_<timestamp>/ (outputs.jsonl, run_meta.json, scorecard.md with the
same table and the score_p2 metrics).

Pass = final action == expected action, and for rows with a key_fact also key fact found (score_p2 metric key_fact)
and quote verified (score_p2 metric quote_verified). Two-topic rows (Q16) are scored on topic 1, as in every other
run. Expected values are read from questions.csv as they are; nothing is changed to make a row pass.
A provider error (daily quota, network) stops the run and nothing is saved.
"""
from __future__ import annotations

import csv
import json
import sys
from datetime import datetime

from helpdesk import handoff, pipeline, router_v2
from helpdesk.score_p2 import QUESTIONS, RUNS, first, git_info, pct, read_rows, score
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
    return text


def actual_text(out: dict) -> str:
    action = out["action"]
    if action == "answer":
        p2 = out["p2"] or {}
        page = f" p.{p2['page']}" if p2.get("page") else ""
        text = f'answer: "{short(p2.get("answer", ""), 70)}" [{short(p2.get("doc_title", ""), 40)}{page}; quote verified]'
    elif action in ("not_found", "handoff"):
        p3 = out.get("p3") or {}
        d = p3.get("draft")
        text = (f'{action}; draft to {p3.get("office_email")}: "{short(d["subject"], 50)}"' if d
                else f"{action}; draft failed ({p3.get('error')})")
    else:
        text = f'{action}: "{short(out.get("reply_text", ""), 60)}"'
    if out.get("multi_topic_note"):
        text += f"; multi-topic note ({len(out['other_topics'])} more topic)"
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


def main() -> None:
    provider = pipeline.default_provider()
    started = datetime.now()
    records, table = [], []
    for row in read_rows():
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
        print(f"{row['id']}: {out['action']:<9} {'Pass' if ok else 'FAIL'}  {out['reason']}")

    n_pass = sum(r["pass"] for r in records)
    stats = provider.stats()
    run_id = f"final_{started.strftime('%Y%m%d-%H%M%S')}"
    totals = {k: {"k": sum(v for v in (r["scores"][k] for r in records) if v is not None),
                  "n": sum(r["scores"][k] is not None for r in records)} for k in records[0]["scores"]}
    meta = {"run_id": run_id, "title": "Final pipeline: P1 v2 + search routed5_all3 + P2 v2 + quote check + P3 " + pipeline.FINAL["p3"],
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
    header = (f"# Final test table ({run_id})\n\n{meta['title']}. Model {meta['settings'].get('chat_model')}, "
              f"temperature {meta['settings'].get('temperature')}; commit {meta['git']['commit'][:10]}"
              f"{' (uncommitted changes)' if meta['git']['dirty'] else ''}; API calls {meta['api_calls']}, cache hits "
              f"{meta['cache_hits']}. Questions: `{meta['questions']}`.\n\nPass = {meta['pass_rule']}. Two-topic rows "
              f"are scored on topic 1. **Pass: {pct(n_pass, len(records))}**\n\n")
    metrics = "\n\n| Metric | Score |\n|---|---|\n" + "\n".join(
        f"| {k} | {pct(v['k'], v['n'])} |" for k, v in totals.items()) + "\n"
    (folder / "scorecard.md").write_text(header + table_md(table) + metrics, encoding="utf-8")
    TABLE_MD.write_text(header + table_md(table) + f"\n\nRaw run: `test-data/runs/{run_id}/`.\n", encoding="utf-8")
    with open(TABLE_CSV, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(COLUMNS)
        w.writerows(table)
    print(f"\nsaved {folder}\nPass {pct(n_pass, len(records))}; API calls {stats['calls_made']}, "
          f"cache hits {stats['cache_hits']}")


if __name__ == "__main__":
    main()
