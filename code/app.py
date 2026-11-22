"""ZEN AI: Campus Helpdesk (Streamlit). Run from the repo root:  streamlit run code/app.py

The frozen final pipeline (helpdesk.pipeline.final_answer): P1 v2 router -> BM25 search (5 routed + 3 all) -> P2 v2
grounded answer -> code quote check -> P3 handoff draft (not_found, handoff) or fixed text (refuse, clarify).
API key: st.secrets["GEMINI_API_KEY"], else the environment (.env locally). Nothing is ever sent by email.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # code/ on the path, wherever streamlit is started

import streamlit as st  # noqa: E402

from helpdesk import handoff, kb_search, pipeline  # noqa: E402
from zenai.config import load_config  # noqa: E402
from zenai.providers import ProviderError, QuotaError  # noqa: E402

MAX_QUESTIONS = 20
EXAMPLES = [
    ("Fee refund (English)", "How long does it take to get my fee refund after I withdraw from the programme?"),
    ("Hostel (Hinglish)", "kya main hostel room mein apna khud ka cooler ya heater rakh sakta hoon?"),
    ("Off-topic", "Can you recommend a good movie for this weekend?"),
    ("Not in the documents", "Is there a dance club audition this month?"),
]
ACTION_LABELS = {"answer": "Answered from the documents", "not_found": "Not found in the documents",
                 "handoff": "Needs a person", "refuse": "Outside what ZEN AI covers", "clarify": "Needs more detail"}

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
    st.markdown(quote_block(p2["quote"]))
    c = chunk_by_id(qc.get("chunk_id"))
    if c is not None:
        parts = [f"**{c.title}**"]
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
    if r["action"] == "not_found":
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
        st.caption("Draft only. Nothing is sent. Replace [Your name] and [Enrollment no.] before sending.")
        st.code(f"To: {d['to']}\nSubject: {d['subject']}\n\n{d['body']}", language=None, wrap_lines=True)
    else:
        st.caption(f"I couldn't prepare a draft this time. Please contact the {office} directly.")


def show_details(r: dict) -> None:
    with st.expander("How ZEN AI decided"):
        topics = (r.get("router") or {}).get("topics") or []
        first = topics[0] if topics else {}
        st.markdown(f"**Final action:** `{r['action']}` ({r['reason']}). LLM calls for this question: {r['llm_calls']}.")
        st.markdown("**Step 1. Router (P1 v2)**")
        if topics:
            st.markdown(f"Office: `{r['office']}` (router domain `{first.get('domain')}`) · request type "
                        f"`{first.get('request_type')}` · search query: `{r.get('search_query') or '-'}`")
            if len(topics) > 1:
                st.dataframe([{k: t.get(k) for k in ("text", "domain", "request_type", "search_query")}
                              for t in topics], hide_index=True)
        else:
            st.markdown("Not run (empty question).")
        st.markdown("**Step 2. Search (BM25: top 5 from the routed folder + top 3 from all folders)**")
        if r.get("retrieval"):
            st.dataframe([{"#": n, "document": h["title"], "page": h["page"], "folder": h["office"],
                           "score": h["score"], "section id": h["id"]} for n, h in enumerate(r["retrieval"], 1)],
                         hide_index=True)
        else:
            st.markdown("Not run: the router decided without searching.")
        st.markdown("**Step 3. Grounded answer (P2 v2), raw reply**")
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
            st.markdown(f"Verified: `{qc['verified']}` · section: `{qc.get('chunk_id') or '-'}`"
                        + (f" · reason: {qc['reason']}" if qc.get("reason") else ""))
        else:
            st.markdown("Not run.")
        if r.get("p3"):
            p3 = r["p3"]
            st.markdown(f"**Step 5. Handoff draft (P3 v1)** · reason given to P3: `{p3['reason']}`")
            if p3.get("checks"):
                st.json(p3["checks"])
            if p3.get("error"):
                st.markdown(f"Draft error: {p3['error']}")


def show_result(r: dict) -> None:
    if r.get("multi_topic_note"):
        st.warning(r["multi_topic_note"])
        st.markdown("Not answered here: " + "; ".join(f"“{t}”" for t in r["other_topics"]))
    with st.container(border=True):
        st.markdown(f"#### {ACTION_LABELS.get(r['action'], r['action'])}")
        if r["action"] == "answer":
            show_answer(r)
        elif r["action"] in ("not_found", "handoff"):
            show_handoff(r)
        else:
            st.markdown(r.get("reply_text") or "")
    show_details(r)


def sidebar() -> None:
    cfg = load_config()
    with st.sidebar:
        st.markdown("### About this prototype")
        st.markdown(f"**Model:** {cfg['provider']['chat_model']} (temperature {cfg['provider']['temperature']})")
        st.markdown("**Prompts in use:**\n- P1 router v2\n- P2 grounded answer v2\n- P3 handoff draft v1\n\n"
                    "**Search:** BM25, top 5 from the routed folder + top 3 from all folders\n\n"
                    "**Quote check:** code, no LLM")
        st.info("No login. Don't enter personal details.")
        left = MAX_QUESTIONS - st.session_state.get("asked", 0)
        st.caption(f"Questions left in this session: {left} of {MAX_QUESTIONS}")


def main() -> None:
    st.session_state.setdefault("asked", 0)
    st.title("ZEN AI: Campus Helpdesk")
    st.markdown("Answers only from official Bennett University documents, quotes the source, and hands off to the "
                "right office when it can't.")

    clicked = None
    st.markdown("**Try an example:**")
    for col, (label, text) in zip(st.columns(len(EXAMPLES)), EXAMPLES):
        if col.button(label, width="stretch"):
            clicked = text
            st.session_state["question_box"] = text
    with st.form("ask", clear_on_submit=False):
        typed = st.text_input("Your question (English or Hinglish)", key="question_box",
                              placeholder="e.g. What is the minimum attendance for B.Tech?")
        submitted = st.form_submit_button("Ask", type="primary")
    question = clicked if clicked is not None else (typed if submitted else None)
    if question is not None:
        ask(question.strip())
    sidebar()
    if st.session_state.get("result"):
        show_result(st.session_state["result"])


def ask(question: str) -> None:
    """Run one question into st.session_state["result"], or show a friendly message (never a stack trace)."""
    st.session_state.pop("result", None)
    if not load_api_key():
        st.error("The helpdesk is not configured yet (the API key is missing). Please try again later.")
        return
    if st.session_state["asked"] >= MAX_QUESTIONS:
        st.warning(f"You've reached the limit of {MAX_QUESTIONS} questions for this session. Please come back later.")
        return
    st.session_state["asked"] += 1
    try:
        with st.spinner("Checking the official documents..."):
            st.session_state["result"] = run_question(question)
    except QuotaError:
        st.error("ZEN AI has used up its question quota for now. Please try again later (the quota resets daily).")
    except ProviderError:
        st.error("ZEN AI couldn't reach the language model just now. Please try again in a minute.")
    except Exception:  # never show a stack trace to the student
        st.error("Something went wrong while answering. Please try again.")


main()
