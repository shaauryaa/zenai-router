---
documents: []
---

# kb/COURSE_SPECIFIC

Hand-off office: course faculty (queue: ACADEMICS). Covers: Information about one named course: syllabus, exam portion, one teacher's policy or availability.

A question about one particular course is answered only from a file listed here for that course, with a citation. If no file is listed for the course, the case is handed to the course faculty through the ACADEMICS queue. General documents elsewhere are never used for a course-specific answer.

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
