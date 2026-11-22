"""Azure AI Search backend for the EXISTING index (default `zenai-kb`).

This module never creates, updates or deletes an index or its schema: it uploads, deletes and queries documents, and
reads the schema and statistics. Index fields used: id (key), content, department (filterable), title, source_url,
content_vector (1536-d HNSW). Page, heading path, last_updated and provenance have no field, so they travel in the
first line of `content` (see model.Chunk.to_azure_doc).
"""
from __future__ import annotations

import os
from typing import Any

from .backend import Backend, BackendError, Candidate, department_filter
from .model import Chunk

SELECT = ["id", "content", "department", "title", "source_url"]
REQUIRED_FIELDS = SELECT


def _clients(cfg: dict):
    from azure.core.credentials import AzureKeyCredential
    from azure.search.documents import SearchClient
    from azure.search.documents.indexes import SearchIndexClient

    endpoint, key = os.environ.get(cfg["endpoint_env"]), os.environ.get(cfg["key_env"])
    for name, value in ((cfg["endpoint_env"], endpoint), (cfg["key_env"], key)):
        if not value or value.startswith(("PASTE_", "your_")):
            raise BackendError(f"{name} is not set in .env")
    index = os.environ.get("SEARCH_INDEX") or cfg["index"]
    cred = AzureKeyCredential(key)
    return index, SearchClient(endpoint, index, cred), SearchIndexClient(endpoint, cred)


def _vector_query(vector: list[float], k: int, field: str):
    from azure.search.documents.models import VectorizedQuery

    return VectorizedQuery(vector=vector, k_nearest_neighbors=k, fields=field)


class AzureBackend(Backend):
    name = "azure"

    def __init__(self, cfg: dict, dim: int, client: Any = None, index_client: Any = None, index_name: str | None = None,
                 vector_query=_vector_query):
        self.cfg, self.dim = cfg, dim
        self.vector_field = cfg["vector_field"]
        self.batch = cfg.get("upload_batch", 100)
        if client is None or index_client is None:
            index_name, client, index_client = _clients(cfg)
        self.index_name = index_name or cfg["index"]
        self.client, self.index_client = client, index_client
        self.vector_query = vector_query

    def _call(self, what: str, fn):
        try:
            return fn()
        except BackendError:
            raise
        except Exception as e:  # azure.core errors; their text never contains the key
            raise BackendError(f"Azure AI Search {what} failed: {type(e).__name__}: {e}") from e

    def verify_schema(self) -> None:
        """Read-only check that the existing index has the six fields and a vector field of the right size."""
        index = self._call("schema read", lambda: self.index_client.get_index(self.index_name))
        fields = {f.name: f for f in index.fields}
        missing = [n for n in REQUIRED_FIELDS + [self.vector_field] if n not in fields]
        if missing:
            raise BackendError(f"index {self.index_name!r} has no field(s) {', '.join(missing)}. This project does "
                               "not change the index; fix the index in the Azure portal.")
        if not fields["id"].key:
            raise BackendError(f"index {self.index_name!r}: `id` is not the key field")
        dims = getattr(fields[self.vector_field], "vector_search_dimensions", None)
        if dims != self.dim:
            raise BackendError(f"index {self.index_name!r}: {self.vector_field} has {dims} dimensions but the KB "
                               f"embeddings have {self.dim}")
        if not fields["department"].filterable:
            raise BackendError(f"index {self.index_name!r}: `department` is not filterable")

    # ---- Backend ----

    def upsert(self, chunks: list[Chunk], vectors: list[list[float]]) -> int:
        stored = 0
        docs = [c.to_azure_doc(v, self.vector_field) for c, v in zip(chunks, vectors)]
        for start in range(0, len(docs), self.batch):
            batch = docs[start:start + self.batch]
            for r in self._call("upload", lambda: self.client.merge_or_upload_documents(documents=batch)):
                if not r.succeeded:
                    raise BackendError(f"Azure AI Search rejected document {r.key}: {getattr(r, 'error_message', '')}")
                stored += 1
        return stored

    def delete(self, ids: list[str]) -> int:
        for start in range(0, len(ids), self.batch * 5):
            batch = [{"id": i} for i in ids[start:start + self.batch * 5]]
            self._call("delete", lambda: self.client.delete_documents(documents=batch))
        return len(ids)

    def list_ids(self) -> list[str]:
        ids: list[str] = []
        while True:  # at most 1000 documents per request
            skip = len(ids)
            rows = self._call("listing", lambda: list(self.client.search(
                search_text="*", select=["id"], top=1000, skip=skip)))
            ids += [r["id"] for r in rows]
            if len(rows) < 1000:
                return ids

    def stats(self) -> dict:
        s = self._call("statistics", lambda: self.index_client.get_index_statistics(self.index_name))

        def stat(snake: str, camel: str) -> int:
            """The SDK result is a model object whose dict form uses camelCase keys; accept either spelling."""
            for get in (lambda: getattr(s, snake), lambda: s[snake], lambda: s[camel]):
                try:
                    value = get()
                except (AttributeError, KeyError, TypeError):
                    continue
                if value is not None:
                    return int(value)
            return 0

        # The document count comes from the documents API, which is current; storage statistics lag a few minutes.
        documents = self._call("document count", lambda: self.client.get_document_count())
        return {"documents": int(documents), "storage_bytes": stat("storage_size", "storageSize"),
                "vector_bytes": stat("vector_index_size", "vectorIndexSize")}

    def keyword(self, query: str, departments: list[str] | None, n: int) -> list[Candidate]:
        rows = self._call("keyword search", lambda: list(self.client.search(
            search_text=query, filter=department_filter(departments), select=SELECT, top=n)))
        return [(Chunk.from_azure_doc(r), float(r["@search.score"])) for r in rows]

    def vector(self, vector: list[float], departments: list[str] | None, n: int) -> list[Candidate]:
        from azure.search.documents.models import VectorFilterMode

        rows = self._call("vector search", lambda: list(self.client.search(
            search_text=None, vector_queries=[self.vector_query(vector, n, self.vector_field)],
            filter=department_filter(departments), select=SELECT, top=n,
            vector_filter_mode=VectorFilterMode.PRE_FILTER)))
        # For a cosine index Azure's score is already (1 + cosine) / 2.
        return [(Chunk.from_azure_doc(r), float(r["@search.score"])) for r in rows]


def estimate_bytes(chunks: list[Chunk], dim: int) -> int:
    """Approximate index storage the chunks need: their text fields plus 4 bytes per vector dimension. The HNSW graph
    adds overhead on top, so this is a lower bound; the 45 MB stop leaves room for it."""
    return sum(len(c.to_azure_doc([], "v")["content"].encode("utf-8")) + len(c.title.encode("utf-8"))
               + len(c.source_url.encode("utf-8")) + len(c.id) + len(c.department) + 4 * dim for c in chunks)
