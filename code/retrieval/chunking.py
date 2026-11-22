"""Chunk extracted sections: split by heading first, then into chunks of about 400 tokens with about 60 tokens of
overlap. Tokens are estimated as characters / 4 (no tokenizer dependency); the sizes are in config.yaml.

A markdown table is never cut in the middle of a row, and when a table continues into the next chunk its header rows
are repeated there, so a row such as `Year 2 | 3,90,000` is never separated from its column names.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

from .loaders import Section
from .model import HEADING_SEP, Chunk

CHARS_PER_TOKEN = 4


@dataclass(frozen=True)
class Unit:
    text: str
    block: int  # units of the same block are joined with a single newline, blocks with a blank line
    table: str | None = None  # header rows of the table this unit is a row of


def approx_tokens(text: str) -> int:
    return -(-len(text) // CHARS_PER_TOKEN)


def chunk_id(folder: str, file: str, position: int) -> str:
    """Stable: the same folder, file and position always give the same id. Letters, digits and dashes only, which
    Azure AI Search allows in a document key."""
    digest = hashlib.sha1(f"{folder}/{file}".encode("utf-8")).hexdigest()[:10]
    return f"{folder.lower().replace('_', '-')}-{digest}-{position:04d}"


def id_prefix(folder: str, file: str) -> str:
    """The part of every chunk id that belongs to one file (used to find stale chunks of a re-ingested file)."""
    return chunk_id(folder, file, 0).rsplit("-", 1)[0] + "-"


def _split_long(text: str, limit: int) -> list[str]:
    """Pieces of at most `limit` characters: at lines, then sentence ends, then words."""
    pieces: list[str] = []
    for line in text.split("\n"):
        if len(line) <= limit:
            pieces.append(line)
            continue
        for sentence in re.split(r"(?<=[.!?])\s+", line):
            while len(sentence) > limit:
                cut = sentence.rfind(" ", 0, limit)
                cut = cut if cut > 0 else limit
                pieces.append(sentence[:cut])
                sentence = sentence[cut:].strip()
            if sentence:
                pieces.append(sentence)
    return pieces


def _is_table(lines: list[str]) -> bool:
    return len(lines) >= 2 and all(ln.lstrip().startswith("|") for ln in lines)


def to_units(text: str, limit: int) -> list[Unit]:
    units: list[Unit] = []
    for block_no, block in enumerate(re.split(r"\n\s*\n", text.strip())):
        lines = [ln.rstrip() for ln in block.split("\n") if ln.strip()]
        if not lines:
            continue
        if _is_table(lines):
            header = "\n".join(lines[:2]) if re.match(r"^\|[\s:|-]+\|?$", lines[1].strip()) else None
            rows = lines[2:] if header else lines
            for row in rows:
                for piece in _split_long(row, limit):
                    units.append(Unit(piece, block_no, header))
            if header and not rows:
                units.append(Unit(header, block_no))
        else:
            for piece in _split_long("\n".join(lines), limit):
                units.append(Unit(piece, block_no))
    return units


def render(units: list[Unit]) -> str:
    """Join units, repeating a table's header rows before the first row of that table in the chunk."""
    out: list[str] = []
    prev: Unit | None = None
    for u in units:
        if u.table and (prev is None or prev.table != u.table or prev.block != u.block):
            out.append(("\n\n" if out else "") + u.table + "\n" + u.text)
        else:
            out.append(("" if not out else "\n" if prev and prev.block == u.block else "\n\n") + u.text)
        prev = u
    return "".join(out).strip()


def split_text(text: str, target_tokens: int = 400, overlap_tokens: int = 60) -> list[str]:
    """Chunks of one section's text."""
    target, overlap = target_tokens * CHARS_PER_TOKEN, overlap_tokens * CHARS_PER_TOKEN
    units = to_units(text, max(target // 2, 200))
    chunks: list[str] = []
    cur: list[Unit] = []
    fresh = 0  # units in `cur` that were not carried over from the previous chunk
    for u in units:
        if cur and len(render(cur + [u])) > target:
            if fresh:
                chunks.append(render(cur))
            carry: list[Unit] = []
            for prev in reversed(cur):
                if len(render([prev] + carry)) > overlap:
                    break
                carry.insert(0, prev)
            while carry and len(render(carry + [u])) > target:
                carry.pop(0)
            cur, fresh = carry, 0
        cur.append(u)
        fresh += 1
    if fresh:
        chunks.append(render(cur))
    return chunks


def chunk_sections(sections: list[Section], *, folder: str, file: str, title: str, source_url: str,
                   last_updated: str | None, provenance: str, course: str | None = None, date_kind: str = "updated",
                   target_tokens: int = 400, overlap_tokens: int = 60, min_chars: int = 15) -> list[Chunk]:
    """Chunks of a whole document in order. Each keeps the document's title, source and date, plus its own page and
    heading path. Empty and near-empty chunks are dropped, so nothing blank is ever indexed."""
    chunks: list[Chunk] = []
    for section in sections:
        for text in split_text(section.text, target_tokens, overlap_tokens):
            if len(re.sub(r"\s+", "", text)) < min_chars:
                continue
            chunks.append(Chunk(
                id=chunk_id(folder, file, len(chunks)), department=folder, title=title, source_url=source_url,
                content=text, last_updated=last_updated, page=section.page,
                heading_path=HEADING_SEP.join(section.heading), provenance=provenance, file=file, course=course,
                date_kind=date_kind))
    return chunks
