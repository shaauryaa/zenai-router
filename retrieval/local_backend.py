"""Local backend: BM25 (rank_bm25) plus numpy vectors, stored under .cache/kb_local/. No service needed to search it.

Files: chunks.jsonl (one Chunk per line), vectors.npy (float32, same order), meta.json (embedding model and size).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np

from .backend import Backend, BackendError, Candidate
from .model import Chunk

TOKEN_RE = re.compile(r"\w+", re.UNICODE)
DOTTED_ABBREVIATION_RE = re.compile(r"(?<=[^\W\d_])\.(?=[^\W\d_])")


def tokenize(text: str) -> list[str]:
    """Lower-case words. Dots inside an abbreviation are dropped (`B.Tech` and `BTech` both give `btech`) and a trailing
    plural `s` is removed (`fees` matches `fee`). No other stemming, so Hinglish words are matched as written."""
    out = []
    for w in TOKEN_RE.findall(DOTTED_ABBREVIATION_RE.sub("", text.lower())):
        if len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
            w = w[:-1]
        out.append(w)
    return out


class LocalBackend(Backend):
    name = "local"

    def __init__(self, directory: Path, embed_model: str = "", dim: int | None = None):
        self.dir = Path(directory)
        self.embed_model, self.dim = embed_model, dim
        self._chunks: list[Chunk] | None = None
        self._matrix: np.ndarray | None = None
        self._bm25 = None

    # ---- persistence ----

    def _load(self) -> None:
        if self._chunks is not None:
            return
        chunks_path, vec_path = self.dir / "chunks.jsonl", self.dir / "vectors.npy"
        if not chunks_path.exists() or not vec_path.exists():
            self._chunks, self._matrix = [], np.zeros((0, self.dim or 0), dtype=np.float32)
            return
        with open(chunks_path, encoding="utf-8") as f:
            self._chunks = [Chunk.from_dict(json.loads(line)) for line in f if line.strip()]
        self._matrix = np.load(vec_path)
        if len(self._chunks) != len(self._matrix):
            raise BackendError(f"{self.dir} is damaged: {len(self._chunks)} chunks but {len(self._matrix)} vectors; "
                               "run `python -m retrieval.ingest --rebuild`")

    def _save(self) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        with open(self.dir / "chunks.jsonl", "w", encoding="utf-8") as f:
            for c in self._chunks:
                f.write(json.dumps(c.to_dict(), ensure_ascii=False) + "\n")
        np.save(self.dir / "vectors.npy", self._matrix)
        (self.dir / "meta.json").write_text(json.dumps(
            {"embed_model": self.embed_model, "dim": self.dim, "chunks": len(self._chunks)}, indent=1),
            encoding="utf-8")
        self._bm25 = None

    # ---- Backend ----

    def upsert(self, chunks: list[Chunk], vectors: list[list[float]]) -> int:
        self._load()
        if len(chunks) != len(vectors):
            raise BackendError("chunks and vectors differ in length")
        new = np.asarray(vectors, dtype=np.float32).reshape(len(chunks), -1)
        if self.dim is None and len(new):
            self.dim = new.shape[1]
        if len(new) and len(self._matrix) and new.shape[1] != self._matrix.shape[1]:
            raise BackendError(f"vectors have {new.shape[1]} dimensions but the store has {self._matrix.shape[1]}")
        ids = {c.id for c in chunks}
        keep = [i for i, c in enumerate(self._chunks) if c.id not in ids]
        base = self._matrix[keep] if len(self._matrix) else self._matrix
        self._chunks = [self._chunks[i] for i in keep] + list(chunks)
        self._matrix = np.vstack([base, new]) if len(base) else new
        self._save()
        return len(chunks)

    def delete(self, ids: list[str]) -> int:
        self._load()
        gone = set(ids)
        keep = [i for i, c in enumerate(self._chunks) if c.id not in gone]
        self._chunks = [self._chunks[i] for i in keep]
        self._matrix = self._matrix[keep]
        self._save()
        return len(gone)

    def list_ids(self) -> list[str]:
        self._load()
        return [c.id for c in self._chunks]

    def stats(self) -> dict:
        self._load()
        size = sum(p.stat().st_size for p in self.dir.glob("*") if p.is_file()) if self.dir.exists() else 0
        return {"documents": len(self._chunks), "storage_bytes": size}

    def _mask(self, departments: list[str] | None) -> np.ndarray:
        if departments is None:
            return np.ones(len(self._chunks), dtype=bool)
        allowed = set(departments)
        return np.array([c.department in allowed for c in self._chunks], dtype=bool)

    def keyword(self, query: str, departments: list[str] | None, n: int) -> list[Candidate]:
        self._load()
        tokens = tokenize(query)
        if not self._chunks or not tokens:
            return []
        if self._bm25 is None:
            from rank_bm25 import BM25Okapi

            self._bm25 = BM25Okapi([tokenize(c.search_text()) for c in self._chunks])
        scores = np.asarray(self._bm25.get_scores(tokens), dtype=float)
        scores[~self._mask(departments)] = 0.0
        order = [i for i in np.argsort(-scores, kind="stable") if scores[i] > 0][:n]
        return [(self._chunks[i], float(scores[i])) for i in order]

    def vector(self, vector: list[float], departments: list[str] | None, n: int) -> list[Candidate]:
        self._load()
        if not self._chunks:
            return []
        q = np.asarray(vector, dtype=np.float32)
        if q.shape[0] != self._matrix.shape[1]:
            raise BackendError(f"query vector has {q.shape[0]} dimensions but the store has {self._matrix.shape[1]}")
        norms = np.linalg.norm(self._matrix, axis=1)
        sims = (self._matrix @ q) / (np.where(norms == 0, 1, norms) * (np.linalg.norm(q) or 1))
        sims[~self._mask(departments)] = -np.inf
        order = [i for i in np.argsort(-sims, kind="stable") if np.isfinite(sims[i])][:n]
        return [(self._chunks[i], float((1 + sims[i]) / 2)) for i in order]
