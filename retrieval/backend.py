"""The interface both retrieval backends implement. search.py fuses what they return, so Azure and local rank the
same way and return the same Chunk objects."""
from __future__ import annotations

import re
from abc import ABC, abstractmethod

from .model import Chunk


class BackendError(RuntimeError):
    """A backend failed (bad credentials, schema mismatch, service error). Messages never contain secrets."""


Candidate = tuple[Chunk, float]


def department_filter(departments: list[str] | None) -> str | None:
    """OData filter for Azure AI Search, or None for all departments. Names are folder names (capital letters and
    underscores), checked here so nothing else can reach the filter string."""
    if departments is None:
        return None
    for d in departments:
        if not re.fullmatch(r"[A-Z_]+", d):
            raise ValueError(f"not a department name: {d!r}")
    return "search.in(department, '{}', ',')".format(",".join(departments))


class Backend(ABC):
    name: str

    @abstractmethod
    def upsert(self, chunks: list[Chunk], vectors: list[list[float]]) -> int:
        """Store chunks with their vectors, replacing chunks with the same id. Returns how many were stored."""

    @abstractmethod
    def delete(self, ids: list[str]) -> int:
        """Remove chunks by id. Returns how many ids were sent for removal."""

    @abstractmethod
    def list_ids(self) -> list[str]:
        """Every chunk id in the store."""

    @abstractmethod
    def stats(self) -> dict:
        """{'documents': int, 'storage_bytes': int} (approximate for Azure)."""

    @abstractmethod
    def keyword(self, query: str, departments: list[str] | None, n: int) -> list[Candidate]:
        """Up to n chunks matching the query words, best first, with a raw BM25 score (> 0)."""

    @abstractmethod
    def vector(self, vector: list[float], departments: list[str] | None, n: int) -> list[Candidate]:
        """Up to n chunks nearest to the vector, best first, with (1 + cosine similarity) / 2 as the score."""

    def clear(self) -> int:
        """Remove every chunk (documents only; an Azure index and its schema stay). Returns how many."""
        return self.delete(self.list_ids())
