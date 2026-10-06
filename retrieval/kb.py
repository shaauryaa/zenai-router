"""Scan kb/: validate every folder's INDEX.md, extract each listed file and chunk it. Nothing is written anywhere.

Warnings never stop a run: unknown folders, unlisted files, missing listed files, scanned PDFs, unreadable files.
Errors do (an entry without a title, source_url or last_updated, a missing INDEX.md for a folder with files):
the caller must not write anything to a backend while `errors` is not empty.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from zenai.config import ROOT
from zenai.offices import load_offices

from .chunking import chunk_sections
from .index_md import IndexError_, build_document, clean_relative_path, read_index
from .loaders import SUPPORTED, LoaderError, extract
from .model import Chunk

KB_ROOT = ROOT / "kb"


@dataclass
class DocReport:
    folder: str
    file: str
    title: str
    chunks: int


@dataclass
class Scan:
    chunks: list[Chunk] = field(default_factory=list)
    documents: list[DocReport] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)  # "kb/FOLDER/file: reason"
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def kb_folders() -> list[str]:
    """The valid knowledge folder names: the `folders` of config/offices.yaml."""
    return list(load_offices()["folders"])


def list_files(folder: Path) -> list[str]:
    """Every file under a kb folder (subfolders included) as a forward-slash path relative to it, except INDEX.md and
    names starting with a dot (.gitkeep and the like)."""
    out = []
    for p in sorted(folder.rglob("*")):
        rel = p.relative_to(folder)
        if p.is_file() and rel.as_posix() != "INDEX.md" and not any(part.startswith(".") for part in rel.parts):
            out.append(rel.as_posix())
    return out


def scan_folder(folder_dir: Path, name: str, chunk_cfg: dict, scan: Scan) -> None:
    present = list_files(folder_dir)
    index_path = folder_dir / "INDEX.md"
    if not index_path.exists():
        if present:
            scan.errors.append(f"kb/{name} has {len(present)} file(s) but no INDEX.md; run "
                               f"`python -m retrieval.index_stub kb/{name}` and fill it in")
        else:
            scan.warnings.append(f"kb/{name} has no INDEX.md (and no files)")
        return
    try:
        entries = read_index(index_path)
    except IndexError_ as e:
        scan.errors.append(str(e))
        return

    listed: set[str] = set()
    for n, entry in enumerate(entries, 1):
        raw = str(entry.get("file") or "").strip()
        rel = clean_relative_path(raw) if raw else None
        if rel is None:
            scan.errors.append(f"kb/{name}/INDEX.md entry {n}: `file` is "
                               + ("missing" if not raw else f"{raw!r}, which is not a path inside the folder"))
            continue
        label = f"kb/{name}/{rel}"
        if rel in listed:
            scan.errors.append(f"{label}: listed more than once in INDEX.md")
            continue
        listed.add(rel)
        path = folder_dir / rel
        if not path.is_file():
            scan.warnings.append(f"{label}: listed in INDEX.md but the file does not exist; skipped")
            scan.skipped.append(f"{label}: missing")
            continue
        if path.suffix.lower() not in SUPPORTED:
            scan.warnings.append(f"{label}: unsupported file type {path.suffix or '(none)'}; skipped")
            scan.skipped.append(f"{label}: unsupported type")
            continue
        try:
            extracted = extract(path)
        except LoaderError as e:
            scan.warnings.append(f"{label}: {e}; skipped")
            scan.skipped.append(f"{label}: unreadable")
            continue
        doc, errors, warnings = build_document({**entry, "file": rel}, extracted.meta, label)
        scan.warnings += warnings
        if doc is None:
            scan.errors += errors
            continue
        for w in extracted.warnings:
            scan.warnings.append(f"{label}: {w}")
        if extracted.scanned:
            scan.skipped.append(f"{label}: scanned PDF, needs OCR")
            continue
        chunks = chunk_sections(
            extracted.sections, folder=name, file=rel, title=doc.title, source_url=doc.source_url,
            last_updated=doc.last_updated, provenance=doc.public_or_permission, course=doc.course,
            date_kind=doc.date_kind, **chunk_cfg)
        if not chunks:
            scan.warnings.append(f"{label}: no indexable text found; skipped")
            scan.skipped.append(f"{label}: no text")
            continue
        scan.chunks += chunks
        scan.documents.append(DocReport(name, rel, doc.title, len(chunks)))

    for rel in present:
        if rel not in listed:
            scan.warnings.append(f"kb/{name}/{rel}: present in the folder but not listed in INDEX.md; not indexed")
            scan.skipped.append(f"kb/{name}/{rel}: unlisted")


def scan_kb(cfg: dict, kb_root: Path = KB_ROOT, folders: list[str] | None = None) -> Scan:
    """Validate and chunk the whole knowledge base (or the given folder names)."""
    scan = Scan()
    valid = folders or kb_folders()
    chunk_cfg = {"target_tokens": cfg["kb"]["chunk"]["target_tokens"],
                 "overlap_tokens": cfg["kb"]["chunk"]["overlap_tokens"],
                 "min_chars": cfg["kb"]["chunk"]["min_chars"]}
    on_disk = sorted(p.name for p in kb_root.iterdir() if p.is_dir() and not p.name.startswith("."))
    for name in on_disk:
        if name not in valid:
            files = list_files(kb_root / name)
            extra = (f" It holds {len(files)} file(s); HELPDESK holds no documents, so they are not indexed. "
                     f"Move them to the folder that owns them." if name == "HELPDESK" and files else "")
            scan.warnings.append(f"kb/{name} is not a knowledge folder (valid: {', '.join(valid)}); skipped.{extra}")
            scan.skipped += [f"kb/{name}/{f}: unknown folder" for f in files]
    for name in valid:
        if name not in on_disk:
            scan.warnings.append(f"kb/{name} does not exist")
            continue
        scan_folder(kb_root / name, name, chunk_cfg, scan)
    ids = [c.id for c in scan.chunks]
    if len(ids) != len(set(ids)):
        scan.errors.append("duplicate chunk ids: two files produce the same id")
    return scan
