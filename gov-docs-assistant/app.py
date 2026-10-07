"""Chat UI. Run with:  python -m streamlit run app.py"""
import csv
import io
from pathlib import Path

import streamlit as st

import rag

st.set_page_config(page_title="Ask Our Documents", page_icon="🌿", layout="wide")

# ---------------- look & feel: calm, minimal, floral ----------------
THEME_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,500;9..144,600&family=Inter:wght@400;500;600&display=swap');
:root {
  --bg: #F4F5EF; --card: #FBFAF5; --line: #E3E6DA; --ink: #1F2D22; --muted: #66756A;
  --green: #2F5233; --green-2: #4B6F4F; --sage: #DDE5D5; --sage-2: #EEF2E8;
  --serif: 'Fraunces', Georgia, 'Times New Roman', serif;
  --sans: 'Inter', 'Segoe UI', system-ui, -apple-system, sans-serif;
}
.stApp { background: var(--bg); color: var(--ink); font-family: var(--sans); }
.stApp p, .stApp label, .stApp li, .stApp input, .stApp textarea, .stApp button, .stApp summary, .stApp [data-baseweb] { font-family: var(--sans); }
[data-testid="stIconMaterial"], .material-icons, [class*="material-symbols"] { font-family: "Material Symbols Rounded", "Material Icons" !important; }
[data-testid="stHeader"] { background: transparent; }
#MainMenu, footer, [data-testid="stAppDeployButton"], .stDeployButton { visibility: hidden; }
[data-testid="stBottom"] > div, [data-testid="stBottomBlockContainer"] { background: transparent; }
.block-container { padding-top: 2.2rem; max-width: 1100px; }

h1, h2, h3, h4 { font-family: var(--serif) !important; color: var(--green) !important; font-weight: 500 !important; letter-spacing: -0.01em; }
[data-testid="stCaptionContainer"], .stCaption, small { color: var(--muted) !important; }

/* hero card */
.hero { display: flex; align-items: center; justify-content: space-between; gap: 1rem;
  background: linear-gradient(135deg, var(--sage-2) 0%, #E6ECDE 100%);
  border: 1px solid var(--line); border-radius: 26px; padding: 1.6rem 2rem; margin-bottom: 1.4rem; overflow: hidden; }
.hero .eyebrow { font-size: .72rem; letter-spacing: .22em; text-transform: uppercase; color: var(--green-2); font-weight: 600; margin-bottom: .35rem; }
.hero .name { font-family: var(--serif); font-size: 2.3rem; line-height: 1.1; color: var(--green); font-weight: 500; margin: 0 0 .5rem 0; }
.hero .sub { color: var(--muted); font-size: .98rem; max-width: 30rem; margin: 0; }
.hero svg { flex: 0 0 auto; height: 150px; width: auto; }
@media (max-width: 700px) { .hero svg { display: none; } .hero .name { font-size: 1.8rem; } }

/* sidebar */
[data-testid="stSidebar"] { background: var(--card); border-right: 1px solid var(--line); }
[data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 { font-size: 1.25rem !important; }

/* buttons */
.stButton > button, .stDownloadButton > button, [data-testid^="stBaseButton"] {
  border-radius: 999px !important; border: 1px solid var(--line); background: var(--card); color: var(--green);
  font-weight: 500; padding: .45rem 1.2rem; transition: all .15s ease; }
.stButton > button:hover, .stDownloadButton > button:hover { border-color: var(--green-2); color: var(--green); background: var(--sage-2); }
.stButton > button[kind="primary"], [data-testid="stBaseButton-primary"] {
  background: var(--green) !important; color: #fff !important; border-color: var(--green) !important; }
.stButton > button[kind="primary"]:hover, [data-testid="stBaseButton-primary"]:hover { background: var(--green-2) !important; }

/* chat */
[data-testid="stChatMessage"] { background: var(--card); border: 1px solid var(--line); border-radius: 20px; padding: 1rem 1.2rem; margin-bottom: .7rem; }
[data-testid="stChatInput"] { border-radius: 999px; border: 1px solid var(--line); background: var(--card); }
[data-testid="stChatInput"] textarea { background: transparent; }

/* cards: expanders, dataframes, inputs */
[data-testid="stExpander"] { background: var(--card); border: 1px solid var(--line) !important; border-radius: 16px; }
[data-testid="stExpander"] summary { font-weight: 500; color: var(--green); }
[data-testid="stDataFrame"] { border: 1px solid var(--line); border-radius: 16px; overflow: hidden; }
[data-baseweb="select"] > div, [data-baseweb="input"] > div, [data-testid="stFileUploader"] section {
  border-radius: 14px !important; border-color: var(--line) !important; background: var(--card) !important; }
[data-testid="stAlert"] { border-radius: 16px; border: 1px solid var(--line); }
[data-testid="stProgress"] > div > div > div { background: var(--green); }
hr { border-color: var(--line) !important; }
[data-baseweb="tag"] { background: var(--sage) !important; color: var(--green) !important; border-radius: 999px !important; }
</style>
"""
st.markdown(THEME_CSS, unsafe_allow_html=True)

HERO_SVG = """<svg viewBox="0 0 200 180" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
<path d="M28 120c-8-44 22-92 70-100 52-8 84 36 74 82-8 38-52 62-98 56-26-4-42-18-46-38z" fill="#D5DFCB" opacity=".75"/>
<g transform="translate(100,114)">
<path transform="rotate(-52) scale(.9)" d="M0 0C-14-26-12-58 0-84 12-58 14-26 0 0Z" fill="#7C9A77"/>
<path transform="rotate(-26)" d="M0 0C-14-26-12-58 0-84 12-58 14-26 0 0Z" fill="#3F6444"/>
<path transform="rotate(0) scale(1.12)" d="M0 0C-14-26-12-58 0-84 12-58 14-26 0 0Z" fill="#2F5233"/>
<path transform="rotate(27)" d="M0 0C-14-26-12-58 0-84 12-58 14-26 0 0Z" fill="#4B6F4F"/>
<path transform="rotate(54) scale(.9)" d="M0 0C-14-26-12-58 0-84 12-58 14-26 0 0Z" fill="#8FAA89"/>
</g>
<path d="M70 112h60l-6 48q-1 6-7 6H83q-6 0-7-6z" fill="#5E7F5A"/>
<rect x="66" y="108" width="68" height="9" rx="4.5" fill="#4B6F4F"/>
</svg>"""

st.markdown(
    '<div class="hero"><div>'
    '<div class="eyebrow">Document knowledge assistant</div>'
    '<div class="name">Ask Our Documents</div>'
    '<p class="sub">Ask in English or Bahasa Malaysia. Answers come only from your documents, with sources.</p>'
    f'</div>{HERO_SVG}</div>',
    unsafe_allow_html=True,
)

# One-time upgrade: older indexes lack the access-level info, so rebuild automatically.
# First start (nothing indexed yet) is handled the same way, so no separate "python ingest.py" is needed.
if not st.session_state.get("auto_indexed") and (rag.needs_reindex() or rag.needs_first_index()):
    st.session_state["auto_indexed"] = True  # try once per session, so a failure can never loop
    try:
        with st.spinner("Setting up for the first time: reading and indexing your documents "
                        "(about a minute, one time only)..."):
            rag.ingest_all(progress=lambda m: None)
    except Exception as e:  # most often: Ollama is not running or the models are not downloaded
        st.error("Could not index the documents. Make sure the Ollama app is running and you have run "
                 "`ollama pull bge-m3` and `ollama pull llama3.2:3b`. Then refresh this page.\n\n"
                 f"Details: {e}")
        st.stop()
    st.rerun()

ROLE_HELP = {
    "Public": "Sees public documents only.",
    "Staff": "Sees public + internal documents.",
    "Manager": "Sees everything, and can add or reclassify documents.",
}

# ---------------- sidebar ----------------
with st.sidebar:
    st.header("👤 Your role")
    role = st.radio("Role (demo)", list(rag.ROLE_ACCESS), index=2, horizontal=True, label_visibility="collapsed")
    levels = rag.ROLE_ACCESS[role]
    is_manager = role == "Manager"
    st.caption(ROLE_HELP[role])

    st.divider()
    st.header("Documents")
    st.write(f"Indexed chunks: **{rag.get_collection().count()}**")

    lib = rag.library_summary(levels)
    hidden = rag.hidden_count(levels)
    with st.expander(f"📚 Library ({sum(len(v) for v in lib.values())} files)"):
        if not lib:
            st.caption("Nothing available for this role.")
        for t in sorted(lib):
            st.markdown(f"**{t}** ({len(lib[t])})")
            for n, info in sorted(lib[t].items()):
                st.caption("• " + rag.file_label(n, info))
        if hidden:
            st.caption(f"🔒 {hidden} file{'' if hidden == 1 else 's'} hidden for your role")

    types = rag.list_doc_types(levels)
    chosen = st.multiselect("Filter by document type", options=types, default=[])
    top_k = st.slider("Passages to use", 2, 8, 5)
    debug = st.checkbox("Show search distances (debug)", value=False)

    if is_manager:
        st.divider()
        st.subheader("Add a document")
        up = st.file_uploader("PDF, DOCX, TXT or MD", type=["pdf", "docx", "txt", "md"])
        new_type = st.selectbox("Document type", ["sop", "circular", "minutes", "policy", "guideline", "report", "general"])
        suggested = rag.default_level(new_type, up.name if up else None)
        new_level = st.selectbox("Who can see it?", rag.LEVELS, index=rag.LEVELS.index(suggested))
        if up and st.button("Add & index"):
            folder = rag.DOCS_DIR / new_type
            folder.mkdir(parents=True, exist_ok=True)
            dest = folder / up.name
            dest.write_bytes(up.getbuffer())
            rag.save_file_level(up.name, new_level)
            with st.spinner("Indexing..."):
                n = rag.ingest_file(dest, doc_type=new_type, classification=new_level)
            st.success(f"Added {up.name} ({n} chunks)")
            st.rerun()

        with st.expander("Change who can see a document"):
            infos = {n: i for t in lib.values() for n, i in t.items()}
            if infos:
                target = st.selectbox("Document", sorted(infos))
                cur = infos[target].get("classification", "internal")
                level_pick = st.selectbox("New level", rag.LEVELS, index=rag.LEVELS.index(cur))
                if st.button("Apply"):
                    rag.set_classification(target, level_pick)
                    st.rerun()
            else:
                st.caption("No documents yet.")

        if st.button("Re-index everything in docs/"):
            with st.spinner("Indexing all documents..."):
                total = rag.ingest_all(progress=lambda m: None)
            st.success(f"Done: {total} chunks")
            st.rerun()

# ---------------- main area: two modes ----------------
mode = st.radio("Mode", ["💬 Ask documents", "📝 Action items"], horizontal=True, label_visibility="collapsed")


def show_sources(hits):
    with st.expander(f"Sources ({len(hits)})"):
        for i, h in enumerate(hits, start=1):
            m = h["meta"]
            st.markdown(f"**[{i}] {m['source']}** · page {m['page']} · _{m['doc_type']}_ · {m.get('classification', '')}")
            st.caption(h["text"][:400] + ("..." if len(h["text"]) > 400 else ""))


if mode == "💬 Ask documents":
    # each role has its own chat history, so switching role never reveals another role's messages
    history = st.session_state.setdefault("chats", {}).setdefault(role, [])

    for msg in history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg.get("hits"):
                show_sources(msg["hits"])

    question = st.chat_input("e.g. What is the procedure for approving staff leave?")
    if question:
        history.append({"role": "user", "content": question})
        with st.chat_message("user"):
            st.markdown(question)

        with st.chat_message("assistant"):
            catalog = rag.answer_catalog_question(question, levels)  # "how many files...?" from the database
            rd = None
            injection = (not catalog) and rag.is_injection(question)  # "ignore all instructions ..."
            if catalog or injection:
                hits, best = [], None
            else:
                with st.spinner("Searching documents..."):
                    hits, best = rag.retrieve(question, k=top_k, doc_types=chosen or None, levels=levels)
                    rd = rag.restricted_distance(question, levels)  # best match among hidden documents
            locked = (not catalog) and (not injection) and (rag.lock_applies(rd, best) or rag.keyword_lock(question, levels))
            lock_message = (f"🔒 This looks related to a document that is restricted for the **{role}** role. "
                            "Please ask a Manager for access.")

            if catalog:
                reply = catalog
                st.markdown(reply)
            elif injection:
                reply = ("I can only answer questions about the documents, and I can't change my rules. "
                         "Please ask a question about your documents.")
                st.markdown(reply)
            elif locked:
                reply = lock_message
                st.markdown(reply)
                hits = []
            elif not hits or (best is not None and best > rag.MAX_DISTANCE) or not rag.grounded(question, hits):
                if rag.get_collection().count() == 0:
                    reply = "No documents are indexed yet. Add some in the sidebar or run `python ingest.py`."
                else:
                    reply = ("I couldn't find anything relevant to that in the documents, "
                             "so I'd rather not guess. Try rephrasing, or check the document filter.")
                st.markdown(reply)
                hits = []
            else:
                slot = st.empty()
                with slot.container():
                    reply = st.write_stream(rag.answer_stream(question, hits))
                if rag.looks_like_refusal(reply):
                    # The model found nothing useful: don't show sources that don't answer anything.
                    # If a hidden document is a plausible match, say so instead of a bare "not found".
                    if rd is not None and rd <= rag.MAX_DISTANCE:
                        reply = lock_message
                    slot.markdown(reply)
                    hits = []
                else:
                    with slot.container():
                        st.markdown(reply)
                        show_sources(hits)

            if debug and not catalog:
                fmt = lambda x: "none" if x is None else f"{x:.2f}"
                st.caption(f"🛠 debug: best visible match {fmt(best)} · best hidden match {fmt(rd)} · "
                           f"limit {rag.MAX_DISTANCE:.2f} (lower = closer)")

        history.append({"role": "assistant", "content": reply, "hits": hits})

else:
    st.subheader("📝 Meeting minutes → action items")
    st.caption("Pick a document. The app reads it and lists the decisions, tasks, owners and deadlines.")

    files = sorted(((t, n) for t in lib for n in lib[t]), key=lambda x: (x[0] != "minutes", x[0], x[1]))
    if not files:
        st.info("No documents are available for your role.")
    else:
        names = [n for _, n in files]
        kind = {n: t for t, n in files}
        choice = st.selectbox("Document", names, format_func=lambda n: f"{n}  ({kind[n]})")

        use_ai = st.checkbox("Use the AI to read the whole document (slower; for minutes without ACTION:/DECISION: labels)",
                             value=False)

        def request_cancel():
            st.session_state["cancelled"] = True

        if st.session_state.pop("cancelled", False):
            st.info("Extraction cancelled.")

        if st.button("Extract action items", type="primary"):
            # Clicking Cancel while this runs makes Streamlit stop this run and start a new one
            # (with the extract button not pressed), so nothing more is processed.
            cancel_slot = st.empty()
            cancel_slot.button("✖ Cancel", key="cancel_extract", on_click=request_cancel)
            bar = st.progress(0.0, text="Reading the document...")

            def on_progress(i, total):
                bar.progress(min(i / total, 1.0), text=f"Reading part {min(i + 1, total)} of {total}...")

            found, method = rag.extract_action_items(choice, levels, progress=on_progress, use_ai=use_ai)
            bar.empty()
            cancel_slot.empty()
            st.session_state.setdefault("actions", {})[role] = {"source": choice, "items": found, "method": method}

        res = st.session_state.get("actions", {}).get(role)  # results are kept per role too
        if res and res["source"] == choice:
            items = res["items"]
            if not items:
                st.warning("No action items or decisions were found in this document.")
            else:
                n_act = sum(1 for i in items if i["type"] == "Action")
                st.success(f"Found {n_act} action{'' if n_act == 1 else 's'} and "
                           f"{len(items) - n_act} decision{'' if len(items) - n_act == 1 else 's'} in {choice}")
                rows = [{"Type": i["type"], "Description": i["description"],
                         "Owner": i["owner"], "Deadline": i["deadline"]} for i in items]
                st.dataframe(rows, hide_index=True)

                buf = io.StringIO()
                writer = csv.DictWriter(buf, fieldnames=["Type", "Description", "Owner", "Deadline"])
                writer.writeheader()
                writer.writerows(rows)
                st.download_button("⬇️ Download as CSV", data=("﻿" + buf.getvalue()).encode("utf-8"),
                                   file_name=f"{Path(choice).stem}_action_items.csv", mime="text/csv")
            if res.get("method") == "rules":
                st.caption("⚡ Read instantly from the ACTION:/DECISION: labels in the document. Please still check it against the document.")
            else:
                st.caption("🤖 Extracted with the AI, which can miss or mix up items. Please check it against the document.")
