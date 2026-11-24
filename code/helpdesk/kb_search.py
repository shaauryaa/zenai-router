"""BM25 search over the helpdesk knowledge base: every code/kb/<OFFICE>/*.md except INDEX.md.

Each document is split at its "## Page N" headings; a page longer than MAX_WORDS is split further at blank lines
(paragraphs), and a single paragraph longer than MAX_WORDS into MAX_WORDS-word windows. A document without page
headings (an original .md) is chunked the same way with page = None. Every chunk keeps the document's title, office,
page, source_url and date. Tokens are lowercased runs of letters and digits minus STOP_WORDS (English and Hinglish
fillers); scoring is rank_bm25's BM25Okapi. search_for_route() mixes in results for a v1 router domain.

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
RRF_K = 60  # reciprocal rank fusion constant (search_dual_prog)
INDEX_VERSION = 2  # bump when chunking or tokenising changes, so old caches are ignored
PAGE_HEADING = re.compile(r"^## Page (\d+)[ \t]*$", re.M)
TOKEN = re.compile(r"[a-z0-9]+")

# Dropped from documents and queries before BM25 scoring: a standard English list plus common Hinglish fillers.
STOP_WORDS = frozenset("""
a about above after again against all am an and any are as at be because been before being below between both but
by can could did do does doing down during each few for from further had has have having he her here hers herself
him himself his how i if in into is it its itself just me more most my myself no nor not now of off on once only or
other our ours ourselves out over own same she should so some such than that the their theirs them themselves then
there these they this those through to too under until up very was we were what when where which while who whom
why will with would you your yours yourself yourselves
kya hai hain kaise kab kahan mujhe mera meri ka ki ke ko se me mein aur nahi karna karne kar ho hota raha rahi pls plz
""".split())

# router domain -> knowledge folders searched first. STUDENT_SUPPORT is a router P1 v2 domain only (the v1 router
# never returns it, so v1 behaviour is unchanged).
DOMAIN_OFFICES = {"FEES": ("FINANCE",), "ACADEMICS": ("COURSE_SPECIFIC",), "IT": ("IT",), "HOSTEL": ("HOSTEL",),
                  "CAMPUS_SERVICES": ("CAMPUS_SERVICES",), "STUDENT_SUPPORT": ("STUDENT_SUPPORT",)}


# Programme mentions -> COURSE_SPECIFIC files (Milestone 2 sprint S1), from the titles in test-data/kb_manifest.csv.
# Plain regex on the lowercased question + search_query. A text can name several programmes: their files are joined.
_CS = "COURSE_SPECIFIC/"
LLB_COMBO = re.compile(r"\b(?:bba|ba)\b[\s.,/&()-]*(?:\(?hons\.?\)?[\s.,/&-]*)?ll\.?\s?b\b")  # "BBA LLB", "BA LL.B"
PROGRAMMES: list[tuple[str, re.Pattern, tuple[str, ...]]] = [
    # "Rules and Regulations for Undergraduate/Integrated Programs: BBA LLB (Hons)/BA LLB (Hons)"
    ("BBA LLB / BA LLB (SOL)", re.compile(r"\bll\.?\s?b\b|\bschool of law\b|\bsol\b"), (_CS + "sol-academic-handbook.md",)),
    # "Rules and Regulations for Bachelor of Business Administration (BBA) Program" (BBA LLB removed first)
    ("BBA", re.compile(r"\bbba\b|bachelor of business administration"), (_CS + "bba-rules.md",)),
    # "Academic Rules Master of Business Administration (MBA)"
    ("MBA", re.compile(r"\bmba\b|master of business administration"), (_CS + "mba-rules.md",)),
    # "Rules and Regulations for Undergraduate BA (Journalism & Mass Communication)"
    ("BAJMC", re.compile(r"\bba\s*\(?\s*jmc\b|\bbajmc\b|\bjmc\b|journalism|mass comm"), (_CS + "bajmc-rules.md",)),
    # "Rules and Regulations for Undergraduate BA Liberal Arts"
    ("BA Liberal Arts", re.compile(r"liberal arts"), (_CS + "ba-liberal-arts-rulebook.md",)),
    # "Ordinances, Rules and Regulations for Post Graduate Programs: Engineering (M.Tech)"
    ("M.Tech", re.compile(r"\bm\.?\s?tech\b|master of technology"), (_CS + "mtech-ordinances-rules.md",)),
    # "Ordinances, Rules and Regulations for Under Graduate Programs: Engineering (B.Tech)" (SEAS)
    ("B.Tech (SEAS)", re.compile(r"\bb\.?\s?tech\b|\bseas\b|bachelor of technology"),
     (_CS + "seas-btech-ordinances-rules.md",)),
]
# "SCSET Academic Rules for Undergraduate Programs" / "SCSET Academic Rules for Master's Programme" (PG / dual)
SCSET = re.compile(r"\bscset\b|\bcse\b|computer science")
SCSET_PG_CUE = re.compile(r"\bmasters?\b|master['’]s|\bpg\b|post\s?-?graduate|\bdual\b|\bm\.?\s?tech\b")
SCSET_UG_FILE, SCSET_PG_FILE = _CS + "scset-academic-rules-ug.md", _CS + "scset-academic-rules-pg-dual.md"


def programme_files(*texts: str) -> list[str]:
    """COURSE_SPECIFIC files of every programme named in the texts (case-insensitive); [] when none is named.
    CSE or SCSET -> SCSET UG, or SCSET PG/dual when master's, PG, dual or M.Tech is also said."""
    t = " ".join(x for x in texts if x).lower()
    files: list[str] = []
    for _, pattern, fs in PROGRAMMES:
        text = t if fs[0].endswith("sol-academic-handbook.md") else LLB_COMBO.sub(" ", t)
        if pattern.search(text):
            files += [f for f in fs if f not in files]
    if SCSET.search(t):
        f = SCSET_PG_FILE if SCSET_PG_CUE.search(t) else SCSET_UG_FILE
        if f not in files:
            files.append(f)
    return files


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
    """Lowercased runs of letters and digits, without STOP_WORDS."""
    return [t for t in TOKEN.findall(text.lower()) if t not in STOP_WORDS]


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

    def _ranked(self, query: str) -> list[tuple[float, int]]:
        """(score, chunk index) for every chunk with score > 0, best first."""
        q = tokenize(query)
        if not q:
            return []
        return sorted(((float(s), i) for i, s in enumerate(self.bm25.get_scores(q)) if s > 0), reverse=True)

    def search(self, query: str, k: int = 5, office: str | None = None) -> list[Hit]:
        """Top k chunks by BM25 score (score > 0 only), optionally only from one office's folder."""
        ranked = [(s, i) for s, i in self._ranked(query) if office is None or self.chunks[i].office == office]
        return [Hit(self.chunks[i], round(s, 4)) for s, i in ranked[:k]]

    def search_for_route(self, query: str, v1_domain: str | None, k: int = 5) -> list[Hit]:
        """Search guided by the v1 router's domain: the top 3 chunks from the domain's folder(s) plus the best
        remaining chunks from all folders (2 when k=5), sorted by score. All folders stay reachable, so documents
        with no v1 domain (STUDENT_SUPPORT: anti-ragging, POSH) can still be found. OUT_OF_SCOPE or None searches
        all folders."""
        if v1_domain is None or v1_domain == "OUT_OF_SCOPE":
            return self.search(query, k=k)
        if v1_domain not in DOMAIN_OFFICES:
            raise ValueError(f"unknown v1 domain {v1_domain!r}")
        ranked = self._ranked(query)
        routed = [x for x in ranked if self.chunks[x[1]].office in DOMAIN_OFFICES[v1_domain]][:min(3, k)]
        others = [x for x in ranked if x not in routed][:k - len(routed)]
        return [Hit(self.chunks[i], round(s, 4)) for s, i in sorted(routed + others, reverse=True)]

    def search_routed_plus_all(self, query: str, domain: str | None, routed_k: int = 5,
                               all_k: int = 3) -> list[Hit]:
        """Milestone 2 step 3: the top routed_k chunks from the domain's folder(s) plus the top all_k of the remaining
        chunks from all folders (k = 8 by default), sorted by score. OUT_OF_SCOPE or None searches all folders for
        routed_k + all_k chunks."""
        if domain is None or domain == "OUT_OF_SCOPE":
            return self.search(query, k=routed_k + all_k)
        if domain not in DOMAIN_OFFICES:
            raise ValueError(f"unknown router domain {domain!r}")
        return self._routed_plus_all(query, lambda c: c.office in DOMAIN_OFFICES[domain], routed_k, all_k)

    def _routed_plus_all(self, query: str, in_routed, routed_k: int, all_k: int) -> list[Hit]:
        ranked = self._ranked(query)
        routed = [x for x in ranked if in_routed(self.chunks[x[1]])][:routed_k]
        others = [x for x in ranked if x not in routed][:all_k]
        return [Hit(self.chunks[i], round(s, 4)) for s, i in sorted(routed + others, reverse=True)]

    def search_routed_plus_all_prog(self, query: str, domain: str | None, question: str = "", routed_k: int = 5,
                                    all_k: int = 3) -> list[Hit]:
        """Programme-aware search_routed_plus_all (Milestone 2 sprint S1): when the domain is ACADEMICS and the
        question or the query names a programme (programme_files), the routed part searches only that programme's
        file(s); the all-folders part is unchanged. Otherwise exactly search_routed_plus_all."""
        files = programme_files(question, query) if domain == "ACADEMICS" else []
        if not files:
            return self.search_routed_plus_all(query, domain, routed_k=routed_k, all_k=all_k)
        return self._routed_plus_all(query, lambda c: c.file in files, routed_k, all_k)

    def _fused(self, queries: list[str]) -> list[tuple[float, int]]:
        """Reciprocal rank fusion of the BM25 rankings of several queries: each chunk scores the sum over queries of
        1 / (RRF_K + rank), rank 1 = best, counting only chunks with BM25 score > 0. Queries with the same tokens
        count once. (score, chunk index), best first."""
        scores: dict[int, float] = {}
        seen: set[tuple[str, ...]] = set()
        for q in queries:
            key = tuple(tokenize(q or ""))
            if not key or key in seen:
                continue
            seen.add(key)
            for rank, (_, i) in enumerate(self._ranked(q), 1):
                scores[i] = scores.get(i, 0.0) + 1.0 / (RRF_K + rank)
        return sorted(((s, i) for i, s in scores.items()), reverse=True)

    def search_dual_prog(self, query: str, topic_text: str, domain: str | None, question: str = "",
                         routed_k: int = 5, all_k: int = 3) -> list[Hit]:
        """Dual-query search (Milestone 2 sprint S4): the router's search_query AND the topic's own text, merged by
        reciprocal rank fusion (_fused), then the same split as search_routed_plus_all_prog: top routed_k from the
        routed folder(s) (only the named programme's file(s) for an ACADEMICS question naming one, programme_files on
        `question` and `query` as before) + top all_k of the rest; OUT_OF_SCOPE or None takes the top
        routed_k + all_k from all folders. Hit.score is the fused score."""
        ranked = self._fused([query, topic_text])
        if domain is None or domain == "OUT_OF_SCOPE":
            return [Hit(self.chunks[i], round(s, 6)) for s, i in ranked[:routed_k + all_k]]
        if domain not in DOMAIN_OFFICES:
            raise ValueError(f"unknown router domain {domain!r}")
        files = programme_files(question, query) if domain == "ACADEMICS" else []
        in_routed = (lambda c: c.file in files) if files else (lambda c: c.office in DOMAIN_OFFICES[domain])
        routed = [x for x in ranked if in_routed(self.chunks[x[1]])][:routed_k]
        others = [x for x in ranked if x not in routed][:all_k]
        return [Hit(self.chunks[i], round(s, 6)) for s, i in sorted(routed + others, reverse=True)]


_DEFAULT: KBIndex | None = None


def default_index() -> KBIndex:
    """The index for code/kb/, loaded once per process (from the cache when it is current)."""
    global _DEFAULT
    if _DEFAULT is None:
        _DEFAULT = KBIndex.load()
    return _DEFAULT


def search(query: str, k: int = 5, office: str | None = None) -> list[Hit]:
    return default_index().search(query, k=k, office=office)


def search_for_route(query: str, v1_domain: str | None, k: int = 5) -> list[Hit]:
    return default_index().search_for_route(query, v1_domain, k=k)


def search_routed_plus_all(query: str, domain: str | None, routed_k: int = 5, all_k: int = 3) -> list[Hit]:
    return default_index().search_routed_plus_all(query, domain, routed_k=routed_k, all_k=all_k)


def search_routed_plus_all_prog(query: str, domain: str | None, question: str = "", routed_k: int = 5,
                                all_k: int = 3) -> list[Hit]:
    return default_index().search_routed_plus_all_prog(query, domain, question, routed_k=routed_k, all_k=all_k)


def search_dual_prog(query: str, topic_text: str, domain: str | None, question: str = "", routed_k: int = 5,
                     all_k: int = 3) -> list[Hit]:
    return default_index().search_dual_prog(query, topic_text, domain, question, routed_k=routed_k, all_k=all_k)


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
