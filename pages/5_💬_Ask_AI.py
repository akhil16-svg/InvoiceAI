import streamlit as st
from dotenv import load_dotenv
load_dotenv()

from utils import InvoiceDatabase
from utils import ai_engine
from utils.rag import InvoiceRAG
from utils.auth import init_auth_state, show_login_page
from utils.ui import apply_theme, render_nav

# ----------------- INIT -------------------
init_auth_state()

st.set_page_config(
    page_title="Ask AI - Your Invoices",
    page_icon="💬",
    layout="wide",
    initial_sidebar_state="collapsed",
)

apply_theme()

if not st.session_state.get('logged_in', False):
    show_login_page()
    st.stop()

user = st.session_state.user
db = InvoiceDatabase(user_email=user['email'], db_type='postgres')


# ----------- GEAR ICON (top-right account access) -----------
def render_account_gear():
    col_spacer, col_gear = st.columns([12, 1])
    with col_gear:
        with st.popover("⚙️", use_container_width=True):
            st.markdown(f"### 👤 {user['name']}")
            st.markdown(f"📧 {user['email']}")
            st.markdown("---")
            if st.button("🚪 Logout", use_container_width=True, key="gear_logout_askai"):
                st.session_state.logged_in = False
                st.session_state.user = None
                st.rerun()

render_account_gear()
render_nav()

st.markdown("""
    <div class="section-header">
        <h2 class="section-title">💬 Ask Your Invoices</h2>
        <p class="section-subtitle">
            Questions are answered from <b>your own uploaded invoices</b> using retrieval-augmented
            generation — every answer is grounded in your documents and cites the invoices it used.
        </p>
    </div>
""", unsafe_allow_html=True)


@st.cache_data(ttl=60, show_spinner=False)
def load_invoices(email: str):
    return InvoiceDatabase(user_email=email, db_type='postgres').get_all_invoices()


invoices = load_invoices(user['email'])
rag = InvoiceRAG(invoices)

if not invoices:
    st.info("📭 You haven't saved any invoices yet. Upload some on the **📤 Upload** page first — then come back and ask anything about them.")

ai_ready = ai_engine.is_ai_available()
if not ai_ready:
    st.warning(
        "🔑 **AI answers are disabled** — set `GOOGLE_API_KEY` in your `.env` to enable them. "
        "Until then you'll get the matching invoices for your question (retrieval only)."
    )

with st.expander("💡 Example questions"):
    st.markdown("""
- *How much did I spend in total, and at which vendor did I spend the most?*
- *Show me all invoices with fraud flags and explain why they were flagged.*
- *What did I buy from 99 Speed Mart?*
- *Which invoices are missing an invoice number or date?*
- *Compare my spending in the first and second half of the date range.*
""")

# ----------------- CHAT -------------------
if "ask_ai_messages" not in st.session_state:
    st.session_state.ask_ai_messages = []

for msg in st.session_state.ask_ai_messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        for src in msg.get("sources", []):
            st.caption(f"📄 {src}")

question = st.chat_input("Ask anything about your invoices…")

if question:
    st.session_state.ask_ai_messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    context, sources = rag.build_context(question, k=6)
    source_labels = [
        f"{inv.get('invoice_number') or 'no number'} — {inv.get('vendor_name') or 'unknown vendor'}"
        f" — {inv.get('date') or 'no date'}"
        for inv in sources
    ]

    with st.chat_message("assistant"):
        if ai_ready:
            history = [
                {"role": m["role"], "content": m["content"]}
                for m in st.session_state.ask_ai_messages[:-1]
            ]
            try:
                answer = st.write_stream(
                    ai_engine.stream_answer(question, context, history=history)
                )
            except Exception as e:
                answer = f"❌ The AI request failed: `{e}`"
                st.error(answer)
        else:
            # Retrieval-only fallback: show what RAG found
            lines = ["**Matching invoices (retrieval only — no API key configured):**\n"]
            if source_labels:
                lines += [f"- {label}" for label in source_labels]
            else:
                lines.append("_No invoices matched your question._")
            lines.append("\n**Portfolio summary:**\n```\n" + rag.aggregate_stats() + "\n```")
            answer = "\n".join(lines)
            st.markdown(answer)

        if source_labels:
            with st.expander(f"📚 Sources ({len(source_labels)} invoices used)"):
                for label in source_labels:
                    st.caption(f"📄 {label}")

    st.session_state.ask_ai_messages.append(
        {"role": "assistant", "content": answer, "sources": source_labels}
    )

col1, col2 = st.columns([5, 1])
with col2:
    if st.session_state.ask_ai_messages and st.button("🗑️ Clear chat", use_container_width=True):
        st.session_state.ask_ai_messages = []
        st.rerun()
