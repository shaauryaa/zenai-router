"""route(message): LLM topics (signal A) + kNN vote (signal B) -> confidence -> decisions."""
import time
from pathlib import Path

from .config import DATA, load_config
from .confidence import aggregate, confidence, decide_topic
from .knn import KNNIndex
from .llm_router import classify
from .providers import Provider
from .schemas import Neighbour, RouteResult, TopicDecision


def decide(message: str, signals: dict, cfg: dict, model: str = "", latency_ms: float = 0.0) -> RouteResult:
    """Build a RouteResult from recorded raw signals. Makes no API calls, so an evaluation can
    re-run it with different weights or thresholds on signals saved from an earlier run."""
    w, th = cfg["confidence"], cfg["thresholds"]
    decisions = []
    for s in signals["topics"]:
        agree, conf = confidence(s["llm_domain"], s["knn_domain"], s["knn_share_of_llm_domain"],
                                 w["w_agree"], w["w_share"])
        action, auto, rule = decide_topic(s["llm_domain"], s["request_type"], conf, th["t_high"], th["t_low"])
        decisions.append(TopicDecision(
            text=s["text"], request_type=s["request_type"], llm_domain=s["llm_domain"],
            knn_domain=s["knn_domain"], knn_share=s["knn_share_of_llm_domain"], agree=agree,
            confidence=conf, action=action, auto_routed=auto,
            reason=f"{rule}; LLM: {s['llm_reason']}",
            neighbours=[Neighbour(**n) for n in s["neighbours"]]))
    return RouteResult(message=message, topics=decisions, **aggregate(decisions),
                       signals=signals, model=model, latency_ms=latency_ms)


class Router:
    def __init__(self, cfg: dict | None = None, provider=None, examples_path: Path = DATA / "examples.jsonl"):
        self.cfg = cfg or load_config()
        self.provider = provider or Provider(self.cfg)
        self.knn = KNNIndex(self.provider, self.cfg["knn"]["k"], examples_path)

    def signals(self, message: str) -> dict:
        """Raw signals for a message: one chat call plus one embedding call (both cached)."""
        topics, llm_info = classify(message, self.provider)
        knn_results = self.knn.query_many([t.text for t in topics])
        return {
            "topics": [{
                "text": t.text,
                "llm_domain": t.domain,
                "request_type": t.request_type,
                "llm_reason": t.reason,
                "knn_domain": r.domain,
                "knn_share_of_llm_domain": r.share(t.domain),
                "knn_shares": r.shares,
                "neighbours": [n.model_dump() for n in r.neighbours],
            } for t, r in zip(topics, knn_results)],
            "llm": llm_info,
            "provider": self.provider.metadata(),
            "knn_k": self.knn.k,
        }

    def route(self, message: str) -> RouteResult:
        start = time.perf_counter()
        signals = self.signals(message)
        latency_ms = round((time.perf_counter() - start) * 1000, 1)
        return decide(message, signals, self.cfg, model=self.provider.chat_model, latency_ms=latency_ms)
