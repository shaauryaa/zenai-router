---
documents:
- file: hostel-sports-refund-policy-2025-26.md
  title: Hostel Charges & Sports Charges Refund Policy for Returning Students (2025-26)
  source_url: https://www.bennett.edu.in/wp-content/uploads/2025/06/Hostel-Sports-Refund-Policy-for-Returning-Students-AY-2025-26.pdf
  date: 2025-2026
  public_or_permission: public
  collector: ZEN AI team
- file: hostel-standing-orders.md
  title: Standing Orders for Hostel
  source_url: https://www.bennett.edu.in/wp-content/uploads/2017/11/HostelRules201117.pdf
  date: 11/2017
  public_or_permission: public
  collector: ZEN AI team
- file: room-partner-user-manual.md
  title: Room Partner User Manual (Student Login)
  source_url: unverified
  date: unknown
  public_or_permission: unverified
  collector: ZEN AI team
- file: student-discipline-conduct-rules.md
  title: Students' Discipline and Conduct Rules
  source_url: https://www.bennett.edu.in/wp-content/uploads/2024/05/STUDENTS-DISCIPLINE-AND-CONDUCT-RULES.pdf
  date: 05/2024
  public_or_permission: public
  collector: ZEN AI team
- file: student-handbook.md
  title: Student Handbook, Academic Year 2019-20
  source_url: https://www.bennett.edu.in/wp-content/uploads/2019/07/studentHandbookBennett.pdf
  date: 07/2019
  public_or_permission: public
  collector: ZEN AI team
- file: travel-policy.md
  title: Travel & Tour Policy
  source_url: https://www.bennett.edu.in/wp-content/uploads/2024/06/Travel-Policy.pdf
  date: 06/2024
  public_or_permission: public
  collector: ZEN AI team
---

# kb/HOSTEL

Hand-off office: Hostel wardens. Covers: Hostel rules, laundry, curfew and in-time, outing and leave, guests, room change, transport.

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
