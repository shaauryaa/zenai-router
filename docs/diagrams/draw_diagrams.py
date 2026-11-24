"""Draw the five ZEN AI Milestone 2 design diagrams (final pipeline, tag m2-final-24nov) as PNGs next to this file.

Run from the repo root:  python docs/diagrams/draw_diagrams.py   (needs matplotlib only)

Every box names something that exists in the code (code/app.py, code/helpdesk/*.py, code/zenai/providers.py,
code/kb/, prompts/final/). Final pipeline = pipeline.FINAL: P1 v2 router, programme-aware search routed5_all3_prog,
P2 v2, quote check v2 (tightened), P3 v2, two topics per message, safety card (helpdesk/safety.py) and the clarify
follow-up (helpdesk/followup.py). Colours: sky = LLM prompt (one Gemini call), grey = code (no LLM call),
green = what the student sees, pink = safety, white = data, amber = external service.
The canvases are small on purpose: the PDF shows two diagrams per row, so text must stay readable at that size.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch  # noqa: E402

OUT = Path(__file__).resolve().parent
DPI = 220
FONT = "DejaVu Sans"

STYLE = {
    "prompt": dict(fc="#E3F4FB", ec="#0593C6"),   # LLM prompt
    "code": dict(fc="#F1F5F9", ec="#475569"),     # code, no LLM
    "out": dict(fc="#E8F7EE", ec="#15803D"),      # shown to the student
    "safe": dict(fc="#FCE8F3", ec="#D83995"),     # safety card
    "data": dict(fc="#FFFFFF", ec="#64748B"),     # data / storage
    "ext": dict(fc="#FEF3C7", ec="#B45309"),      # external service
}
INK = "#0F172A"
EDGE = "#334155"
NAMES = {"prompt": "LLM prompt", "code": "Code, no LLM", "out": "Shown to student",
         "safe": "Safety", "data": "Data", "ext": "External service"}


def canvas(w: float, h: float, title: str):
    fig, ax = plt.subplots(figsize=(w, h))
    ax.set_xlim(0, w)
    ax.set_ylim(0, h)
    ax.axis("off")
    fig.patch.set_facecolor("white")
    ax.text(0.08, h - 0.08, title, fontsize=11.5, fontweight="bold", color=INK, va="top", family=FONT)
    return fig, ax


def box(ax, x, y, w, h, text, kind="code", size=8.6, bold=True):
    """Box centred at (x, y); the first line is bold."""
    s = STYLE[kind]
    ax.add_patch(FancyBboxPatch((x - w / 2, y - h / 2), w, h, boxstyle="round,pad=0.015,rounding_size=0.07",
                                fc=s["fc"], ec=s["ec"], lw=1.2))
    lines = text.split("\n")
    head, rest = lines[0], lines[1:]
    if not bold:
        ax.text(x, y, text, ha="center", va="center", fontsize=size - 0.6, color=INK, family=FONT, linespacing=1.25)
    elif rest:
        ax.text(x, y, head + "\n" * len(rest), ha="center", va="center", fontsize=size, fontweight="bold",
                color=INK, family=FONT, linespacing=1.25)
        ax.text(x, y, "\n" + "\n".join(rest), ha="center", va="center", fontsize=size - 0.9, color=INK,
                family=FONT, linespacing=1.25)
    else:
        ax.text(x, y, head, ha="center", va="center", fontsize=size, fontweight="bold", color=INK, family=FONT)
    return (x, y, w, h)


def at(b, side, f=0.5):
    x, y, w, h = b
    return {"t": (x - w / 2 + w * f, y + h / 2), "b": (x - w / 2 + w * f, y - h / 2),
            "l": (x - w / 2, y - h / 2 + h * f), "r": (x + w / 2, y - h / 2 + h * f)}[side]


def arrow(ax, p, q, label=None, lpos=0.5, rad=0.0, loff=(0.0, 0.0), size=7.4):
    ax.add_patch(FancyArrowPatch(p, q, arrowstyle="-|>", mutation_scale=10, color=EDGE, lw=1.0,
                                 connectionstyle=f"arc3,rad={rad}", shrinkA=1.5, shrinkB=1.5))
    if label:
        lx = p[0] + (q[0] - p[0]) * lpos + loff[0]
        ly = p[1] + (q[1] - p[1]) * lpos + loff[1]
        ax.text(lx, ly, label, ha="center", va="center", fontsize=size, color="#1E293B", family=FONT,
                bbox=dict(boxstyle="round,pad=0.12", fc="white", ec="none"))


def legend(ax, x, y, kinds, step=1.55):
    for i, k in enumerate(kinds):
        s = STYLE[k]
        ax.add_patch(FancyBboxPatch((x + i * step, y - 0.06), 0.2, 0.12, boxstyle="round,pad=0.01,rounding_size=0.03",
                                    fc=s["fc"], ec=s["ec"], lw=1.0))
        ax.text(x + i * step + 0.27, y, NAMES[k], fontsize=7.2, va="center", color=INK, family=FONT)


def save(fig, name):
    fig.savefig(OUT / name, dpi=DPI, bbox_inches="tight", pad_inches=0.06, facecolor="white")
    plt.close(fig)


# 1. Prompt workflow --------------------------------------------------------------------------------------------
def prompt_workflow():
    fig, ax = canvas(7.55, 5.3, "1. Prompt workflow (pipeline.final_answer)")
    msg = box(ax, 1.0, 4.55, 1.75, 0.6, "Student message\nEnglish or Hinglish", "data")
    fu = box(ax, 3.25, 4.55, 2.2, 0.6, "Follow-up join (code)\nafter a clarify: reply <= 8 words\njoined to last question", "code", 8.2)
    p1 = box(ax, 5.95, 4.55, 2.55, 0.66, "P1 router v2\nsplits up to 2 questions; each\ngets office, request type, query", "prompt", 8.2)
    arrow(ax, at(msg, "r"), at(fu, "l"))
    arrow(ax, at(fu, "r"), at(p1, "l"))

    saf = box(ax, 0.9, 3.05, 1.5, 0.62, "Safety card\ncontacts copied\nfrom the KB", "safe", 8.2)
    ref = box(ax, 2.45, 3.05, 1.35, 0.62, "Refuse\nfixed text", "out", 8.2)
    cla = box(ax, 3.9, 3.05, 1.35, 0.62, "Clarify\nfixed text", "out", 8.2)
    se = box(ax, 5.95, 3.05, 2.55, 0.7, "Programme-aware search\nBM25: top 5 routed (named\nprogramme's rules) + top 3 all", "code", 8.2)
    arrow(ax, at(p1, "b", 0.15), at(saf, "t", 0.7), "report", 0.5, size=7)
    arrow(ax, at(p1, "b", 0.25), at(ref, "t", 0.6), "not_campus", 0.55, size=7)
    arrow(ax, at(p1, "b", 0.35), at(cla, "t", 0.6), "vague / empty", 0.55, size=7)
    arrow(ax, at(p1, "b", 0.6), at(se, "t", 0.6), "info", 0.5, size=7)

    p2 = box(ax, 5.95, 1.85, 2.55, 0.62, "P2 grounded answer v2\nJSON: found, answer, quote,\ndoc_title, page, language", "prompt", 8.2)
    arrow(ax, at(se, "b"), at(p2, "t"), "8 sections", 0.5, size=7)
    qc = box(ax, 3.45, 1.85, 2.2, 0.62, "Quote check v2 (code)\nexact or tight near match\nin a retrieved section?", "code", 8.2)
    arrow(ax, at(p2, "l"), at(qc, "r"), "found", 0.5, size=7)
    ans = box(ax, 1.25, 1.85, 1.65, 0.7, "Answer\nquote, document, page\n+ source badges", "out", 8.2)
    arrow(ax, at(qc, "l"), at(ans, "r"), "verified", 0.5, loff=(0, 0.2), size=7)

    p3 = box(ax, 4.6, 0.62, 2.3, 0.62, "P3 handoff draft v2\nJSON: to, subject, body", "prompt", 8.2)
    dr = box(ax, 1.95, 0.62, 2.3, 0.62, "Email draft to the office\n\"Draft only, nothing is sent\"", "out", 8.2)
    arrow(ax, at(qc, "b"), at(p3, "t", 0.2), "not verified", 0.45, size=7)
    arrow(ax, at(p2, "b", 0.3), at(p3, "t", 0.8), "not found", 0.5, size=7)
    ax.plot([at(p1, "r")[0], 7.4, 7.4], [4.55, 4.55, 0.62], color=EDGE, lw=1.0)
    ax.add_patch(FancyArrowPatch((7.4, 0.62), at(p3, "r"), arrowstyle="-|>", mutation_scale=10, color=EDGE, lw=1.0))
    ax.text(7.4, 2.5, "needs_human", rotation=90, fontsize=7, ha="center", va="center", family=FONT,
            bbox=dict(boxstyle="round,pad=0.1", fc="white", ec="none"))
    ax.plot([0.25, 0.25, 0.42], [2.74, 0.62, 0.62], color=EDGE, lw=1.0)
    ax.add_patch(FancyArrowPatch((0.42, 0.62), at(dr, "l"), arrowstyle="-|>", mutation_scale=10, color=EDGE, lw=1.0))
    ax.text(0.25, 1.3, "then P3\ndraft", fontsize=7, ha="center", va="center", family=FONT, bbox=dict(fc="white", ec="none", pad=0.6))
    arrow(ax, at(p3, "l"), at(dr, "r"))
    legend(ax, 0.05, 0.08, ["prompt", "code", "out", "safe"], step=1.75)
    save(fig, "1_prompt_workflow.png")


# 2. Task decomposition -----------------------------------------------------------------------------------------
def task_decomposition():
    fig, ax = canvas(7.4, 4.7, "2. Task decomposition: prompts (sky) and code (grey)")
    root = box(ax, 3.7, 4.0, 6.9, 0.42, "Answer a campus question from official documents, or hand it to an office", "data", 8.4)
    tasks = [
        ("1 Route + split", "prompt", "P1 v2: office,\nrequest type, English\nquery, up to 2 topics"),
        ("2 Safety check", "code", "safety.py: report?\ncard of contacts\ncopied from the KB"),
        ("3 Retrieve", "code", "kb_search.py BM25\n1,149 chunks; named\nprogramme's rules"),
        ("4 Answer", "prompt", "P2 v2: only from\n8 sections, exact\nquote, reply language"),
        ("5 Verify", "code", "quote check v2:\nnumbers, negations\n+ source badges"),
        ("6 Hand off", "prompt", "P3 v2: email to the\nright office, under\n120 words, never sent"),
        ("7 Refuse / clarify", "code", "fixed text, no LLM;\nfollow-up joins a\nshort reply"),
        ("8 Show steps", "code", "app.py chat UI:\n\"How ZEN AI decided\"\npanel per answer"),
    ]
    for i, (name, kind, detail) in enumerate(tasks):
        r, c = divmod(i, 4)
        x = 0.95 + c * 1.83
        y = 3.05 - r * 1.75
        b = box(ax, x, y, 1.7, 0.36, name, kind, 8.4)
        d = box(ax, x, y - 0.68, 1.7, 0.82, detail, "data", 8.4, bold=False)
        arrow(ax, at(b, "b"), at(d, "t"))
        if r == 0:
            arrow(ax, at(root, "b", 0.1 + 0.27 * c), at(b, "t"))
    legend(ax, 0.05, 0.08, ["prompt", "code", "data"], step=1.75)
    save(fig, "2_task_decomposition.png")


# 3. Input-output flow ------------------------------------------------------------------------------------------
def io_flow():
    fig, ax = canvas(7.4, 4.9, "3. Input-output flow: what each prompt takes and returns")
    rows = [3.95, 2.45, 0.95]
    ins = [
        "P1 input\nsystem: prompts/final/P1_router.md\nuser: \"Student message: {message}\"",
        "P2 input (one user message)\n{question}: the topic's own text\n{sections}: 8 labelled chunks\n(Document | Office | Page | Source)",
        "P3 input (one user message)\n{question}, {office}, {office_email}\n{reason}: not found | own record |\nsomeone must act",
    ]
    prompts = ["P1 router v2", "P2 answer v2", "P3 handoff v2"]
    outs = [
        "P1 output (JSON)\n{\"topics\": [{text, domain,\nrequest_type, search_query, reason}]}",
        "P2 output (JSON)\n{found, answer, quote,\ndoc_title, page, language}",
        "P3 output (JSON)\n{to, subject, body}; body ends\n[Your name] / [Enrollment no.]",
    ]
    for y, i, p, o in zip(rows, ins, prompts, outs):
        bi = box(ax, 1.35, y, 2.6, 0.95, i, "data", 8.0)
        bp = box(ax, 3.65, y, 1.45, 0.42, p, "prompt", 8.3)
        bo = box(ax, 5.95, y, 2.75, 0.85, o, "data", 8.0)
        arrow(ax, at(bi, "r"), at(bp, "l"))
        arrow(ax, at(bp, "r"), at(bo, "l"))
    box(ax, 3.7, 3.2, 7.1, 0.3, "code: per topic, search_query + domain + programme -> BM25 -> {sections}", "code", 8.2, bold=False)
    box(ax, 3.7, 1.7, 7.1, 0.3, "code: quote check v2 on \"quote\"; found=false or not verified -> P3, office from domain", "code", 8.2, bold=False)
    legend(ax, 0.05, 0.12, ["prompt", "code", "data"], step=1.75)
    save(fig, "3_input_output_flow.png")


# 4. System architecture ----------------------------------------------------------------------------------------
def architecture():
    fig, ax = canvas(7.4, 4.5, "4. System architecture")
    br = box(ax, 0.85, 3.35, 1.6, 0.7, "Browser\nno login,\nno chats stored", "data", 8.0)
    app = box(ax, 3.4, 3.35, 2.75, 0.95, "Streamlit chat app (app.py)\nsuggestion cards, office shortcuts,\nsafety card, source badges,\n\"How ZEN AI decided\" panel", "code", 8.0)
    pipe = box(ax, 6.2, 3.35, 2.2, 0.95, "Helpdesk pipeline\ncode/helpdesk/: router_v2,\nkb_search, check_quote,\nsafety, followup, handoff", "code", 8.0)
    prm = box(ax, 5.95, 1.95, 1.7, 0.55, "prompts/final/\nP1, P2, P3; offices", "data", 8.0)
    prov = box(ax, 3.35, 1.95, 2.75, 0.6, "Provider (zenai/providers.py)\ndisk cache, rate limit, daily cap", "code", 8.0)
    gem = box(ax, 3.35, 0.7, 2.75, 0.55, "Gemini API\ngemini-3.5-flash-lite, temperature 0", "ext", 8.0)
    idx = box(ax, 6.2, 0.7, 2.2, 0.55, "BM25 index, 1,149 chunks\nfrom 25 documents (code/kb/)", "data", 8.0)
    sec = box(ax, 0.85, 1.95, 1.6, 0.6, "Streamlit Secrets\nGEMINI_API_KEY\n(never in git)", "data", 8.0)
    arrow(ax, at(br, "r"), at(app, "l"), "question", 0.5, size=7)
    arrow(ax, at(app, "r"), at(pipe, "l"))
    arrow(ax, at(prm, "t"), (5.95, 2.875))
    arrow(ax, at(pipe, "b", 0.1), at(prov, "r", 0.8), "P1/P2/P3", 0.5, size=7)
    arrow(ax, at(prov, "b"), at(gem, "t"), "on cache miss", 0.5, size=7)
    arrow(ax, at(pipe, "b", 0.93), (7.15, 0.98), "search", 0.5, size=7)
    arrow(ax, at(sec, "r"), at(prov, "l"), "key", 0.5, size=7)
    legend(ax, 0.05, 0.08, ["code", "data", "ext"], step=1.75)
    save(fig, "4_system_architecture.png")


# 5. RAG pipeline -----------------------------------------------------------------------------------------------
def rag_pipeline():
    fig, ax = canvas(7.4, 4.3, "5. RAG pipeline: official documents to a verified answer")
    a = box(ax, 0.95, 3.25, 1.65, 0.8, "25 official\nBennett documents\nPDF, web page, .md", "data", 8.0)
    b = box(ax, 2.85, 3.25, 1.85, 0.8, "tools/build_kb.py\nOCR (11), PDF text (11),\nHTML (1), Markdown (2)", "code", 8.0)
    c = box(ax, 4.75, 3.25, 1.75, 0.8, "Markdown in code/kb/\n\"## Page N\", title,\nsource URL, date", "data", 8.0)
    d = box(ax, 6.55, 3.25, 1.6, 0.8, "build_chunks\nby page; > 350 words\nby paragraph: 1,149", "code", 8.0)
    e = box(ax, 6.55, 1.95, 1.6, 0.7, "BM25 index\nEnglish + Hinglish\nstop words", "code", 8.0)
    q = box(ax, 0.95, 1.95, 1.65, 0.7, "P1 v2 output\nEnglish search_query,\ndomain", "prompt", 8.0)
    m = box(ax, 3.8, 1.95, 3.0, 0.7, "routed5_all3_prog\ntop 5 from the routed folder (a named\nprogramme: its rules only) + top 3 all", "code", 8.0)
    p2 = box(ax, 2.0, 0.6, 1.9, 0.55, "P2 answer v2\n8 labelled sections", "prompt", 8.0)
    v = box(ax, 4.6, 0.6, 2.2, 0.55, "Quote check v2\nexact or tight near match", "code", 8.0)
    o = box(ax, 6.65, 0.6, 1.4, 0.55, "Answer\n+ source badges", "out", 8.0)
    arrow(ax, at(a, "r"), at(b, "l"))
    arrow(ax, at(b, "r"), at(c, "l"))
    arrow(ax, at(c, "r"), at(d, "l"))
    arrow(ax, at(d, "b"), at(e, "t"))
    arrow(ax, at(q, "r"), at(m, "l"))
    arrow(ax, at(e, "l"), at(m, "r"), "ranked", 0.5, size=7)
    arrow(ax, at(m, "b", 0.2), at(p2, "t", 0.7))
    arrow(ax, at(p2, "r"), at(v, "l"))
    arrow(ax, at(v, "r"), at(o, "l"))
    legend(ax, 0.05, 0.08, ["prompt", "code", "data", "out"], step=1.75)
    save(fig, "5_rag_pipeline.png")


if __name__ == "__main__":
    prompt_workflow()
    task_decomposition()
    io_flow()
    architecture()
    rag_pipeline()
    print("wrote", sorted(p.name for p in OUT.glob("*.png")))
