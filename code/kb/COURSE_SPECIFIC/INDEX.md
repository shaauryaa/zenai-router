---
documents:
- file: ba-liberal-arts-rulebook.md
  title: Rules and Regulations for Undergraduate BA Liberal Arts
  source_url: https://www.bennett.edu.in/wp-content/uploads/2022/03/BA_Liberal_Arts_Rulebook.pdf
  date: 03/2022
  public_or_permission: public
  collector: ZEN AI team
- file: bajmc-rules.md
  title: Rules and Regulations for Undergraduate BA (Journalism & Mass Communication)
  source_url: https://www.bennett.edu.in/wp-content/uploads/2017/08/BAJMC-Rules-revised-02-Nov-18-a.pdf
  date: 02-Nov-18
  public_or_permission: public
  collector: ZEN AI team
- file: bba-rules.md
  title: Rules and Regulations for Bachelor of Business Administration (BBA) Program
  source_url: https://www.bennett.edu.in/wp-content/uploads/2017/08/BBA-rules-02-Nov-2018.pdf
  date: 02-Nov-2018
  public_or_permission: public
  collector: ZEN AI team
- file: mba-rules.md
  title: Academic Rules Master of Business Administration (MBA)
  source_url: https://www.bennett.edu.in/wp-content/uploads/2017/08/MBA-Rules-VK-02-Nov.pdf
  date: 02-Nov-2017
  public_or_permission: public
  collector: ZEN AI team
- file: mtech-ordinances-rules.md
  title: 'Ordinances, Rules and Regulations for Post Graduate Programs: Engineering (M.Tech)'
  source_url: https://www.bennett.edu.in/wp-content/uploads/2017/08/Ord_RulesReg_MTech2018-02-Nov-18.pdf
  date: 02-Nov-18
  public_or_permission: public
  collector: ZEN AI team
- file: scset-academic-rules-pg-dual.md
  title: SCSET Academic Rules for Master's Programme
  source_url: http://bennett.edu.in/wp-content/uploads/2022/03/Academic-Rules-for-SCSET_PGDual.pdf
  date: 03/2022
  public_or_permission: public
  collector: ZEN AI team
- file: scset-academic-rules-ug.md
  title: SCSET Academic Rules for Undergraduate Programs
  source_url: https://www.bennett.edu.in/wp-content/uploads/2022/03/Academic-Rules-for-SCSET_UG.pdf
  date: 03/2022
  public_or_permission: public
  collector: ZEN AI team
- file: seas-btech-ordinances-rules.md
  title: 'Ordinances, Rules and Regulations for Under Graduate Programs: Engineering (B.Tech)'
  source_url: https://www.bennett.edu.in/wp-content/uploads/2017/08/SEAS-Ord_Rules-Reg_01-Nov.pdf
  date: 01-Nov-2017
  public_or_permission: public
  collector: ZEN AI team
- file: sol-academic-handbook.md
  title: 'Rules and Regulations for Undergraduate/Integrated Programs: BBA LLB (Hons)/BA LLB (Hons)'
  source_url: https://www.bennett.edu.in/wp-content/uploads/2019/04/Academic-Hand-Book-SOL-updated_Final.pdf
  date: '2018'
  public_or_permission: public
  collector: ZEN AI team
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
