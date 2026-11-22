"""Show what the knowledge base returns for a query.

    python -m retrieval.inspect "hostel curfew kab hai" --department HOSTEL
    python -m retrieval.inspect "BTech CSE fees kitni hai"          # all departments

Prints the top chunks with department, title, score, page and a 200-character snippet. The backend is RETRIEVER from
.env (azure or local), or choose with --backend.
"""
from __future__ import annotations

import argparse
import re
import sys

from zenai.config import load_config
from zenai.providers import ProviderError

from .backend import BackendError
from .search import get_backend, search

SNIPPET_CHARS = 200


def snippet(text: str, n: int = SNIPPET_CHARS) -> str:
    flat = re.sub(r"\s+", " ", text).strip()
    return flat if len(flat) <= n else flat[:n].rstrip() + "..."


def format_results(results) -> str:
    if not results:
        return "(no chunks found)"
    lines = []
    for n, r in enumerate(results, 1):
        c = r.chunk
        parts = [f"score {r.score:.3f}"]
        if r.vector_score is not None:
            parts.append(f"vector {r.vector_score:.3f}")
        if r.keyword_score is not None:
            parts.append(f"keyword {r.keyword_score:.3f}")
        lines.append(f"[{n}] {c.department}  {c.title}  ({', '.join(parts)})")
        lines.append(f"    page: {c.page if c.page else '-'}   heading: {c.heading_path or '-'}   "
                     f"citation: {c.citation_label()}")
        lines.append(f"    {snippet(c.content)}")
    if results[0].mode != "hybrid":
        lines.append(f"\nnote: {results[0].mode} (the query could not be embedded, so vector search was skipped)")
    return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("query")
    ap.add_argument("--department", action="append", metavar="FOLDER",
                    help="restrict to this kb folder (repeat for several); default: all")
    ap.add_argument("-k", type=int, help="number of chunks (default: config kb.search.default_k)")
    ap.add_argument("--backend", choices=["local", "azure"], help="default: RETRIEVER from .env")
    args = ap.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")

    cfg = load_config()
    try:
        results = search(args.query, args.department, args.k, backend=get_backend(cfg, args.backend), cfg=cfg)
    except (ProviderError, BackendError, ValueError) as e:
        print(f"error: {e}")
        return 1
    print(format_results(results))
    return 0


if __name__ == "__main__":
    sys.exit(main())
