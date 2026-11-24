"""Draw the five ZEN AI Milestone 2 design diagrams as PNGs next to this file.

Run from the repo root:  python docs/diagrams/draw_diagrams.py   (needs matplotlib only)

Every box names something that exists in the code (code/app.py, code/helpdesk/*.py, code/zenai/providers.py,
code/kb/, prompts/final/). Colours: blue = LLM prompt (one Gemini call), grey = code (no LLM call),
green = what the student sees, white = data or storage.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch  # noqa: E402

OUT = Path(__file__).resolve().parent
DPI = 200
FONT = "DejaVu Sans"

STYLE = {
    "prompt": dict(fc="#DBEAFE", ec="#1D4ED8"),   # LLM prompt
    "code": dict(fc="#F1F5F9", ec="#475569"),     # code, no LLM
    "out": dict(fc="#DCFCE7", ec="#15803D"),      # shown to the student
    "data": dict(fc="#FFFFFF", ec="#64748B"),     # data / storage
    "ext": dict(fc="#FEF3C7", ec="#B45309"),      # external service
}
INK = "#0F172A"
EDGE = "#334155"


def canvas(w: float, h: float, title: str):
    fig, ax = plt.subplots(figsize=(w, h))
    ax.set_xlim(0, w)
    ax.set_ylim(0, h)
    ax.axis("off")
    fig.patch.set_facecolor("white")
    ax.text(0.25, h - 0.3, title, fontsize=13, fontweight="bold", color=INK, va="top", family=FONT)
    return fig, ax


def box(ax, x, y, w, h, text, kind="code", size=9.0, bold_first=True):
    """Box centred at (x, y). The first line of text is bold when bold_first."""
    s = STYLE[kind]
    ax.add_patch(FancyBboxPatch((x - w / 2, y - h / 2), w, h, boxstyle="round,pad=0.02,rounding_size=0.12",
                                fc=s["fc"], ec=s["ec"], lw=1.4))
    lines = text.split("\n")
    if bold_first and len(lines) > 1:
        ax.text(x, y + 0.02, lines[0] + "\n" * (len(lines) - 1), ha="center", va="center", fontsize=size,
                fontweight="bold", color=INK, family=FONT, linespacing=1.35)
        ax.text(x, y + 0.02, "\n" + "\n".join(lines[1:]), ha="center", va="center", fontsize=size - 0.8,
                color=INK, family=FONT, linespacing=1.35)
    else:
        ax.text(x, y, text, ha="center", va="center", fontsize=size, color=INK, family=FONT,
                fontweight="bold" if bold_first else "normal", linespacing=1.35)
    return (x, y, w, h)


def anchor(b, side):
    x, y, w, h = b
    return {"t": (x, y + h / 2), "b": (x, y - h / 2), "l": (x - w / 2, y), "r": (x + w / 2, y)}[side]


def arrow(ax, p, q, label=None, lpos=0.5, rad=0.0, loff=(0.0, 0.0), dashed=False):
    ax.add_patch(FancyArrowPatch(p, q, arrowstyle="-|>", mutation_scale=12, color=EDGE, lw=1.2,
                                 connectionstyle=f"arc3,rad={rad}", linestyle="--" if dashed else "-",
                                 shrinkA=2, shrinkB=2))
    if label:
        lx = p[0] + (q[0] - p[0]) * lpos + loff[0]
        ly = p[1] + (q[1] - p[1]) * lpos + loff[1]
        ax.text(lx, ly, label, ha="center", va="center", fontsize=7.6, color="#1E293B", family=FONT,
                bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none"))


def legend(ax, x, y, kinds):
    names = {"prompt": "LLM prompt (one Gemini call)", "code": "Code, no LLM call", "out": "Shown to the student",
             "data": "Data / storage", "ext": "External service"}
    for i, k in enumerate(kinds):
        s = STYLE[k]
        ax.add_patch(FancyBboxPatch((x + i * 2.55, y - 0.09), 0.28, 0.18, boxstyle="round,pad=0.01,rounding_size=0.04",
                                    fc=s["fc"], ec=s["ec"], lw=1.2))
        ax.text(x + i * 2.55 + 0.38, y, names[k], fontsize=7.6, va="center", color=INK, family=FONT)


def save(fig, name):
    fig.savefig(OUT / name, dpi=DPI, bbox_inches="tight", facecolor="white")
    plt.close(fig)


# 1. Prompt workflow --------------------------------------------------------------------------------------------
def prompt_workflow():
    fig, ax = canvas(12, 8.2, "1. Prompt workflow (pipeline.final_answer)")
    q = box(ax, 1.6, 6.9, 2.4, 0.75, "Student question\nEnglish or Hinglish", "data")
    e = box(ax, 4.7, 6.9, 2.3, 0.75, "Empty input?\ncode", "code")
    cl0 = box(ax, 4.7, 5.55, 2.3, 0.75, "Clarify\nfixed text, no LLM", "out")
    p1 = box(ax, 8.1, 6.9, 2.9, 0.95, "P1 router v2\ndomain, request_type,\nEnglish search_query", "prompt")
    arrow(ax, anchor(q, "r"), anchor(e, "l"))
    arrow(ax, anchor(e, "b"), anchor(cl0, "t"), "yes", 0.45)
    arrow(ax, anchor(e, "r"), anchor(p1, "l"), "no", 0.5)

    ref = box(ax, 7.25, 5.3, 1.8, 0.75, "Refuse\nfixed text", "out")
    cla = box(ax, 9.3, 5.3, 1.8, 0.75, "Clarify\nfixed text", "out")
    arrow(ax, (7.25, 6.42), anchor(ref, "t"), "not_campus", 0.5)
    arrow(ax, (9.1, 6.42), anchor(cla, "t"), "vague", 0.5)

    s = box(ax, 4.7, 4.0, 3.1, 0.95, "BM25 search (kb_search)\ntop 5 from the routed folder\n+ top 3 from all folders", "code")
    arrow(ax, (7.0, 6.42), anchor(s, "t"), "info", 0.45, loff=(-0.2, 0.0))

    p2 = box(ax, 4.7, 2.55, 3.1, 0.95, "P2 grounded answer v2\nJSON: found, answer, quote,\ndoc_title, page, language", "prompt")
    arrow(ax, anchor(s, "b"), anchor(p2, "t"), "8 sections", 0.5)
    qc = box(ax, 4.7, 1.1, 3.1, 0.85, "Quote check (check_quote)\nquote found word for word in a section?", "code")
    arrow(ax, anchor(p2, "b"), anchor(qc, "t"), "found = true", 0.5)

    ans = box(ax, 1.55, 1.1, 2.4, 0.95, "Answer\nwith quote, document,\npage, verified badge", "out")
    arrow(ax, anchor(qc, "l"), anchor(ans, "r"), "verified", 0.5)

    nf = box(ax, 8.0, 2.55, 2.0, 0.75, "not_found\ncode decision", "code")
    arrow(ax, anchor(p2, "r"), anchor(nf, "l"), "found = false", 0.5)
    arrow(ax, anchor(qc, "r"), (8.0, 2.17), "not verified", 0.45, rad=0.25, loff=(0.0, -0.18))

    p3 = box(ax, 10.75, 3.75, 2.3, 0.95, "P3 handoff draft v2\nJSON: to, subject, body", "prompt")
    arrow(ax, anchor(nf, "r"), (10.0, 3.27), None, rad=0.25)
    arrow(ax, anchor(p1, "r"), (11.4, 4.23), "needs_human /\nunusable reply", 0.55, rad=-0.3, loff=(0.45, 0.1))
    dr = box(ax, 10.75, 1.1, 2.3, 0.95, "Email draft\n\"Draft only.\nNothing is sent.\"", "out")
    arrow(ax, anchor(p3, "b"), anchor(dr, "t"))
    legend(ax, 0.3, 0.15, ["prompt", "code", "out", "data"])
    save(fig, "1_prompt_workflow.png")


# 2. Task decomposition -----------------------------------------------------------------------------------------
def task_decomposition():
    fig, ax = canvas(12, 5.6, "2. Task decomposition: which part is a prompt and which is code")
    root = box(ax, 6.0, 4.45, 6.2, 0.7, "Answer one campus question from official documents", "data", bold_first=True,
               size=9.5)
    tasks = [
        ("Route", "prompt", "P1 router v2\noffice (domain)\nrequest type\nEnglish search query\nsplit into topics"),
        ("Retrieve", "code", "kb_search.py\nBM25 over\n1,149 chunks\n5 routed + 3 all"),
        ("Answer", "prompt", "P2 answer v2\nonly from the\n8 sections\ncopy the exact quote\nreply language"),
        ("Verify", "code", "check_quote\nnormalise ** __,\nOCR hyphens, spaces\nreject if not found"),
        ("Hand off", "prompt", "P3 handoff v2\nemail to the office\nplaceholders\nunder 120 words\nnever sent"),
        ("Refuse / clarify", "code", "fixed text\nhandoff.py\nempty input:\npipeline.py\nno LLM call"),
    ]
    xs = [1.05 + i * 1.98 for i in range(6)]
    for x, (name, kind, detail) in zip(xs, tasks):
        b = box(ax, x, 2.75, 1.8, 0.62, name + ("\nprompt" if kind == "prompt" else "\ncode"), kind)
        arrow(ax, (x * 0.35 + 6.0 * 0.65, 4.1), anchor(b, "t"))
        d = box(ax, x, 1.35, 1.85, 1.55, detail, "data", size=8.0, bold_first=True)
        arrow(ax, anchor(b, "b"), anchor(d, "t"))
    legend(ax, 0.3, 0.15, ["prompt", "code", "data"])
    save(fig, "2_task_decomposition.png")


# 3. Input-output flow ------------------------------------------------------------------------------------------
def io_flow():
    fig, ax = canvas(12, 7.8, "3. Input-output flow: the fields each prompt takes and returns")
    rows = [6.35, 3.95, 1.55]
    ins = [
        "P1 input\nsystem: prompts/final/P1_router.md\nuser: \"Student message: <message>\"",
        "P2 input (one user message)\n{question}: the student's message\n{sections}: 8 chunks, each with\nDocument | Office | Page | Source",
        "P3 input (one user message)\n{question}, {office},\n{office_email} (demo address),\n{reason}: not found in documents |\nneeds the student's own record |\nneeds someone to act",
    ]
    prompts = ["P1 router v2", "P2 grounded answer v2", "P3 handoff draft v2"]
    outs = [
        "P1 output (JSON)\n{\"topics\": [{\"text\", \"domain\",\n\"request_type\", \"search_query\",\n\"reason\"}]}",
        "P2 output (JSON)\n{\"found\", \"answer\", \"quote\",\n\"doc_title\", \"page\", \"language\"}",
        "P3 output (JSON)\n{\"to\", \"subject\", \"body\"}\nbody ends with [Your name]\n[Enrollment no.]",
    ]
    ob = []
    for y, i, p, o in zip(rows, ins, prompts, outs):
        bi = box(ax, 2.2, y, 3.9, 1.45, i, "data", size=8.6)
        bp = box(ax, 5.55, y, 2.2, 0.6, p, "prompt", bold_first=False, size=8.8)
        bo = box(ax, 9.25, y, 4.3, 1.3, o, "data", size=8.6)
        arrow(ax, anchor(bi, "r"), anchor(bp, "l"))
        arrow(ax, anchor(bp, "r"), anchor(bo, "l"))
        ob.append((bi, bo))
    c1 = box(ax, 6.0, 5.15, 7.0, 0.48, "Code: first topic's domain + search_query -> BM25 search -> {sections}", "code",
             size=8.2, bold_first=False)
    c2 = box(ax, 6.0, 2.75, 7.0, 0.48, "Code: quote check on \"quote\"; found=false or not verified -> P3, office from domain",
             "code", size=8.2, bold_first=False)
    arrow(ax, anchor(ob[0][1], "b"), (8.8, 5.39))
    arrow(ax, (2.6, 4.91), (2.6, 4.68))
    arrow(ax, anchor(ob[1][1], "b"), (8.8, 2.99))
    arrow(ax, (2.6, 2.51), (2.6, 2.28))
    legend(ax, 0.3, 0.2, ["prompt", "code", "data"])
    save(fig, "3_input_output_flow.png")


# 4. System architecture ----------------------------------------------------------------------------------------
def architecture():
    fig, ax = canvas(12, 6.4, "4. System architecture")
    br = box(ax, 1.5, 4.6, 2.2, 0.8, "Student's browser\nno login", "data")
    app = box(ax, 4.75, 4.6, 3.3, 1.35, "Streamlit app (code/app.py)\nStreamlit Community Cloud\nst.cache_data per question\n20 questions per session", "code")
    sec = box(ax, 4.6, 2.85, 2.9, 0.85, "Streamlit Secrets / .env\nGEMINI_API_KEY (never in git)", "data")
    pipe = box(ax, 8.7, 4.6, 3.5, 1.35, "Helpdesk pipeline (code/helpdesk/)\npipeline.final_answer: router_v2,\nkb_search, check_quote, handoff", "code")
    prm = box(ax, 8.7, 6.0 - 0.15, 3.5, 0.6, "prompts/final/ (P1, P2, P3)\nconfig/offices.yaml, mailbox_map.yaml", "data",
              size=8.0, bold_first=False)
    prov = box(ax, 8.7, 2.85, 3.5, 0.95, "Provider (code/zenai/providers.py)\ndisk cache, rate limit, daily cap", "code")
    gem = box(ax, 8.7, 1.1, 3.5, 0.85, "Gemini API\ngemini-3.5-flash-lite, temperature 0", "ext")
    idx = box(ax, 4.75, 1.1, 3.3, 0.95, "KB index (BM25, 1,149 chunks)\ncached in code/.cache/kb_search/", "data")
    kb = box(ax, 1.5, 1.1, 2.2, 0.95, "code/kb/\n25 documents\n(Markdown)", "data")
    dc = box(ax, 11.3, 2.85, 1.3, 0.85, "Disk cache\n.cache/", "data", size=8.4)
    arrow(ax, anchor(br, "r"), anchor(app, "l"), "question", 0.5)
    arrow(ax, anchor(sec, "t"), anchor(app, "b"), "API key", 0.5)
    arrow(ax, anchor(app, "r"), anchor(pipe, "l"), "final_answer()", 0.5)
    arrow(ax, anchor(prm, "b"), anchor(pipe, "t"))
    arrow(ax, anchor(pipe, "b"), anchor(prov, "t"), "P1 / P2 / P3", 0.5)
    arrow(ax, anchor(prov, "b"), anchor(gem, "t"), "on cache miss", 0.5)
    arrow(ax, anchor(prov, "r"), anchor(dc, "l"))
    arrow(ax, (7.15, 3.92), (6.3, 1.58), "search", 0.62, loff=(-0.3, 0.0))
    arrow(ax, anchor(kb, "r"), anchor(idx, "l"), "build_chunks", 0.5)
    legend(ax, 0.3, 0.15, ["code", "data", "ext"])
    save(fig, "4_system_architecture.png")


# 5. RAG pipeline -----------------------------------------------------------------------------------------------
def rag_pipeline():
    fig, ax = canvas(12, 5.4, "5. RAG pipeline: from official documents to P2")
    a = box(ax, 1.3, 3.7, 2.1, 1.1, "25 official\nBennett documents\nPDF, web page, .md", "data")
    b = box(ax, 3.95, 3.7, 2.6, 1.1, "tools/build_kb.py\nOCR text (11 scanned PDFs),\nPDF text (11), HTML (1), .md (2)", "code")
    c = box(ax, 6.75, 3.7, 2.4, 1.1, "Markdown in code/kb/\n<OFFICE>/*.md\n\"## Page N\", title,\nsource_url, date", "data")
    d = box(ax, 9.45, 3.7, 2.4, 1.1, "build_chunks\nsplit by page; > 350 words\nsplit by paragraph\n= 1,149 chunks", "code")
    e = box(ax, 9.45, 1.85, 2.4, 0.95, "BM25Okapi index\nlowercase tokens,\nEnglish + Hinglish stop words", "code")
    q = box(ax, 1.3, 1.85, 2.1, 0.95, "P1 v2 output\nsearch_query (English)\n+ domain", "prompt")
    m = box(ax, 4.45, 1.85, 3.2, 0.95, "search_routed_plus_all\ntop 5 from the routed folder\n+ top 3 from all other chunks", "code")
    f = box(ax, 6.75, 0.85, 2.4, 0.62, "format_sections\n8 labelled sections", "code", size=8.6)
    p2 = box(ax, 9.45, 0.85, 2.4, 0.62, "P2 grounded answer v2", "prompt", bold_first=False)
    arrow(ax, anchor(a, "r"), anchor(b, "l"))
    arrow(ax, anchor(b, "r"), anchor(c, "l"))
    arrow(ax, anchor(c, "r"), anchor(d, "l"))
    arrow(ax, anchor(d, "b"), anchor(e, "t"))
    arrow(ax, anchor(q, "r"), anchor(m, "l"))
    arrow(ax, anchor(e, "l"), anchor(m, "r"), "ranked chunks", 0.5)
    arrow(ax, (5.2, 1.37), anchor(f, "l"), rad=0.15)
    arrow(ax, anchor(f, "r"), anchor(p2, "l"))
    legend(ax, 0.3, 0.12, ["prompt", "code", "data"])
    save(fig, "5_rag_pipeline.png")


if __name__ == "__main__":
    prompt_workflow()
    task_decomposition()
    io_flow()
    architecture()
    rag_pipeline()
    print("wrote", sorted(p.name for p in OUT.glob("*.png")))
