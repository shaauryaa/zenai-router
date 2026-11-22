"""Routing accuracy of router P1 v2 on test-data/test_set.csv, the 70-row set the frozen v1 router was scored on.

Run (from code/):  python -m helpdesk.route_eval
Labelled a SEEN set: v1's errors on it were studied before P1 v2 was written, so it is not a clean test of v2. The
set is only run and scored here; nothing in it is used to write prompts (code/CLAUDE.md).

Definitions match v1's llm_only baseline (evaluation/baselines.py, evaluation/metrics.py), so the numbers are
comparable with v1's 85% (test-data/results/20260927-032804_test/scorecard.md):
- predicted primary office: the domain of the first topic whose request_type is not not_campus; OUT_OF_SCOPE if
  every topic is not_campus; "" for an unusable router reply
- routing accuracy: predicted primary == primary_domain, over rows whose expected_action is not clarify (n = 60)
- routing accuracy, either office: predicted primary is primary_domain or secondary_domain (same rows)
- action accuracy: action from request_type (info answer, needs_human handoff, vague clarify, not_campus refuse;
  most cautious over topics: refuse < answer < clarify < handoff, as in zenai/confidence.py), over all 70 rows
The test set's labels have no STUDENT_SUPPORT office, so a STUDENT_SUPPORT prediction always counts as wrong.
Saves test-data/runs/P1_v2_seen_test_set_<timestamp>/ (predictions.jsonl, scorecard.md, run_meta.json).
"""
from __future__ import annotations

import csv
import json
import sys
from datetime import datetime

from helpdesk import pipeline, router_v2
from helpdesk.score_p2 import RUNS, git_info, pct
from zenai.confidence import ACTION_RANK
from zenai.paths import REPO_ROOT, TEST_DATA
from zenai.providers import ProviderError

TEST_SET = TEST_DATA / "test_set.csv"
REQUEST_TYPE_ACTION = {"info": "answer", "needs_human": "handoff", "vague": "clarify", "not_campus": "refuse"}
V1_REFERENCE = {"run": "test-data/results/20260927-032804_test", "routing_accuracy": "85% (n = 60)",
                "routing_accuracy_either_office": "93% (n = 60)", "action_accuracy_llm_only": "74% (n = 70)"}


def primary_and_action(topics) -> tuple[str, str]:
    if any(t.domain is None for t in topics):
        return "", "handoff"
    kept = [t for t in topics if t.request_type != "not_campus"]
    if not kept:
        return "OUT_OF_SCOPE", "refuse"
    action = max((REQUEST_TYPE_ACTION[t.request_type] for t in kept), key=ACTION_RANK.__getitem__)
    return kept[0].domain, action


def main() -> None:
    provider = pipeline.default_provider()
    with open(TEST_SET, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    started = datetime.now()
    preds = []
    for row in rows:
        try:
            topics, meta = router_v2.classify(row["question"], provider)
        except ProviderError as e:
            sys.exit(f"stopped at {row['id']}: {type(e).__name__}: {e}\nNothing saved.")
        primary, action = primary_and_action(topics)
        preds.append({"id": row["id"], "primary_domain": row["primary_domain"],
                      "secondary_domain": row["secondary_domain"], "expected_action": row["expected_action"],
                      "pred_primary": primary, "pred_action": action,
                      "topics": [t.model_dump() for t in topics], "router_meta": meta})
    routing = [p for p in preds if p["expected_action"] != "clarify"]
    k_route = sum(p["pred_primary"] == p["primary_domain"] for p in routing)
    k_either = sum(p["pred_primary"] != "" and p["pred_primary"] in (p["primary_domain"], p["secondary_domain"])
                   for p in routing)
    k_action = sum(p["pred_action"] == p["expected_action"] for p in preds)
    n_student_support = sum(p["pred_primary"] == "STUDENT_SUPPORT" for p in routing)
    totals = {"routing_accuracy": {"k": k_route, "n": len(routing)},
              "routing_accuracy_either_office": {"k": k_either, "n": len(routing)},
              "action_accuracy": {"k": k_action, "n": len(preds)},
              "predicted_student_support_on_routing_rows": n_student_support}

    run_id = f"P1_v2_seen_test_set_{started.strftime('%Y%m%d-%H%M%S')}"
    folder = RUNS / run_id
    folder.mkdir(parents=True)
    meta = {"run_id": run_id, "set": TEST_SET.relative_to(REPO_ROOT).as_posix(), "set_status": "seen",
            "n_rows": len(rows), "started": started.isoformat(timespec="seconds"),
            "finished": datetime.now().isoformat(timespec="seconds"), "settings": provider.metadata(),
            "router_prompt_file": router_v2.PROMPT_FILE.relative_to(REPO_ROOT).as_posix(),
            "router_prompt_sha256": router_v2.file_sha256(), "git": git_info(),
            "api_calls": provider.stats()["calls_made"], "cache_hits": provider.stats()["cache_hits"],
            "totals": totals, "v1_reference": V1_REFERENCE}
    with open(folder / "predictions.jsonl", "w", encoding="utf-8", newline="\n") as f:
        for p in preds:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")
    (folder / "run_meta.json").write_text(json.dumps(meta, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    wrong = [p for p in routing if p["pred_primary"] != p["primary_domain"]]
    lines = [f"# Router P1 v2 on the seen set ({run_id})", "",
             "SEEN set: test-data/test_set.csv. v1's errors on it were studied before P1 v2 was written, so this is "
             "not a clean test. Definitions: docstring of code/helpdesk/route_eval.py (same as v1's llm_only).", "",
             f"Model {meta['settings'].get('chat_model')}, temperature {meta['settings'].get('temperature')}; router "
             f"prompt `{meta['router_prompt_file']}` sha256 {meta['router_prompt_sha256'][:12]}; commit "
             f"{meta['git']['commit'][:10]}{' (uncommitted changes)' if meta['git']['dirty'] else ''}; API calls "
             f"{meta['api_calls']}, cache hits {meta['cache_hits']}.", "",
             "| Metric | P1 v1 (frozen, `20260927-032804_test`) | P1 v2 (this run) |", "|---|---|---|",
             f"| Routing accuracy | 85% (n = 60) | {pct(k_route, len(routing))} |",
             f"| Routing accuracy, either office | 93% (n = 60) | {pct(k_either, len(routing))} |",
             f"| Action accuracy (from request_type, llm_only) | 74% (n = 70) | {pct(k_action, len(preds))} |", "",
             f"P1 v2 predicted STUDENT_SUPPORT as the primary office on {n_student_support} routing rows (always "
             "wrong here: the labels have no STUDENT_SUPPORT).", "", "## Routing errors", "",
             "| id | labelled primary | labelled secondary | predicted |", "|---|---|---|---|"]
    lines += [f"| {p['id']} | {p['primary_domain']} | {p['secondary_domain'] or '-'} | {p['pred_primary'] or '(none)'} |"
              for p in wrong]
    (folder / "scorecard.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines[8:12]) + f"\nsaved {folder}")


if __name__ == "__main__":
    main()
