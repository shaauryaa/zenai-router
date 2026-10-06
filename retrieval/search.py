"""Hybrid search over the knowledge base, the same for both backends.

    search("hostel curfew kab hai", departments=["HOSTEL"], k=8)

1. The backend returns up to `candidates` chunks by keyword (BM25) and up to `candidates` by vector similarity,
   both restricted to the requested departments.
2. The two rankings are fused with reciprocal rank fusion: a chunk at rank r in a list gains 1 / (rrf_k + r).
3. Scores are put on 0..1 (see SearchResult): `score` is the fused value divided by its maximum, `vector_score` is
   (1 + cosine) / 2 and `keyword_score` is BM25 divided by the best BM25 candidate.

If the query cannot be embedded (no network, no Azure key) the vector ranking is skipped and the result is
keyword-only (`mode == "keyword-only"`), so the local backend still works offline.
"""
from __future__ import annotations

import os
import re

import openai

from zenai.config import ROOT, load_config
from zenai.providers import ProviderError

from .azure_backend import AzureBackend
from .backend import Backend, Candidate
from .embedding import kb_embed_dim, kb_provider
from .kb import kb_folders
from .local_backend import LocalBackend
from .model import SearchResult

_embedders: dict = {}


def retriever_name(cfg: dict) -> str:
    name = (os.environ.get("RETRIEVER") or cfg["kb"]["retriever"]).strip().lower()
    if name not in ("azure", "local"):
        raise ValueError(f"RETRIEVER must be azure or local, not {name!r}")
    return name


def get_backend(cfg: dict, name: str | None = None) -> Backend:
    name = name or retriever_name(cfg)
    if name == "local":
        return LocalBackend(ROOT / cfg["kb"]["local_dir"], cfg["providers"]["azure"]["embed_model"],
                            kb_embed_dim(cfg))
    if name == "azure":
        return AzureBackend(cfg["kb"]["azure_search"], kb_embed_dim(cfg))
    raise ValueError(f"unknown backend {name!r}")


def validate_departments(departments: list[str] | None) -> list[str] | None:
    """Department names are the kb folder names. None means all of them."""
    if departments is None:
        return None
    valid = kb_folders()
    bad = [d for d in departments if d not in valid]
    if bad:
        raise ValueError(f"unknown department(s) {', '.join(bad)}; valid: {', '.join(valid)}")
    return list(dict.fromkeys(departments))


def fuse(keyword: list[Candidate], vector: list[Candidate] | None, k: int, rrf_k: int = 60) -> list[SearchResult]:
    """Reciprocal rank fusion of a keyword and an optional vector ranking, best first, at most k results."""
    rankings = [("keyword", keyword)] + ([("vector", vector)] if vector is not None else [])
    rrf: dict[str, float] = {}
    chunks, vec_score, kw_score = {}, {}, {}
    best_kw = max((s for _, s in keyword), default=0.0)
    for name, ranking in rankings:
        for rank, (chunk, score) in enumerate(ranking, 1):
            rrf[chunk.id] = rrf.get(chunk.id, 0.0) + 1.0 / (rrf_k + rank)
            chunks[chunk.id] = chunk
            if name == "vector":
                vec_score[chunk.id] = score
            else:
                kw_score[chunk.id] = score / best_kw if best_kw > 0 else 0.0
    top = len(rankings) / (rrf_k + 1)  # a chunk ranked first in every ranking
    mode = "hybrid" if vector is not None else "keyword-only"
    results = [SearchResult(chunks[i], rrf[i] / top, vec_score.get(i), kw_score.get(i), mode) for i in rrf]
    results.sort(key=lambda r: (-r.score, -(r.vector_score or 0.0), r.chunk.id))
    return results[:k]


def expand_query(query: str, aliases: dict | None) -> str:
    """Keyword form of the query: abbreviations listed in config kb.search.aliases get their long form appended
    (`cse` adds `computer science engineering`), because a fee table says "Computer Science Engineering" while students
    write "CSE". Only the keyword search sees this; the vector search embeds the query as typed."""
    words = {w.lower() for w in re.findall(r"\w+", query)}
    extra = [long for short, long in (aliases or {}).items() if short.lower() in words]
    return " ".join([query, *extra])


def default_embedder(cfg: dict):
    if "kb" not in _embedders:
        _embedders["kb"] = kb_provider(cfg)
    return _embedders["kb"]


def search(query: str, departments: list[str] | None = None, k: int | None = None, *, backend: Backend | None = None,
           embedder=None, cfg: dict | None = None) -> list[SearchResult]:
    """Hybrid search. `departments` are kb folder names (None = all). Returns at most k results."""
    cfg = cfg or load_config()
    departments = validate_departments(departments)
    if not query.strip() or departments == []:
        return []
    s = cfg["kb"]["search"]
    k = k or s["default_k"]
    backend = backend or get_backend(cfg)
    keyword = backend.keyword(expand_query(query, s.get("aliases")), departments, s["candidates"])
    vector = None
    try:
        embedder = embedder or default_embedder(cfg)
        [query_vector] = embedder.embed([query])
        vector = backend.vector(query_vector, departments, s["candidates"])
    except (ProviderError, openai.OpenAIError):
        pass  # keyword-only
    return fuse(keyword, vector, k, s["rrf_k"])
