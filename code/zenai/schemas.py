"""Data shapes shared by the router and the evaluator."""
from typing import Literal, get_args

from pydantic import BaseModel, Field, model_validator

Domain = Literal["IT", "FEES", "ACADEMICS", "HOSTEL", "CAMPUS_SERVICES", "OUT_OF_SCOPE"]
RequestType = Literal["info", "needs_human", "vague", "not_campus"]
Action = Literal["answer", "clarify", "handoff", "refuse"]

DOMAINS: tuple[str, ...] = get_args(Domain)
ACTIONS: tuple[str, ...] = get_args(Action)


class Topic(BaseModel):
    """One topic from the LLM. domain and request_type are None only for the parse-failure fallback."""
    text: str = Field(min_length=1)
    domain: Domain | None
    request_type: RequestType | None
    reason: str = ""


class LLMTopics(BaseModel):
    """Strict shape of the LLM reply: at least one topic, no null labels."""
    topics: list[Topic] = Field(min_length=1)

    @model_validator(mode="after")
    def labels_present(self):
        for t in self.topics:
            if t.domain is None or t.request_type is None:
                raise ValueError("every topic needs a domain and a request_type")
        return self


class Neighbour(BaseModel):
    id: str
    domain: Domain
    similarity: float


class TopicDecision(BaseModel):
    text: str
    request_type: RequestType | None
    llm_domain: Domain | None
    knn_domain: Domain | None
    knn_share: float  # share of the k neighbours whose domain equals llm_domain
    agree: bool
    confidence: float
    action: Action
    auto_routed: bool
    reason: str
    neighbours: list[Neighbour] = []


class RouteResult(BaseModel):
    message: str
    topics: list[TopicDecision]
    primary_domain: Domain | None
    secondary_domain: Domain | None
    action: Action
    auto_routed: bool
    signals: dict
    model: str
    latency_ms: float
