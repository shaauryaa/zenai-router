"""Check that no example or dev text duplicates (or nearly duplicates) a test or simulated question.

Run: python -m evaluation.leakage
Exact duplicates (after normalizing) fail; similarity >= 0.85 (difflib ratio or token Jaccard) warns.
"""
import difflib
import json
import re
import sys
from pathlib import Path

from zenai.config import DATA

from .datasets import read_csv

WARN_AT = 0.85


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", text.lower())).strip()


def jaccard(a: str, b: str) -> float:
    ta, tb = set(a.split()), set(b.split())
    return len(ta & tb) / len(ta | tb) if ta | tb else 1.0


def compare(train: list[tuple[str, str, str]], test: list[tuple[str, str, str]], warn_at: float = WARN_AT) -> dict:
    """train/test items are (file, id, text). Returns {"exact": [...], "near": [...]}."""
    exact, near = [], []
    test_norm = [(f, i, normalize(t)) for f, i, t in test]
    for tf, tid, ttext in train:
        a = normalize(ttext)
        matcher = difflib.SequenceMatcher(None, a)
        for sf, sid, b in test_norm:
            pair = {"train_file": tf, "train_id": tid, "test_file": sf, "test_id": sid}
            if a == b:
                exact.append(pair)
                continue
            jac = jaccard(a, b)
            matcher.set_seq2(b)
            # quick_ratio is an upper bound on ratio, so skip the full ratio when it cannot reach warn_at
            ratio = matcher.ratio() if matcher.quick_ratio() >= warn_at else 0.0
            if ratio >= warn_at or jac >= warn_at:
                near.append({**pair, "ratio": round(ratio, 3), "jaccard": round(jac, 3)})
    return {"exact": exact, "near": near}


def load_texts() -> tuple[list, list]:
    with open(DATA / "examples.jsonl", encoding="utf-8") as f:
        examples = [json.loads(line) for line in f if line.strip()]
    train = [("examples.jsonl", e["id"], e["text"]) for e in examples]
    train += [("dev_set.csv", r["id"], r["question"]) for _, r in read_csv(DATA / "dev_set.csv").iterrows()]
    test = []
    for name in ("test_set.csv", "simulated_synced.csv"):
        test += [(name, r["id"], r["question"]) for _, r in read_csv(DATA / name).iterrows()]
    return train, test


def run() -> dict:
    train, test = load_texts()
    report = compare(train, test)
    report.update({"train_texts": len(train), "test_texts": len(test), "warn_at": WARN_AT,
                   "passed": not report["exact"]})
    return report


def format_report(report: dict) -> str:
    lines = [f"Leakage check: {report['train_texts']} example/dev texts vs {report['test_texts']} test/simulated texts",
             f"exact duplicates: {len(report['exact'])} ({'FAIL' if report['exact'] else 'ok'})",
             f"near duplicates (ratio or Jaccard >= {report['warn_at']}): {len(report['near'])}"]
    for p in report["exact"]:
        lines.append(f"  EXACT  {p['train_file']}:{p['train_id']} == {p['test_file']}:{p['test_id']}")
    for p in report["near"]:
        lines.append(f"  WARN   {p['train_file']}:{p['train_id']} ~ {p['test_file']}:{p['test_id']} "
                     f"(ratio {p['ratio']}, jaccard {p['jaccard']})")
    return "\n".join(lines)


def save(report: dict, run_dir: Path) -> None:
    (run_dir / "leakage.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    (run_dir / "leakage.txt").write_text(format_report(report) + "\n", encoding="utf-8")


def main() -> int:
    report = run()
    print(format_report(report))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
