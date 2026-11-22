"""The Chunk and SearchResult shapes shared by both retrieval backends.

A Chunk keeps everything needed to cite it. The Azure AI Search index has no field for page, heading path,
last_updated or provenance, and its schema must not change, so `to_azure_doc` writes those into the first line of
`content` (a `ZENAI-META {...}` line) and `from_azure_doc` reads them back. The local backend stores the fields as is.
"""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field

META_PREFIX = "ZENAI-META "
PROVENANCES = ("public", "office-provided", "team-written", "unverified")  # unverified: source not confirmed
TEAM_COMPILED_LABEL = "team-compiled"
DATE_KINDS = ("updated", "fetched_on")
HEADING_SEP = " > "


@dataclass(frozen=True)
class Chunk:
    id: str
    department: str  # the kb/ folder name, for example HOSTEL
    title: str
    source_url: str  # for a team-written document: what it was compiled from (not a URL)
    content: str
    last_updated: str | None = None  # YYYY-MM-DD; None only for office-provided documents that state none
    page: int | None = None  # PDF page, 1-based
    heading_path: str = ""  # for example "Fee Structure > B.Tech CSE > Hostel Fees"
    provenance: str = "public"  # public | office-provided | team-written | unverified
    file: str = ""  # path inside kb/<department>/
    course: str | None = None  # COURSE_SPECIFIC documents
    date_kind: str = "updated"  # updated | fetched_on

    # ---- text used for embedding and keyword search ----

    def search_text(self) -> str:
        """Title, heading path and body: what is embedded and what BM25 reads. Matches what Azure indexes
        (title field plus the content field, whose first line carries the heading path)."""
        return "\n".join(p for p in (self.title, self.heading_path, self.content) if p)

    # ---- citations ----

    @property
    def team_compiled(self) -> bool:
        return self.provenance == "team-written"

    def citation_label(self) -> str:
        """For example `Fee structure, p. 3`; a team-written document always carries the team-compiled label."""
        label = self.title + (f", p. {self.page}" if self.page else "")
        return f"{label} [{TEAM_COMPILED_LABEL}]" if self.team_compiled else label

    def citation(self, n: int, snippet_chars: int = 200) -> dict:
        """The citation object of docs/API.md for this chunk."""
        from zenai.offices import handoff_office

        snippet = re.sub(r"\s+", " ", self.content).strip()
        if len(snippet) > snippet_chars:
            snippet = snippet[:snippet_chars].rstrip() + "..."
        return {"n": n, "title": self.title, "source_url": self.source_url, "last_updated": self.last_updated,
                "snippet": snippet, "office": handoff_office(self.department), "page": self.page,
                "heading": self.heading_path or None, "provenance": self.provenance,
                "team_compiled": self.team_compiled, "date_kind": self.date_kind, "label": self.citation_label()}

    # ---- storage ----

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Chunk":
        return cls(**{k: d[k] for k in cls.__dataclass_fields__ if k in d})

    def meta_header(self) -> str:
        meta = {"f": self.file, "p": self.page, "h": self.heading_path or None, "u": self.last_updated,
                "k": self.date_kind if self.date_kind != "updated" else None, "v": self.provenance,
                "c": self.course}
        return META_PREFIX + json.dumps({k: v for k, v in meta.items() if v not in (None, "")},
                                        ensure_ascii=False, separators=(",", ":"))

    def to_azure_doc(self, vector: list[float], vector_field: str = "content_vector") -> dict:
        """The document uploaded to the existing zenai-kb index: only its six fields."""
        return {"id": self.id, "content": self.meta_header() + "\n\n" + self.content, "department": self.department,
                "title": self.title, "source_url": self.source_url, vector_field: vector}

    @classmethod
    def from_azure_doc(cls, row: dict) -> "Chunk":
        content = row.get("content") or ""
        meta: dict = {}
        if content.startswith(META_PREFIX):
            head, _, rest = content.partition("\n")
            try:
                meta = json.loads(head[len(META_PREFIX):])
                content = rest.lstrip("\n")
            except json.JSONDecodeError:
                meta = {}
        return cls(id=row["id"], department=row.get("department") or "", title=row.get("title") or "",
                   source_url=row.get("source_url") or "", content=content, last_updated=meta.get("u"),
                   page=meta.get("p"), heading_path=meta.get("h") or "", provenance=meta.get("v") or "public",
                   file=meta.get("f") or "", course=meta.get("c"), date_kind=meta.get("k") or "updated")


@dataclass
class SearchResult:
    """One retrieved chunk. All three scores are on 0..1 (see docs/RETRIEVAL.md):
    score: reciprocal rank fusion of the keyword and vector rankings, divided by its maximum, so 1.0 means first in
        every ranking. It orders results; it is relative to this query's candidates.
    vector_score: (1 + cosine similarity) / 2 of the chunk and the query embedding. The only absolute relevance
        signal; None when the query could not be embedded.
    keyword_score: BM25 score divided by the best BM25 score among the candidates; None if no keyword hit."""
    chunk: Chunk
    score: float
    vector_score: float | None = None
    keyword_score: float | None = None
    mode: str = "hybrid"  # hybrid | keyword-only
    extra: dict = field(default_factory=dict)
