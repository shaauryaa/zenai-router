---
documents:
- file: bennett-fee-structure.md
  title: Bennett University fee structure
  source_url: https://www.bennett.edu.in/admission/fee-structure/
  last_updated: '2026-10-06'
  date_kind: fetched_on
  public_or_permission: public
  collector: ZEN AI team (fetched with Claude Code)
- file: fee-refund-policy-2026-27.md
  title: Fee Refund Policy, Academic Year 2026-27
  source_url: https://d2xwywryb7yxbo.cloudfront.net/s3bucket-images/Fee-Refund-Policy-26-27_compressed.pdf
  date: 2026-2027
  public_or_permission: public
  collector: ZEN AI team
- file: late-fee-payment-rules.md
  title: 'Annexure I: Rules for Late Fee Payment'
  source_url: unverified
  date: unverified
  public_or_permission: public
  collector: ZEN AI team
- file: scholarship-policy-2026-27.md
  title: Scholarship Policy, Academic Year 2026-27
  source_url: https://d2xwywryb7yxbo.cloudfront.net/s3bucket-images/Scholarship-Policy-26-27_compressed.pdf
  date: 2026-2027
  public_or_permission: public
  collector: ZEN AI team
---

# kb/FINANCE

Hand-off office: Finance office. Covers: Fee structure, payment steps and deadlines, refunds, scholarships.

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
