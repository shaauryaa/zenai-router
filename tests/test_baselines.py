import pandas as pd

from evaluation.baselines import keyword_domain, llm_only, run_baselines


def test_keyword_domain():
    assert keyword_domain("my outlook email is locked") == "IT"
    assert keyword_domain("Scholarship refund status") == "FEES"
    assert keyword_domain("exams and attendance") == "ACADEMICS"
    assert keyword_domain("the AC in block Q is broken") == "CAMPUS_SERVICES"  # short keyword matches exactly
    assert keyword_domain("accurate") == "OUT_OF_SCOPE"                         # 'ac' must not match inside words
    assert keyword_domain("what is the meaning of life") == "OUT_OF_SCOPE"


def test_keyword_tie_goes_to_first_domain():
    assert keyword_domain("wifi fee") == "IT"


def t(domain, rtype):
    return {"llm_domain": domain, "request_type": rtype}


def test_llm_only_ignores_confidence():
    assert llm_only([t("IT", "info")]) == ("IT", "answer")
    assert llm_only([t("OUT_OF_SCOPE", "not_campus"), t("HOSTEL", "needs_human")]) == ("HOSTEL", "handoff")
    assert llm_only([t("OUT_OF_SCOPE", "not_campus")]) == ("OUT_OF_SCOPE", "refuse")
    assert llm_only([t(None, None)]) == ("", "handoff")


def test_run_baselines_table_shape():
    preds = pd.DataFrame([{
        "question": "wifi password reset", "label_primary": "IT", "label_secondary": "", "label_action": "answer",
        "pred_primary": "IT", "pred_action": "answer", "confidence": 1.0, "auto_routed": True,
        "fallback_handoff": False, "topic_domains": ["IT"], "signals_topics": [t("IT", "info")],
    }])
    out = run_baselines(preds, ["FEES"])
    assert out["keyword"]["routing_accuracy"]["value"] == 1.0 and out["keyword"]["action_accuracy"] is None
    assert out["knn_only"]["routing_accuracy"]["value"] == 0.0
    assert out["llm_only"]["action_accuracy"]["value"] == 1.0
    assert out["combined"]["routing_accuracy"]["value"] == 1.0
