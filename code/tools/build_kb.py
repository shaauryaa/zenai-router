"""Rebuild the helpdesk knowledge base (kb/<OFFICE>/<slug>.md, the INDEX.md lists, test-data/kb_manifest.csv).

Sources (keep them outside the repo; they are never committed):
  --zip-dir  the team's "yiti-ai data.zip", unzipped: the folder holding one sub-folder per department
             (campus services, course specific, employee, finance, hostel, it, student support)
  --ocr-dir  the OCR folder: one "<pdf name>.txt" per scanned PDF, with "=== page N ===" markers
  pdftotext  (poppler) for PDFs with a text layer: on PATH, or give --pdftotext <path to the executable>

Rebuild, from code/:
  python -m tools.build_kb --zip-dir "<unzipped>/yiti-ai data" --ocr-dir "<ocr folder>"
  python -m tools.build_kb --zip-dir ... --ocr-dir ... --check   # write nothing; list files that would change

What it does, per entry in DOCS (titles from each document's first page; office, date and source URL exactly as in
the team's "doc dates" list, "unknown" when the list has none):
  - text: the OCR file when the PDF is scanned, else pdftotext page by page; original .md files as they are
  - body: one "## Page N" section per page with text. Wording is never changed. Cleaning removes only repeated
    header/footer lines, lone page numbers at the top or bottom of a page (within 3 of the page index, or
    "Page x of y"), lines with no letters or digits, and runs of 4+ leader symbols (.... ____ ----) inside a line
  - redaction (team decision): student details -> "[student details removed]"; staff personal mobile numbers and
    named personal emails -> "[contact removed]". Names, designations, 0120 landlines and role mailboxes stay
  - front matter: title, office, source_url, date, text_source, original_file
  - INDEX.md: one entry per document (tools.kb_index); the late-fee annexure, the Room Partner manual and the
    contacts file are `public_or_permission: unverified`
Left out by team decision: PhD ordinances, finance/guidelines.pdf, punctualiti.pdf, the fee payment guidelines .docx,
the admission withdrawal form, hostel_warden_contacts.md, the HR manual, processed-data/, and the campus services
copy of the student handbook (the HOSTEL copy is used). kb/FINANCE/bennett-fee-structure.md is not built here.
"""
from __future__ import annotations

import argparse
import csv
import io
import re
import shutil
import subprocess
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import yaml

from tools.kb_index import render_index, split_front_matter
from zenai.paths import KB, TEST_DATA

U = "https://www.bennett.edu.in/wp-content/uploads/"
COLLECTOR = "ZEN AI team"


@dataclass(frozen=True)
class Doc:
    src: str  # path inside the unzipped team folder
    office: str
    slug: str
    title: str
    date: str  # exactly as in the team's dates list
    source_url: str
    provenance: str = "public"


DOCS = [
    Doc("campus services/Circular-regarding-student-quries-online.pdf", "CAMPUS_SERVICES",
        "circular-student-queries-online", "Circular: Online Helpdesk for Student Queries",
        "10/2024", U + "2024/10/Circular-regarding-student-quries-online.pdf"),
    Doc("course specific/Academic-Hand-Book-SOL-updated_Final.pdf", "COURSE_SPECIFIC", "sol-academic-handbook",
        "Rules and Regulations for Undergraduate/Integrated Programs: BBA LLB (Hons)/BA LLB (Hons)",
        "2018", U + "2019/04/Academic-Hand-Book-SOL-updated_Final.pdf"),
    Doc("course specific/Academic-Rules-for-SCSET_PGDual.pdf", "COURSE_SPECIFIC", "scset-academic-rules-pg-dual",
        "SCSET Academic Rules for Master's Programme",
        "03/2022", "http://bennett.edu.in/wp-content/uploads/2022/03/Academic-Rules-for-SCSET_PGDual.pdf"),
    Doc("course specific/Academic-Rules-for-SCSET_UG.pdf", "COURSE_SPECIFIC", "scset-academic-rules-ug",
        "SCSET Academic Rules for Undergraduate Programs", "03/2022", U + "2022/03/Academic-Rules-for-SCSET_UG.pdf"),
    Doc("course specific/BA_Liberal_Arts_Rulebook.pdf", "COURSE_SPECIFIC", "ba-liberal-arts-rulebook",
        "Rules and Regulations for Undergraduate BA Liberal Arts", "03/2022", U + "2022/03/BA_Liberal_Arts_Rulebook.pdf"),
    Doc("course specific/BAJMC-Rules-revised-02-Nov-18-a.pdf", "COURSE_SPECIFIC", "bajmc-rules",
        "Rules and Regulations for Undergraduate BA (Journalism & Mass Communication)",
        "02-Nov-18", U + "2017/08/BAJMC-Rules-revised-02-Nov-18-a.pdf"),
    Doc("course specific/BBA-rules-02-Nov-2018.pdf", "COURSE_SPECIFIC", "bba-rules",
        "Rules and Regulations for Bachelor of Business Administration (BBA) Program",
        "02-Nov-2018", U + "2017/08/BBA-rules-02-Nov-2018.pdf"),
    Doc("course specific/MBA-Rules-VK-02-Nov.pdf", "COURSE_SPECIFIC", "mba-rules",
        "Academic Rules Master of Business Administration (MBA)", "02-Nov-2017", U + "2017/08/MBA-Rules-VK-02-Nov.pdf"),
    Doc("course specific/Ord_RulesReg_MTech2018-02-Nov-18.pdf", "COURSE_SPECIFIC", "mtech-ordinances-rules",
        "Ordinances, Rules and Regulations for Post Graduate Programs: Engineering (M.Tech)",
        "02-Nov-18", U + "2017/08/Ord_RulesReg_MTech2018-02-Nov-18.pdf"),
    Doc("course specific/SEAS-Ord_Rules-Reg_01-Nov.pdf", "COURSE_SPECIFIC", "seas-btech-ordinances-rules",
        "Ordinances, Rules and Regulations for Under Graduate Programs: Engineering (B.Tech)",
        "01-Nov-2017", U + "2017/08/SEAS-Ord_Rules-Reg_01-Nov.pdf"),
    Doc("employee/Policy_Professor-of-Practice.pdf", "EMPLOYEES", "professor-of-practice-policy",
        "Policy for the Appointment of Professor of Practice", "01/2025", U + "2025/01/Policy_Professor-of-Practice.pdf"),
    Doc("finance/Fee-Refund-Policy-26-27_compressed.pdf", "FINANCE", "fee-refund-policy-2026-27",
        "Fee Refund Policy, Academic Year 2026-27", "2026-2027",
        "https://d2xwywryb7yxbo.cloudfront.net/s3bucket-images/Fee-Refund-Policy-26-27_compressed.pdf"),
    Doc("finance/Scholarship-Policy-26-27_compressed.pdf", "FINANCE", "scholarship-policy-2026-27",
        "Scholarship Policy, Academic Year 2026-27", "2026-2027",
        "https://d2xwywryb7yxbo.cloudfront.net/s3bucket-images/Scholarship-Policy-26-27_compressed.pdf"),
    Doc("finance/annexure_I_rules_for_late_fee_payment.md", "FINANCE", "late-fee-payment-rules",
        "Annexure I: Rules for Late Fee Payment", "unverified", "unverified", provenance="unverified"),
    Doc("hostel/Hostel-Sports-Refund-Policy-for-Returning-Students-AY-2025-26.pdf", "HOSTEL",
        "hostel-sports-refund-policy-2025-26",
        "Hostel Charges & Sports Charges Refund Policy for Returning Students (2025-26)", "2025-2026",
        U + "2025/06/Hostel-Sports-Refund-Policy-for-Returning-Students-AY-2025-26.pdf"),
    Doc("hostel/Room Partner User Manual _Students login.pdf", "HOSTEL", "room-partner-user-manual",
        "Room Partner User Manual (Student Login)", "unknown", "unverified", provenance="unverified"),
    Doc("hostel/STUDENTS-DISCIPLINE-AND-CONDUCT-RULES.pdf", "HOSTEL", "student-discipline-conduct-rules",
        "Students' Discipline and Conduct Rules", "05/2024", U + "2024/05/STUDENTS-DISCIPLINE-AND-CONDUCT-RULES.pdf"),
    Doc("hostel/Standing-Orders-for-Hostel.pdf", "HOSTEL", "hostel-standing-orders", "Standing Orders for Hostel",
        "11/2017", U + "2017/11/HostelRules201117.pdf"),
    Doc("hostel/Travel-Policy.pdf", "HOSTEL", "travel-policy", "Travel & Tour Policy", "06/2024",
        U + "2024/06/Travel-Policy.pdf"),
    Doc("hostel/studentHandbookBennett.pdf", "HOSTEL", "student-handbook", "Student Handbook, Academic Year 2019-20",
        "07/2019", U + "2019/07/studentHandbookBennett.pdf"),
    Doc("it/IT_Policy.pdf", "IT", "it-policy", "IT Policy", "06/2024", U + "2024/06/IT_Policy.pdf"),
    Doc("student support/Anti-Ragging.pdf", "STUDENT_SUPPORT", "anti-ragging",
        "Rules on Curbing the Menace of Ragging in Bennett University", "05/2024", U + "2024/05/Anti-Ragging.pdf"),
    Doc("student support/Posh_.pdf", "STUDENT_SUPPORT", "posh-policy", "Policy on Prevention of Sexual Harassment",
        "05/2024", U + "2024/05/Posh_.pdf"),
    Doc("student support/bennett_university_anti_ragging_and_sexual_harassment (1).md", "STUDENT_SUPPORT",
        "anti-ragging-and-sexual-harassment-contacts",
        "Anti-Ragging Committee and Sexual Harassment Complaint Contacts", "unknown", "unknown",
        provenance="unverified"),
]

# ---- text extraction ----

MARKER = re.compile(r"^\f?=== page (\d+) ===[ \t]*$", re.M)


def ocr_pages(path: Path) -> list[str]:
    parts = MARKER.split(path.read_text(encoding="utf-8", errors="replace"))  # ['', '1', text1, '2', text2, ...]
    pages = {int(parts[i]): parts[i + 1] for i in range(1, len(parts) - 1, 2)}
    n = max(pages)
    if sorted(pages) != list(range(1, n + 1)):
        raise SystemExit(f"{path.name}: page markers are not 1..{n}")
    return [pages[i] for i in range(1, n + 1)]


def pdftotext_pages(path: Path, exe: str) -> list[str]:
    out = subprocess.run([exe, "-enc", "UTF-8", str(path), "-"], capture_output=True, check=True).stdout
    pages = out.decode("utf-8", "replace").split("\f")
    return pages[:-1] if pages and not pages[-1].strip() else pages


# ---- cleaning (never changes wording) ----

LONE_PAGE_NO = re.compile(r"^\s*[-–(\[]?\s*(page\s*)?\d{1,3}\s*((of|/)\s*\d{1,3})?\s*[-–)\]]?\s*$", re.I)
LEADER_RUN = re.compile(r"([.…_\-=*~·•])\1{3,}")
HAS_ALNUM = re.compile(r"[A-Za-z0-9ऀ-ॿ]")


def _norm(line: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"\d+", "#", line.strip().lower()))


def clean(pages: list[str]) -> tuple[list[str], Counter]:
    removed = Counter()
    split = [[ln.rstrip() for ln in p.replace("\r\n", "\n").replace("\r", "\n").replace("\f", "").split("\n")]
             for p in pages]
    # repeated headers/footers: a normalised line in the first/last 3 non-empty lines of >= half the pages (3+ pages)
    edge_counts = Counter()
    for lines in split:
        ne = [ln for ln in lines if ln.strip()]
        edge_counts.update({_norm(ln) for ln in ne[:3] + ne[-3:] if len(ln.strip()) > 3})
    repeated = {k for k, c in edge_counts.items() if len(split) >= 3 and c >= max(3, len(split) / 2)}
    out = []
    for page_no, lines in enumerate(split, 1):
        idx = [i for i, ln in enumerate(lines) if ln.strip()]
        edges = set(idx[:3] + idx[-3:])
        keep = []
        for i, ln in enumerate(lines):
            if i in edges and _norm(ln) in repeated:
                removed["header/footer"] += 1
                continue
            m = LONE_PAGE_NO.match(ln)
            if i in (idx[:2] + idx[-2:]) and m and (m.group(1) or m.group(2)
                                                    or abs(int(re.search(r"\d+", ln).group()) - page_no) <= 3):
                removed["page number"] += 1
                continue
            if ln.strip() and not HAS_ALNUM.search(ln):
                removed["symbol-only line"] += 1
                continue
            new = LEADER_RUN.sub(" ", ln)
            if new != ln:
                removed["leader run"] += 1
            new = re.sub(r"^(\s*)#", r"\1\\#", new)  # a source line starting with '#' must not become a heading
            keep.append(new.rstrip())
        out.append(re.sub(r"\n{3,}", "\n\n", "\n".join(keep)).strip())
    return out, removed


# ---- redaction (team decision; see the module docstring) ----

STUDENT_TAG, CONTACT_TAG = "[student details removed]", "[contact removed]"
ENROL_ID = re.compile(r"\b[A-Z]{1,2}\d{2}[A-Z]{2,6}\d{2,4}\b|\bEnro\w*\.?\s*No\b.*\w\d", re.I)
HONORIFIC_LINE = re.compile(r"^\s*(\(?[ivx]+\)\s*\|?\s*)?(Ms|Mr|Mrs|Dr|Prof)\.?\s+[A-Z]", re.I)
MOBILE = re.compile(r"(?<!\d)(?:\+?91[\s-]?)?(?:[6-9]\d{9}|[6-9]\d{4}[\s-]\d{5}|[6-9]\d{3}[\s-]\d{6})(?!\d)")
EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
ROLE_MAILBOXES = {"registrar", "icc", "dsa", "finance", "ithelpdesk", "helpdesk", "info", "registry.comm",
                  "ops-helpdesk", "netid", "admissions", "admission", "antiragging", "registerar",
                  "thelpdesk"}  # the last two are OCR misreads of role mailboxes (registrar@, ithelpdesk@)
INSTITUTIONAL_LINE = re.compile(r"^\s*or call at\b", re.I)  # the handbook back cover (Office of Student Affairs)
CONTACTS_SLUG = "anti-ragging-and-sexual-harassment-contacts"


def redact(text: str, slug: str) -> tuple[str, Counter]:
    n = Counter()
    lines = text.split("\n")
    # students: a line with an enrolment number, and the name line just before it
    for i, ln in enumerate(lines):
        if ENROL_ID.search(ln):
            m = re.match(r"^(\s*\(?[ivx]+\)\s*\|?\s*)", ln)
            lines[i] = (m.group(1) if m else "") + STUDENT_TAG
            n["student (enrolment no.)"] += 1
            j = i - 1
            while j >= 0 and not lines[j].strip():
                j -= 1
            if j >= 0 and HONORIFIC_LINE.match(lines[j]) and not ENROL_ID.search(lines[j]):
                lines[j] = STUDENT_TAG
                n["student (name line)"] += 1
    # students in the contacts .md: '### Name' blocks naming a student member, and the blocks after it whose details
    # are cut off in the source (the other student members of the committee)
    if slug == CONTACTS_SLUG:
        blocks, cur = [], []
        for ln in lines:
            if ln.startswith("### ") and cur:
                blocks.append(cur)
                cur = []
            cur.append(ln)
        blocks.append(cur)
        seen_student = False
        for b in blocks:
            body = "\n".join(b)
            is_student = "Student Representative" in body
            if b[0].startswith("### ") and (is_student or (seen_student and "cut off in the provided image" in body)):
                b[0] = "### " + STUDENT_TAG
                for k in range(1, len(b)):
                    b[k] = re.sub(r"^(- \*\*(Email|Phone):\*\*).*$", r"\1 " + STUDENT_TAG, b[k])
                n["student (contacts block)"] += 1
                seen_student = seen_student or is_student
        lines = [ln for b in blocks for ln in b]
    text = "\n".join(lines)

    def _email(m):
        if m.group(0).split("@")[0].lower() in ROLE_MAILBOXES:
            return m.group(0)
        n["personal email"] += 1
        return CONTACT_TAG

    def _mobile(m):
        n["mobile number"] += 1
        return CONTACT_TAG

    text = EMAIL.sub(_email, text)
    text = "\n".join(ln if INSTITUTIONAL_LINE.match(ln) else MOBILE.sub(_mobile, ln) for ln in text.split("\n"))
    return text, n


# ---- build ----

def build_doc(doc: Doc, zip_dir: Path, ocr_dir: Path, pdftotext: str | None) -> tuple[str, dict]:
    """(file text, info) for one document; info has pages, text_source, cleaning and redaction counts."""
    path = zip_dir / doc.src
    if not path.is_file():
        raise SystemExit(f"missing source file: {doc.src} (is --zip-dir the unzipped 'yiti-ai data' folder?)")
    ocr = ocr_dir / (path.stem + ".txt")
    removed, red = Counter(), Counter()
    if path.suffix == ".md":
        kind, pages_n, pages = "original md", "", [path.read_text(encoding="utf-8").strip()]
    else:
        if ocr.exists():
            kind, raw = "ocr", ocr_pages(ocr)
        else:
            if not pdftotext:
                raise SystemExit(f"{doc.src} needs pdftotext: put it on PATH or pass --pdftotext")
            kind, raw = "pdf text", pdftotext_pages(path, pdftotext)
        pages, removed = clean(raw)
        pages_n = len(raw)
    for i, p in enumerate(pages):
        pages[i], c = redact(p, doc.slug)
        red += c
    body = pages[0] if kind == "original md" else \
        "\n\n".join(f"## Page {i}\n\n{t}" for i, t in enumerate(pages, 1) if t)
    meta = {"title": doc.title, "office": doc.office, "source_url": doc.source_url, "date": doc.date,
            "text_source": kind, "original_file": path.name}
    fm = yaml.safe_dump(meta, sort_keys=False, allow_unicode=True, width=1000)
    return f"---\n{fm}---\n\n{body}\n", {"pages": pages_n, "text_source": kind, "removed": dict(removed),
                                          "redacted": dict(red)}


def index_entry(doc: Doc) -> dict:
    return {"file": f"{doc.slug}.md", "title": doc.title, "source_url": doc.source_url, "date": doc.date,
            "public_or_permission": doc.provenance, "collector": COLLECTOR}


def manifest_csv(kb: Path, texts: dict[Path, str], pages: dict[Path, int | str]) -> str:
    """test-data/kb_manifest.csv: every kb/*/*.md (built texts override what is on disk)."""
    files = sorted(set(texts) | {p for p in kb.glob("*/*.md") if p.name != "INDEX.md"})
    rows = []
    for p in files:
        meta, body = split_front_matter(texts.get(p) or p.read_text(encoding="utf-8"))
        words = len(re.sub(r"^## Page \d+[ \t]*$", "", body.lstrip("\n"), flags=re.M).split())
        rows.append({"office": meta["office"], "title": meta["title"], "file": f"code/kb/{p.parent.name}/{p.name}",
                     "pages": pages.get(p, ""), "words": words, "text_source": meta["text_source"],
                     "date": meta["date"], "source_url": meta["source_url"]})
    rows.sort(key=lambda r: (r["office"], r["file"]))
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=list(rows[0]), lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
    return buf.getvalue()


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(prog="python -m tools.build_kb", description=__doc__.split("\n")[0])
    ap.add_argument("--zip-dir", type=Path, required=True, help="the unzipped 'yiti-ai data' folder")
    ap.add_argument("--ocr-dir", type=Path, required=True, help="folder of OCR .txt files with page markers")
    ap.add_argument("--pdftotext", default=shutil.which("pdftotext"), help="pdftotext executable (default: PATH)")
    ap.add_argument("--kb", type=Path, default=KB, help="knowledge base folder (default: code/kb)")
    ap.add_argument("--manifest", type=Path, default=TEST_DATA / "kb_manifest.csv")
    ap.add_argument("--check", action="store_true", help="write nothing; list files that would change (exit 1)")
    args = ap.parse_args(argv)

    outputs: dict[Path, str] = {}
    texts: dict[Path, str] = {}
    pages: dict[Path, int | str] = {}
    built: dict[str, list[dict]] = {}
    for doc in DOCS:
        text, info = build_doc(doc, args.zip_dir, args.ocr_dir, args.pdftotext)
        target = args.kb / doc.office / f"{doc.slug}.md"
        outputs[target] = texts[target] = text
        pages[target] = info["pages"]
        built.setdefault(doc.office, []).append(index_entry(doc))
        extra = {k: v for k, v in (("cleaned", info["removed"]), ("redacted", info["redacted"])) if v}
        print(f"{doc.office}/{doc.slug}.md  {info['text_source']}  pages={info['pages'] or '-'}  {extra or ''}")
    for office, entries in built.items():
        index = args.kb / office / "INDEX.md"
        outputs[index] = render_index(index.read_text(encoding="utf-8"), entries)
    outputs[args.manifest] = manifest_csv(args.kb, texts, pages)

    changed = [p for p, t in outputs.items() if not p.exists() or p.read_text(encoding="utf-8") != t]
    if args.check:
        print(f"\n{len(changed)} of {len(outputs)} files would change" + "".join(f"\n  {p}" for p in changed))
        return 1 if changed else 0
    for p in changed:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(outputs[p], encoding="utf-8", newline="\n")
    print(f"\nwrote {len(changed)} changed file(s) of {len(outputs)}" + "".join(f"\n  {p}" for p in changed))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
