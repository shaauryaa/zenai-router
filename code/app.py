"""ZEN AI: Campus Helpdesk (Streamlit). Run from the repo root:  streamlit run code/app.py

The final pipeline (helpdesk.pipeline.final_answer, pipeline.FINAL): P1 v2 router -> BM25 search (5 routed, or 5 from
the named programme's rules for an academic question, + 3 all) -> P2 grounded answer -> code quote check -> P3 handoff
draft (not_found, handoff) or fixed text (refuse, clarify). A message with two topics gets one result card per topic.
API key: st.secrets["GEMINI_API_KEY"], else the environment (.env locally). Nothing is ever sent by email.
Look and feel: theme in .streamlit/config.toml (light and dark) plus the small scoped CSS in APP_CSS.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # code/ on the path, wherever streamlit is started

import streamlit as st  # noqa: E402

from helpdesk import followup, handoff, kb_search, pipeline  # noqa: E402
from zenai.config import load_config  # noqa: E402
from zenai.providers import ProviderError, QuotaError  # noqa: E402

MAX_QUESTIONS = 20
EXAMPLES = [
    ("Fee refund (English)", ":material/payments:",
     "How long does it take to get my fee refund after I withdraw from the programme?"),
    ("Hostel (Hinglish)", ":material/translate:", "kya main hostel room mein apna pet, jaise ek billi, rakh sakta hoon?"),
    ("Off-topic", ":material/block:", "Can you recommend a good movie for this weekend?"),
    ("Not in the documents", ":material/search_off:", "Is there a dance club audition this month?"),
]
ACTION_LABELS = {"answer": "Answered from the documents", "not_found": "Not found in the documents",
                 "handoff": "Needs a person", "refuse": "Outside what ZEN AI covers", "clarify": "Needs more detail",
                 "safety": "Please reach out now"}
ACTION_STYLE = {"answer": ("green", ":material/task_alt:"), "not_found": ("orange", ":material/search_off:"),
                "handoff": ("blue", ":material/support_agent:"), "refuse": ("gray", ":material/block:"),
                "clarify": ("violet", ":material/help:"), "safety": ("red", ":material/emergency:")}

# Only what the theme cannot do: heading tracking, the source quote, and press feedback on buttons.
APP_CSS = """
<style>
h1 { letter-spacing: -0.022em; line-height: 1.1; }
[class*="st-key-result_card"] blockquote {
  margin: 0.25rem 0 0; padding: 0.75rem 1rem; border-left: 3px solid #2563EB; border-radius: 0 0.5rem 0.5rem 0;
  background: rgba(127, 127, 140, 0.09);
}
[class*="st-key-result_card"] blockquote, [class*="st-key-result_card"] blockquote p { color: inherit !important; opacity: 1 !important; }
[class*="st-key-result_card"] blockquote p { font-size: 0.95rem; line-height: 1.55; }
[class*="st-key-result_card"] .stCode pre { white-space: pre-wrap; }
.stButton button, .stFormSubmitButton button { transition: transform 120ms cubic-bezier(0.23, 1, 0.32, 1); }
.stButton button:active, .stFormSubmitButton button:active { transform: scale(0.97); }
@media (prefers-reduced-motion: reduce) {
  .stButton button, .stFormSubmitButton button { transition: none; }
  .stButton button:active, .stFormSubmitButton button:active { transform: none; }
}
</style>
"""

st.set_page_config(page_title="ZEN AI: Campus Helpdesk", page_icon=":material/school:", layout="centered")


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


@st.cache_data(show_spinner=False, max_entries=1000)
def run_question(question: str) -> dict:
    get_index()
    return pipeline.final_answer(question, get_provider())


def chunk_by_id(chunk_id: str | None):
    if not chunk_id:
        return None
    return next((c for c in get_index().chunks if c.id == chunk_id), None)


def quote_block(text: str) -> str:
    return "\n".join("> " + line for line in (text or "").strip().splitlines())


def show_answer(r: dict) -> None:
    p2, qc = r["p2"], r["quote_check"]
    st.markdown(p2["answer"])
    st.caption("From the official document")
    st.markdown(quote_block(p2["quote"]))
    c = chunk_by_id(qc.get("chunk_id"))
    if c is not None:
        parts = [f":material/description: **{c.title}**"]
        if c.page is not None:
            parts.append(f"page {c.page}")
        if c.date:
            parts.append(f"date {c.date}")
        if c.source_url:
            parts.append(f"[source document]({c.source_url})")
        st.markdown(" · ".join(parts))
    st.badge("Quote verified in source", icon=":material/check_circle:", color="green")


def show_handoff(r: dict) -> None:
    p3 = r.get("p3") or {}
    office = r["office_name"]
    if r["action"] == "safety":
        st.markdown(f"ZEN AI can't act on this itself. You can also send this email to **{office}**.")
    elif r["action"] == "not_found":
        st.markdown(f"I couldn't find this in the official documents, so I won't guess. "
                    f"You can send this email to the **{office}** instead.")
    elif p3.get("reason") == handoff.REASON_RECORD:
        st.markdown(f"This depends on your own record, which ZEN AI cannot see. "
                    f"You can send this email to the **{office}**.")
    else:
        st.markdown(f"This needs someone at the office to act, which ZEN AI cannot do. "
                    f"You can send this email to the **{office}**.")
    d = p3.get("draft")
    if d:
        with st.container(horizontal=True, vertical_alignment="center", gap="small"):
            st.badge("Draft only. Nothing is sent.", icon=":material/drafts:", color="orange")
            st.caption("Replace [Your name] and [Enrollment no.] before sending.", width="content")
        st.code(f"To: {d['to']}\nSubject: {d['subject']}\n\n{d['body']}", language=None, wrap_lines=True)
    else:
        st.caption(f"I couldn't prepare a draft this time. Please contact the {office} directly.")


def show_details(r: dict, topic: dict | None, all_topics: list[dict], calls_label: str) -> None:
    """The debug expander for one topic's result. all_topics: every P1 topic, shown as a table (first card only)."""
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


def show_result(r: dict) -> None:
    """One result card (and debug expander) per answered topic; the note lists topics that were not answered."""
    if r.get("multi_topic_note"):
        st.warning(r["multi_topic_note"], icon=":material/call_split:")
        st.markdown("Not answered here: " + "; ".join(f"“{t}”" for t in r["other_topics"]))
    all_topics = (r.get("router") or {}).get("topics") or []
    results = r.get("topic_results") or [{**r, "topic": all_topics[0] if all_topics else None}]
    several = len(results) > 1
    for n, tr in enumerate(results, 1):
        if several:
            st.subheader(f"Question {n} of {len(results)}", anchor=False)
            st.caption(f"“{tr.get('question') or ''}”")
        with st.container(border=True, key=f"result_card_{n}"):
            color, icon = ACTION_STYLE.get(tr["action"], ("gray", None))
            st.badge(ACTION_LABELS.get(tr["action"], tr["action"]), icon=icon, color=color)
            if tr["action"] == "answer":
                show_answer(tr)
            elif tr["action"] == "safety":
                st.error(tr.get("reply_text") or "", icon=":material/health_and_safety:")
                show_handoff(tr)
            elif tr["action"] in ("not_found", "handoff"):
                show_handoff(tr)
            else:
                st.markdown(tr.get("reply_text") or "")
        label = ("LLM calls for this question" if not several
                 else "LLM calls (router + this part)" if n == 1 else "LLM calls for this part")
        show_details(tr, tr.get("topic"), all_topics if n == 1 else [], label)


def sidebar() -> None:
    cfg = load_config()
    with st.sidebar:
        st.markdown("### About this prototype")
        st.markdown(f"**Model:** {cfg['provider']['chat_model']} (temperature {cfg['provider']['temperature']})")
        st.markdown(f"**Prompts in use:**\n- P1 router {pipeline.FINAL['router']}\n"
                    f"- P2 grounded answer {pipeline.FINAL['p2']}\n- P3 handoff draft {pipeline.FINAL['p3']}\n\n"
                    "**Search:** BM25, top 5 from the routed folder (or the named programme's rules) + top 3 from "
                    "all folders\n\n**Two questions in one message:** each is answered on its own\n\n"
                    "**Quote check:** code, no LLM")
        st.info("No login. Don't enter personal details.", icon=":material/lock:")
        asked = st.session_state.get("asked", 0)
        st.progress(min(asked, MAX_QUESTIONS) / MAX_QUESTIONS)
        st.caption(f"Questions left in this session: {MAX_QUESTIONS - asked} of {MAX_QUESTIONS}")


def pick_example(text: str) -> None:
    """Button callback: runs before the rerun, so the question box can be filled even though it is drawn above."""
    st.session_state["question_box"] = text
    st.session_state["pending_question"] = text


def main() -> None:
    st.session_state.setdefault("asked", 0)
    st.html(APP_CSS)
    st.title("ZEN AI: Campus Helpdesk", anchor=False)
    st.markdown("Answers only from official Bennett University documents, quotes the source, and hands off to the "
                "right office when it can't.")
    with st.container(horizontal=True, gap="small"):
        st.badge("Official documents only", icon=":material/menu_book:", color="blue")
        st.badge("Every quote checked", icon=":material/fact_check:", color="blue")
        st.badge("Nothing is sent for you", icon=":material/mark_email_read:", color="blue")

    with st.form("ask", clear_on_submit=False, border=False):
        typed = st.text_input("Your question (English or Hinglish)", key="question_box",
                              placeholder="e.g. What is the minimum attendance for B.Tech?")
        submitted = st.form_submit_button("Ask", type="primary", icon=":material/arrow_upward:")
    st.caption("Or try an example")
    with st.container(horizontal=True, gap="small"):
        for label, icon, text in EXAMPLES:
            st.button(label, icon=icon, on_click=pick_example, args=(text,))

    clicked = st.session_state.pop("pending_question", None)
    question = clicked if clicked is not None else (typed if submitted else None)
    if question is not None:
        ask(question.strip())
    sidebar()
    if st.session_state.get("result"):
        if st.session_state.get("followup_of"):
            st.caption(followup.FOLLOWUP_NOTE.format(previous=st.session_state["followup_of"]),
                       help="Your last question needed more detail, so this short reply was added to it.")
        show_result(st.session_state["result"])


def ask(question: str) -> None:
    """Run one question into st.session_state["result"], or show a friendly message (never a stack trace)."""
    st.session_state.pop("result", None)
    st.session_state.pop("followup_of", None)
    if not load_api_key():
        st.error("The helpdesk is not configured yet (the API key is missing). Please try again later.")
        return
    if st.session_state["asked"] >= MAX_QUESTIONS:
        st.warning(f"You've reached the limit of {MAX_QUESTIONS} questions for this session. Please come back later.")
        return
    st.session_state["asked"] += 1
    run_on, previous = followup.resolve(st.session_state.get("last_turn"), question)
    try:
        with st.spinner("Checking the official documents..."):
            st.session_state["result"] = run_question(run_on)
        st.session_state["last_turn"] = followup.remember(st.session_state["result"], run_on)
        st.session_state["followup_of"] = previous
    except QuotaError:
        st.error("ZEN AI has used up its question quota for now. Please try again later (the quota resets daily).")
    except ProviderError:
        st.error("ZEN AI couldn't reach the language model just now. Please try again in a minute.")
    except Exception:  # never show a stack trace to the student
        st.error("Something went wrong while answering. Please try again.")


main()
