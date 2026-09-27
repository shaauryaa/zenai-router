"""Demo web API on top of the router. Routing logic lives in router.py; this file only serves it.

Run: uvicorn zenai.api:app --reload    then open http://127.0.0.1:8000
"""
import csv
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from .config import DATA, ROOT
from .providers import ProviderError, QuotaError
from .router import Router

STATIC = ROOT / "static"
# Sample messages shown in the demo: dev set only, never test data (CLAUDE.md).
SAMPLE_IDS = ["D026", "D031", "D017", "D024"]


class RouteRequest(BaseModel):
    message: str = Field(min_length=1, max_length=1000)


def create_app(router: Router | None = None) -> FastAPI:
    """Build the app. The router (and its example embeddings) is created at startup unless injected."""
    state = {"router": router}

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if state["router"] is None:
            state["router"] = Router()
        yield

    app = FastAPI(title="ZEN AI Router demo", lifespan=lifespan)

    @app.get("/", include_in_schema=False)
    def index():
        return FileResponse(STATIC / "index.html")

    @app.get("/health")
    def health() -> dict:
        r = state["router"]
        th = r.cfg["thresholds"]
        return {"status": "ok", "model": r.provider.chat_model, "embed_model": r.provider.embed_model,
                "thresholds": {k: th.get(k) for k in ("t_high", "t_low", "frozen", "tuned_on")},
                "confidence_weights": r.cfg["confidence"], "knn_k": r.knn.k}

    @app.get("/samples")
    def samples() -> list[dict]:
        with open(DATA / "dev_set.csv", encoding="utf-8-sig", newline="") as f:
            dev = {row["id"]: row["question"] for row in csv.DictReader(f)}
        return [{"id": i, "question": dev[i]} for i in SAMPLE_IDS]

    @app.post("/route")
    def route(req: RouteRequest) -> dict:
        """RouteResult JSON, plus example_texts: the text of every nearest example shown in the result."""
        message = req.message.strip()
        if not message:
            raise HTTPException(422, "message is empty")
        r = state["router"]
        try:
            result = r.route(message)
        except QuotaError as e:
            raise HTTPException(429, str(e))
        except ProviderError as e:
            raise HTTPException(502, str(e))
        texts = {e["id"]: e["text"] for e in r.knn.examples}
        neighbour_ids = {n.id for t in result.topics for n in t.neighbours}
        return {**result.model_dump(), "example_texts": {i: texts[i] for i in sorted(neighbour_ids)}}

    return app


app = create_app()
