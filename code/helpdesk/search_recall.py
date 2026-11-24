"""Search recall before and after programme-aware search (Milestone 2 sprint S1, part C). No API call.

Run (from code/):  python -m helpdesk.search_recall

For every row of test-data/questions.csv (seen) and test-data/fresh_questions.csv (fresh) with an expected_doc, takes
the first topic's search_query and domain that P1 v2 produced in the saved runs (SOURCES; the query falls back to the
question when empty, as in pipeline.answer) and runs both searches with k = 8:
  old  kb_search.search_routed_plus_all            (search="routed5_all3", the final pipeline)
  new  kb_search.search_routed_plus_all_prog       (search="routed5_all3_prog")
Metrics per row (first topic, as everywhere else):
  doc hit@8   a retrieved section is from expected_doc
  page hit@8  a retrieved section is from expected_doc on expected_page (n/a when expected_page is blank)
  fact hit@8  a retrieved section contains key_fact word for word, whitespace collapsed (n/a without key_fact)
Also checks that the old search reproduces each saved run's retrieval (rows that reached search in the run).
Saves test-data/runs/search_recall_<timestamp>/ (recall.md, rows.csv, run_meta.json).
"""
from __future__ import annotations

import csv
import json
import re
from datetime import datetime

from helpdesk import kb_search
from helpdesk.score_p2 import RUNS, first, git_info, pct
from zenai.paths import REPO_ROOT, TEST_DATA

SOURCES = {"seen": (TEST_DATA / "questions.csv", "final_20261122-201923"),
           "fresh": (TEST_DATA / "fresh_questions.csv", "fresh_20261122-214926")}
METRICS = ("doc", "page", "fact")


def _ws(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def hits_metrics(hits: list[kb_search.Hit], doc: str, page: str, fact: str) -> dict:
    return {"doc": any(h.chunk.file == doc for h in hits),
            "page": any(h.chunk.file == doc and str(h.chunk.page) == page for h in hits) if page else None,
            "fact": any(_ws(fact) in _ws(h.chunk.text) for h in hits) if fact else None}


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
                doc = first(row["expected_doc"])
                if not doc:
                    continue
                rec = saved[row["id"]]
                topic = ((rec.get("router") or {}).get("topics") or [{}])[0]
                domain = topic.get("domain")
                query = (topic.get("search_query") or "").strip() or row["question"]
                old = index.search_routed_plus_all(query, domain)
                new = index.search_routed_plus_all_prog(query, domain, row["question"])
                if rec.get("retrieval") and [h["id"] for h in rec["retrieval"]] != [h.chunk.id for h in old]:
                    mismatches.append(row["id"])
                page, fact = first(row["expected_page"]), first(row["key_fact"])
                files = kb_search.programme_files(row["question"], query) if domain == "ACADEMICS" else []
                rows.append({"set": name, "id": row["id"], "domain": domain, "search_query": query,
                             "expected_doc": doc, "expected_page": page, "programme_files": ";".join(files),
                             "searched_in_run": bool(rec.get("retrieval")),
                             **{f"old_{k}": v for k, v in hits_metrics(old, doc, page, fact).items()},
                             **{f"new_{k}": v for k, v in hits_metrics(new, doc, page, fact).items()}})
    return rows, mismatches


def summary(rows: list[dict]) -> dict:
    out = {}
    for name in SOURCES:
        rs = [r for r in rows if r["set"] == name]
        out[name] = {}
        for m in METRICS:
            for side in ("old", "new"):
                vals = [r[f"{side}_{m}"] for r in rs if r[f"{side}_{m}"] is not None]
                out[name][f"{side}_{m}"] = {"k": sum(vals), "n": len(vals)}
    return out


def main() -> None:
    started = datetime.now()
    rows, mismatches = evaluate()
    totals = summary(rows)
    changed = [r for r in rows if any(r[f"old_{m}"] != r[f"new_{m}"] for m in METRICS)]
    restricted = [r for r in rows if r["programme_files"]]
    yn = {True: "hit", False: "miss", None: "n/a"}
    lines = ["| Set | Rows | Doc hit@8 old | Doc hit@8 new | Page hit@8 old | Page hit@8 new | Fact hit@8 old | "
             "Fact hit@8 new |", "|---|---|---|---|---|---|---|---|"]
    for name, t in totals.items():
        n = sum(r["set"] == name for r in rows)
        lines.append(f"| {name} | {n} | " + " | ".join(pct(t[f'{s}_{m}']['k'], t[f'{s}_{m}']['n'])
                                                     for m in METRICS for s in ("old", "new")) + " |")
    lines += ["", "## Rows whose result changed", ""]
    if changed:
        lines += ["| Row | Programme files | Doc old -> new | Page old -> new | Fact old -> new |", "|---|---|---|---|---|"]
        lines += [f"| {r['id']} | {r['programme_files'] or '-'} | " + " | ".join(
            f"{yn[r[f'old_{m}']]} -> {yn[r[f'new_{m}']]}" for m in METRICS) + " |" for r in changed]
    else:
        lines.append("None.")
    lines += ["", "## Rows where the new search restricted the routed part to programme files", ""]
    lines += [f"- {r['id']} ({r['set']}): {r['programme_files']}; search_query `{r['search_query']}`"
              for r in restricted] or ["None."]
    run_id = f"search_recall_{started.strftime('%Y%m%d-%H%M%S')}"
    head = [f"# Search recall: routed5_all3 (old) vs routed5_all3_prog (new) ({run_id})", "",
            "Search query and domain: P1 v2's first topic as saved in "
            + ", ".join(f"`test-data/runs/{run}`" for _, run in SOURCES.values())
            + " (no API call). Rows with an expected_doc only; first topic. Metric definitions: docstring of "
              "`code/helpdesk/search_recall.py`. The fresh rows are now seen: they were used to choose this fix.", "",
            f"Old search reproduces the saved retrieval: {'yes, every row that searched' if not mismatches else 'NO for ' + ', '.join(mismatches)}.",
            ""]
    text = "\n".join(head + lines) + "\n"
    folder = RUNS / run_id
    folder.mkdir(parents=True)
    (folder / "recall.md").write_text(text, encoding="utf-8")
    with open(folder / "rows.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    meta = {"run_id": run_id, "title": "Search recall, old vs programme-aware search",
            "started": started.isoformat(timespec="seconds"), "script": "code/helpdesk/search_recall.py",
            "sources": {k: {"questions": q.relative_to(REPO_ROOT).as_posix(), "run": f"test-data/runs/{r}"}
                        for k, (q, r) in SOURCES.items()},
            "totals": totals, "changed_rows": [r["id"] for r in changed],
            "old_search_reproduces_saved_retrieval": not mismatches, "mismatches": mismatches,
            "git": git_info(), "api_calls": 0}
    (folder / "run_meta.json").write_text(json.dumps(meta, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(text + f"\nsaved {folder.relative_to(REPO_ROOT).as_posix()}")


if __name__ == "__main__":
    main()
