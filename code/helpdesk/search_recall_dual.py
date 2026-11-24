"""Search recall: programme-aware search (old, routed5_all3_prog) vs dual-query search (new, dual_prog). No API call.

Run (from code/):  python -m helpdesk.search_recall_dual

For every labelled topic (a topic with an expected_doc; ;-separated fields give topic 2 of two-topic rows) of
test-data/questions.csv (seen) and test-data/fresh_questions.csv (fresh check 1, now seen), takes P1 v2's topic as
saved in the checkpoint runs (SOURCES) and searches exactly as pipeline.answer_topic would, k = 8:
  old  kb_search.search_routed_plus_all_prog(search_query, domain, question)
  new  kb_search.search_dual_prog(search_query, topic text, domain, question)
where search_query falls back to the question when empty, the question is the text P2 got (the topic's own text
when P1 found two or more topics) and the topic text is P1's topic "text" (else the question).
Metrics: page hit@8 (a section from expected_doc on expected_page; n/a when expected_page is blank), plus doc hit@8
and fact hit@8 as in helpdesk/search_recall.py. Also checks that "old" reproduces each saved run's retrieval.
Decision rule (fixed before the measurement): adopt the new search only if no topic loses its expected page.
Saves test-data/runs/search_recall_dual_<timestamp>/ (recall.md, rows.csv, run_meta.json).
"""
from __future__ import annotations

import csv
import json
from datetime import datetime

from helpdesk import kb_search
from helpdesk.score_p2 import RUNS, git_info, pct
from helpdesk.search_recall import METRICS, hits_metrics
from zenai.paths import REPO_ROOT, TEST_DATA

SOURCES = {"seen": (TEST_DATA / "questions.csv", "final_20261124-174710"),
           "fresh 1": (TEST_DATA / "fresh_questions.csv", "fresh_20261124-174736")}


def field(row: dict, name: str, t: int) -> str:
    parts = (row[name] or "").split(";")
    return parts[t].strip() if t < len(parts) else ""


def evaluate() -> tuple[list[dict], list[str]]:
    index = kb_search.default_index()
    rows, mismatches = [], []
    for name, (questions, run) in SOURCES.items():
        saved = {}
        for line in (RUNS / run / "outputs.jsonl").read_text(encoding="utf-8").splitlines():
            rec = json.loads(line)
            saved[rec["id"]] = rec
        with open(questions, encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                rec = saved[row["id"]]
                topics = (rec.get("router") or {}).get("topics") or []
                results = rec.get("topic_results") or [rec]
                for t, topic in enumerate(topics[:2]):
                    doc = field(row, "expected_doc", t)
                    if not doc:
                        continue
                    res = results[t] if t < len(results) else {}
                    question = (res.get("question") if t else rec.get("p2_question")) or (
                        (topic.get("text") or "").strip() if t else row["question"]) or row["question"]
                    query = (topic.get("search_query") or "").strip() or question
                    text = (topic.get("text") or "").strip() or question
                    domain = topic.get("domain")
                    old = index.search_routed_plus_all_prog(query, domain, question)
                    new = index.search_dual_prog(query, text, domain, question)
                    label = row["id"] + (f" t{t + 1}" if len(topics) > 1 else "")
                    if res.get("retrieval") and [h["id"] for h in res["retrieval"]] != [h.chunk.id for h in old]:
                        mismatches.append(label)
                    page, fact = field(row, "expected_page", t), field(row, "key_fact", t)
                    rows.append({"set": name, "id": label, "domain": domain, "search_query": query,
                                 "topic_text": text, "expected_doc": doc, "expected_page": page,
                                 "searched_in_run": bool(res.get("retrieval")),
                                 **{f"old_{k}": v for k, v in hits_metrics(old, doc, page, fact).items()},
                                 **{f"new_{k}": v for k, v in hits_metrics(new, doc, page, fact).items()}})
    return rows, mismatches


def main() -> None:
    started = datetime.now()
    rows, mismatches = evaluate()
    yn = {True: "hit", False: "miss", None: "n/a"}
    totals = {}
    for name in SOURCES:
        rs = [r for r in rows if r["set"] == name]
        totals[name] = {f"{side}_{m}": {"k": sum(r[f"{side}_{m}"] for r in rs if r[f"{side}_{m}"] is not None),
                                        "n": sum(r[f"{side}_{m}"] is not None for r in rs)}
                        for m in METRICS for side in ("old", "new")}
    lost = [r["id"] for r in rows if r["old_page"] is True and r["new_page"] is False]
    gained = [r["id"] for r in rows if r["old_page"] is False and r["new_page"] is True]
    adopt = not lost
    changed = [r for r in rows if any(r[f"old_{m}"] != r[f"new_{m}"] for m in METRICS)]
    lines = ["| Set | Topics | Page hit@8 old | Page hit@8 new | Doc hit@8 old | Doc hit@8 new | Fact hit@8 old | "
             "Fact hit@8 new |", "|---|---|---|---|---|---|---|---|"]
    for name, t in totals.items():
        n = sum(r["set"] == name for r in rows)
        lines.append(f"| {name} | {n} | " + " | ".join(pct(t[f'{s}_{m}']['k'], t[f'{s}_{m}']['n'])
                                                     for m in ("page", "doc", "fact") for s in ("old", "new")) + " |")
    lines += ["", f"Topics that lose their expected page: {', '.join(lost) or 'none'}. "
                  f"Topics that gain it: {', '.join(gained) or 'none'}.", "",
              f"**Decision: {'adopt dual_prog' if adopt else 'keep routed5_all3_prog'}** (rule: adopt only if no "
              "topic loses its expected page).", "", "## Topics whose result changed", ""]
    if changed:
        lines += ["| Topic | Page old -> new | Doc old -> new | Fact old -> new | search_query | topic text |",
                  "|---|---|---|---|---|---|"]
        lines += [f"| {r['id']} | " + " | ".join(f"{yn[r[f'old_{m}']]} -> {yn[r[f'new_{m}']]}"
                                                for m in ("page", "doc", "fact"))
                  + f" | {r['search_query'].replace('|', '/')} | {r['topic_text'].replace('|', '/')} |" for r in changed]
    else:
        lines.append("None.")
    run_id = f"search_recall_dual_{started.strftime('%Y%m%d-%H%M%S')}"
    head = [f"# Search recall: routed5_all3_prog (old) vs dual_prog (new) ({run_id})", "",
            "P1 v2 topics as saved in " + ", ".join(f"`test-data/runs/{run}`" for _, run in SOURCES.values())
            + " (no API call). Every topic with an expected_doc, both topics of two-topic rows. Both sets are seen. "
              "Definitions: docstring of `code/helpdesk/search_recall_dual.py`.", "",
            "Old search reproduces the saved retrieval: "
            + ("yes, every topic that searched" if not mismatches else "NO for " + ", ".join(mismatches)) + ".", ""]
    text = "\n".join(head + lines) + "\n"
    folder = RUNS / run_id
    folder.mkdir(parents=True)
    (folder / "recall.md").write_text(text, encoding="utf-8")
    with open(folder / "rows.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    meta = {"run_id": run_id, "title": "Search recall, programme-aware vs dual-query search",
            "started": started.isoformat(timespec="seconds"), "script": "code/helpdesk/search_recall_dual.py",
            "sources": {k: {"questions": q.relative_to(REPO_ROOT).as_posix(), "run": f"test-data/runs/{r}"}
                        for k, (q, r) in SOURCES.items()},
            "totals": totals, "lost_page": lost, "gained_page": gained, "adopt": adopt,
            "changed": [r["id"] for r in changed], "old_search_reproduces_saved_retrieval": not mismatches,
            "mismatches": mismatches, "git": git_info(), "api_calls": 0}
    (folder / "run_meta.json").write_text(json.dumps(meta, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(text + f"\nsaved {folder.relative_to(REPO_ROOT).as_posix()}")


if __name__ == "__main__":
    main()
