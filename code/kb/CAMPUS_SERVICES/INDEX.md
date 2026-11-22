---
documents:
- file: circular-student-queries-online.md
  title: 'Circular: Online Helpdesk for Student Queries'
  source_url: https://www.bennett.edu.in/wp-content/uploads/2024/10/Circular-regarding-student-quries-online.pdf
  date: 10/2024
  public_or_permission: public
  collector: ZEN AI team
---

# kb/CAMPUS_SERVICES

Hand-off office: Campus services (Punctualiti helpdesk). Covers: Mess and food outlets, sports, maintenance.

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
