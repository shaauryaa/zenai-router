---
documents: []
---

# kb/STUDENT_SUPPORT

Hand-off office: Student support. Covers: Anti-ragging and harassment policy, helpline numbers, counselling and health support.

Helpline numbers and emergency contacts shown to a student come only from files listed here. If none is listed, ZEN AI hands the case to the office without quoting any number.

Metadata for every file in this folder, one entry per file under `documents:` above. Ingestion
(`python -m retrieval.ingest`) indexes only listed files and warns about unlisted ones.

Each entry:

- `file`: path inside this folder (subfolders allowed)
- `title`: shown in citations, for example `Fee structure`
- `source_url`: the public URL; for a `team-written` document, say what it was compiled from
- `last_updated`: YYYY-MM-DD from the document; if it states none, the day it was fetched, with `date_kind: fetched_on`
- `public_or_permission`: `public`, `office-provided` or `team-written`
- `collector`: who added it
- `course`: optional, the course code (COURSE_SPECIFIC)

`office-provided` documents may leave `source_url` and `last_updated` empty. See docs/RETRIEVAL.md.
