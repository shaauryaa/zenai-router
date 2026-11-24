"""False-accept check for quote check v2 (Milestone 2 sprint S1). No API call.

Run (from code/):  python -m helpdesk.quote_mutations

Takes every quote that was verified in the saved runs RUNS_IN (P2's quote and the run's retrieved sections), mutates
it, and runs pipeline.verify_quote() on the mutated quote against the same retrieved sections. Every acceptance of a
mutated quote is a false accept. Mutations (deterministic):
  number     change the first digit of the quote's first number to (digit + 1) mod 10           (requested)
  word       replace the middle content word (letters only, 3+ chars) with "giraffe"            (requested)
  other_doc  the verified quote of the next row whose section's document is not among this row's retrieved
             documents                                                                         (requested)
  number_in_section  stress: the quote's first number replaced by another number from the same section
  negation   stress: the first "no"/"not"/"never" removed (these are kb_search stop words)
A mutation that does not apply to a quote (no number, no negation) is n/a.
Saves test-data/runs/quote_check_v2_tight_<timestamp>/ (mutations.csv, summary.md, run_meta.json).
"""
from __future__ import annotations

import csv
import json
import re
from datetime import datetime

from helpdesk import kb_search, pipeline
from helpdesk.score_p2 import QUOTE_CHECK_TEXT, RUNS, git_info
from zenai.paths import REPO_ROOT

RUNS_IN = ("final_20261122-201923", "fresh_20261122-214926")
REQUESTED = ("number", "word", "other_doc")
STRESS = ("number_in_section", "negation")
SWAP_WORD = "giraffe"
NEGATION = re.compile(r"\b(?:no|not|never)\b\s*", re.I)


def verified_quotes() -> list[dict]:
    chunks = {c.id: c for c in kb_search.default_index().chunks}
    out = []
    for run in RUNS_IN:
        for line in (RUNS / run / "outputs.jsonl").read_text(encoding="utf-8").splitlines():
            rec = json.loads(line)
            qc = rec.get("quote_check") or {}
            if not qc.get("verified"):
                continue
            hits = [kb_search.Hit(chunks[h["id"]], h["score"]) for h in rec["retrieval"]]
            out.append({"run": run, "id": rec["id"], "quote": rec["p2"]["quote"], "hits": hits,
                        "chunk": chunks[qc["chunk_id"]]})
    return out


def mutate_number(q: str) -> str | None:
    m = pipeline.NUMBER.search(q)
    if not m:
        return None
    i = m.start()
    return q[:i] + str((int(q[i]) + 1) % 10) + q[i + 1:]


def mutate_word(q: str) -> str | None:
    words = [w for w in pipeline.content_words(q) if w.isalpha() and len(w) >= 3]
    if not words:
        return None
    w = words[len(words) // 2]
    return re.sub(rf"\b{re.escape(w)}\b", SWAP_WORD, q, count=1, flags=re.I)


def mutate_number_in_section(q: str, section: str) -> str | None:
    m = pipeline.NUMBER.search(q)
    if not m:
        return None
    own = m.group().replace(",", "")
    other = next((n for n in pipeline.NUMBER.findall(section) if n.replace(",", "") != own), None)
    return None if other is None else q[:m.start()] + other + q[m.end():]


def mutate_negation(q: str) -> str | None:
    return NEGATION.sub("", q, count=1) if NEGATION.search(q) else None


def other_doc(items: list[dict], n: int) -> str | None:
    files = {h.chunk.file for h in items[n]["hits"]}
    for k in range(1, len(items)):
        cand = items[(n + k) % len(items)]
        if cand["chunk"].file not in files:
            return cand["quote"]
    return None


def main() -> None:
    started = datetime.now()
    items = verified_quotes()
    rows = []
    for n, it in enumerate(items):
        base = pipeline.verify_quote(it["quote"], it["hits"])
        rows.append({"run": it["run"], "id": it["id"], "mutation": "original (not a mutation)",
                     "quote": it["quote"], "accepted": base["verified"], "rule": base["rule"] or "",
                     "chunk_id": base["chunk_id"] or ""})
        mutated = {"number": mutate_number(it["quote"]), "word": mutate_word(it["quote"]),
                   "other_doc": other_doc(items, n),
                   "number_in_section": mutate_number_in_section(it["quote"], it["chunk"].text),
                   "negation": mutate_negation(it["quote"])}
        for kind, q in mutated.items():
            if q is None:
                rows.append({"run": it["run"], "id": it["id"], "mutation": kind, "quote": "", "accepted": "n/a",
                             "rule": "", "chunk_id": ""})
                continue
            r = pipeline.verify_quote(q, it["hits"])
            rows.append({"run": it["run"], "id": it["id"], "mutation": kind, "quote": q, "accepted": r["verified"],
                         "rule": r["rule"] or "", "chunk_id": r["chunk_id"] or ""})

    def tally(kind: str) -> dict:
        rs = [r for r in rows if r["mutation"] == kind]
        tried = [r for r in rs if r["accepted"] != "n/a"]
        return {"mutations": len(tried), "n_a": len(rs) - len(tried),
                "accepted_exact": sum(r["accepted"] is True and r["rule"] == "exact" for r in tried),
                "accepted_near": sum(r["accepted"] is True and r["rule"] == "near" for r in tried),
                "false_accepts": [r["id"] for r in tried if r["accepted"] is True]}

    totals = {k: tally(k) for k in ("original (not a mutation)", *REQUESTED, *STRESS)}
    run_id = f"quote_check_v2_tight_{started.strftime('%Y%m%d-%H%M%S')}"
    folder = RUNS / run_id
    folder.mkdir(parents=True)
    with open(folder / "mutations.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    meta = {"run_id": run_id, "title": "Quote check v2 (tightened) false-accept check (mutated verified quotes)",
            "started": started.isoformat(timespec="seconds"), "source_runs": [f"test-data/runs/{r}" for r in RUNS_IN],
            "n_verified_quotes": len(items), "script": "code/helpdesk/quote_mutations.py",
            "quote_check": QUOTE_CHECK_TEXT, "near_rule": {"min_content_words": pipeline.NEAR_MIN_WORDS,
                                                           "word_share": 1.0, "negations": sorted(pipeline.NEGATIONS),
                                                           "negation_window": pipeline.NEGATION_WINDOW},
            "totals": totals, "git": git_info(), "api_calls": 0}
    (folder / "run_meta.json").write_text(json.dumps(meta, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    lines = [f"# Quote check v2 (tightened): false-accept check ({run_id})", "",
             f"{len(items)} verified quotes from {', '.join(f'`test-data/runs/{r}`' for r in RUNS_IN)}; each mutated "
             "and checked against the same row's retrieved sections with `pipeline.verify_quote` (v2). No API call. "
             "Mutation definitions: docstring of `code/helpdesk/quote_mutations.py`. A mutated quote that is "
             "accepted is a false accept.", "",
             "| Mutation | Kind | Tried | n/a | Wrongly accepted (exact) | Wrongly accepted (near) | Rows |",
             "|---|---|---|---|---|---|---|"]
    for k, t in totals.items():
        kind = "baseline" if k.startswith("original") else ("requested" if k in REQUESTED else "stress")
        acc = "accepted (should be all)" if kind == "baseline" else ""
        lines.append(f"| {k} | {kind}{' ' + acc if acc else ''} | {t['mutations']} | {t['n_a']} | "
                     f"{t['accepted_exact']} | {t['accepted_near']} | {', '.join(t['false_accepts']) or '-'} |")
    req = [totals[k] for k in REQUESTED]
    lines += ["", f"Requested mutations: {sum(t['accepted_exact'] + t['accepted_near'] for t in req)} of "
              f"{sum(t['mutations'] for t in req)} wrongly accepted.", "",
              "## Every mutation", "", "| Row | Mutation | Accepted | Rule | Mutated quote |", "|---|---|---|---|---|"]
    for r in rows:
        if r["mutation"].startswith("original"):
            continue
        q = " ".join(r["quote"].split()).replace("|", "/")
        lines.append(f"| {r['id']} | {r['mutation']} | {r['accepted']} | {r['rule'] or '-'} | "
                     f"{q[:140] + ('...' if len(q) > 140 else '')} |")
    (folder / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines[:len(totals) + 9]))
    print(f"\nsaved {folder.relative_to(REPO_ROOT).as_posix()}")


if __name__ == "__main__":
    main()
