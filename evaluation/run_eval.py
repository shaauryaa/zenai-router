"""Evaluate the router on a labelled set.

python -m evaluation.run_eval --set dev|test|simulated [--baselines] [--limit N]

Writes results/<timestamp>_<set>/ with predictions.csv, run_meta.json, leakage report, scorecard and charts.
Test and simulated runs require frozen thresholds and are logged in results/test_runs.log.
"""
import argparse
import hashlib
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
import yaml

from zenai.config import DATA, ROOT, load_config
from zenai.providers import ProviderError
from zenai.router import Router

from . import baselines, leakage, metrics, report
from .datasets import SET_FILES, TEST_SETS, load_set, read_csv, sha256_file
from .sync_simulated import write_synced

RESULTS = ROOT / "results"


def git_info() -> dict:
    def git(*args):
        try:
            return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
        except (OSError, subprocess.CalledProcessError):
            return None
    status = git("status", "--porcelain")
    return {"commit": git("rev-parse", "HEAD") or "unknown", "dirty": bool(status)}


def primary_topic(result):
    kept = [t for t in result.topics if t.action != "refuse"]
    return (kept or result.topics)[0]


def prediction_row(row: pd.Series, result) -> dict:
    kept = [t for t in result.topics if t.action != "refuse"]
    signals_topics = result.signals["topics"]
    return {
        "id": row["id"], "question": row["question"], "language": row["language"], "source": row["source"],
        "variant_type": row["variant_type"],
        "label_primary": row["label_primary"], "label_secondary": row["label_secondary"],
        "label_action": row["label_action"],
        "pred_primary": result.primary_domain or "", "pred_secondary": result.secondary_domain or "",
        "pred_action": result.action,
        "confidence": primary_topic(result).confidence,
        "auto_routed": result.auto_routed,
        # handoff caused by the fallback rule (low confidence or no LLM domain), not by request_type
        "fallback_handoff": result.action == "handoff" and any(t.action == "handoff" and not t.auto_routed
                                                                for t in kept),
        "n_topics": len(result.topics),
        "topic_domains": [t.llm_domain for t in result.topics if t.llm_domain],
        "llm_fallback": result.signals["llm"]["fallback"],
        "topic_reasons": " | ".join(t.reason for t in result.topics),
        "signals_topics": signals_topics,
        "latency_ms": result.latency_ms,
    }


def to_csv(preds: pd.DataFrame, path: Path) -> None:
    out = preds.copy()
    out["topic_domains"] = out["topic_domains"].map(json.dumps)
    out["signals"] = out.pop("signals_topics").map(lambda s: json.dumps(s, ensure_ascii=False))
    out.to_csv(path, index=False, encoding="utf-8")


def label_status(path: Path) -> dict:
    df = pd.read_json(path, lines=True, dtype=str) if path.suffix == ".jsonl" else read_csv(path)
    return df["label_status"].value_counts().to_dict() if "label_status" in df else {}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--set", required=True, choices=list(SET_FILES))
    ap.add_argument("--baselines", action="store_true")
    ap.add_argument("--limit", type=int)
    args = ap.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")

    cfg = load_config()
    config_text = (ROOT / "config.yaml").read_text(encoding="utf-8")
    config_hash = hashlib.sha256(config_text.encode("utf-8")).hexdigest()
    if args.set in TEST_SETS and not cfg["thresholds"].get("frozen"):
        print("Tune on dev and freeze thresholds first.")
        return 2

    if args.set == "simulated" or not (DATA / "simulated_synced.csv").exists():
        changes = write_synced()
        print(f"synced simulated labels from test_set.csv ({len(changes)} rows differ from simulated_v1.csv)")

    started = datetime.now()
    run_id = f"{started:%Y%m%d-%H%M%S}_{args.set}"
    run_dir = RESULTS / run_id
    run_dir.mkdir(parents=True)
    git = git_info()

    leak = leakage.run()
    leakage.save(leak, run_dir)
    print(leakage.format_report(leak))
    meta = {
        "run_id": run_id, "set": args.set, "limit": args.limit, "baselines": args.baselines,
        "started": started.isoformat(timespec="seconds"), "git": git,
        "config": yaml.safe_load(config_text), "config_sha256": config_hash,
        "data_sha256": {p.name: sha256_file(p) for p in sorted(DATA.iterdir()) if p.is_file()},
        "label_status": label_status(DATA / SET_FILES[args.set]),
        "examples_label_status": label_status(DATA / "examples.jsonl"),
        "leakage": {"exact": len(leak["exact"]), "near": len(leak["near"])},
    }

    def save_meta(status: str, **extra) -> None:
        meta.update(status=status, **extra)
        (run_dir / "run_meta.json").write_text(json.dumps(meta, indent=1, default=str), encoding="utf-8")

    if not leak["passed"]:
        save_meta("failed: leakage (exact duplicates between example/dev and test data)")
        print(f"FAILED: exact duplicates found; see {run_dir / 'leakage.txt'}")
        return 1

    if args.set in TEST_SETS:
        with open(RESULTS / "test_runs.log", "a", encoding="utf-8") as log:
            log.write(f"{started.isoformat(timespec='seconds')}\tset={args.set}\tconfig={config_hash[:12]}\t"
                      f"commit={git['commit'][:10]}{'+dirty' if git['dirty'] else ''}\trun={run_id}\t"
                      f"limit={args.limit or 'all'}\n")

    rows = load_set(args.set)
    if args.limit:
        rows = rows.head(args.limit)

    t0 = time.perf_counter()
    router = None
    records = []
    try:
        router = Router(cfg)
        for i, (_, row) in enumerate(rows.iterrows(), 1):
            records.append(prediction_row(row, router.route(row["question"])))
            print(f"\r{i}/{len(rows)} routed", end="", flush=True)
        print()
        preds = metrics.add_flags(pd.DataFrame(records))
        base = None
        if args.baselines:
            knn_msg = [r.domain for r in router.knn.query_many(list(preds["question"]))]
            base = baselines.run_baselines(preds, knn_msg)
    except ProviderError as e:
        if records:
            to_csv(pd.DataFrame(records), run_dir / "predictions_partial.csv")
        provider = router.provider if router else None
        save_meta(f"incomplete: {e}", provider=provider.metadata() if provider else None,
                  **(provider.stats() if provider else {}), duration_s=round(time.perf_counter() - t0, 1), rows_done=len(records))
        print(f"\nSTOPPED after {len(records)} rows: {e}\nRe-run later; cached rows cost nothing.")
        return 3

    m = metrics.compute_all(preds)
    to_csv(preds, run_dir / "predictions.csv")
    meta.update(provider=router.provider.metadata(), **router.provider.stats(),
                duration_s=round(time.perf_counter() - t0, 1), rows_done=len(preds))
    report.write(run_dir, args.set, preds, m, base, meta)
    save_meta("complete")

    print(f"\n{run_dir.relative_to(ROOT)}")
    print(f"routing accuracy: {report.fmt_rate(m['routing_accuracy'])}")
    print(f"action accuracy:  {report.fmt_rate(m['action_accuracy'])}")
    print(f"provider: {router.provider.stats()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
