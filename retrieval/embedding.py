"""KB embeddings: always the Azure `embed` deployment (1536 dimensions) through the cached provider in
zenai/providers.py, whatever LLM_PROVIDER is. The router and kNN keep their own provider and vectors; Gemini vectors
and Azure KB vectors are never mixed."""
from __future__ import annotations

from zenai.providers import Provider, make_provider


def kb_embed_dim(cfg: dict) -> int:
    return cfg["providers"]["azure"]["embed_dim"]


def kb_provider(cfg: dict, **kwargs) -> Provider:
    """The Azure provider, with its embedding size verified once (one cached call)."""
    return make_provider({"provider": {"name": "azure", **cfg["providers"]["azure"]}}, **kwargs)
