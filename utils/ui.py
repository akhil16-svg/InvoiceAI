"""
Shared UI helpers so new pages don't have to copy the theme/nav blocks.
"""

import streamlit as st

PAGE_FILES = {
    "Home": "main.py",
    "Upload": "pages/1_📤_Upload.py",
    "Fraud Detection": "pages/2_🔍_Fraud_Detection.py",
    "Analytics": "pages/3_📊_Analytics.py",
    "Database": "pages/4_💾_Database.py",
    "Ask AI": "pages/5_💬_Ask_AI.py",
}

NAV_BUTTONS = [
    ("🏠 Home", "Home"),
    ("📤 Upload", "Upload"),
    ("🔍 Fraud Detection", "Fraud Detection"),
    ("📊 Analytics", "Analytics"),
    ("💬 Ask AI", "Ask AI"),
    ("💾 Database", "Database"),
]

THEME_CSS = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap');
    * { margin: 0; padding: 0; font-family: 'Inter', sans-serif; }
    html, body { background-color: #1a1a1a; color: #e0e0e0; }
    [data-testid="stApp"] { background: linear-gradient(180deg, #2d2d2d 0%, #1a1a1a 100%); color: #e0e0e0; }
    [data-testid="stSidebarNav"], [data-testid="stSidebar"], [data-testid="collapsedControl"] { display: none !important; }
    footer { visibility: hidden; }
    .stDeployButton { display: none; }
    header { visibility: visible !important; background: none !important; box-shadow: none !important; }

    .section-header { text-align: center; margin: 30px 0 40px 0; }
    .section-title { font-size: 3rem; font-weight: 800; letter-spacing: 2px; color: #ffffff; }
    .section-subtitle { font-size: 1.2rem; color: rgba(255, 255, 255, 0.8); max-width: 800px; margin: 15px auto 0; line-height: 1.8; }

    .stButton > button {
        border: 1px solid rgba(255, 255, 255, 0.2);
        background: linear-gradient(135deg, rgba(255, 255, 255, 0.1) 0%, rgba(255, 255, 255, 0.05) 100%);
        backdrop-filter: blur(10px);
        color: #ffffff; font-size: 1rem; font-weight: 600;
        border-radius: 12px; padding: 12px 24px; width: 100%;
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        box-shadow: 0 4px 15px rgba(0, 0, 0, 0.2);
    }
    .stButton > button:hover {
        transform: translateY(-3px) scale(1.03);
        border-color: #00D639;
        background: linear-gradient(135deg, rgba(0, 214, 57, 0.2) 0%, rgba(0, 214, 57, 0.1) 100%);
        box-shadow: 0 8px 30px rgba(0, 214, 57, 0.4);
    }

    .stTextInput > div > div > input, .stTextArea > div > textarea, .stChatInput textarea {
        background-color: rgba(13, 13, 18, 0.9); color: #ffffff;
        border: 1px solid rgba(255, 255, 255, 0.2); border-radius: 8px;
    }
    [data-testid="stChatMessage"] {
        background: rgba(13, 13, 18, 0.6); border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 12px;
    }
    .stExpander { border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 12px; background: rgba(13, 13, 18, 0.8); }
    hr { border: none; height: 1px; background: linear-gradient(90deg, transparent, rgba(255,255,255,0.2), transparent); margin: 30px 0 !important; }
</style>
"""


def apply_theme():
    st.markdown(THEME_CSS, unsafe_allow_html=True)


def render_nav():
    """Top navigation buttons shared by every page."""
    st.markdown(
        '<div style="position: relative; z-index: 50;">',
        unsafe_allow_html=True,
    )
    cols = st.columns(len(NAV_BUTTONS))
    for col, (label, key) in zip(cols, NAV_BUTTONS):
        with col:
            if st.button(label, use_container_width=True, key=f"nav_{key}"):
                st.switch_page(PAGE_FILES[key])
    st.markdown("</div>", unsafe_allow_html=True)
