import math

import pandas as pd
import pytest

from evaluation import metrics


def test_wilson_known_value():
    # 8/10 at 95%: Wilson interval is (0.4902, 0.9433) - standard textbook value
    lo, hi = metrics.wilson(8, 10)
    assert lo == pytest.approx(0.4902, abs=1e-4)
    assert hi == pytest.approx(0.9433, abs=1e-4)


def test_wilson_edges():
    assert metrics.wilson(0, 10)[0] == 0.0
    assert metrics.wilson(10, 10)[1] == 1.0
    assert all(math.isnan(x) for x in metrics.wilson(0, 0))


def test_rate_shape():
    r = metrics.rate([True, True, False, True])
    assert (r["value"], r["k"], r["n"]) == (0.75, 3, 4)
    assert r["ci_low"] < 0.75 < r["ci_high"]
    assert metrics.rate([])["value"] is None


def row(lp, la, pp, pa, ls="", conf=0.9, auto=True, fb=False, topics=None, lang="en", src="s", vt=""):
    return {"label_primary": lp, "label_secondary": ls, "label_action": la, "pred_primary": pp, "pred_action": pa,
            "confidence": conf, "auto_routed": auto, "fallback_handoff": fb,
            "topic_domains": topics if topics is not None else [pp], "language": lang, "source": src,
            "variant_type": vt}


@pytest.fixture
def df():
    return metrics.add_flags(pd.DataFrame([
        row("IT", "answer", "IT", "answer"),                                      # all correct
        row("FEES", "handoff", "IT", "handoff", ls="IT", topics=["IT", "FEES"]),  # wrong primary, right secondary
        row("HOSTEL", "clarify", "IT", "clarify", auto=False, conf=0.5),          # excluded from routing
        row("OUT_OF_SCOPE", "refuse", "OUT_OF_SCOPE", "refuse", auto=False, conf=0.95, lang="hinglish"),
        row("ACADEMICS", "answer", "", "handoff", auto=False, conf=0.2, fb=True, topics=[]),
    ]))


def test_routing_accuracy_excludes_clarify_rows(df):
    r = metrics.routing_accuracy(df)
    assert (r["k"], r["n"]) == (2, 4)


def test_either_office_counts_secondary(df):
    r = metrics.routing_accuracy_either_office(df)
    assert (r["k"], r["n"]) == (3, 4)


def test_action_accuracy_all_rows(df):
    assert (metrics.action_accuracy(df)["k"], metrics.action_accuracy(df)["n"]) == (4, 5)


def test_multi_topic_recall(df):
    r = metrics.multi_topic_recall(df)
    assert (r["k"], r["n"]) == (1, 1)


def test_auto_route_precision_and_coverage(df):
    p = metrics.auto_route_precision(df)
    assert (p["k"], p["n"]) == (1, 2)
    c = metrics.auto_route_coverage(df)
    assert (c["k"], c["n"]) == (2, 5)


def test_rates(df):
    assert metrics.clarify_rate(df)["k"] == 1
    assert metrics.fallback_handoff_rate(df)["k"] == 1
    r = metrics.refuse_recall(df)
    assert (r["k"], r["n"]) == (1, 1)


def test_breakdown_by_language(df):
    b = metrics.breakdown(df, "language")
    assert b["hinglish"]["routing_accuracy"]["n"] == 1
    assert b["en"]["action_accuracy"]["n"] == 4


def test_calibration_bands_include_one(df):
    bands = {b["band"]: (b["k"], b["n"]) for b in metrics.calibration(df)}
    assert bands == {"[0.0, 0.4)": (0, 1), "[0.4, 0.7)": (0, 0), "[0.7, 1.0]": (2, 3)}


def test_confusion_counts_and_none_column(df):
    c = metrics.confusion(df)
    assert c["predicted"][-1] == "NONE"
    m = {lab: dict(zip(c["predicted"], r)) for lab, r in zip(c["labelled"], c["matrix"])}
    assert m["FEES"]["IT"] == 1 and m["ACADEMICS"]["NONE"] == 1 and m["HOSTEL"]["IT"] == 0
    assert sum(map(sum, c["matrix"])) == 4


def test_compute_all_runs(df):
    out = metrics.compute_all(df)
    assert out["rows"] == 5 and "variant_type" not in out["breakdowns"]
