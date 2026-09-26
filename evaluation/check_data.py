"""Validate the files in data/ without modifying them.

Run: python -m evaluation.check_data
Exits with status 1 if any row has a domain or action outside the allowed lists.
"""
import re
import sys
from pathlib import Path

import pandas as pd

DATA = Path(__file__).resolve().parent.parent / "data"

DOMAINS = {"IT", "FEES", "ACADEMICS", "HOSTEL", "CAMPUS_SERVICES", "OUT_OF_SCOPE"}
ACTIONS = {"answer", "clarify", "handoff", "refuse"}

# (file, text column, domain column, action column or None)
FILES = [
    ("examples.jsonl", "text", "domain", None),
    ("dev_set.csv", "question", "primary_domain", "expected_action"),
    ("test_set.csv", "question", "primary_domain", "expected_action"),
    ("simulated_v1.csv", "question", "primary_domain", "expected_action"),
]
TEST_FILES = {"test_set.csv", "simulated_v1.csv"}


def load(name: str) -> pd.DataFrame:
    path = DATA / name
    if name.endswith(".jsonl"):
        return pd.read_json(path, lines=True, dtype=str).fillna("")
    # utf-8-sig strips the BOM Excel writes; keep empty cells as "" rather than NaN
    return pd.read_csv(path, encoding="utf-8-sig", dtype=str, keep_default_na=False)


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", "", text.lower())).strip()


def check_file(name: str, df: pd.DataFrame, text_col: str, domain_col: str, action_col: str | None) -> list[str]:
    """Print counts for one file and return a list of problems found."""
    problems = []
    print(f"\n=== {name}: {len(df)} rows ===")
    count_cols = [domain_col] + ([action_col] if action_col else ["request_type"]) + ["language"]
    for col in count_cols:
        if col not in df.columns:
            problems.append(f"{name}: missing column {col!r}")
            continue
        print(f"\n{col}:")
        print(df[col].replace("", "<empty>").value_counts().to_string())

    id_col = df.columns[0]
    for dup in df[df[id_col].duplicated()][id_col]:
        problems.append(f"{name}: duplicate {id_col} {dup!r}")

    for i, row in df.iterrows():
        rid = row[id_col]
        if row.get(domain_col, "") not in DOMAINS:
            problems.append(f"{name} row {rid}: {domain_col}={row.get(domain_col)!r} not allowed")
        sec = row.get("secondary_domain", "")
        if sec and sec not in DOMAINS:
            problems.append(f"{name} row {rid}: secondary_domain={sec!r} not allowed")
        if action_col and row.get(action_col, "") not in ACTIONS:
            problems.append(f"{name} row {rid}: {action_col}={row.get(action_col)!r} not allowed")
        if not row.get(text_col, "").strip():
            problems.append(f"{name} row {rid}: empty {text_col}")
    return problems


def check_leakage(frames: dict[str, tuple[pd.DataFrame, str]]) -> list[str]:
    """Flag test questions whose normalized text also appears in a non-test file."""
    warnings = []
    seen = {}
    for name, (df, text_col) in frames.items():
        if name not in TEST_FILES:
            for t in df[text_col]:
                seen.setdefault(normalize(t), name)
    for name, (df, text_col) in frames.items():
        if name in TEST_FILES:
            for rid, t in zip(df[df.columns[0]], df[text_col]):
                if normalize(t) in seen:
                    warnings.append(f"{name} row {rid} text also appears in {seen[normalize(t)]}")
    return warnings


def main() -> int:
    problems, frames = [], {}
    for name, text_col, domain_col, action_col in FILES:
        df = load(name)
        frames[name] = (df, text_col)
        problems += check_file(name, df, text_col, domain_col, action_col)

    leaks = check_leakage(frames)

    print("\n=== summary ===")
    print("invalid rows:", len(problems))
    for p in problems:
        print("  ", p)
    print("test/train text overlaps:", len(leaks))
    for w in leaks:
        print("  ", w)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
