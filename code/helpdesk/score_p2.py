"""Run the helpdesk pipeline on test-data/questions.csv, score it and save the run.

Run (from code/):  python -m helpdesk.score_p2 v1
                   python -m helpdesk.score_p2 v2 --router v2 --search routed5_all3 --name step3_P1v2_search8_P2v2
                   python -m helpdesk.score_p2 --rescore ../test-data/runs/P2_v2_20261122-184902 --name P2_v2_requote
--router picks P1 (v1 frozen, v2 helpdesk/router_v2.py), --search the retrieval (see helpdesk/pipeline.py).
--rescore makes no API call: it re-runs only the code quote check (pipeline step e) and the decision (step f) on a
saved run's P2 replies and retrieved chunks with the current check, then re-scores.
Saves test-data/runs/<name, default P2_<version>>_<timestamp>/ with outputs.jsonl (every intermediate field plus the
scores), scorecard.md (each metric as k/n and %) and run_meta.json (model, settings, prompt file hashes, git commit,
API calls, cache hits). A provider error (daily quota, network) stops the run and nothing is saved, so an error is
never recorded as an answer.

Metrics, per question (multi-topic rows such as Q16 are scored on the first topic; the second is noted):
- action: final action == expected_action                                                      (all rows)
- key_fact: normalised key_fact appears in P2's answer or quote                         (rows with a key_fact)
- quote_verified: the pipeline's quote check passed (step e)            (rows whose expected action is answer)
- doc_cited: the expected document's title is named: in P2's doc_title (JSON versions, equal or one contains the
  other) or anywhere in the reply (v1)                                       (rows with an expected_doc)
- format_valid: P2 reply parsed as JSON with all keys and a true/false "found"       (rows that reached P2, v2+)
- language: the answer is in Hinglish (at least 3 Hinglish function words)                     (Hinglish rows)
- router_office: the router's first-topic domain == v1_domain          (router_scorable = yes and v1_domain set)
- topic2_action: the second topic's action == the second expected_action    (rows labelled with two actions, in runs
  of the two-topic final pipeline, which records out["topic_results"]; not part of Pass)
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from helpdesk import kb_search, pipeline
from helpdesk.kb_search import read_document
from zenai.paths import KB, REPO_ROOT, TEST_DATA
from zenai.providers import ProviderError

QUESTIONS = TEST_DATA / "questions.csv"
RUNS = TEST_DATA / "runs"
HINGLISH_WORDS = frozenset("""hai hain aap aapko aapke aapka ke ki ka ko mein nahi sakte sakta sakti milta milega
milegi kar karna karein karke ya aur toh hoga liye kya bhi agar jab tak lekin raha rahi ho hota""".split())
METRICS = [("action", "Final action correct"), ("key_fact", "Key fact found"), ("quote_verified", "Quote verified"),
           ("doc_cited", "Right document cited"), ("format_valid", "Valid format (JSON)"),
           ("language", "Language matches (Hinglish rows)"), ("router_office", "Router office correct"),
           ("topic2_action", "Topic 2 action correct (two-action rows)")]
ROW_FIELDS = ("expected_action", "expected_office", "expected_doc", "key_fact", "language", "v1_domain")
ROUTER_TEXT = {"v1": "zenai/llm_router.py classify() (P1 v1, frozen)",
               "v2": "helpdesk/router_v2.py classify() (P1 v2, prompts/v2/P1_router.md)"}
SEARCH_TEXT = {"route5": "helpdesk.kb_search.search_for_route(question, first topic domain, k=5)",
               "routed5_all3": "helpdesk.kb_search.search_routed_plus_all(first topic search_query or question, "
                               "first topic domain): top 5 from the routed folder + top 3 from all folders (k=8)",
               "routed5_all3_prog": "helpdesk.kb_search.search_routed_plus_all_prog: as routed5_all3, but an "
                                    "ACADEMICS question naming a programme takes its top 5 routed only from that "
                                    "programme's COURSE_SPECIFIC file(s)"}
QUOTE_CHECK_TEXT = ("pipeline.verify_quote (quote check v2, tightened): rule exact = quote_forms() match (** and __ "
                    "removed, OCR line-end hyphens joined, whitespace collapsed, lowercased); else rule near = against "
                    "one section, every content word present (negations kept), every number next to the same token, "
                    ">= 4 content words; both rules reject a dropped negation")


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
    actions = row["expected_action"].split(";")
    if len(actions) > 1 and "topic_results" in out:
        results = out["topic_results"]
        s["topic2_action"] = len(results) > 1 and results[1]["action"] == actions[1]
    else:
        s["topic2_action"] = None
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
    router_prompt = (f"; router prompt `{meta['router_prompt_file']}` sha256 {meta['router_prompt_sha256'][:12]}"
                     if meta.get("router_prompt_file") else "")
    lines = [f"# Scorecard: {meta.get('title') or 'P2 ' + version} ({run_id})", "",
             f"Model {meta['settings'].get('chat_model')}, temperature {meta['settings'].get('temperature')}, "
             f"reasoning_effort {meta['settings'].get('reasoning_effort_sent')}; prompt "
             f"`{meta['prompt_file']}` sha256 {meta['prompt_sha256'][:12]}{router_prompt}; commit "
             f"{meta['git']['commit'][:10]}{' (uncommitted changes)' if meta['git']['dirty'] else ''}; API calls "
             f"{meta['api_calls']}, cache hits {meta['cache_hits']}.", "",
             f"Router: {meta['router']}. Retrieval: {meta['retrieval']}. Quote check: "
             f"{meta.get('quote_check', 'whitespace collapsed, lowercased (original)')}."
             + (f" Re-scored offline from `{meta['rescored_from']}` (no API call)." if meta.get("rescored_from") else ""),
             "", "| Metric | Score |", "|---|---|"]
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


def read_rows() -> list[dict]:
    with open(QUESTIONS, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def make_record(row: dict, out: dict) -> dict:
    rec = {"id": row["id"], **{k: row[k] for k in ROW_FIELDS}, **out}
    rec["scores"] = score(row, out)
    if ";" in row["expected_action"]:
        topics = (out.get("router") or {}).get("topics") or []
        second = topics[1] if len(topics) > 1 else None
        rec["note"] = ("two-topic row, scored on topic 1 only; topic 2 expected "
                       f"{row['expected_action'].split(';')[1]} / {row['v1_domain'].split(';')[1]}, router gave "
                       + (f"{second['domain']} / {second['request_type']}" if second else "no second topic"))
    print(f"{row['id']}: {out['action']:<9} {'ok' if rec['scores']['action'] else 'WRONG'}  {out['reason']}")
    return rec


def save(run_id: str, version: str, records: list[dict], meta: dict) -> str:
    folder = RUNS / run_id
    folder.mkdir(parents=True)
    with open(folder / "outputs.jsonl", "w", encoding="utf-8", newline="\n") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    (folder / "run_meta.json").write_text(json.dumps(meta, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    (folder / "scorecard.md").write_text(scorecard(version, run_id, records, meta), encoding="utf-8")
    print(f"\nsaved {folder}\n" + "\n".join(f"{label}: {pct(meta['totals'][k]['k'], meta['totals'][k]['n'])}"
                                         for k, label in METRICS)
          + f"\nAPI calls {meta['api_calls']}, cache hits {meta['cache_hits']}")
    return str(folder)


def run(version: str, router: str = "v1", search: str = "route5", name: str | None = None) -> str:
    if not pipeline.prompt_path(version).is_file():
        sys.exit(f"no prompt file {pipeline.prompt_path(version)}")
    provider = pipeline.default_provider()
    rows = read_rows()
    started = datetime.now()
    records = []
    for row in rows:
        try:
            out = pipeline.answer(row["question"], version, provider, router=router, search=search)
        except ProviderError as e:
            sys.exit(f"stopped at {row['id']}: {type(e).__name__}: {e}\nNothing saved; no error recorded as an answer.")
        records.append(make_record(row, out))

    run_id = f"{name or 'P2_' + version}_{started.strftime('%Y%m%d-%H%M%S')}"
    meta = {"run_id": run_id, "title": f"P1 {router} + search {search} + P2 {version}", "p2_version": version,
            "started": started.isoformat(timespec="seconds"),
            "finished": datetime.now().isoformat(timespec="seconds"),
            "questions": QUESTIONS.relative_to(REPO_ROOT).as_posix(), "n_questions": len(rows),
            "settings": provider.metadata(), "prompt_file": pipeline.prompt_path(version).relative_to(REPO_ROOT).as_posix(),
            "prompt_sha256": pipeline.file_sha256(version), "router": ROUTER_TEXT[router], "router_version": router,
            "search": search, "retrieval": SEARCH_TEXT[search], "quote_check": QUOTE_CHECK_TEXT, "git": git_info(),
            "api_calls": provider.stats()["calls_made"], "cache_hits": provider.stats()["cache_hits"],
            "totals": totals(records)}
    if router == "v2":
        from helpdesk import router_v2
        meta["router_prompt_file"] = router_v2.PROMPT_FILE.relative_to(REPO_ROOT).as_posix()
        meta["router_prompt_sha256"] = router_v2.file_sha256()
    return save(run_id, version, records, meta)


def rescore(source: Path, name: str) -> str:
    """Offline (no API call): re-run the quote check (step e) and the decision (step f) on a saved run."""
    source = Path(source).resolve()
    src_meta = json.loads((source / "run_meta.json").read_text(encoding="utf-8"))
    rows = {r["id"]: r for r in read_rows()}
    chunks = {c.id: c for c in kb_search.default_index().chunks}
    started = datetime.now()
    records = []
    for line in (source / "outputs.jsonl").read_text(encoding="utf-8").splitlines():
        old = json.loads(line)
        out = {k: v for k, v in old.items() if k not in ("id", "scores", "note", *ROW_FIELDS)}
        if out.get("p2") is not None:  # P2 ran: redo steps e and f with the current quote check
            missing = [r["id"] for r in out["retrieval"] if r["id"] not in chunks]
            if missing:
                sys.exit(f"{old['id']}: retrieved chunks {missing} are not in the current index (kb/ changed?)")
            hits = [kb_search.Hit(chunks[r["id"]], r["score"]) for r in out["retrieval"]]
            out["quote_check"] = qc = pipeline.verify_quote(out["p2"]["quote"], hits)
            out.update(zip(("action", "reason"), pipeline.decide(out["p2"], qc["verified"], qc["reason"], qc["rule"])))
        records.append(make_record(rows[old["id"]], out))
    version = src_meta["p2_version"]
    run_id = f"{name}_{started.strftime('%Y%m%d-%H%M%S')}"
    meta = {"run_id": run_id, "title": f"P2 {version}, quote check re-run offline",
            **{k: src_meta[k] for k in ("p2_version", "questions", "n_questions", "settings", "prompt_file",
                                         "prompt_sha256", "router", "retrieval")},
            "started": started.isoformat(timespec="seconds"), "finished": datetime.now().isoformat(timespec="seconds"),
            "rescored_from": source.relative_to(REPO_ROOT).as_posix(), "quote_check": QUOTE_CHECK_TEXT,
            "git": git_info(), "api_calls": 0, "cache_hits": 0, "totals": totals(records)}
    return save(run_id, version, records, meta)


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="python -m helpdesk.score_p2")
    ap.add_argument("version", nargs="?", help="P2 prompt version folder under prompts/, e.g. v1")
    ap.add_argument("--router", choices=pipeline.ROUTERS, default="v1", help="P1 router version (default v1)")
    ap.add_argument("--search", choices=pipeline.SEARCHES, default="route5", help="retrieval (default route5)")
    ap.add_argument("--name", help="run folder name before the timestamp (default P2_<version>)")
    ap.add_argument("--rescore", type=Path, help="saved run folder to re-score offline with the current quote check")
    args = ap.parse_args(argv)
    if args.rescore:
        if not args.name:
            ap.error("--rescore needs --name")
        rescore(args.rescore, args.name)
    elif args.version:
        run(args.version, args.router, args.search, args.name)
    else:
        ap.error("give a version or --rescore")


if __name__ == "__main__":
    main()
