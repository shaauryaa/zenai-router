"""Write the `documents:` front matter of kb/<FOLDER>/INDEX.md files; the prose below the front matter is kept.

Used by tools.build_kb. Entries for documents the build produces are replaced by freshly built ones; entries for
other files (for example kb/FINANCE/bennett-fee-structure.md) are kept exactly as they are. Entries are sorted by file.
"""
from __future__ import annotations

import yaml


def split_front_matter(text: str) -> tuple[dict, str]:
    """(front matter, everything after the closing ---) of a file that starts with YAML front matter."""
    if not text.startswith("---\n"):
        raise ValueError("no front matter")
    end = text.index("\n---\n", 4)
    return yaml.safe_load(text[4:end]) or {}, text[end + 5:]


def render_index(index_text: str, built: list[dict]) -> str:
    """The INDEX.md text with `built` entries merged in (replacing entries for the same file)."""
    meta, prose = split_front_matter(index_text)
    by_file = {d["file"]: d for d in (meta.get("documents") or [])}
    by_file.update({d["file"]: d for d in built})
    docs = [by_file[f] for f in sorted(by_file)]
    body = yaml.safe_dump({"documents": docs}, sort_keys=False, allow_unicode=True, default_flow_style=False,
                          width=1000) if docs else "documents: []\n"
    return f"---\n{body}---\n{prose}"
