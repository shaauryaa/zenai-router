"""Create an INDEX.md skeleton listing every file in a kb folder, for the team to fill in.

    python -m retrieval.index_stub kb/HOSTEL [--force]

One entry per file found (subfolders included), with title, source_url, last_updated, public_or_permission and
collector left blank. A .md or .txt file that already has front matter pre-fills those fields. The blanks are
intentional: ingestion refuses an entry until they are filled in. An existing INDEX.md is never overwritten
unless --force is given.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .index_md import front_matter_yaml
from .kb import kb_folders, list_files
from .loaders import LoaderError, decode_bytes, split_front_matter

BODY = """
# kb/{folder}

Metadata for every file in this folder, one entry per file under `documents:` above. Ingestion
(`python -m retrieval.ingest`) indexes only listed files and warns about unlisted ones.

Each entry:

- `file`: path inside this folder (subfolders allowed)
- `title`: shown in citations, for example `Fee structure`
- `source_url`: the public URL; for a `team-written` document, say what it was compiled from
- `last_updated`: YYYY-MM-DD from the document; if it states none, the day it was fetched, with `date_kind: fetched_on`
- `public_or_permission`: `public`, `office-provided`, `team-written` or `unverified` (source not confirmed)
- `collector`: who added it
- `course`: optional, the course code (COURSE_SPECIFIC)

`office-provided` documents may leave `source_url` and `last_updated` empty. See docs/RETRIEVAL.md.
"""


def build_entries(folder_dir: Path, folder: str) -> list[dict]:
    entries = []
    for rel in list_files(folder_dir):
        meta: dict = {}
        if Path(rel).suffix.lower() in (".md", ".markdown", ".txt"):
            try:
                meta, _ = split_front_matter(decode_bytes((folder_dir / rel).read_bytes()))
            except (LoaderError, OSError):
                meta = {}
        entry = {"file": rel}
        for key in ("title", "source_url", "last_updated", "public_or_permission", "collector"):
            entry[key] = meta.get(key) if meta.get(key) is not None else ""
        if folder == "COURSE_SPECIFIC":
            entry["course"] = meta.get("course") or ""
        entries.append(entry)
    return entries


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("folder", type=Path, help="a kb folder, for example kb/HOSTEL")
    ap.add_argument("--force", action="store_true", help="overwrite an existing INDEX.md")
    args = ap.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")

    folder_dir = args.folder.resolve()
    name = folder_dir.name
    if not folder_dir.is_dir():
        print(f"error: {args.folder} is not a folder")
        return 1
    if name not in kb_folders():
        print(f"error: {name} is not a knowledge folder; valid: {', '.join(kb_folders())}")
        return 1
    target = folder_dir / "INDEX.md"
    if target.exists() and not args.force:
        print(f"{target.relative_to(folder_dir.parent.parent)} already exists; use --force to overwrite it")
        return 1
    entries = build_entries(folder_dir, name)
    target.write_text(front_matter_yaml(entries) + BODY.format(folder=name), encoding="utf-8")
    print(f"wrote {target.relative_to(folder_dir.parent.parent)} with {len(entries)} entr"
          f"{'y' if len(entries) == 1 else 'ies'}; fill in the blank fields")
    return 0


if __name__ == "__main__":
    sys.exit(main())
