---
documents:
- file: anti-ragging-and-sexual-harassment-contacts.md
  title: Anti-Ragging Committee and Sexual Harassment Complaint Contacts
  source_url: unknown
  date: unknown
  public_or_permission: unverified
  collector: ZEN AI team
- file: anti-ragging.md
  title: Rules on Curbing the Menace of Ragging in Bennett University
  source_url: https://www.bennett.edu.in/wp-content/uploads/2024/05/Anti-Ragging.pdf
  date: 05/2024
  public_or_permission: public
  collector: ZEN AI team
- file: posh-policy.md
  title: Policy on Prevention of Sexual Harassment
  source_url: https://www.bennett.edu.in/wp-content/uploads/2024/05/Posh_.pdf
  date: 05/2024
  public_or_permission: public
  collector: ZEN AI team
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
- `public_or_permission`: `public`, `office-provided`, `team-written` or `unverified` (source not confirmed)
- `collector`: who added it
- `course`: optional, the course code (COURSE_SPECIFIC)

`office-provided` documents may leave `source_url` and `last_updated` empty. See docs/RETRIEVAL.md.
