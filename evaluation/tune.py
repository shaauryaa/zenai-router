"""Grid-search thresholds and weights on the latest dev run's saved signals (no API calls).

python -m evaluation.tune [--write]

Objective: maximize dev action_accuracy; tie-break by higher auto_route_precision, then lower clarify_rate,
then smallest change from the current config (so exact ties never move the settings without dev evidence).
The full grid is saved to results/<timestamp>_tune/. --write stores the winner in config.yaml and freezes it.
Only the dev set may be tuned on (CLAUDE.md).
"""
import argparse
import copy
import json
import re
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

from zenai.config import DATA, ROOT, load_config
from zenai.router import decide

from . import metrics
from .datasets import read_csv, sha256_file
from .run_eval import RESULTS, prediction_row


def frange(lo: float, hi: float, step: float = 0.05) -> list[float]:
    n = int(round((hi - lo) / step))
    return [round(lo + i * step, 2) for i in range(n + 1)]


def latest_complete_run(set_name: str = "dev") -> Path:
    for run_dir in sorted(RESULTS.glob(f"*_{set_name}"), reverse=True):
        meta = json.loads((run_dir / "run_meta.json").read_text(encoding="utf-8"))
        if meta.get("status") == "complete" and not meta.get("limit"):
            return run_dir
    raise SystemExit(f"no complete, unlimited {set_name} run in results/")


def load_run(run_dir: Path) -> list[tuple[pd.Series, dict]]:
    preds = read_csv(run_dir / "predictions.csv")
    rows = []
    for _, r in preds.iterrows():
        signals = {"topics": json.loads(r["signals"]), "llm": {"fallback": r["llm_fallback"] == "True"}}
        rows.append((r, signals))
    return rows


def score(rows: list[tuple[pd.Series, dict]], cfg: dict) -> dict:
    records = [prediction_row(r, decide(r["question"], signals, cfg)) for r, signals in rows]
    df = metrics.add_flags(pd.DataFrame(records))
    return {"action_accuracy": metrics.action_accuracy(df), "auto_route_precision": metrics.auto_route_precision(df),
            "auto_route_coverage": metrics.auto_route_coverage(df), "clarify_rate": metrics.clarify_rate(df),
            "routing_accuracy": metrics.routing_accuracy(df)}


def sort_key(s: dict, current: dict | None = None) -> tuple:
    """Objective, then tie-breaks; the last element is the distance from the current config."""
    prec = s["auto_route_precision"]["value"]
    change = 0.0 if current is None else round(sum(abs(s[k] - current[k]) for k in ("w_agree", "t_high", "t_low")), 2)
    return (-s["action_accuracy"]["value"], -(prec if prec is not None else -1), s["clarify_rate"]["value"], change)


def grid(rows, base_cfg: dict) -> list[dict]:
    current = {"w_agree": base_cfg["confidence"]["w_agree"], **base_cfg["thresholds"]}
    results = []
    for w_agree in (0.3, 0.5, 0.7):
        for t_high in frange(0.50, 0.95):
            for t_low in frange(0.20, t_high):
                cfg = copy.deepcopy(base_cfg)
                cfg["confidence"] = {"w_agree": w_agree, "w_share": round(1 - w_agree, 2)}
                cfg["thresholds"].update(t_high=t_high, t_low=t_low)
                results.append({"w_agree": w_agree, "w_share": round(1 - w_agree, 2), "t_high": t_high,
                                "t_low": t_low, **score(rows, cfg)})
    return sorted(results, key=lambda r: sort_key(r, current))


def fmt(r: dict) -> str:
    return "n/a" if r["value"] is None else f"{r['value'] * 100:.1f}% ({r['k']}/{r['n']})"


def write_config(best: dict, tuned_on: str) -> None:
    path = ROOT / "config.yaml"
    text = path.read_text(encoding="utf-8")
    text, n1 = re.subn(r"(?m)^confidence:.*$",
                       f"confidence: {{w_agree: {best['w_agree']}, w_share: {best['w_share']}}}", text)
    text, n2 = re.subn(r"(?m)^thresholds:.*$",
                       f"thresholds: {{t_high: {best['t_high']}, t_low: {best['t_low']}, "
                       f"tuned_on: \"{tuned_on}\", frozen: true}}", text)
    assert n1 == n2 == 1, "config.yaml confidence/thresholds lines not found"
    path.write_text(text, encoding="utf-8")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--write", action="store_true", help="write the winner to config.yaml and freeze it")
    args = ap.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")

    cfg = load_config()
    run_dir = latest_complete_run("dev")
    rows = load_run(run_dir)
    results = grid(rows, cfg)
    current = score(rows, cfg)

    out_dir = RESULTS / f"{datetime.now():%Y%m%d-%H%M%S}_tune"
    out_dir.mkdir(parents=True)
    flat = [{k: (v["value"] if isinstance(v, dict) else v) for k, v in r.items()} for r in results]
    pd.DataFrame(flat).to_csv(out_dir / "grid.csv", index=False)
    dev_hash = sha256_file(DATA / "dev_set.csv")
    summary = {"source_run": run_dir.name, "dev_set_sha256": dev_hash, "settings_tried": len(results),
               "objective": "max action_accuracy; tie-break max auto_route_precision, then min clarify_rate, "
                            "then smallest change from current config",
               "current_config": {"confidence": cfg["confidence"], "thresholds": cfg["thresholds"], **current},
               "top5": results[:5]}
    (out_dir / "tune_summary.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")

    print(f"Tuned on signals from {run_dir.relative_to(ROOT)} ({len(rows)} dev rows), "
          f"{len(results)} settings, 0 API calls. Grid saved to {out_dir.relative_to(ROOT)}")
    print(f"\ncurrent config: action {fmt(current['action_accuracy'])}, "
          f"auto-route precision {fmt(current['auto_route_precision'])}, clarify {fmt(current['clarify_rate'])}")
    print("\nrank  w_agree  t_high  t_low  action_acc      auto_prec       coverage        clarify         routing")
    for i, r in enumerate(results[:5], 1):
        print(f"{i:<5} {r['w_agree']:<8} {r['t_high']:<7} {r['t_low']:<6} {fmt(r['action_accuracy']):<15} "
              f"{fmt(r['auto_route_precision']):<15} {fmt(r['auto_route_coverage']):<15} "
              f"{fmt(r['clarify_rate']):<15} {fmt(r['routing_accuracy'])}")
    ties = sum(1 for r in results if sort_key(r)[:3] == sort_key(results[0])[:3])
    print(f"\nWARNING: the dev set has only {len(rows)} rows, so one row moves action accuracy by "
          f"{100 / len(rows):.1f} points. {ties} setting(s) tie on the three objectives; the final tie-break "
          "(smallest change from the current config) picks among them. Treat this choice as rough.")

    if args.write:
        write_config(results[0], f"dev_set.csv sha256:{dev_hash}")
        print(f"\nwrote winner to config.yaml (frozen: true, tuned_on dev_set.csv sha256:{dev_hash[:12]}...)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
