"""Turn a KB file (PDF, markdown, text, HTML) into sections of clean text.

A Section is a run of text with the page it came from (PDF only) and its heading path (markdown and HTML).
Headings are kept so a chunk can say where in the document it sits, for example `Fees > B.Tech CSE`.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

SUPPORTED = {".pdf", ".md", ".markdown", ".txt", ".html", ".htm"}
HTML_SUFFIXES = {".html", ".htm"}
# A PDF whose pages carry fewer characters than this on average has no real text layer: it is a scan.
SCANNED_CHARS_PER_PAGE = 30
# Tags that never hold content, and block-level containers that are page furniture.
DROP_TAGS = ["script", "style", "noscript", "template", "svg", "iframe", "form", "button", "select", "input",
             "nav", "header", "footer", "aside"]
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")
FENCE_RE = re.compile(r"^\s*(```|~~~)")


@dataclass
class Section:
    text: str
    page: int | None = None
    heading: tuple[str, ...] = ()


@dataclass
class Extracted:
    sections: list[Section] = field(default_factory=list)
    meta: dict = field(default_factory=dict)  # front matter of a .md/.txt file
    warnings: list[str] = field(default_factory=list)
    scanned: bool = False


class LoaderError(ValueError):
    pass


def decode_bytes(data: bytes) -> str:
    """UTF-8, but a stray cp1252 byte (a Word-style dash in an otherwise UTF-8 page) becomes its character
    instead of a replacement mark."""
    text = data.decode("utf-8", errors="surrogateescape")
    if not any("\udc80" <= c <= "\udcff" for c in text):
        return text
    return "".join(bytes([ord(c) - 0xDC00]).decode("cp1252", errors="replace") if "\udc80" <= c <= "\udcff" else c
                   for c in text)


def split_front_matter(text: str) -> tuple[dict, str]:
    """(front matter dict, remaining text). A file without `---` front matter returns ({}, text)."""
    text = text.lstrip("﻿")
    m = re.match(r"---[ \t]*\r?\n(.*?)\r?\n---[ \t]*(?:\r?\n|$)", text, re.DOTALL)
    if not m:
        return {}, text
    try:
        meta = yaml.safe_load(m.group(1))
    except yaml.YAMLError as e:
        raise LoaderError(f"front matter is not valid YAML: {e}") from e
    return (meta if isinstance(meta, dict) else {}), text[m.end():]


def split_markdown(text: str) -> list[Section]:
    """Sections of a markdown/plain text body, one per heading, each with its heading path."""
    sections: list[Section] = []
    stack: list[tuple[int, str]] = []
    buf: list[str] = []
    in_fence = False

    def flush():
        body = "\n".join(buf).strip()
        if body:
            sections.append(Section(body, None, tuple(t for _, t in stack)))
        buf.clear()

    for line in text.replace("\r\n", "\n").split("\n"):
        if FENCE_RE.match(line):
            in_fence = not in_fence
        m = None if in_fence else HEADING_RE.match(line)
        if m:
            flush()
            level, title = len(m.group(1)), re.sub(r"\s+", " ", m.group(2)).strip()
            while stack and stack[-1][0] >= level:
                stack.pop()
            stack.append((level, title))
        else:
            buf.append(line.rstrip())
    flush()
    return sections


# ---- HTML (readability-style) ----

def _text_len(tag) -> int:
    return len(tag.get_text(" ", strip=True))


def _link_density(tag) -> float:
    total = _text_len(tag) or 1
    return sum(_text_len(a) for a in tag.find_all("a")) / total


def main_content(soup):
    """The element that holds the page's main text: <main>/<article>/role=main, otherwise the block with the
    most text that is not mostly links."""
    for finder in (lambda: soup.find("main"), lambda: soup.find("article"), lambda: soup.find(attrs={"role": "main"})):
        found = finder()
        if found is not None and _text_len(found) > 200:
            return found
    best, best_score = None, 0.0
    for tag in soup.find_all(["div", "section", "td"]):
        score = _text_len(tag) * (1 - _link_density(tag))
        if score > best_score:
            best, best_score = tag, score
    return best or soup.body or soup


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("\xa0", " ")).strip()


def _cell(tag) -> str:
    return _clean(tag.get_text(" ", strip=True)).replace("|", "/")


def _table_to_markdown(table) -> str:
    rows = []
    for tr in table.find_all("tr"):
        cells = tr.find_all(["th", "td"])
        if cells:
            rows.append(([_cell(c) for c in cells], bool(tr.find("th")) and not tr.find("td")))
    if not rows:
        return ""
    width = max(len(r) for r, _ in rows)
    lines = []
    header_done = False
    for cells, is_header in rows:
        cells = cells + [""] * (width - len(cells))
        lines.append("| " + " | ".join(cells) + " |")
        if not header_done:
            lines.append("|" + "|".join(" --- " for _ in range(width)) + "|")
            header_done = True
    return "\n".join(lines)


BLOCK_TAGS = {"p", "div", "section", "ul", "ol", "li", "table", "h1", "h2", "h3", "h4", "h5", "h6", "blockquote",
              "pre", "dl", "dt", "dd", "tr", "article", "main", "figure", "figcaption"}


def _blocks(node, out: list[str]) -> None:
    """Append markdown blocks for node's children, in document order."""
    from bs4 import NavigableString, Tag

    inline: list[str] = []

    def flush_inline():
        text = _clean(" ".join(inline))
        inline.clear()
        if text:
            out.append(text)

    for child in node.children:
        if isinstance(child, NavigableString):
            if type(child).__name__ in ("Comment", "Doctype"):
                continue
            inline.append(str(child))
        elif isinstance(child, Tag):
            name = child.name
            if name == "br":
                flush_inline()
            elif name not in BLOCK_TAGS:
                inline.append(child.get_text(" ") if not child.find(BLOCK_TAGS) else "")
                if child.find(BLOCK_TAGS):
                    flush_inline()
                    _blocks(child, out)
            elif name in ("h1", "h2", "h3", "h4", "h5", "h6"):
                flush_inline()
                title = _clean(child.get_text(" ", strip=True))
                if title:
                    out.append(title if STATEMENT_RE.search(title) else "#" * int(name[1]) + " " + title)
            elif name == "table":
                flush_inline()
                md = _table_to_markdown(child)
                if md:
                    out.append(md)
            elif name in ("ul", "ol"):
                flush_inline()
                items = [_clean(li.get_text(" ", strip=True)) for li in child.find_all("li", recursive=False)]
                if items:
                    out.append("\n".join(f"- {i}" for i in items if i))
            elif name == "pre":
                flush_inline()
                out.append("```\n" + child.get_text() + "\n```")
            else:
                flush_inline()
                _blocks(child, out)
    flush_inline()


REPEATED_HEADING_MIN = 3
# Web pages sometimes mark a note ("The hostel fee is subject to an annual increase") as a heading. A heading that
# contains one of these verbs is a statement, so it is kept as plain text and does not enter the heading path.
STATEMENT_RE = re.compile(r"(is|are|will|shall|may|must|can|should)", re.IGNORECASE)


def nest_repeated_headings(blocks: list[str]) -> list[str]:
    """Pages like a fee table repeat labels such as `Hostel Fees` under every programme, often with a heading level
    that is higher than the programme heading before them. Read as markdown, that would drop the programme from the
    heading path. A heading whose text repeats at least REPEATED_HEADING_MIN times is a section label, so it is
    pushed one level below the last distinctive heading. Only heading levels change, never the text."""
    texts: dict[str, int] = {}
    for b in blocks:
        m = HEADING_RE.match(b) if b.startswith("#") and "\n" not in b else None
        if m:
            key = re.sub(r"\s+", " ", m.group(2)).strip().lower()
            texts[key] = texts.get(key, 0) + 1
    out, last_distinct = [], None
    for b in blocks:
        m = HEADING_RE.match(b) if b.startswith("#") and "\n" not in b else None
        if not m:
            out.append(b)
            continue
        level = len(m.group(1))
        if texts[re.sub(r"\s+", " ", m.group(2)).strip().lower()] >= REPEATED_HEADING_MIN:
            if last_distinct is not None:
                level = min(6, max(level, last_distinct + 1))
        else:
            last_distinct = level
        out.append("#" * level + " " + m.group(2))
    return out


def html_to_markdown(html: str) -> str:
    """Readability-style extraction: drop scripts, menus and footers, take the main content block, and write
    it as markdown with headings, lists and tables preserved."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(DROP_TAGS):
        tag.decompose()
    root = main_content(soup)
    blocks: list[str] = []
    _blocks(root, blocks)
    # Drop exact repeats of short lines that sit next to each other (breadcrumb and title echoes).
    cleaned: list[str] = []
    for b in blocks:
        if cleaned and b == cleaned[-1] and len(b) < 200:
            continue
        cleaned.append(b)
    return "\n\n".join(nest_repeated_headings(cleaned)) + "\n"


# ---- PDF ----

def extract_pdf(path: Path, min_chars_per_page: int = SCANNED_CHARS_PER_PAGE) -> Extracted:
    """One section per page that has text, keeping page numbers (1-based). A PDF with almost no extractable text
    is a scan: no sections are returned and `scanned` is set, so nothing empty is ever indexed."""
    from pypdf import PdfReader

    try:
        reader = PdfReader(str(path))
        pages = [(reader.pages[i].extract_text() or "") for i in range(len(reader.pages))]
    except Exception as e:  # pypdf raises many types for damaged or encrypted files
        raise LoaderError(f"cannot read PDF: {type(e).__name__}: {e}") from e
    cleaned = [re.sub(r"[ \t]+", " ", p).strip() for p in pages]
    total = sum(len(re.sub(r"\s+", "", p)) for p in cleaned)
    out = Extracted()
    if not pages or total / len(pages) < min_chars_per_page:
        out.scanned = True
        out.warnings.append("almost no extractable text (probably scanned): OCR is needed before this PDF can be "
                            "indexed; skipped")
        return out
    for number, text in enumerate(cleaned, 1):
        if text:
            out.sections.append(Section(text, page=number))
    return out


# ---- entry point ----

def extract(path: Path) -> Extracted:
    """Extract a KB file by its extension. Raises LoaderError for unsupported or unreadable files."""
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return extract_pdf(path)
    if suffix not in SUPPORTED:
        raise LoaderError(f"unsupported file type {suffix or '(none)'}; use PDF, md, txt or html")
    text = decode_bytes(path.read_bytes())
    if suffix in HTML_SUFFIXES:
        sections = split_markdown(html_to_markdown(text))
        return Extracted(sections=sections)
    meta, body = split_front_matter(text)
    return Extracted(sections=split_markdown(body), meta=meta)
