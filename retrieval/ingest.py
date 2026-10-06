"""Ingest kb/ into the retrieval backends.

    python -m retrieval.ingest [--backend local|azure|both] [--rebuild] [--dry-run]

Steps: validate every kb/<FOLDER>/INDEX.md, extract and chunk the listed files, embed the chunks with the Azure `embed`
deployment (cached, batched), then write them to the backend(s). Validation errors stop the run before anything is
written. The default backend is RETRIEVER from .env (azure or local), else config.yaml kb.retriever.

Re-running is safe: chunk ids are stable, so chunks are replaced, and chunks that an edited file no longer produces
are deleted. --rebuild first removes every chunk from the backend (documents only: the Azure index and its schema
are never touched), then uploads. The local backend is a derived cache and can be rebuilt any time.
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field

from zenai.config import load_config
from zenai.providers import ProviderError

from .azure_backend import AzureBackend, estimate_bytes
from .backend import Backend, BackendError
from .chunking import id_prefix
from .embedding import kb_embed_dim, kb_provider
from .kb import Scan, scan_kb
from .search import get_backend, retriever_name

MB = 1024 * 1024


@dataclass
class BackendReport:
    name: str
    uploaded: int = 0
    stale_deleted: int = 0
    rebuild_deleted: int = 0
    foreign: int = 0  # chunks in the store that no file in the current KB produces
    before: dict = field(default_factory=dict)
    after: dict = field(default_factory=dict)
    estimate_bytes: int = 0
    blocked: str = ""  # why nothing was written, if so


@dataclass
class Report:
    scan: Scan
    backends: list[BackendReport] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.scan.ok and not any(b.blocked for b in self.backends)


def _write(backend: Backend, scan: Scan, vectors: list[list[float]], rebuild: bool, limit_mb: float | None,
           say) -> BackendReport:
    rep = BackendReport(backend.name)
    if isinstance(backend, AzureBackend):
        backend.verify_schema()  # read-only: the index must already exist with the agreed fields
    rep.before = backend.stats()
    rep.estimate_bytes = estimate_bytes(scan.chunks, kb_embed_dim_of(vectors)) if isinstance(backend, AzureBackend) \
        else 0
    if isinstance(backend, AzureBackend) and limit_mb:
        existing = 0 if rebuild else rep.before["storage_bytes"] + rep.before.get("vector_bytes", 0)
        if existing + rep.estimate_bytes > limit_mb * MB:
            rep.blocked = (f"stopped before uploading: about {(existing + rep.estimate_bytes) / MB:.1f} MB would be "
                           f"used, over the {limit_mb:g} MB limit (index holds {existing / MB:.1f} MB now)")
            return rep
    if rebuild:
        ids = backend.list_ids()
        say(f"[{backend.name}] REBUILD: deleting {len(ids)} existing chunk(s) from "
            f"{getattr(backend, 'index_name', 'the local store')} (the index and its schema are kept), then "
            f"uploading {len(scan.chunks)} chunk(s)")
        rep.rebuild_deleted = backend.clear()
    rep.uploaded = backend.upsert(scan.chunks, vectors)
    new_ids = {c.id for c in scan.chunks}
    prefixes = {id_prefix(d.folder, d.file) for d in scan.documents}
    existing_ids = backend.list_ids()
    stale = [i for i in existing_ids if i not in new_ids and any(i.startswith(p) for p in prefixes)]
    if stale:
        rep.stale_deleted = backend.delete(stale)
    rep.foreign = len([i for i in existing_ids if i not in new_ids and i not in set(stale)])
    rep.after = backend.stats()
    return rep


def kb_embed_dim_of(vectors: list[list[float]]) -> int:
    return len(vectors[0]) if vectors else 0


def ingest(cfg: dict, backends: list[Backend], *, rebuild: bool = False, dry_run: bool = False, embedder=None,
           scan: Scan | None = None, say=print) -> Report:
    """Validate, chunk, embed and write. `backends` may be empty (validation only). Returns a Report."""
    scan = scan or scan_kb(cfg)
    report = Report(scan)
    if not scan.ok or dry_run or not scan.chunks:
        return report
    embedder = embedder or kb_provider(cfg)
    vectors = embedder.embed([c.search_text() for c in scan.chunks])
    limit = cfg["kb"]["azure_search"].get("storage_limit_mb")
    for backend in backends:
        report.backends.append(_write(backend, scan, vectors, rebuild, limit, say))
    return report


def print_report(report: Report, dry_run: bool = False, say=print) -> None:
    scan = report.scan
    for w in scan.warnings:
        say(f"WARNING: {w}")
    for e in scan.errors:
        say(f"ERROR: {e}")
    say(f"documents ingested: {len(scan.documents)}")
    for d in scan.documents:
        say(f"  kb/{d.folder}/{d.file}: {d.chunks} chunk(s)  [{d.title}]")
    say(f"chunks created: {len(scan.chunks)}")
    say(f"files skipped: {len(scan.skipped)}")
    for s in scan.skipped:
        say(f"  {s}")
    if not scan.ok:
        say("validation failed: nothing was written")
        return
    if dry_run:
        say("dry run: nothing embedded or written")
    for b in report.backends:
        if b.blocked:
            say(f"[{b.name}] {b.blocked}")
            continue
        say(f"[{b.name}] chunks uploaded: {b.uploaded}; stale chunks deleted: {b.stale_deleted}"
            + (f"; removed by rebuild: {b.rebuild_deleted}" if b.rebuild_deleted else ""))
        if b.foreign:
            say(f"[{b.name}] {b.foreign} chunk(s) in the store belong to files not in the current KB; "
                "--rebuild removes them")
        after = b.after
        size = f"{after['storage_bytes'] / MB:.2f} MB" if after.get("storage_bytes") else "n/a yet"
        say(f"[{b.name}] store now: {after.get('documents')} chunk(s), about {size}"
            + (f" (this upload needs about {b.estimate_bytes / MB:.2f} MB; Azure statistics can lag a few minutes)"
               if b.name == "azure" else ""))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--backend", choices=["local", "azure", "both"],
                    help="where to write (default: RETRIEVER from .env, else config.yaml kb.retriever)")
    ap.add_argument("--rebuild", action="store_true", help="remove every chunk from the backend(s) first")
    ap.add_argument("--dry-run", action="store_true", help="validate and chunk only; embed and write nothing")
    args = ap.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")

    cfg = load_config()
    choice = args.backend or retriever_name(cfg)
    names = ["local", "azure"] if choice == "both" else [choice]
    try:
        backends = [] if args.dry_run else [get_backend(cfg, n) for n in names]
        report = ingest(cfg, backends, rebuild=args.rebuild, dry_run=args.dry_run)
    except (ProviderError, BackendError) as e:
        print(f"ingestion stopped: {e}")
        return 1
    print_report(report, args.dry_run)
    return 0 if report.ok else 1


if __name__ == "__main__":
    sys.exit(main())
