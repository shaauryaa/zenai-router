"""ZEN AI: Campus Helpdesk (Streamlit chat UI). Run from the repo root:  streamlit run code/app.py

The final pipeline (helpdesk.pipeline.final_answer, pipeline.FINAL): P1 v2 router -> BM25 search (5 routed, or 5 from
the named programme's rules for an academic question, + 3 all) -> P2 grounded answer -> code quote check -> P3 handoff
draft (not_found, handoff) or fixed text (refuse, clarify). A message with two topics gets one section per topic.
API key: st.secrets["GEMINI_API_KEY"], else the environment (.env locally). Nothing is ever sent by email.
Look and feel: light-only theme in .streamlit/config.toml plus the small scoped CSS in app_css(). The UI never
changes what the pipeline does: StepProvider only watches the provider calls to show live progress.
"""
from __future__ import annotations

import html
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # code/ on the path, wherever streamlit is started

import streamlit as st  # noqa: E402

from helpdesk import followup, handoff, kb_search, pipeline, safety  # noqa: E402
from zenai.config import load_config  # noqa: E402
from zenai.providers import ProviderError, QuotaError  # noqa: E402

MAX_QUESTIONS = 20
FOOTER = "Answers come only from official Bennett University documents. Drafts are never sent automatically."
# Suggestion cards only fill the message box; nothing runs until the student presses Send or Enter.
# Each is a test-data/questions.csv question (Q01, Q04, Q13, Q12) that passes in run final_20261124-181511, so its
# verified answer is already in the provider cache.
SUGGESTIONS = [
    ("Fees", ":material/payments:",
     "I'm in first year and thinking of cancelling my admission in mid October. Will I get my full fee back?"),
    ("Outpass", ":material/door_open:", "Do I need an out pass to go out of campus on a Sunday afternoon?"),
    ("Hostel", ":material/translate:", "kya mere parents mere hostel room mein aa sakte hain?"),
    ("Academics", ":material/school:",
     "How do I raise a request with the Registrar's office online, like for a bonafide certificate?"),
]
OFFICE_CHIPS = [("Fees", "About fees: "), ("Hostel", "About the hostel: "), ("IT", "About IT and wifi: "),
                ("Academics", "About academics: "), ("Student support", "About student support: ")]
STEPS = ["Routing", "Searching", "Answering", "Checking quote"]
DRAFT_STEP = "Writing email draft"
# Copy button for the email draft: one delegated click listener, added once per page (st.html runs it in the page,
# so the clipboard is available). Falls back to a hidden textarea where navigator.clipboard is missing (plain http).
COPY_SCRIPT = """<script>
if (!window.__zenCopy) {
  window.__zenCopy = true;
  document.addEventListener("click", (ev) => {
    const b = ev.target.closest && ev.target.closest(".zen-copy");
    if (!b) return;
    const t = b.dataset.text || "", l = b.querySelector(".lbl");
    const done = () => { l.textContent = "Copied"; setTimeout(() => { l.textContent = "Copy draft"; }, 1600); };
    if (navigator.clipboard && window.isSecureContext) { navigator.clipboard.writeText(t).then(done); return; }
    const a = document.createElement("textarea"); a.value = t; document.body.appendChild(a); a.select();
    document.execCommand("copy"); a.remove(); done();
  });
}
</script>"""

# Colours the theme cannot express (light mode only).
TOKENS = {"sky": "#0593C6", "link": "#0479A6", "pink": "#D83995", "muted": "#5B6B78", "card": "#FFFFFF", "border": "#E6EDF2",
          "bubble": "#E9F6FC", "bubble_text": "#14212B", "quote": "#F5F9FB", "red": "#B42318",
          "red_bg": "#FDF1EF", "amber": "#B45309", "amber_text": "#8A3B06", "amber_bg": "#FDF3E4", "glow_sky": "rgba(5,147,198,0.20)",
          "glow_pink": "rgba(216,57,149,0.13)", "active_bg": "rgba(216,57,149,0.08)", "shadow": "rgba(20,33,43,0.05)"}


def app_css(t: dict) -> str:
    """Scoped CSS: only what config.toml cannot do. Containers are targeted by their st-key-* class."""
    return f"""<style>
:root {{ --zen-sky:{t['sky']}; --zen-link:{t['link']};--zen-pink:{t['pink']}; --zen-muted:{t['muted']}; --zen-card:{t['card']};
  --zen-border:{t['border']}; --zen-bubble:{t['bubble']}; --zen-bubble-text:{t['bubble_text']}; --zen-quote:{t['quote']};
  --zen-red:{t['red']}; --zen-red-bg:{t['red_bg']}; --zen-amber:{t['amber']}; --zen-amber-text:{t['amber_text']}; --zen-amber-bg:{t['amber_bg']}; --zen-shadow:{t['shadow']};
  --zen-ease: cubic-bezier(0.23, 1, 0.32, 1); }}
.block-container {{ max-width: 46rem; padding-top: 3rem; padding-bottom: 2rem; }}
h1, h2, h3 {{ letter-spacing: -0.02em; }}
*:focus-visible {{ outline-color: var(--zen-sky) !important; }}

/* Logo */
.zen-logo {{ display:flex; align-items:center; gap:.5rem; font-weight:700; font-size:1.125rem; letter-spacing:-0.01em; }}
.zen-logo .dot {{ width:.625rem; height:.625rem; border-radius:50%; background:var(--zen-pink); display:inline-block; }}
.zen-logo .sub {{ font-weight:500; color:var(--zen-muted); font-size:.8125rem; }}

/* Sidebar: chats, active chat in pink, bottom block pushed down */
[data-testid="stSidebarUserContent"] {{ padding-top: 1.25rem; }}
.st-key-side_top, .st-key-side_chats {{ gap: .25rem; }}
.zen-group {{ font-size:.75rem; font-weight:600; color:var(--zen-muted); margin:.75rem 0 .125rem .25rem; }}
[class*="st-key-chat_"] button, [class*="st-key-chatactive_"] button, .st-key-how button {{
  justify-content:flex-start; width:100%; min-height:2.25rem; padding:.375rem .625rem; border-radius:.625rem; }}
[class*="st-key-chat_"] button p, [class*="st-key-chatactive_"] button p {{
  white-space:nowrap; overflow:hidden; text-overflow:ellipsis; text-align:left; }}
[class*="st-key-chatactive_"] button {{ background:{t['active_bg']}; box-shadow: inset 3px 0 0 var(--zen-pink); }}
[class*="st-key-chatactive_"] button p {{ font-weight:600; }}
.st-key-side_bottom {{ border-top:1px solid var(--zen-border); padding-top:.75rem; margin-top:1rem; gap:.25rem; }}
.zen-privacy {{ font-size:.8125rem; color:var(--zen-muted); line-height:1.45; padding: 0 .25rem; }}
.zen-privacy b {{ font-weight:600; color:inherit; }}

/* Empty state */
.st-key-hero {{ position:relative; align-items:center; text-align:center; padding: 3.5rem 0 1.25rem; }}
.st-key-hero::before {{ content:""; position:absolute; inset:-2rem -4rem auto; height:18rem; z-index:0; pointer-events:none;
  background: radial-gradient(40% 55% at 38% 45%, {t['glow_sky']}, transparent 70%),
              radial-gradient(36% 50% at 64% 52%, {t['glow_pink']}, transparent 70%); filter: blur(8px); }}
.st-key-hero > * {{ position:relative; z-index:1; }}
.zen-greet {{ font-size:clamp(1.625rem, 4.5vw, 2.125rem); font-weight:650; letter-spacing:-0.022em; line-height:1.15; margin:0; }}
.zen-greet-sub {{ color:var(--zen-muted); margin:.5rem 0 0; font-size:1rem; line-height:1.5; }}
[class*="st-key-sugg_"] button {{ display:flex; justify-content:flex-start; align-items:flex-start; text-align:left;
  min-height:5.25rem; height:100%; padding:.875rem 1rem; background:var(--zen-card); border:1px solid var(--zen-border);
  border-radius:1rem; box-shadow:0 1px 2px var(--zen-shadow);
  transition: border-color 150ms ease, transform 140ms var(--zen-ease); }}
[class*="st-key-sugg_"] button p {{ font-size:.9375rem; line-height:1.4; text-align:left; }}
[class*="st-key-sugg_"] button [data-testid="stIconMaterial"] {{ color:var(--zen-sky); }}
[class*="st-key-sugg_"] {{ height:100%; }}
[data-testid="stHorizontalBlock"]:has([class*="st-key-sugg_"]) [data-testid="stColumn"] > div {{ height:100%; }}
.st-key-chips {{ justify-content:center; flex-wrap:wrap; gap:.5rem; margin-top:.25rem; }}
[class*="st-key-chip_"] button {{ border-radius:999px; min-height:2rem; padding:.25rem .875rem; background:transparent;
  transition: border-color 150ms ease, transform 140ms var(--zen-ease); }}
[class*="st-key-chip_"] button p {{ font-size:.875rem; }}
@media (hover:hover) and (pointer:fine) {{
  [class*="st-key-sugg_"] button:hover, [class*="st-key-chip_"] button:hover {{ border-color:var(--zen-sky); color:inherit; }}
}}
.zen-label {{ font-size:.8125rem; color:var(--zen-muted); text-align:center; margin:.75rem 0 0; }}

/* Messages */
[class*="st-key-user_"] {{ align-items:flex-end; margin: 1.25rem 0 .5rem; }}
[class*="st-key-user_"] [data-testid="stElementContainer"] {{ width:auto !important; max-width:min(85%, 34rem);
  background:var(--zen-bubble); color:var(--zen-bubble-text); padding:.625rem 1rem;
  border-radius:1.25rem 1.25rem .375rem 1.25rem; }}
[class*="st-key-user_"] [data-testid="stMarkdownContainer"] {{ margin-bottom:0; }}
[class*="st-key-user_"] [data-testid="stMarkdown"] p {{ margin:0; line-height:1.5; overflow-wrap:anywhere; color:inherit; }}
[class*="st-key-bot_"] {{ gap:.75rem; margin-bottom:.75rem; }}
[class*="st-key-bot_"] p {{ line-height:1.6; }}
.zen-who {{ display:flex; align-items:center; gap:.4rem; font-size:.8125rem; font-weight:600; color:var(--zen-muted); }}
.zen-who .dot {{ width:.5rem; height:.5rem; border-radius:50%; background:var(--zen-sky); display:inline-block; }}
.zen-section {{ font-size:.8125rem; font-weight:600; color:var(--zen-muted); margin:.5rem 0 -.25rem;
  padding-top:.75rem; border-top:1px solid var(--zen-border); }}
.zen-section:first-child {{ border-top:0; padding-top:0; }}
.zen-section q {{ font-weight:400; }}
.zen-note {{ font-size:.875rem; color:var(--zen-muted); }}

/* Cards */
[class*="st-key-src_"], [class*="st-key-handoff_"], [class*="st-key-safety_"] {{ background:var(--zen-card);
  border:1px solid var(--zen-border); border-radius:1rem; padding:1rem 1.125rem; gap:.625rem; box-shadow:0 1px 2px var(--zen-shadow); }}
.zen-card-head {{ display:flex; align-items:center; gap:.5rem; font-size:.75rem; font-weight:600; letter-spacing:.02em;
  text-transform:uppercase; color:var(--zen-muted); }}
.zen-quote {{ margin:0; padding:.625rem .875rem; border-left:3px solid var(--zen-sky); background:var(--zen-quote);
  border-radius:0 .5rem .5rem 0; font-size:.9375rem; line-height:1.55; overflow-wrap:anywhere; }}
.zen-doc {{ font-weight:600; line-height:1.4; overflow-wrap:anywhere; }}
.zen-meta {{ font-size:.875rem; color:var(--zen-muted); margin-top:.125rem; }}
.zen-old {{ display:inline-block; margin-left:.375rem; padding:0 .4375rem; border-radius:999px; font-size:.75rem;
  line-height:1.5rem; background:color-mix(in srgb, var(--zen-muted) 14%, transparent); color:var(--zen-muted);
  white-space:nowrap; vertical-align:baseline; }}
.zen-warn {{ display:flex; gap:.5rem; align-items:flex-start; font-size:.875rem; line-height:1.45; padding:.5rem .75rem;
  border-radius:.625rem; color:var(--zen-amber-text); background:var(--zen-amber-bg);
  border:1px solid color-mix(in srgb, var(--zen-amber) 35%, transparent); }}
.zen-warn span {{ font-weight:700; }}
.zen-meta a, .zen-meta a:visited {{ color:var(--zen-link); font-weight:500; text-decoration:none; white-space:nowrap; }}
.zen-meta a:hover {{ text-decoration:underline; }}
.zen-copy {{ font:inherit; font-size:.875rem; font-weight:500; display:inline-flex; align-items:center; gap:.375rem;
  padding:.375rem .875rem; border-radius:.625rem; border:1px solid var(--zen-border); background:var(--zen-card);
  color:inherit; cursor:pointer; transition: transform 140ms var(--zen-ease), border-color 150ms ease; }}
.zen-copy:active {{ transform:scale(0.97); }}
.zen-copy:focus-visible {{ outline:2px solid var(--zen-sky); outline-offset:2px; }}
@media (hover:hover) and (pointer:fine) {{ .zen-copy:hover {{ border-color:var(--zen-sky); }} }}
@media (prefers-reduced-motion: reduce) {{ .zen-copy {{ transition:none; }} .zen-copy:active {{ transform:none; }} }}
[class*="st-key-safety_"] {{ border-color: color-mix(in srgb, var(--zen-red) 35%, var(--zen-border));
  box-shadow: inset 4px 0 0 var(--zen-red); background:var(--zen-red-bg); }}
.zen-safety-head {{ color:var(--zen-red); font-weight:650; display:flex; gap:.5rem; align-items:center; }}
.zen-safety-body {{ display:grid; gap:1rem; }}
.zen-intro {{ margin:0; line-height:1.55; }}
.zen-contacts {{ display:grid; gap:1rem; padding:1rem 0; border-top:1px solid color-mix(in srgb, var(--zen-red) 18%, transparent);
  border-bottom:1px solid color-mix(in srgb, var(--zen-red) 18%, transparent); }}
.zen-contact-section {{ display:grid; gap:.625rem; }}
.zen-contact-section h4 {{ margin:0; padding:0; font-size:.9375rem; font-weight:700; letter-spacing:0; line-height:1.4; }}
.zen-contact-section p {{ margin:0; line-height:1.5; }}
.zen-person {{ display:grid; gap:.125rem; line-height:1.45; }}
.zen-person .who {{ font-weight:600; }}
.zen-person .role, .zen-person .mail {{ font-size:.9375rem; }}
.zen-contacts a, .zen-contacts a:visited {{ color:var(--zen-link); font-weight:500; text-decoration:none; overflow-wrap:anywhere; }}
.zen-contacts a:hover {{ text-decoration:underline; }}
.zen-source {{ font-size:.8125rem; color:var(--zen-muted); margin:0; }}
.zen-draft {{ background:var(--zen-quote); border-radius:.75rem; padding:.875rem 1rem; font-size:.9375rem; line-height:1.6;
  overflow-wrap:anywhere; }}
.zen-draft .hdr {{ display:grid; gap:.125rem; padding-bottom:.625rem; margin-bottom:.625rem;
  border-bottom:1px solid var(--zen-border); }}
.zen-draft .hdr span {{ color:var(--zen-muted); margin-right:.5rem; }}
.zen-draft .body {{ white-space:pre-wrap; }}
.zen-hint {{ font-size:.8125rem; color:var(--zen-muted); }}
.zen-error {{ display:flex; gap:.5rem; align-items:flex-start; color:inherit; padding:.75rem 1rem; border-radius:.75rem;
  border:1px solid var(--zen-border); background:var(--zen-card); }}
[class*="st-key-bot_"] [data-testid="stExpander"] details {{ border-color:var(--zen-border); }}
[class*="st-key-bot_"] [data-testid="stExpander"] summary p {{ font-size:.8125rem; color:var(--zen-muted); }}

/* Bottom: message box and footer */
[data-testid="stBottomBlockContainer"] {{ max-width:46rem; padding-bottom:.75rem; }}
[data-testid="stChatInput"] {{ border-radius:1.5rem; box-shadow:0 2px 10px var(--zen-shadow); }}
[data-testid="stChatInput"]:focus-within {{ border-color: var(--zen-sky); }}
.zen-footer {{ text-align:center; font-size:.75rem; color:var(--zen-muted); margin:.25rem 0 0; line-height:1.4; }}

/* Press feedback */
.stButton button {{ transition: transform 140ms var(--zen-ease), border-color 150ms ease, background-color 150ms ease; }}
.stButton button:active {{ transform: scale(0.97); }}
@media (prefers-reduced-motion: reduce) {{
  .stButton button, [class*="st-key-sugg_"] button, [class*="st-key-chip_"] button {{ transition:none; }}
  .stButton button:active {{ transform:none; }}
}}
@media (max-width: 640px) {{
  .block-container {{ padding-top: 2.5rem; padding-left:1rem; padding-right:1rem; }}
  .st-key-hero {{ padding-top: 1.5rem; }}
  [class*="st-key-sugg_"] button {{ min-height:0; }}
  [class*="st-key-user_"] [data-testid="stElementContainer"] {{ max-width:90%; }}
}}
</style>"""




# ---------- pipeline access (unchanged behaviour) ----------

def load_api_key() -> bool:
    """Put the key from st.secrets into the environment (the provider reads it there). True if a key is available."""
    try:
        key = st.secrets["GEMINI_API_KEY"]
    except Exception:  # no secrets file, or no such secret
        key = None
    if key:
        os.environ["GEMINI_API_KEY"] = str(key)
    load_config()  # loads .env locally; never overrides a value already set
    return bool(os.environ.get("GEMINI_API_KEY"))


@st.cache_resource(show_spinner="Loading the document index...")
def get_index() -> kb_search.KBIndex:
    return kb_search.default_index()


@st.cache_resource
def get_provider():
    return pipeline.default_provider()


@st.cache_resource
def answer_memo() -> dict:
    """Finished results by question, shared across sessions (the provider's disk cache also covers repeats)."""
    return {}


class StepProvider:
    """Wraps the provider to report progress; every call and its result pass through unchanged."""

    def __init__(self, inner, on_step):
        self._inner, self._on_step = inner, on_step
        self._draft_start = handoff.load_template().strip()[:60]

    def _kind(self, messages: list[dict]) -> str:
        if messages and messages[0].get("role") == "system":
            return "route"
        content = (messages[-1].get("content") or "") if messages else ""
        return "draft" if content.startswith(self._draft_start) else "answer"

    def _call(self, fn, messages):
        kind = self._kind(messages)
        self._on_step({"route": "Routing", "answer": "Answering", "draft": DRAFT_STEP}[kind])
        out = fn(messages)
        if kind == "route":
            self._on_step("Searching")
        elif kind == "answer":
            self._on_step("Checking quote")
        return out

    def chat_json(self, messages):
        return self._call(self._inner.chat_json, messages)

    def chat_text(self, messages):
        return self._call(self._inner.chat_text, messages)

    def __getattr__(self, name):
        return getattr(self._inner, name)


def run_question(question: str, on_step) -> dict:
    memo = answer_memo()
    if question in memo:
        for s in STEPS:
            on_step(s)
        return memo[question]
    get_index()
    result = pipeline.final_answer(question, StepProvider(get_provider(), on_step))
    memo[question] = result
    return result


def chunk_by_id(chunk_id: str | None):
    if not chunk_id:
        return None
    return next((c for c in get_index().chunks if c.id == chunk_id), None)


# ---------- helpers ----------

_MD_SPECIAL = re.compile(r"([\\`*_{}\[\]()#+\-.!|<>~$])")


def md_escape(text: str) -> str:
    """Student text shown as-is (no Markdown, links or maths)."""
    return _MD_SPECIAL.sub(r"\\\1", text or "")


def esc(text) -> str:
    return html.escape(str(text or ""))


# ---------- session state: chats live only in this session ----------

def init_state() -> None:
    st.session_state.setdefault("asked", 0)
    st.session_state.setdefault("chats", [])
    st.session_state.setdefault("next_id", 1)
    if not st.session_state["chats"]:
        new_chat()


def new_chat() -> None:
    chats = st.session_state["chats"]
    if chats and not current_chat()["messages"]:
        return  # the current chat is still empty: reuse it
    cid = st.session_state["next_id"]
    st.session_state["next_id"] = cid + 1
    chats.insert(0, {"id": cid, "title": "New chat", "messages": [], "last_turn": None})
    st.session_state["current"] = cid


def current_chat() -> dict:
    cid = st.session_state.get("current")
    return next((c for c in st.session_state["chats"] if c["id"] == cid), st.session_state["chats"][0])


def open_chat(cid: int) -> None:
    st.session_state["current"] = cid


def fill_box(text: str) -> None:
    """Card and chip callback: only fills the message box. Nothing is asked until Send or Enter."""
    st.session_state["chat_box"] = text


# ---------- sidebar ----------

@st.dialog("How ZEN AI works")
def how_it_works() -> None:
    cfg = load_config()
    st.markdown(
        "1. **Routing.** ZEN AI reads your message, splits it into at most two questions and picks the office "
        "for each.\n"
        "2. **Searching.** It searches the official Bennett University documents for that office.\n"
        "3. **Answering.** It answers only from what it found, and quotes the line it used.\n"
        "4. **Checking quote.** Code (not the AI) checks that the quote really is in the document. If it isn't, "
        "ZEN AI says it couldn't find the answer.\n\n"
        "When a person has to act, or the documents don't cover your question, ZEN AI writes an email draft for the "
        "right office. **It never sends anything.** You copy the draft and send it yourself.")
    st.caption(f"Model {cfg['provider']['chat_model']} (temperature {cfg['provider']['temperature']}) · prompts "
               f"P1 router {pipeline.FINAL['router']}, P2 answer {pipeline.FINAL['p2']}, P3 draft "
               f"{pipeline.FINAL['p3']} · search BM25, top 5 from the routed folder (or the named programme's rules) "
               "+ top 3 from all folders · quote check in code, no LLM.")


def sidebar() -> None:
    with st.sidebar:
        with st.container(key="side_top"):
            st.html('<div class="zen-logo"><span class="dot" aria-hidden="true"></span>ZEN AI'
                    '<span class="sub">Campus helpdesk</span></div>')
            st.button("New chat", icon=":material/edit_square:", key="new_chat", on_click=new_chat,
                      width="stretch")
        with st.container(key="side_chats"):
            started = [c for c in st.session_state["chats"] if c["messages"]]
            if started:
                st.html('<div class="zen-group">Today</div>')
                cur = current_chat()["id"]
                for c in started:
                    prefix = "chatactive_" if c["id"] == cur else "chat_"
                    st.button(md_escape(c["title"]), key=f"{prefix}{c['id']}", type="tertiary", on_click=open_chat,
                              args=(c["id"],), help=c["title"] if len(c["title"]) > 34 else None)
        with st.container(key="side_bottom"):
            if st.button("How ZEN AI works", icon=":material/info:", key="how", type="tertiary"):
                how_it_works()
            left = MAX_QUESTIONS - st.session_state["asked"]
            st.html(f'<div class="zen-privacy"><b>Private by design.</b> No login, and chats are kept only until you '
                    f'close this tab. Please don\'t enter personal details.<br>{left} of {MAX_QUESTIONS} questions '
                    f'left this session.</div>')


# ---------- empty state ----------

def empty_state() -> None:
    with st.container(key="hero"):
        st.html('<p class="zen-greet">How can I help today?</p>'
                '<p class="zen-greet-sub">Ask about fees, the hostel, IT, academics or student support, in English '
                'or Hinglish.</p>')
    for row in (SUGGESTIONS[:2], SUGGESTIONS[2:]):
        cols = st.columns(2, gap="small")
        for col, (label, icon, text) in zip(cols, row):
            with col:
                st.button(text, icon=icon, key=f"sugg_{label}", on_click=fill_box, args=(text,),
                          width="stretch")
    st.html('<p class="zen-label">Or start with an office</p>')
    with st.container(horizontal=True, key="chips"):
        for label, starter in OFFICE_CHIPS:
            st.button(label, key=f"chip_{label}", on_click=fill_box, args=(starter,))


# ---------- one reply ----------

def office_phrase(name: str) -> str:
    """The office as a proper name in a sentence (Markdown): "the **Finance Office**", "the **Hostel Wardens**",
    "the **Student Support office**", "the **Campus Services office** (Punctualiti)"."""
    base, sep, extra = (name or "").strip().partition(" (")
    if base.split()[-1:] not in (["Office"], ["Wardens"], ["Desk"]):
        base += " office"
    return f"the **{base}**" + (f" ({extra}" if sep else "")


_MD_BOLD = re.compile(r"\*\*(.+?)\*\*")
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")


def contact_html(line: str) -> str:
    """One copied line as HTML: Markdown marks dropped, the words unchanged, each email address a mailto link."""
    text = _MD_BOLD.sub(r"\1", re.sub(r"^(?:#+\s*|-\s+)", "", line.strip()))
    out, last = [], 0
    for m in _EMAIL.finditer(text):
        out += [esc(text[last:m.start()]), f'<a href="mailto:{esc(m.group(0))}">{esc(m.group(0))}</a>']
        last = m.end()
    return "".join(out) + esc(text[last:])


def safety_html(card: dict) -> str:
    """The contacts: one block per section (bold name, then each person: name, designation, email), built from the
    lines safety.py copied word for word from the KB file. No address is added or changed here."""
    sections: list[dict] = []
    for line in card.get("lines") or []:
        if line.startswith("## "):
            sections.append({"name": line[3:].strip(), "items": []})
        elif not sections:
            continue
        elif line.startswith("### "):
            sections[-1]["items"].append(("person", [line]))
        elif line.startswith("- ") and sections[-1]["items"] and sections[-1]["items"][-1][0] == "person":
            sections[-1]["items"][-1][1].append(line)
        elif sections[-1]["items"] and sections[-1]["items"][-1][0] == "text":
            sections[-1]["items"][-1][1].append(line)  # e.g. "Send all complaints and queries to:" + its address
        else:
            sections[-1]["items"].append(("text", [line]))
    blocks = []
    for sec in sections:
        parts = [f"<h4>{esc(sec['name'])}</h4>"]
        for kind, lines in sec["items"]:
            classes = (["who"] if kind == "person" else ["line"]) + [
                "mail" if "@" in x else "role" for x in lines[1:]]
            parts.append('<div class="zen-person">' + "".join(
                f'<span class="{c}">{contact_html(x)}</span>' for c, x in zip(classes, lines)) + "</div>")
        blocks.append('<div class="zen-contact-section">' + "".join(parts) + "</div>")
    return '<div class="zen-contacts">' + "".join(blocks) + "</div>"


# ---------- honest source badges (display only: the pipeline's result is never changed) ----------

OLD_BEFORE_YEAR = 2022
_NUMBER = re.compile(r"\d+(?:[.,]\d+)*")
# (label, level, pattern). level: "ug", "pg" or "phd". A generic label ("Bachelor's", "Master's") covers every
# programme of its level, so "MBA" in the question and "Master's Programme" in the title is not a mismatch.
PROGRAMMES = [
    ("B.Tech", "ug", r"\bb\.?\s?tech\b"), ("M.Tech", "pg", r"\bm\.?\s?tech\b"),
    ("BBA", "ug", r"\bbba\b"), ("MBA", "pg", r"\bmba\b"), ("BCA", "ug", r"\bbca\b"), ("MCA", "pg", r"\bmca\b"),
    ("B.Sc", "ug", r"\bb\.?\s?sc\b"), ("M.Sc", "pg", r"\bm\.?\s?sc\b"), ("B.Com", "ug", r"\bb\.?\s?com\b"),
    ("B.Des", "ug", r"\bb\.?\s?des\b"), ("M.Des", "pg", r"\bm\.?\s?des\b"),
    ("LLB", "ug", r"\bll\.?\s?b\b"), ("LLM", "pg", r"\bll\.?\s?m\b"), ("PhD", "phd", r"\bph\.?\s?d\b"),
    ("Bachelor's", "ug", r"\bbachelor'?s?\b|\bunder\s?graduate\b"),
    ("Master's", "pg", r"\bmaster'?s?\b|\bpost\s?graduate\b"),
]
GENERIC = {"Bachelor's": "Bachelor's programmes", "Master's": "Master's programmes"}


def _num(text: str) -> str:
    return text.replace(",", "")


def numbers_not_in_quote(answer: str, quote: str) -> list[str]:
    """Numbers in the answer (70%, 45 days, Rs. 1,000) that the verified quote does not contain, in order."""
    have = {_num(m) for m in _NUMBER.findall(quote or "")}
    out: list[str] = []
    for m in _NUMBER.findall(answer or ""):
        if _num(m) not in have and m not in out:
            out.append(m)
    return out


def programmes_in(text: str) -> list[tuple[str, str]]:
    """(label, level) of every programme the text names."""
    t = (text or "").replace("’", "'")
    return [(label, level) for label, level, pat in PROGRAMMES if re.search(pat, t, re.I)]


def programme_mismatch(question: str, title: str) -> str | None:
    """The source's programme (for the note) when the question names a programme and the source title names only
    other ones; None when either names none or they agree (same programme, or a generic one at the same level)."""
    asked, source = programmes_in(question), programmes_in(title)
    if not asked or not source:
        return None
    for a_label, a_level in asked:
        for s_label, s_level in source:
            if a_label == s_label or (a_level == s_level and (a_label in GENERIC or s_label in GENERIC)):
                return None
    return ", ".join(GENERIC.get(label, label) for label, _ in source)


def older_year(date: str | None) -> int | None:
    """The document's year when it is before OLD_BEFORE_YEAR ("07/2019" -> 2019), else None. An academic year
    ("2021-2022") counts by its later year; a date with no year ("unknown") is never flagged."""
    years = [int(y) for y in re.findall(r"\b(?:19|20)\d{2}\b", date or "")]
    if not years or max(years) >= OLD_BEFORE_YEAR:
        return None
    return max(years)


def show_answer(r: dict, n: int) -> None:
    p2, qc = r["p2"], r["quote_check"]
    st.markdown(p2["answer"])
    c = chunk_by_id(qc.get("chunk_id"))
    with st.container(key=f"src_{n}"):
        st.html('<div class="zen-card-head">Source</div>')
        if c is not None:
            meta = []
            if c.page is not None:
                meta.append(f"Page {esc(c.page)}")
            if c.date:
                old = older_year(c.date)
                meta.append(esc(c.date) + (f' <span class="zen-old">Older document ({old})</span>' if old else ""))
            if c.source_url:
                meta.append(f'<a href="{esc(c.source_url)}" target="_blank" rel="noopener">Open document&nbsp;↗</a>')
            st.html(f'<div class="zen-doc">{esc(c.title)}</div><div class="zen-meta">{" · ".join(meta)}</div>')
        st.html(f'<blockquote class="zen-quote">{esc((p2.get("quote") or "").strip())}</blockquote>')
        missing = numbers_not_in_quote(p2.get("answer") or "", p2.get("quote") or "")
        near = qc.get("rule") == "near"
        if missing:
            st.badge("Quote verified · number not in quote", icon=":material/error:", color="orange",
                     help=("The quote is in the document, but it does not show " + ", ".join(missing)
                           + " from the answer. Check the document before relying on that number."))
        else:
            st.badge("Quote verified · near match" if near else "Quote verified · exact",
                     icon=":material/check_circle:", color="green",
                     help=("Not word for word: all numbers and at least 90% of the words are in the section."
                           if near else "Found word for word in the document."))
        other = programme_mismatch(r.get("question") or "", c.title if c is not None else "")
        if other:
            st.html(f'<div class="zen-warn" role="note"><span aria-hidden="true">!</span>This source is for '
                    f"{esc(other)}. Check your own programme's rules.</div>")


def show_handoff(r: dict, n: int) -> None:
    p3 = r.get("p3") or {}
    office = r["office_name"]
    to = office_phrase(office)
    if r["action"] == "safety":
        st.markdown(f"ZEN AI can't act on this itself. You can also send this email to {to}.")
    elif r["action"] == "not_found":
        st.markdown(f"I couldn't find this in the official documents, so I won't guess. "
                    f"You can send this email to {to} instead.")
    elif p3.get("reason") == handoff.REASON_RECORD:
        st.markdown(f"This depends on your own record, which ZEN AI cannot see. You can send this email to {to}.")
    else:
        st.markdown(f"This needs someone at the office to act, which ZEN AI cannot do. "
                    f"You can send this email to {to}.")
    d = p3.get("draft")
    if not d:
        st.caption(f"I couldn't prepare a draft this time. Please contact {to} directly.")
        return
    with st.container(key=f"handoff_{n}"):
        with st.container(horizontal=True, vertical_alignment="center", gap="small"):
            st.html(f'<div class="zen-card-head">Email draft · {esc(office)}</div>', width="content")
            st.badge("Draft only, nothing is sent", icon=":material/drafts:", color="orange")
        text = f"To: {d['to']}\nSubject: {d['subject']}\n\n{d['body']}"
        st.html(f'<div class="zen-draft"><div class="hdr"><div><span>To</span>{esc(d["to"])}</div>'
                f'<div><span>Subject</span>{esc(d["subject"])}</div></div>'
                f'<div class="body">{esc((d["body"] or "").strip())}</div></div>')
        with st.container(horizontal=True, vertical_alignment="center", gap="small"):
            st.html(f'<button class="zen-copy" type="button" data-text="{esc(text)}">'
                    '<span aria-hidden="true">⧉</span><span class="lbl">Copy draft</span></button>',
                    width="content")
            st.html('<div class="zen-hint">Replace [Your name] and [Enrollment no.], then send it from your own '
                    'email.</div>')


def show_safety(r: dict, n: int, card: dict | None) -> None:
    """card: the result's safety_card (for topic 1 it sits on the top-level result); safety.card() re-reads the same
    KB file (no LLM) when a result has none."""
    card = card or safety.card()
    with st.container(key=f"safety_{n}"):
        st.html('<div class="zen-safety-head"><span aria-hidden="true">●</span>Please reach out now</div>')
        if card.get("lines"):
            st.html(f'<div class="zen-safety-body"><p class="zen-intro">{esc(card["intro"])}</p>{safety_html(card)}'
                    f'<p class="zen-intro">{esc(card["fallback"])}</p>'
                    f'<p class="zen-source">Source: {esc(card["source_title"])}</p></div>')
        else:
            st.html(f'<p class="zen-intro">{esc(card.get("fallback") or safety.CARD_FALLBACK)}</p>')
    show_handoff(r, n)


def show_details(r: dict, topic: dict | None, all_topics: list[dict], calls_label: str) -> None:
    """The debug expander for one topic's result. all_topics: every P1 topic, shown as a table (first part only)."""
    with st.expander("How ZEN AI decided", icon=":material/account_tree:"):
        st.markdown(f"**Final action:** `{r['action']}` ({r['reason']}). {calls_label}: {r['llm_calls']}.")
        st.markdown(f"**Step 1. Router (P1 {pipeline.FINAL['router']})**")
        if topic:
            st.markdown(f"Office: `{r['office']}` (router domain `{topic.get('domain')}`) · request type "
                        f"`{topic.get('request_type')}` · search query: `{r.get('search_query') or '-'}`")
            if len(all_topics) > 1:
                st.dataframe([{k: t.get(k) for k in ("text", "domain", "request_type", "search_query")}
                              for t in all_topics], hide_index=True)
        else:
            st.markdown("Not run (empty question).")
        st.markdown("**Step 2. Search (BM25: top 5 from the routed folder, or from the named programme's rules for an "
                    "academic question, + top 3 from all folders)**")
        if r.get("programme_files"):
            st.markdown("Programme named: searched only " + ", ".join(f"`{f}`" for f in r["programme_files"]))
        if r.get("retrieval"):
            st.dataframe([{"#": n, "document": h["title"], "page": h["page"], "folder": h["office"],
                           "score": h["score"], "section id": h["id"]} for n, h in enumerate(r["retrieval"], 1)],
                         hide_index=True)
        else:
            st.markdown("Not run: the router decided without searching.")
        st.markdown(f"**Step 3. Grounded answer (P2 {pipeline.FINAL['p2']}), raw reply**")
        raw = r.get("p2_raw")
        if isinstance(raw, dict):
            st.json(raw)
        elif raw:
            st.code(str(raw), language=None)
        else:
            st.markdown("Not run.")
        st.markdown("**Step 4. Quote check (code, no LLM)**")
        qc = r.get("quote_check")
        if qc:
            rule = {"exact": "exact (word for word after normalising)",
                    "near": "near (not word for word: all numbers and at least 90% of the words are in the section)"}
            st.markdown(f"Verified: `{qc['verified']}`"
                        + (f" · rule: {rule.get(qc['rule'], qc['rule'])}" if qc.get("rule") else "")
                        + f" · section: `{qc.get('chunk_id') or '-'}`"
                        + (f" · reason: {qc['reason']}" if qc.get("reason") else ""))
        else:
            st.markdown("Not run.")
        if r.get("p3"):
            p3 = r["p3"]
            st.markdown(f"**Step 5. Handoff draft (P3 {pipeline.FINAL['p3']})** · reason given to P3: `{p3['reason']}`")
            if p3.get("checks"):
                st.json(p3["checks"])
            if p3.get("error"):
                st.markdown(f"Draft error: {p3['error']}")


def show_result(r: dict, key: str) -> None:
    """One section per answered topic (a safety topic comes first); a note lists topics that were not answered."""
    all_topics = (r.get("router") or {}).get("topics") or []
    results = r.get("topic_results") or [{**r, "topic": all_topics[0] if all_topics else None}]
    several = len(results) > 1
    order = sorted(range(len(results)), key=lambda i: results[i]["action"] != "safety")
    for i in order:
        tr, n = results[i], i + 1
        if several:
            st.html(f'<div class="zen-section">Part {n} of {len(results)} · <q>{esc(tr.get("question"))}</q></div>')
        action, card = tr["action"], f"{key}_{n}"
        if action == "answer":
            show_answer(tr, card)
        elif action == "safety":
            show_safety(tr, card, tr.get("safety_card") or (r.get("safety_card") if i == 0 else None))
        elif action in ("not_found", "handoff"):
            show_handoff(tr, card)
        else:
            st.markdown(tr.get("reply_text") or "")
        label = ("LLM calls for this question" if not several
                 else "LLM calls (router + this part)" if n == 1 else "LLM calls for this part")
        show_details(tr, tr.get("topic"), all_topics if n == 1 else [], label)
    if r.get("multi_topic_note"):
        st.html(f'<div class="zen-note">{esc(r["multi_topic_note"])} Not answered here: '
                + "; ".join(f"“{esc(t)}”" for t in r.get("other_topics") or []) + "</div>")


def show_user(text: str, key: str) -> None:
    with st.container(key=f"user_{key}"):
        st.markdown(md_escape(text))


def show_bot(msg: dict, key: str) -> None:
    with st.container(key=f"bot_{key}"):
        st.html('<div class="zen-who"><span class="dot" aria-hidden="true"></span>ZEN AI</div>')
        if msg.get("followup_of"):
            st.caption(":material/subdirectory_arrow_right: "
                       + md_escape(followup.FOLLOWUP_NOTE.format(previous=msg["followup_of"])),
                       help="Your last question needed more detail, so this short reply was added to it.")
        if msg.get("error"):
            st.html(f'<div class="zen-error" role="alert"><span aria-hidden="true">⚠</span>{esc(msg["error"])}</div>')
        else:
            show_result(msg["result"], key)


# ---------- asking ----------

def step_view(box, current: str, extra: list[str]) -> None:
    steps = STEPS + extra
    idx = steps.index(current) if current in steps else 0
    lines = []
    for i, s in enumerate(steps):
        if i < idx:
            lines.append(f":green[:material/check_circle:] {s}")
        elif i == idx:
            lines.append(f":blue[:material/radio_button_checked:] **{s}…**")
        else:
            lines.append(f":gray[:material/radio_button_unchecked:] :gray[{s}]")
    box.markdown("  \n".join(lines))


def ask(question: str) -> None:
    """Run one message and store the reply in the current chat. Friendly messages only, never a stack trace."""
    chat = current_chat()
    key = f"{chat['id']}_{len(chat['messages'])}"
    chat["messages"].append({"role": "user", "text": question})
    if chat["title"] == "New chat":
        chat["title"] = question if len(question) <= 48 else question[:46].rstrip() + "…"
    show_user(question, key)

    def reply(**msg) -> None:
        chat["messages"].append({"role": "assistant", **msg})

    if not load_api_key():
        return reply(error="The helpdesk is not configured yet (the API key is missing). Please try again later.")
    if st.session_state["asked"] >= MAX_QUESTIONS:
        return reply(error=f"You've reached the limit of {MAX_QUESTIONS} questions for this session. "
                           "Please come back later.")
    st.session_state["asked"] += 1
    run_on, previous = followup.resolve(chat.get("last_turn"), question)
    extra: list[str] = []
    with st.container(key=f"bot_{key}_live"):
        with st.status("Working on it…", expanded=True) as status:
            box = st.empty()

            def on_step(name: str) -> None:
                if name == DRAFT_STEP and DRAFT_STEP not in extra:
                    extra.append(DRAFT_STEP)
                step_view(box, name, extra)

            on_step("Routing")
            try:
                result = run_question(run_on, on_step)
            except QuotaError:
                return reply(error="ZEN AI has used up its question quota for now. Please try again later "
                                   "(the quota resets daily).")
            except ProviderError:
                return reply(error="ZEN AI couldn't reach the language model just now. Please try again in a minute.")
            except Exception:  # never show a stack trace to the student
                return reply(error="Something went wrong while answering. Please try again.")
            status.update(label="Done", state="complete")
    chat["last_turn"] = followup.remember(result, run_on)
    reply(result=result, followup_of=previous)


# ---------- page ----------

def main() -> None:
    st.set_page_config(page_title="ZEN AI: Campus Helpdesk", page_icon=":material/school:", layout="centered",
                       initial_sidebar_state="auto")
    init_state()
    st.html(app_css(TOKENS))
    st.html(COPY_SCRIPT, unsafe_allow_javascript=True)
    left = MAX_QUESTIONS - st.session_state["asked"]
    with st.bottom:
        prompt = st.chat_input("Ask ZEN AI about campus life" if left > 0 else
                               f"You've used all {MAX_QUESTIONS} questions for this session",
                               key="chat_box", max_chars=600, disabled=left <= 0)
        st.html(f'<p class="zen-footer">{FOOTER}</p>')
    chat = current_chat()
    if not chat["messages"] and not (prompt and prompt.strip()):
        with st.container(key="view_empty"):
            empty_state()
    else:  # a differently keyed view, so the empty state never lingers (faded) while the first reply runs
        with st.container(key=f"view_chat_{chat['id']}"):
            for i in range(0, len(chat["messages"]), 2):
                key = f"{chat['id']}_{i}"
                show_user(chat["messages"][i]["text"], key)
                if i + 1 < len(chat["messages"]):
                    show_bot(chat["messages"][i + 1], key)
            if prompt and prompt.strip():
                ask(prompt.strip())
        if prompt and prompt.strip():
            st.rerun()
    sidebar()


if __name__ == "__main__":  # Streamlit runs this file as __main__; tests import the checks above without a page
    main()
