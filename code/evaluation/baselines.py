"""Simple baselines scored on the same rows as the router, reusing its cached signals.

keyword:  keyword hits per domain; the lists are written ONLY from the domain descriptions in
          zenai/llm_router.py SYSTEM_PROMPT, never from dataset questions.
knn_only: kNN vote over the whole message (one batched, cached embedding request per 64 rows).
llm_only: LLM domain; action from request_type alone, ignoring confidence.
combined: the real router.
"""
import re
from types import SimpleNamespace

import pandas as pd

from zenai.confidence import aggregate

from . import metrics

KEYWORDS = {
    "IT": ["erp", "email", "outlook", "lms", "laptop", "network", "account", "wifi", "connectivity"],
    "FEES": ["fee", "payment", "pay", "receipt", "scholarship", "refund", "deadline"],
    "ACADEMICS": ["exam", "calendar", "holiday", "attendance", "faculty", "contact", "registrar", "document",
                  "course", "batch", "placement", "club", "fest"],
    "HOSTEL": ["hostel", "warden", "room", "allotment", "curfew", "leave", "outing", "guest", "rule", "laundry"],
    "CAMPUS_SERVICES": ["maintenance", "cleaning", "electrical", "plumbing", "ac", "mess", "food", "outlet",
                        "transport", "sports", "library", "lost", "found"],
}

REQUEST_TYPE_ACTION = {"info": "answer", "needs_human": "handoff", "vague": "clarify", "not_campus": "refuse"}


def _hits(word: str, keyword: str) -> bool:
    # Short keywords (ac, erp, lms, pay) must match exactly; longer ones also match plurals/inflections.
    return word == keyword if len(keyword) <= 3 else word.startswith(keyword)


def keyword_domain(text: str) -> str:
    """Domain with the most keyword hits; ties go to the first domain listed; no hits -> OUT_OF_SCOPE."""
    words = re.findall(r"[a-z]+", text.lower())
    scores = {d: sum(_hits(w, k) for w in words for k in kws) for d, kws in KEYWORDS.items()}
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "OUT_OF_SCOPE"


def llm_only(topics: list[dict]) -> tuple[str, str]:
    """(primary, action) from the LLM's topic labels alone, aggregated like the router."""
    decisions = [SimpleNamespace(llm_domain=t["llm_domain"],
                                 action="handoff" if t["llm_domain"] is None
                                 else REQUEST_TYPE_ACTION[t["request_type"]],
                                 auto_routed=False) for t in topics]
    agg = aggregate(decisions)
    return agg["primary_domain"] or "", agg["action"]


def _score(preds: pd.DataFrame, pred_primary, pred_action=None) -> dict:
    df = preds.copy()
    df["pred_primary"] = list(pred_primary)
    if pred_action is not None:
        df["pred_action"] = list(pred_action)
    df = metrics.add_flags(df)
    return {"routing_accuracy": metrics.routing_accuracy(df),
            "action_accuracy": metrics.action_accuracy(df) if pred_action is not None else None}


def run_baselines(preds: pd.DataFrame, knn_message_domains: list[str]) -> dict:
    """preds must hold the router's predictions plus a `signals_topics` column (list of topic signal dicts)."""
    llm = [llm_only(t) for t in preds["signals_topics"]]
    return {
        "keyword": _score(preds, [keyword_domain(q) for q in preds["question"]]),
        "knn_only": _score(preds, knn_message_domains),
        "llm_only": _score(preds, [p for p, _ in llm], [a for _, a in llm]),
        "combined": _score(preds, preds["pred_primary"], preds["pred_action"]),
    }
