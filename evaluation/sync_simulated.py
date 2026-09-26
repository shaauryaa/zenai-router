"""Re-derive simulated_v1.csv labels from the current test_set.csv labels -> data/simulated_synced.csv.

Run: python -m evaluation.sync_simulated
Only primary_domain, secondary_domain and expected_action are rewritten; question text is never changed.
"""
import pandas as pd

from zenai.config import DATA

from .datasets import read_csv

COPY_VARIANTS = {"paraphrase", "language_switch", "typo_sms"}
ACTION_RANK = {"answer": 0, "clarify": 1, "handoff": 2}
LABEL_COLS = ["primary_domain", "secondary_domain", "expected_action"]


def derive_labels(variant_type: str, seed_id: str, seeds: dict[str, dict]) -> tuple[str, str, str]:
    """(primary, secondary, action) for one simulated row, from its seed row(s) in the test set."""
    if variant_type in COPY_VARIANTS:
        s = seeds[seed_id]
        return s["primary_domain"], s["secondary_domain"], s["expected_action"]
    if variant_type == "vaguer":
        return seeds[seed_id]["primary_domain"], "", "clarify"
    if variant_type == "merge":
        a, b = seed_id.split("+")
        # Refused parts are dropped unless both are refused, matching the router's message aggregation.
        parts = [seeds[x] for x in (a, b) if seeds[x]["expected_action"] != "refuse"]
        if not parts:
            return "OUT_OF_SCOPE", "", "refuse"
        primary = parts[0]["primary_domain"]
        secondary = parts[1]["primary_domain"] if len(parts) > 1 else ""
        if secondary == primary:
            secondary = ""
        action = max((p["expected_action"] for p in parts), key=ACTION_RANK.__getitem__)
        return primary, secondary, action
    raise ValueError(f"unknown variant_type {variant_type!r}")


def sync(sim: pd.DataFrame, test: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """Return (synced copy of sim, list of human-readable changes)."""
    seeds = test.set_index("id").to_dict("index")
    out = sim.copy()
    changes = []
    for i, row in out.iterrows():
        new = derive_labels(row["variant_type"], row["seed_id"], seeds)
        diffs = [f"{c}: {row[c] or '-'} -> {v or '-'}" for c, v in zip(LABEL_COLS, new) if row[c] != v]
        if diffs:
            changes.append(f"{row['id']} ({row['variant_type']}, seed {row['seed_id']}): " + "; ".join(diffs))
            out.loc[i, LABEL_COLS] = list(new)
    assert (out["question"] == sim["question"]).all()
    return out, changes


def write_synced() -> list[str]:
    sim = read_csv(DATA / "simulated_v1.csv")
    test = read_csv(DATA / "test_set.csv")
    synced, changes = sync(sim, test)
    synced.to_csv(DATA / "simulated_synced.csv", index=False, encoding="utf-8")
    return changes


def main() -> None:
    changes = write_synced()
    print(f"wrote data/simulated_synced.csv; {len(changes)} rows changed")
    for c in changes:
        print("  ", c)


if __name__ == "__main__":
    main()
