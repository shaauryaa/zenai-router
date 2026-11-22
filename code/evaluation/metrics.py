"""Evaluation metrics. Pure functions over a predictions DataFrame; every rate carries n and a 95% Wilson interval.

Expected columns: label_primary, label_secondary, label_action, pred_primary, pred_action, confidence,
auto_routed (bool), fallback_handoff (bool), topic_domains (list of str), plus breakdown columns
language, source, variant_type.

Domain metrics (routing accuracy, calibration, confusion) use only rows whose labelled action is not
clarify: a vague question has no single correct office.
"""
import math

import pandas as pd

from zenai.schemas import DOMAINS

BANDS = [(0.0, 0.4), (0.4, 0.7), (0.7, 1.0)]


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """95% Wilson score interval for k successes out of n."""
    if n == 0:
        return (math.nan, math.nan)
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    margin = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, centre - margin), min(1.0, centre + margin))


def rate(flags) -> dict:
    """{value, k, n, ci_low, ci_high} for an iterable of booleans (value is None when n == 0)."""
    flags = [bool(f) for f in flags]
    k, n = sum(flags), len(flags)
    lo, hi = wilson(k, n)
    return {"value": k / n if n else None, "k": k, "n": n,
            "ci_low": None if n == 0 else lo, "ci_high": None if n == 0 else hi}


def add_flags(df: pd.DataFrame) -> pd.DataFrame:
    """Add correctness columns used by all metrics."""
    df = df.copy()
    df["routing_eligible"] = df["label_action"] != "clarify"
    df["routing_correct"] = df["pred_primary"] == df["label_primary"]
    df["routing_correct_either"] = [p != "" and p in (a, b) for p, a, b in
                                    zip(df["pred_primary"], df["label_primary"], df["label_secondary"])]
    df["action_correct"] = df["pred_action"] == df["label_action"]
    df["multi_topic_correct"] = [(a in set(t) and b in set(t)) if b else None for a, b, t in
                                 zip(df["label_primary"], df["label_secondary"], df["topic_domains"])]
    return df


def routing_rows(df: pd.DataFrame) -> pd.DataFrame:
    return df[df["label_action"] != "clarify"]


def routing_accuracy(df: pd.DataFrame) -> dict:
    return rate(routing_rows(df)["routing_correct"])


def routing_accuracy_either_office(df: pd.DataFrame) -> dict:
    return rate(routing_rows(df)["routing_correct_either"])


def action_accuracy(df: pd.DataFrame) -> dict:
    return rate(df["action_correct"])


def multi_topic_recall(df: pd.DataFrame) -> dict:
    return rate(df.loc[df["label_secondary"] != "", "multi_topic_correct"])


def auto_route_precision(df: pd.DataFrame) -> dict:
    return rate(df.loc[df["auto_routed"], "routing_correct"])


def auto_route_coverage(df: pd.DataFrame) -> dict:
    return rate(df["auto_routed"])


def clarify_rate(df: pd.DataFrame) -> dict:
    return rate(df["pred_action"] == "clarify")


def fallback_handoff_rate(df: pd.DataFrame) -> dict:
    return rate(df["fallback_handoff"])


def refuse_recall(df: pd.DataFrame) -> dict:
    return rate(df.loc[df["label_primary"] == "OUT_OF_SCOPE", "pred_action"] == "refuse")


def breakdown(df: pd.DataFrame, col: str) -> dict:
    out = {}
    for value, group in df.groupby(col, sort=True):
        out[value or "(blank)"] = {"routing_accuracy": routing_accuracy(group), "action_accuracy": action_accuracy(group)}
    return out


def band_label(lo: float, hi: float) -> str:
    return f"[{lo:.1f}, {hi:.1f}]" if hi == 1.0 else f"[{lo:.1f}, {hi:.1f})"


def calibration(df: pd.DataFrame) -> list[dict]:
    """Routing accuracy per confidence band; the top band includes 1.0."""
    rows = routing_rows(df)
    out = []
    for lo, hi in BANDS:
        in_band = (rows["confidence"] >= lo) & ((rows["confidence"] < hi) | ((hi == 1.0) & (rows["confidence"] <= hi)))
        out.append({"band": band_label(lo, hi), **rate(rows.loc[in_band, "routing_correct"])})
    return out


def confusion(df: pd.DataFrame) -> dict:
    """Counts of labelled (rows) vs predicted (columns) primary domain over routing rows."""
    rows = routing_rows(df)
    predicted = list(DOMAINS) + (["NONE"] if (rows["pred_primary"] == "").any() else [])
    matrix = [[int(((rows["label_primary"] == lab) & (rows["pred_primary"].replace("", "NONE") == pred)).sum())
               for pred in predicted] for lab in DOMAINS]
    return {"labelled": list(DOMAINS), "predicted": predicted, "matrix": matrix}


def compute_all(df: pd.DataFrame) -> dict:
    df = add_flags(df) if "routing_correct" not in df else df
    breakdown_cols = ["label_primary", "language", "source"]
    if (df["variant_type"] != "").any():
        breakdown_cols.append("variant_type")
    return {
        "rows": len(df),
        "routing_accuracy": routing_accuracy(df),
        "routing_accuracy_either_office": routing_accuracy_either_office(df),
        "action_accuracy": action_accuracy(df),
        "multi_topic_recall": multi_topic_recall(df),
        "auto_route_precision": auto_route_precision(df),
        "auto_route_coverage": auto_route_coverage(df),
        "clarify_rate": clarify_rate(df),
        "fallback_handoff_rate": fallback_handoff_rate(df),
        "refuse_recall": refuse_recall(df),
        "breakdowns": {col: breakdown(df, col) for col in breakdown_cols},
        "calibration": calibration(df),
        "confusion": confusion(df),
    }
