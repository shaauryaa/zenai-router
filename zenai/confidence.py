"""Confidence score and decision rules. Pure functions: no API calls, so decisions can be recomputed offline."""

ACTION_RANK = {"answer": 0, "clarify": 1, "handoff": 2}


def confidence(llm_domain: str | None, knn_domain: str | None, share_llm: float,
               w_agree: float, w_share: float) -> tuple[bool, float]:
    """agree = LLM and kNN picked the same domain; confidence = w_agree*agree + w_share*share(llm_domain)."""
    agree = llm_domain is not None and llm_domain == knn_domain
    return agree, round(w_agree * int(agree) + w_share * share_llm, 4)


def decide_topic(domain: str | None, request_type: str | None, conf: float,
                 t_high: float, t_low: float) -> tuple[str, bool, str]:
    """Return (action, auto_routed, rule) for one topic. Rules are checked in order."""
    if domain == "OUT_OF_SCOPE" or request_type == "not_campus":
        return "refuse", False, "out of scope"
    if domain is None:
        return "handoff", False, "no domain from LLM (fallback)"
    if request_type == "vague":
        return "clarify", False, "request is vague"
    if conf >= t_high:
        if request_type == "info":
            return "answer", True, f"confidence {conf:.2f} >= t_high, info request"
        return "handoff", True, f"confidence {conf:.2f} >= t_high, needs a human"
    if conf >= t_low:
        return "clarify", False, f"t_low <= confidence {conf:.2f} < t_high"
    return "handoff", False, f"confidence {conf:.2f} < t_low (fallback)"


def aggregate(topics: list) -> dict:
    """Combine topic decisions (objects with llm_domain, action, auto_routed) into a message decision."""
    kept = [t for t in topics if t.action != "refuse"]
    if not kept:
        return {"primary_domain": "OUT_OF_SCOPE", "secondary_domain": None, "action": "refuse", "auto_routed": False}
    primary = kept[0]
    secondary = next((t.llm_domain for t in kept[1:]
                      if t.llm_domain is not None and t.llm_domain != primary.llm_domain), None)
    action = max((t.action for t in kept), key=ACTION_RANK.__getitem__)
    return {"primary_domain": primary.llm_domain, "secondary_domain": secondary,
            "action": action, "auto_routed": primary.auto_routed}
