"""BM25 search over the helpdesk knowledge base: every code/kb/<OFFICE>/*.md except INDEX.md.

Each document is split at its "## Page N" headings; a page longer than MAX_WORDS is split further at blank lines
(paragraphs), and a single paragraph longer than MAX_WORDS into MAX_WORDS-word windows. A document without page
headings (an original .md) is chunked the same way with page = None. Every chunk keeps the document's title, office,
page, source_url and date. Tokens are lowercased runs of letters and digits; scoring is rank_bm25's BM25Okapi.

The chunks and their tokens are cached in code/.cache/kb_search/ (git-ignored), keyed by a hash of every kb file, so
the index is rebuilt only when the knowledge base changes.

CLI (from code/):  python -m helpdesk.kb_search "hostel in-time" --office HOSTEL --k 4
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

import yaml
from rank_bm25 import BM25Okapi

from zenai.paths import KB, KB_SEARCH_CACHE

MAX_WORDS = 350
INDEX_VERSION = 1  # bump when chunking or tokenising changes, so old caches are ignored
PAGE_HEADING = re.compile(r"^## Page (\d+)[ \t]*$", re.M)
TOKEN = re.compile(r"[a-z0-9]+")


@dataclass(frozen=True)
class Chunk:
    id: str
    office: str
    file: str  # path inside kb/, e.g. FINANCE/fee-refund-policy-2026-27.md
    title: str
    page: int | None
    source_url: str
    date: str
    text: str


@dataclass(frozen=True)
class Hit:
    chunk: Chunk
    score: float


def tokenize(text: str) -> list[str]:
    return TOKEN.findall(text.lower())


def kb_files(kb: Path = KB) -> list[Path]:
    return sorted(p for p in kb.glob("*/*.md") if p.name != "INDEX.md")


def read_document(path: Path) -> tuple[dict, str]:
    """(front matter, body) of a kb file."""
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text
    return yaml.safe_load(text[3:end]) or {}, text[end + 4:].lstrip("\n")


def split_pages(body: str) -> list[tuple[int | None, str]]:
    """[(page, text)] from "## Page N" headings; text before the first heading (or a body without any) has page None."""
    parts = PAGE_HEADING.split(body)
    pages = [(None, parts[0])] if parts[0].strip() else []
    pages += [(int(parts[i]), parts[i + 1]) for i in range(1, len(parts) - 1, 2)]
    return [(p, t.strip()) for p, t in pages if t.strip()]


def split_text(text: str, max_words: int = MAX_WORDS) -> list[str]:
    """The text if it has at most max_words words, else paragraphs packed up to max_words (long ones windowed)."""
    if len(text.split()) <= max_words:
        return [text]
    pieces: list[str] = []
    for para in (p.strip() for p in re.split(r"\n\s*\n", text)):
        words = para.split()
        if len(words) <= max_words:
            if para:
                pieces.append(para)
        else:
            pieces += [" ".join(words[i:i + max_words]) for i in range(0, len(words), max_words)]
    chunks, cur, n = [], [], 0
    for piece in pieces:
        w = len(piece.split())
        if cur and n + w > max_words:
            chunks.append("\n\n".join(cur))
            cur, n = [], 0
        cur.append(piece)
        n += w
    if cur:
        chunks.append("\n\n".join(cur))
    return chunks


def build_chunks(kb: Path = KB) -> list[Chunk]:
    chunks = []
    for path in kb_files(kb):
        meta, body = read_document(path)
        office = str(meta.get("office") or path.parent.name)
        rel = f"{path.parent.name}/{path.name}"
        for page, text in split_pages(body):
            for n, piece in enumerate(split_text(text), 1):
                chunks.append(Chunk(id=f"{rel}#p{page if page is not None else 0}-{n}", office=office, file=rel,
                                    title=str(meta.get("title") or path.stem), page=page,
                                    source_url=str(meta.get("source_url") or ""), date=str(meta.get("date") or ""),
                                    text=piece))
    return chunks


def kb_fingerprint(kb: Path = KB) -> str:
    h = hashlib.sha256(f"v{INDEX_VERSION} max_words={MAX_WORDS}".encode())
    for path in kb_files(kb):
        h.update(path.relative_to(kb).as_posix().encode() + b"\0" + path.read_bytes() + b"\0")
    return h.hexdigest()


class KBIndex:
    def __init__(self, chunks: list[Chunk], tokens: list[list[str]]):
        self.chunks = chunks
        self.bm25 = BM25Okapi(tokens)

    @classmethod
    def load(cls, kb: Path = KB, cache_dir: Path | None = KB_SEARCH_CACHE, rebuild: bool = False) -> "KBIndex":
        """The index for the current kb/, from the cache when it matches, else built (and cached if cache_dir)."""
        key = kb_fingerprint(kb)
        cache = Path(cache_dir) / "index.json" if cache_dir else None
        if cache and cache.exists() and not rebuild:
            try:
                data = json.loads(cache.read_text(encoding="utf-8"))
                if data.get("key") == key:
                    return cls([Chunk(**c) for c in data["chunks"]], data["tokens"])
            except (ValueError, KeyError, TypeError):
                pass  # unreadable cache: rebuild it
        chunks = build_chunks(kb)
        tokens = [tokenize(f"{c.title}\n{c.text}") for c in chunks]
        if cache:
            cache.parent.mkdir(parents=True, exist_ok=True)
            tmp = cache.with_suffix(".tmp")
            tmp.write_text(json.dumps({"key": key, "chunks": [asdict(c) for c in chunks], "tokens": tokens},
                                      ensure_ascii=False), encoding="utf-8")
            tmp.replace(cache)
        return cls(chunks, tokens)

    def search(self, query: str, k: int = 5, office: str | None = None) -> list[Hit]:
        """Top k chunks by BM25 score (score > 0 only), optionally only from one office's folder."""
        q = tokenize(query)
        if not q:
            return []
        scores = self.bm25.get_scores(q)
        ranked = sorted(((float(s), i) for i, s in enumerate(scores)
                         if s > 0 and (office is None or self.chunks[i].office == office)), reverse=True)
        return [Hit(self.chunks[i], round(s, 4)) for s, i in ranked[:k]]


def search(query: str, k: int = 5, office: str | None = None) -> list[Hit]:
    return KBIndex.load().search(query, k=k, office=office)


def main(argv: list[str] | None = None) -> None:
    offices = sorted(p.name for p in KB.iterdir() if p.is_dir() and not p.name.startswith("."))
    ap = argparse.ArgumentParser(prog="python -m helpdesk.kb_search", description="BM25 search over code/kb/")
    ap.add_argument("query")
    ap.add_argument("--office", choices=offices, help="only search this office's folder")
    ap.add_argument("--k", type=int, default=5, help="number of hits (default 5)")
    ap.add_argument("--rebuild", action="store_true", help="ignore the cached index")
    args = ap.parse_args(argv)
    index = KBIndex.load(rebuild=args.rebuild)
    hits = index.search(args.query, k=args.k, office=args.office)
    print(f"{len(index.chunks)} chunks; query {args.query!r}" + (f" in {args.office}" if args.office else ""))
    if not hits:
        print("no matching chunks")
    for n, h in enumerate(hits, 1):
        c = h.chunk
        snippet = re.sub(r"\s+", " ", c.text).strip()[:200]
        page = c.page if c.page is not None else "-"
        print(f"\n{n}. {c.title}  [{c.office}]  page {page}  score {h.score:.2f}\n   {snippet}")


if __name__ == "__main__":
    main()
