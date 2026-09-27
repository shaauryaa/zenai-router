"""Sync rules for simulated labels and the leakage checker. Rows here are invented."""
import pandas as pd
import pytest

from evaluation.leakage import compare, jaccard, normalize
from evaluation.sync_simulated import derive_labels, sync

SEEDS = {
    "A": {"primary_domain": "IT", "secondary_domain": "FEES", "expected_action": "answer"},
    "B": {"primary_domain": "HOSTEL", "secondary_domain": "", "expected_action": "handoff"},
    "C": {"primary_domain": "IT", "secondary_domain": "", "expected_action": "clarify"},
    "R": {"primary_domain": "OUT_OF_SCOPE", "secondary_domain": "", "expected_action": "refuse"},
    "R2": {"primary_domain": "OUT_OF_SCOPE", "secondary_domain": "", "expected_action": "refuse"},
}


@pytest.mark.parametrize("variant", ["paraphrase", "language_switch", "typo_sms"])
def test_copy_variants(variant):
    assert derive_labels(variant, "A", SEEDS) == ("IT", "FEES", "answer")


def test_vaguer():
    assert derive_labels("vaguer", "A", SEEDS) == ("IT", "", "clarify")


def test_merge_takes_highest_action():
    assert derive_labels("merge", "A+B", SEEDS) == ("IT", "HOSTEL", "handoff")
    assert derive_labels("merge", "C+A", SEEDS) == ("IT", "", "clarify")  # same primary -> no secondary


def test_merge_with_refuse_matches_router_aggregation():
    assert derive_labels("merge", "R+B", SEEDS) == ("HOSTEL", "", "handoff")
    assert derive_labels("merge", "R+R2", SEEDS) == ("OUT_OF_SCOPE", "", "refuse")


def test_unknown_variant_raises():
    with pytest.raises(ValueError):
        derive_labels("rewrite", "A", SEEDS)


def test_sync_changes_labels_not_text():
    test = pd.DataFrame([{"id": k, **v} for k, v in SEEDS.items()])
    sim = pd.DataFrame([
        {"id": "S1", "seed_id": "A", "variant_type": "paraphrase", "question": "q one",
         "primary_domain": "FEES", "secondary_domain": "", "expected_action": "answer"},
        {"id": "S2", "seed_id": "B", "variant_type": "typo_sms", "question": "q two",
         "primary_domain": "HOSTEL", "secondary_domain": "", "expected_action": "handoff"},
    ])
    out, changes = sync(sim, test)
    assert len(changes) == 1 and changes[0].startswith("S1")
    assert list(out.loc[0, ["primary_domain", "secondary_domain"]]) == ["IT", "FEES"]
    assert list(out["question"]) == ["q one", "q two"]
    assert sim.loc[0, "primary_domain"] == "FEES"  # input untouched


def test_normalize_and_jaccard():
    assert normalize("  Where's the  PRINTER?! ") == "where s the printer"
    assert jaccard("a b c", "a b d") == pytest.approx(0.5)


def test_compare_exact_near_and_clean():
    train = [("ex", "E1", "Where is the printer room?"), ("ex", "E2", "the canteen closes at nine on weekdays"),
             ("ex", "E3", "totally unrelated text")]
    test = [("t", "T1", "where is the PRINTER room"), ("t", "T2", "the canteen closes at nine on weekday")]
    report = compare(train, test)
    assert [(p["train_id"], p["test_id"]) for p in report["exact"]] == [("E1", "T1")]
    assert [(p["train_id"], p["test_id"]) for p in report["near"]] == [("E2", "T2")]
