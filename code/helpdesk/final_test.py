"""Final test table: the final pipeline (helpdesk.pipeline.final_answer with pipeline.FINAL: P1 -> search -> P2 ->
quote check -> P3 handoff draft / templates, two topics) on all 24 rows of test-data/questions.csv.

Run (from code/):  python -m helpdesk.final_test [--no-table] [--max-calls N] [--questions CSV --label TEXT]
--no-table saves only the run folder (test-data/final_test_table.* untouched); --max-calls stops (nothing saved)
before a question that could take the run past N API calls (3 per topic: P1, P2, P3).
--questions (path from the repo root) runs the same pipeline and scorer on another question file (a fresh check, e.g.
test-data/fresh_questions.csv); the run folder is then fresh_<timestamp>, --label is recorded as the questions'
status, and test-data/final_test_table.* are never touched.

Writes test-data/final_test_table.csv and test-data/final_test_table.md with the columns
    Test no. | Input (short) | Type | Expected output | Actual output (short) | Pass/Fail
and saves the raw run in test-data/runs/final_<timestamp>/ (outputs.jsonl, run_meta.json, scorecard.md with the
same table and the score_p2 metrics).

Pass = final action == expected action, and for rows with a key_fact also key fact found (score_p2 metric key_fact)
and quote verified (score_p2 metric quote_verified). Two-topic rows (Q16) are scored on topic 1, as in every other
run; the two-topic pipeline's second topic is the separate metric topic2_action (not part of Pass). Expected values are read from questions.csv as they are; nothing is changed to make a row pass.
A provider error (daily quota, network) stops the run and nothing is saved.

With --questions, three more row types are scored by the rules in test-data/README.md (fresh check 2, written
before its run); questions.csv rows (Q16 included) are always scored as above:
- two-question rows (";" in expected_action): Pass only if both parts have the right action (part i = topic i of
  out["topic_results"]) and every part whose expected action is answer has its key fact and a verified quote;
  the row's metrics are the AND over its parts (incomplete / needs_review: any part).
- safety rows (expected_action safety): Pass if the action is safety and the card shows the contacts (metric
  safety_card: a verified card with at least one unredacted email or phone line from the knowledge base).
- follow-up rows (a turn2_question): turn 1 runs as the app runs it, then turn 2 through helpdesk.followup.resolve /
  remember (joined to turn 1 after a clarify). Pass if turn 1's action is turn1_expected_action (metric
  turn1_clarify) and turn 2 passes like a one-question row; the other metrics are turn 2's.
Row-type metrics two_question_row, safety_row and followup_row are the Pass of that row type (None for other rows).
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime

from helpdesk import followup, handoff, pipeline, router_v2, safety
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
    elif action in ("not_found", "handoff", "safety"):
        p3 = out.get("p3") or {}
        d = p3.get("draft")
        text = (f'{action}{" (contacts card)" if action == "safety" else ""}; draft to {p3.get("office_email")}: "{short(d["subject"], 50)}"' if d
                else f"{action}; draft failed ({p3.get('error')})")
    else:
        text = f'{action}: "{short(out.get("reply_text", ""), 60)}"'
    return text


PART_FIELDS = ("expected_office", "expected_action", "expected_doc", "expected_page", "key_fact")
ALL_METRICS = ("action", "key_fact", "quote_verified", "doc_cited", "format_valid", "language")
ANY_METRICS = ("incomplete", "needs_review")


def row_kind(row: dict) -> str:
    """The row type of a --questions row: one, two, safety or followup (see the module docstring)."""
    if (row.get("turn2_question") or "").strip():
        return "followup"
    if ";" in row["expected_action"]:
        return "two"
    return "safety" if row["expected_action"] == "safety" else "one"


def part_rows(row: dict) -> list[dict]:
    """One row per part of a two-question row: the ;-separated fields split in part order (missing parts blank)."""
    n = len(row["expected_action"].split(";"))
    split = {k: (row.get(k) or "").split(";") for k in PART_FIELDS}
    return [{**row, **{k: (v[i] if i < len(v) else "") for k, v in split.items()}, "router_scorable": "no",
             "v1_domain": ""} for i in range(n)]


def score_parts(row: dict, out: dict) -> tuple[dict, list[dict]]:
    """(row scores, per-part scores) of a two-question row. Part i is scored on topic i of out["topic_results"]
    with score_p2.score; a missing topic fails its action and every metric that applies to it."""
    results = out.get("topic_results") or [out]
    parts = []
    for i, prow in enumerate(part_rows(row)):
        if i < len(results):
            parts.append(score(prow, {**results[i], "p2_version": out["p2_version"]}))
        else:
            parts.append({"action": False, "key_fact": False if prow["key_fact"] else None,
                          "quote_verified": False if prow["expected_action"] == "answer" else None,
                          "doc_cited": False if prow["expected_doc"] else None, "format_valid": None,
                          "language": None, "incomplete": None, "needs_review": None})
    s = score(row, out)  # router_office and topic2_action as in every run
    for k in ALL_METRICS:
        vals = [p[k] for p in parts if p[k] is not None]
        s[k] = all(vals) if vals else None
    for k in ANY_METRICS:
        vals = [p[k] for p in parts if p[k] is not None]
        s[k] = any(vals) if vals else None
    return s, parts


def card_shows_contacts(out: dict) -> bool:
    card = out.get("safety_card") or {}
    return (out.get("action") == "safety" and bool(card.get("verified"))
            and any(safety.is_contact(line) for line in card.get("lines") or []))


def score_row(kind: str, row: dict, out: dict, turn1: dict | None = None) -> tuple[dict, bool, list[dict] | None]:
    """(scores, Pass, per-part scores or None) for a row of type `kind`, by the rules in test-data/README.md."""
    parts = None
    if kind == "two":
        s, parts = score_parts(row, out)
        ok = all(p["action"] for p in parts) and all(
            bool(p["key_fact"]) and bool(p["quote_verified"])
            for p, prow in zip(parts, part_rows(row)) if prow["expected_action"] == "answer")
    else:
        s = score(row, out)
        if kind == "safety":
            if out["action"] != "answer":
                s["language"] = None  # no P2 text to judge
            ok = bool(s["action"]) and card_shows_contacts(out)
        elif kind == "followup":
            ok = (turn1 or {}).get("action") == row["turn1_expected_action"] and passed(row, s)
        else:
            ok = passed(row, s)
    s["turn1_clarify"] = ((turn1 or {}).get("action") == row["turn1_expected_action"]) if kind == "followup" else None
    s["safety_card"] = card_shows_contacts(out) if kind == "safety" else None
    for k, name in (("two", "two_question_row"), ("safety", "safety_row"), ("followup", "followup_row")):
        s[name] = ok if kind == k else None
    return s, ok, parts


def run_followup(row: dict, provider) -> tuple[dict, dict, str]:
    """(turn 1 result, turn 2 result, the previous question turn 2 was joined to or ""), as app.ask() runs them."""
    run1, _ = followup.resolve(None, row["question"])
    out1 = pipeline.final_answer(run1, provider)
    run2, previous = followup.resolve(followup.remember(out1, run1), row["turn2_question"])
    return out1, pipeline.final_answer(run2, provider), previous


def kind_expected_text(kind: str, row: dict) -> str:
    if kind == "two":
        texts = []
        for i, prow in enumerate(part_rows(row), 1):
            fact = prow["key_fact"]
            t = f"part {i} {prow['expected_action']}"
            t += (f'; key fact "{short(fact, 50)}", quote verified' if fact
                  else "; handoff draft" if prow["expected_action"] in ("not_found", "handoff") else "")
            texts.append(t)
        return " / ".join(texts)
    if kind == "safety":
        return "safety; contacts card copied from the KB, then a draft to Student Support"
    if kind == "followup":
        return f"turn 1 {row['turn1_expected_action']}; turn 2 " + expected_text(row)
    return expected_text(row)


def kind_actual_text(kind: str, out: dict, turn1: dict | None = None, previous: str = "") -> str:
    if kind == "followup":
        joined = f'joined to "{short(previous, 30)}"' if previous else "not joined"
        return f"turn 1 {topic_text(turn1)}; turn 2 ({joined}): " + actual_text(out)
    text = actual_text(out)
    if kind == "safety" and out.get("action") == "safety":
        card = out.get("safety_card") or {}
        n = sum(safety.is_contact(line) for line in card.get("lines") or [])
        text += (f"; card: {n} contact lines from {card.get('source_file')}" if n
                 else "; card: no contacts (fallback line only)")
    return text


def kind_input_text(kind: str, row: dict) -> str:
    if kind == "followup":
        return f'T1 "{short(row["question"], 25)}" / T2 "{short(row["turn2_question"], 35)}"'
    return short(row["question"], 60) or "(empty)"


def passed(row: dict, s: dict) -> bool:
    if not s["action"]:
        return False
    if first(row["key_fact"]):
        return bool(s["key_fact"]) and bool(s["quote_verified"])
    return True


def review_md(records: list[dict]) -> str:
    """The rows a human should read: incomplete (answer shown, key fact missing) and needs_review (answer shown,
    expected action not answer). Listed only, never marked wrong automatically."""
    lines = ["", "## Rows for a human to read", ""]
    for key, label in (("incomplete", "Incomplete (answer shown, key fact missing)"),
                       ("needs_review", "Needs review (answer shown, expected action not answer)")):
        hits = [r for r in records if r["scores"].get(key)]
        lines.append(f"- {label}: " + ("; ".join(
            f'{r["id"]} (expected {r["expected_action"]}): "{short((r.get("p2") or {}).get("answer", ""), 90)}"'
            for r in hits) or "none"))
    return "\n".join(lines) + "\n"


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
    ap.add_argument("--questions", help="another question file, path from the repo root (a fresh check); implies --no-table")
    ap.add_argument("--label", default="", help="status of the questions, e.g. 'fresh check 1, now seen'")
    args = ap.parse_args(argv)
    fresh = args.questions is not None
    questions = (REPO_ROOT / args.questions).resolve() if fresh else QUESTIONS
    if fresh:
        args.no_table = True
        with open(questions, encoding="utf-8", newline="") as f:
            rows = list(csv.DictReader(f))
    else:
        rows = read_rows()
    provider = pipeline.default_provider()
    per_question = 3 * pipeline.FINAL.get("topics", 1)
    started = datetime.now()
    records, table = [], []
    for row in rows:
        kind = row_kind(row) if fresh else "one"
        need = per_question * (2 if kind == "followup" else 1)
        if args.max_calls is not None and provider.stats()["calls_made"] + need > args.max_calls:
            sys.exit(f"stopped before {row['id']}: the budget of {args.max_calls} API calls could be exceeded. "
                     "Nothing saved.")
        turn1, previous = None, ""
        try:
            if kind == "followup":
                turn1, out, previous = run_followup(row, provider)
            else:
                out = pipeline.final_answer(row["question"], provider)
        except ProviderError as e:
            sys.exit(f"stopped at {row['id']}: {type(e).__name__}: {e}\nNothing saved; no error recorded as an answer.")
        if fresh:
            s, ok, parts = score_row(kind, row, out, turn1)
        else:
            s, parts = score(row, out), None
            ok = passed(row, s)
        rec = {"id": row["id"], "type": row["type"], "expected_action": row["expected_action"],
               "key_fact": row["key_fact"], **out, "scores": s, "pass": ok}
        if fresh:
            rec["row_kind"] = kind
        if parts is not None:
            rec["part_scores"] = parts
        if kind == "followup":
            rec.update(turn2_question=row["turn2_question"], turn1_expected_action=row["turn1_expected_action"],
                       followup_of=previous, turn1=turn1)
        records.append(rec)
        table.append([row["id"], kind_input_text(kind, row), row["type"], kind_expected_text(kind, row),
                      kind_actual_text(kind, out, turn1, previous), "Pass" if ok else "Fail"])
        t2 = (out.get("topic_results") or [None, None])[1:2]
        print(f"{row['id']}: {(turn1['action'] + ' -> ') if turn1 else ''}{out['action']:<9} "
              f"{'Pass' if ok else 'FAIL'}  {out['reason']}"
              + (f"  | topic 2: {t2[0]['action']} ({t2[0]['reason']})" if t2 and t2[0] else "")
              + f"  (calls so far {provider.stats()['calls_made']})")

    n_pass = sum(r["pass"] for r in records)
    stats = provider.stats()
    run_id = f"{'fresh' if fresh else 'final'}_{started.strftime('%Y%m%d-%H%M%S')}"
    totals = {k: {"k": sum(v for v in (r["scores"][k] for r in records) if v is not None),
                  "n": sum(r["scores"][k] is not None for r in records)} for k in records[0]["scores"]}
    fin = pipeline.FINAL
    meta = {"run_id": run_id,
            "title": (f"Final pipeline: P1 {fin['router']} + search {fin['search']} + P2 {fin['p2']} + quote check "
                      f"v2 (tightened) + P3 {fin['p3']}"
                      + (f", {fin['topics']} topics answered" if fin.get("topics", 1) > 1 else "")),
            "started": started.isoformat(timespec="seconds"), "finished": datetime.now().isoformat(timespec="seconds"),
            "runner": "code/helpdesk/final_test.py", "questions": questions.relative_to(REPO_ROOT).as_posix(),
            "question_status": args.label or ("" if fresh else "seen"), "n_questions": len(records),
            "settings": provider.metadata(), "final": pipeline.FINAL,
            "router_prompt_file": router_v2.PROMPT_FILE.relative_to(REPO_ROOT).as_posix(),
            "router_prompt_sha256": router_v2.file_sha256(),
            "p2_prompt_file": pipeline.prompt_path(fin["p2"]).relative_to(REPO_ROOT).as_posix(),
            "p2_prompt_sha256": pipeline.file_sha256(fin["p2"]), "quote_check": QUOTE_CHECK_TEXT,
            "p3_prompt_file": handoff.PROMPT_FILE.relative_to(REPO_ROOT).as_posix(),
            "p3_prompt_sha256": handoff.file_sha256(),
            "pass_rule": ("action correct, and for rows with a key_fact also key fact found and quote verified"
                          + ("; two-question, safety and follow-up rows by the rules in test-data/README.md"
                             if fresh else "")),
            "pass": {"k": n_pass, "n": len(records)}, "totals": totals, "git": git_info(),
            "api_calls": stats["calls_made"], "cache_hits": stats["cache_hits"]}

    folder = RUNS / run_id
    folder.mkdir(parents=True)
    with open(folder / "outputs.jsonl", "w", encoding="utf-8", newline="\n") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    (folder / "run_meta.json").write_text(json.dumps(meta, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    header = (f"# {'Fresh check' if fresh else 'Final test table'} ({run_id})\n\n{meta['title']}. "
              + (f"Questions: {args.label}. " if args.label else "") + f"Model {meta['settings'].get('chat_model')}, "
              f"temperature {meta['settings'].get('temperature')}; commit {meta['git']['commit'][:10]}"
              f"{' (uncommitted changes)' if meta['git']['dirty'] else ''}; API calls {meta['api_calls']}, cache hits "
              f"{meta['cache_hits']}. Questions: `{meta['questions']}`.\n\nPass = {meta['pass_rule']}. "
              + ("" if fresh else "Two-topic rows are scored on topic 1. ")
              + f"**Pass: {pct(n_pass, len(records))}**\n\n")
    metrics = "\n\n| Metric | Score |\n|---|---|\n" + "\n".join(
        f"| {k} | {pct(v['k'], v['n'])} |" for k, v in totals.items()) + "\n"
    (folder / "scorecard.md").write_text(header + table_md(table) + metrics + review_md(records), encoding="utf-8")
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
