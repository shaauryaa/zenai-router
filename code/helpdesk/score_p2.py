"""Run the helpdesk pipeline with one P2 version on test-data/questions.csv, score it and save the run.

Run (from code/):  python -m helpdesk.score_p2 v1
Saves test-data/runs/P2_<version>_<timestamp>/ with outputs.jsonl (every intermediate field plus the scores),
scorecard.md (each metric as k/n and %) and run_meta.json (model, settings, prompt file hash, git commit, API calls,
cache hits). A provider error (daily quota, network) stops the run and nothing is saved, so an error is never
recorded as an answer.

Metrics, per question (multi-topic rows such as Q16 are scored on the first topic; the second is noted):
- action: final action == expected_action                                                      (all rows)
- key_fact: normalised key_fact appears in P2's answer or quote                         (rows with a key_fact)
- quote_verified: the pipeline's quote check passed (step e)            (rows whose expected action is answer)
- doc_cited: the expected document's title is named: in P2's doc_title (JSON versions, equal or one contains the
  other) or anywhere in the reply (v1)                                       (rows with an expected_doc)
- format_valid: P2 reply parsed as JSON with all keys and a true/false "found"       (rows that reached P2, v2+)
- language: the answer is in Hinglish (at least 3 Hinglish function words)                     (Hinglish rows)
- router_office: the router's first-topic domain == v1_domain          (router_scorable = yes and v1_domain set)
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
import sys
from datetime import datetime

from helpdesk import pipeline
from helpdesk.kb_search import read_document
from zenai.paths import KB, REPO_ROOT, TEST_DATA
from zenai.providers import ProviderError

QUESTIONS = TEST_DATA / "questions.csv"
RUNS = TEST_DATA / "runs"
HINGLISH_WORDS = frozenset("""hai hain aap aapko aapke aapka ke ki ka ko mein nahi sakte sakta sakti milta milega
milegi kar karna karein karke ya aur toh hoga liye kya bhi agar jab tak lekin raha rahi ho hota""".split())
METRICS = [("action", "Final action correct"), ("key_fact", "Key fact found"), ("quote_verified", "Quote verified"),
           ("doc_cited", "Right document cited"), ("format_valid", "Valid format (JSON)"),
           ("language", "Language matches (Hinglish rows)"), ("router_office", "Router office correct")]


def first(field: str) -> str:
    return field.split(";")[0] if field else ""


def norm(text: str) -> str:
    text = (text or "").replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    return re.sub(r"\s+", " ", text).strip().lower()


def is_hinglish(text: str) -> bool:
    return sum(w in HINGLISH_WORDS for w in re.findall(r"[a-z]+", (text or "").lower())) >= 3


def doc_title(rel: str) -> str:
    meta, _ = read_document(KB / rel)
    return str(meta.get("title") or "")


def score(row: dict, out: dict) -> dict:
    """{metric: True/False, or None when the metric does not apply to this row}."""
    exp_action, fact, doc = first(row["expected_action"]), first(row["key_fact"]), first(row["expected_doc"])
    p2 = out.get("p2") or {}
    text = f"{p2.get('answer', '')}\n{p2.get('quote', '')}"
    s: dict = {"action": out["action"] == exp_action}
    s["key_fact"] = (norm(fact) in norm(text)) if fact else None
    s["quote_verified"] = bool((out.get("quote_check") or {}).get("verified")) if exp_action == "answer" else None
    if doc:
        title = norm(doc_title(doc))
        if out["p2_version"] in pipeline.PLAIN_TEXT_VERSIONS:
            s["doc_cited"] = title in norm(p2.get("answer", ""))
        else:
            cited = norm(p2.get("doc_title", ""))
            s["doc_cited"] = bool(cited) and (cited == title or cited in title or title in cited)
    else:
        s["doc_cited"] = None
    s["format_valid"] = (p2.get("format_valid") is True
                         if p2 and out["p2_version"] not in pipeline.PLAIN_TEXT_VERSIONS else None)
    s["language"] = is_hinglish(p2.get("answer", "")) if row["language"] == "hinglish" else None
    if row["router_scorable"] == "yes" and row["v1_domain"]:
        s["router_office"] = (out.get("first_topic") or {}).get("domain") == first(row["v1_domain"])
    else:
        s["router_office"] = None
    return s


def git_info() -> dict:
    def git(*args):
        try:
            return subprocess.run(["git", *args], cwd=REPO_ROOT, capture_output=True, text=True, check=True).stdout.strip()
        except (OSError, subprocess.CalledProcessError):
            return ""
    return {"commit": git("rev-parse", "HEAD") or "unknown", "dirty": bool(git("status", "--porcelain"))}


def pct(k: int, n: int) -> str:
    return f"{k}/{n} ({100 * k / n:.0f}%)" if n else "n/a"


def totals(records: list[dict]) -> dict:
    out = {}
    for key, _ in METRICS:
        vals = [r["scores"][key] for r in records if r["scores"][key] is not None]
        out[key] = {"k": sum(vals), "n": len(vals)}
    return out


def scorecard(version: str, run_id: str, records: list[dict], meta: dict) -> str:
    t = totals(records)
    lines = [f"# Scorecard: P2 {version} ({run_id})", "",
             f"Model {meta['settings'].get('chat_model')}, temperature {meta['settings'].get('temperature')}, "
             f"reasoning_effort {meta['settings'].get('reasoning_effort_sent')}; prompt "
             f"`{meta['prompt_file']}` sha256 {meta['prompt_sha256'][:12]}; commit {meta['git']['commit'][:10]}"
             f"{' (uncommitted changes)' if meta['git']['dirty'] else ''}; API calls {meta['api_calls']}, "
             f"cache hits {meta['cache_hits']}.", "", "| Metric | Score |", "|---|---|"]
    lines += [f"| {label} | {pct(t[key]['k'], t[key]['n'])} |" for key, label in METRICS]
    lines += ["", "Metric definitions: see the docstring of code/helpdesk/score_p2.py. n differs per metric because "
              "each applies only to some rows.", "", "## Per question", "",
              "| id | expected | got | wrong metrics | reason |", "|---|---|---|---|---|"]
    for r in records:
        wrong = ", ".join(k for k, v in r["scores"].items() if v is False) or "-"
        reason = r["reason"].replace("|", "/")
        lines.append(f"| {r['id']} | {first(r['expected_action'])} | {r['action']} | {wrong} | {reason} |")
    notes = [r for r in records if r.get("note")]
    if notes:
        lines += ["", "## Notes", ""] + [f"- {r['id']}: {r['note']}" for r in notes]
    return "\n".join(lines) + "\n"


def run(version: str) -> str:
    if not pipeline.prompt_path(version).is_file():
        sys.exit(f"no prompt file {pipeline.prompt_path(version)}")
    provider = pipeline.default_provider()
    with open(QUESTIONS, encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    started = datetime.now()
    records = []
    for row in rows:
        try:
            out = pipeline.answer(row["question"], version, provider)
        except ProviderError as e:
            sys.exit(f"stopped at {row['id']}: {type(e).__name__}: {e}\nNothing saved; no error recorded as an answer.")
        rec = {"id": row["id"], **{k: row[k] for k in ("expected_action", "expected_office", "expected_doc",
                                                        "key_fact", "language", "v1_domain")}, **out}
        rec["scores"] = score(row, out)
        if ";" in row["expected_action"]:
            topics = (out.get("router") or {}).get("topics") or []
            second = topics[1] if len(topics) > 1 else None
            rec["note"] = ("two-topic row, scored on topic 1 only; topic 2 expected "
                           f"{row['expected_action'].split(';')[1]} / {row['v1_domain'].split(';')[1]}, router gave "
                           + (f"{second['domain']} / {second['request_type']}" if second else "no second topic"))
        records.append(rec)
        print(f"{row['id']}: {out['action']:<9} {'ok' if rec['scores']['action'] else 'WRONG'}  {out['reason']}")

    run_id = f"P2_{version}_{started.strftime('%Y%m%d-%H%M%S')}"
    folder = RUNS / run_id
    folder.mkdir(parents=True)
    meta = {"run_id": run_id, "p2_version": version, "started": started.isoformat(timespec="seconds"),
            "finished": datetime.now().isoformat(timespec="seconds"), "questions": str(QUESTIONS.relative_to(REPO_ROOT)),
            "n_questions": len(rows), "settings": provider.metadata(),
            "prompt_file": str(pipeline.prompt_path(version).relative_to(REPO_ROOT)).replace("\\", "/"),
            "prompt_sha256": pipeline.file_sha256(version), "router": "zenai/llm_router.py classify() (v1, frozen)",
            "retrieval": "helpdesk.kb_search.search_for_route(question, first topic domain, k=5)",
            "git": git_info(), "api_calls": provider.stats()["calls_made"],
            "cache_hits": provider.stats()["cache_hits"], "totals": totals(records)}
    with open(folder / "outputs.jsonl", "w", encoding="utf-8", newline="\n") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    (folder / "run_meta.json").write_text(json.dumps(meta, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    (folder / "scorecard.md").write_text(scorecard(version, run_id, records, meta), encoding="utf-8")
    print(f"\nsaved {folder}\n" + "\n".join(f"{label}: {pct(meta['totals'][k]['k'], meta['totals'][k]['n'])}"
                                         for k, label in METRICS)
          + f"\nAPI calls {meta['api_calls']}, cache hits {meta['cache_hits']}")
    return str(folder)


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="python -m helpdesk.score_p2")
    ap.add_argument("version", help="prompt version folder under prompts/, e.g. v1")
    run(ap.parse_args(argv).version)


if __name__ == "__main__":
    main()
