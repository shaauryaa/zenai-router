"""Read and validate a kb/<FOLDER>/INDEX.md: YAML front matter with a `documents:` list, one entry per file.

Entry fields: file, title, source_url, last_updated, public_or_permission, collector, course (optional),
date_kind (optional: `updated`, the default, or `fetched_on` when last_updated is the day the page was fetched),
date (optional: the document date exactly as the team's source list gives it, e.g. `10/2024`, `2026-2027` or
`unknown`; it stands in for last_updated when no exact YYYY-MM-DD date is known, so no day is ever guessed).
A .md or .txt file may carry front matter with the same fields; it fills only fields INDEX.md leaves blank.
Converted documents also carry provenance fields (office, text_source, original_file) that are not validated here.
"""
from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

import yaml

from .loaders import LoaderError, split_front_matter
from .model import DATE_KINDS, PROVENANCES

FIELDS = ("file", "title", "source_url", "last_updated", "public_or_permission", "collector", "course", "date_kind",
          "date")
METADATA_FIELDS = FIELDS[1:]  # everything but `file`, which only INDEX.md can say
# front matter keys a file may carry for provenance; accepted without a warning, not used for validation
FILE_ONLY_FIELDS = ("fetched_on", "source", "note", "office", "text_source", "original_file")


class IndexError_(ValueError):
    """INDEX.md is missing, not valid YAML, or has no `documents:` list."""


@dataclass(frozen=True)
class KBDocument:
    file: str
    title: str
    source_url: str
    last_updated: str | None
    public_or_permission: str
    collector: str
    course: str | None
    date_kind: str
    date: str | None = None


def _text(value) -> str:
    """A field value as a clean string ('' when blank). YAML dates become YYYY-MM-DD."""
    if value is None:
        return ""
    if isinstance(value, (dt.date, dt.datetime)):
        return value.strftime("%Y-%m-%d")
    return str(value).strip()


def read_index(path: Path) -> list[dict]:
    """The `documents` entries of an INDEX.md, as plain dicts."""
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError as e:
        raise IndexError_(f"{path.parent.name}/INDEX.md does not exist") from e
    try:
        meta, _ = split_front_matter(text)
    except LoaderError as e:
        raise IndexError_(f"{path.parent.name}/INDEX.md: {e}") from e
    docs = meta.get("documents")
    if docs is None:
        raise IndexError_(f"{path.parent.name}/INDEX.md has no `documents:` list in its front matter")
    if not isinstance(docs, list) or any(not isinstance(d, dict) for d in docs):
        raise IndexError_(f"{path.parent.name}/INDEX.md: `documents:` must be a list of entries with a `file:`")
    return docs


def clean_relative_path(value: str) -> str | None:
    """The file path normalised to forward slashes, or None if it is absolute or leaves the folder."""
    p = PurePosixPath(value.replace("\\", "/"))
    if p.is_absolute() or ".." in p.parts or re.match(r"^[A-Za-z]:", value) or not p.parts:
        return None
    return str(p)


def build_document(entry: dict, file_meta: dict | None = None, label: str = "") -> tuple[KBDocument | None, list[str],
                                                                                      list[str]]:
    """Merge an INDEX.md entry with the file's own front matter (which only fills blanks), then validate.
    Returns (document or None if invalid, errors, warnings); `label` prefixes messages, e.g. `kb/FINANCE/x.md`."""
    errors, warnings = [], []
    file_meta = file_meta or {}
    for key in entry:
        if key not in FIELDS:
            warnings.append(f"{label}: unknown field `{key}` in INDEX.md is ignored")
    for key in file_meta:
        if key not in METADATA_FIELDS and key not in FILE_ONLY_FIELDS:
            warnings.append(f"{label}: unknown front matter field `{key}` is ignored")
    values = {k: _text(entry.get(k)) for k in METADATA_FIELDS}
    for k in METADATA_FIELDS:
        if not values[k] and _text(file_meta.get(k)):
            values[k] = _text(file_meta.get(k))

    if not values["title"]:
        errors.append(f"{label}: missing title")
    kind = values["public_or_permission"]
    if kind not in PROVENANCES:
        errors.append(f"{label}: public_or_permission must be one of {' | '.join(PROVENANCES)}"
                      + (f" (got {kind!r})" if kind else " (it is missing)"))
    office_provided = kind == "office-provided"
    if not values["source_url"] and not office_provided:
        errors.append(f"{label}: missing source_url" + (" (for a team-written document, say what it was compiled "
                                                         "from)" if kind == "team-written" else ""))
    if not values["last_updated"] and not values["date"] and not office_provided:
        errors.append(f"{label}: missing last_updated (or `date` as the source list gives it)")
    if values["last_updated"]:
        try:
            dt.date.fromisoformat(values["last_updated"])
        except ValueError:
            errors.append(f"{label}: last_updated {values['last_updated']!r} is not a date like 2026-10-06")
    date_kind = values["date_kind"] or "updated"
    if date_kind not in DATE_KINDS:
        errors.append(f"{label}: date_kind must be one of {' | '.join(DATE_KINDS)} (got {date_kind!r})")
    if not values["collector"]:
        warnings.append(f"{label}: no collector named")
    if errors:
        return None, errors, warnings
    return (KBDocument(file=_text(entry.get("file")), title=values["title"], source_url=values["source_url"],
                       last_updated=values["last_updated"] or None, public_or_permission=kind,
                       collector=values["collector"], course=values["course"] or None, date_kind=date_kind,
                       date=values["date"] or None),
            errors, warnings)


def front_matter_yaml(documents: list[dict]) -> str:
    """INDEX.md front matter text for a list of entries (used by index_stub)."""
    if not documents:
        return "---\ndocuments: []\n---\n"
    return "---\n" + yaml.safe_dump({"documents": documents}, sort_keys=False, allow_unicode=True,
                                    default_flow_style=False, width=1000) + "---\n"
