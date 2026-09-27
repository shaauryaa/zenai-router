"""Demo API endpoints with FakeProvider. Endpoints are called directly (no HTTP client, no network)."""
import json

import pytest
from fastapi import HTTPException

from zenai.api import SAMPLE_IDS, RouteRequest, create_app
from zenai.providers import FakeProvider, QuotaError
from zenai.router import Router

CFG = {"knn": {"k": 3}, "confidence": {"w_agree": 0.5, "w_share": 0.5},
       "thresholds": {"t_high": 0.7, "t_low": 0.4, "tuned_on": "dev_set.csv sha256:abc", "frozen": True}}
EXAMPLES = [
    {"id": "E1", "text": "projector in lab broken", "domain": "CAMPUS_SERVICES"},
    {"id": "E2", "text": "lab projector not working", "domain": "CAMPUS_SERVICES"},
    {"id": "E3", "text": "warden late entry rules", "domain": "HOSTEL"},
    {"id": "E4", "text": "late entry warden form", "domain": "HOSTEL"},
]


@pytest.fixture
def endpoints(tmp_path):
    path = tmp_path / "examples.jsonl"
    path.write_text("\n".join(json.dumps(e) for e in EXAMPLES), encoding="utf-8")
    provider = FakeProvider(chat_fn=lambda msgs: {"topics": [
        {"text": "lab projector broken", "domain": "CAMPUS_SERVICES", "request_type": "needs_human", "reason": "fix"},
        {"text": "warden late entry rules", "domain": "HOSTEL", "request_type": "info", "reason": "rules"}]})
    router = Router(CFG, provider, path)
    app = create_app(router)
    return router, {route.path: route.endpoint for route in app.routes}


def test_route_returns_topics_and_example_texts(endpoints):
    _, ep = endpoints
    out = ep["/route"](RouteRequest(message="lab projector broken and warden late entry rules?"))
    assert [t["llm_domain"] for t in out["topics"]] == ["CAMPUS_SERVICES", "HOSTEL"]
    assert out["action"] == "handoff" and out["secondary_domain"] == "HOSTEL"
    ids = {n["id"] for t in out["topics"] for n in t["neighbours"]}
    assert set(out["example_texts"]) == ids
    assert out["example_texts"]["E1"] == "projector in lab broken"


def test_route_rejects_blank_message(endpoints):
    _, ep = endpoints
    with pytest.raises(HTTPException) as exc:
        ep["/route"](RouteRequest(message="   "))
    assert exc.value.status_code == 422


def test_route_maps_quota_error_to_429(endpoints):
    router, ep = endpoints

    def over_quota(msgs):
        raise QuotaError("daily chat cap reached")
    router.provider.chat_fn = over_quota
    with pytest.raises(HTTPException) as exc:
        ep["/route"](RouteRequest(message="anything"))
    assert exc.value.status_code == 429


def test_health_reports_model_and_frozen_thresholds(endpoints):
    _, ep = endpoints
    h = ep["/health"]()
    assert h["model"] == "fake-chat"
    assert h["thresholds"] == {"t_high": 0.7, "t_low": 0.4, "frozen": True, "tuned_on": "dev_set.csv sha256:abc"}


def test_samples_come_from_dev_set_only(endpoints):
    _, ep = endpoints
    samples = ep["/samples"]()
    assert [s["id"] for s in samples] == SAMPLE_IDS
    assert all(s["id"].startswith("D") and s["question"] for s in samples)
