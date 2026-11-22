from types import SimpleNamespace

import pytest

from zenai.confidence import aggregate, confidence, decide_topic
from zenai.knn import vote
from zenai.schemas import Neighbour

T_HIGH, T_LOW = 0.7, 0.4


# ---- confidence math ----

def test_confidence_agree_full_share():
    assert confidence("IT", "IT", 1.0, 0.5, 0.5) == (True, 1.0)


def test_confidence_disagree_uses_share_of_llm_domain():
    # kNN majority is HOSTEL, but 3/7 neighbours are IT (the LLM's pick)
    agree, conf = confidence("IT", "HOSTEL", 3 / 7, 0.5, 0.5)
    assert agree is False
    assert conf == pytest.approx(0.5 * 3 / 7, abs=1e-4)


def test_confidence_null_domain_never_agrees():
    assert confidence(None, None, 0.0, 0.5, 0.5) == (False, 0.0)


def test_confidence_respects_weights():
    assert confidence("FEES", "FEES", 0.4, 0.8, 0.2)[1] == pytest.approx(0.88)


# ---- every decision branch ----

@pytest.mark.parametrize("domain,rtype,conf,expected", [
    ("OUT_OF_SCOPE", "not_campus", 1.0, ("refuse", False)),
    ("OUT_OF_SCOPE", "info", 1.0, ("refuse", False)),      # domain alone triggers refuse
    ("IT", "not_campus", 1.0, ("refuse", False)),           # request type alone triggers refuse
    (None, None, 0.0, ("handoff", False)),                  # LLM fallback
    ("FEES", "vague", 1.0, ("clarify", False)),             # vague beats high confidence
    ("IT", "info", 0.7, ("answer", True)),                  # exactly t_high
    ("IT", "needs_human", 0.9, ("handoff", True)),
    ("HOSTEL", "info", 0.69, ("clarify", False)),
    ("HOSTEL", "info", 0.4, ("clarify", False)),            # exactly t_low
    ("HOSTEL", "info", 0.39, ("handoff", False)),
])
def test_decide_topic_branches(domain, rtype, conf, expected):
    action, auto, _ = decide_topic(domain, rtype, conf, T_HIGH, T_LOW)
    assert (action, auto) == expected


# ---- message aggregation ----

def topic(domain, action, auto=False):
    return SimpleNamespace(llm_domain=domain, action=action, auto_routed=auto)


def test_aggregate_multi_topic_takes_highest_action_and_first_domains():
    out = aggregate([topic("CAMPUS_SERVICES", "answer", True), topic("HOSTEL", "handoff", True)])
    assert out == {"primary_domain": "CAMPUS_SERVICES", "secondary_domain": "HOSTEL",
                   "action": "handoff", "auto_routed": True}


def test_aggregate_secondary_skips_same_domain():
    out = aggregate([topic("IT", "answer"), topic("IT", "answer"), topic("FEES", "clarify")])
    assert out["secondary_domain"] == "FEES"
    assert out["action"] == "clarify"


def test_aggregate_all_refuse():
    out = aggregate([topic("OUT_OF_SCOPE", "refuse"), topic("OUT_OF_SCOPE", "refuse")])
    assert out == {"primary_domain": "OUT_OF_SCOPE", "secondary_domain": None,
                   "action": "refuse", "auto_routed": False}


def test_aggregate_mixed_refuse_drops_refused_topic():
    out = aggregate([topic("OUT_OF_SCOPE", "refuse"), topic("ACADEMICS", "answer", True)])
    assert out == {"primary_domain": "ACADEMICS", "secondary_domain": None,
                   "action": "answer", "auto_routed": True}


def test_aggregate_single_topic_has_no_secondary():
    assert aggregate([topic("FEES", "clarify")])["secondary_domain"] is None


# ---- kNN vote ----

def nb(domain, sim, i=0):
    return Neighbour(id=f"X{i}", domain=domain, similarity=sim)


def test_vote_majority_and_shares():
    r = vote([nb("IT", 0.9), nb("IT", 0.8), nb("FEES", 0.95)])
    assert r.domain == "IT"
    assert r.share("IT") == pytest.approx(2 / 3)
    assert r.share("HOSTEL") == 0.0
    assert r.share(None) == 0.0


def test_vote_tie_broken_by_summed_similarity():
    r = vote([nb("IT", 0.5), nb("IT", 0.5), nb("FEES", 0.6), nb("FEES", 0.6)])
    assert r.domain == "FEES"
