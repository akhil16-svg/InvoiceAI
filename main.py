import streamlit as st
from dotenv import load_dotenv
load_dotenv()
from PIL import Image
import pytesseract
from utils import InvoiceParser, InvoiceDatabase, analytics
import json
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import base64

# ----------------- INIT -------------------
from utils.auth import init_auth_state, AuthSystem
init_auth_state()

# These are still needed for the sidebar stats
@st.cache_resource
def init_parser():
    return InvoiceParser(use_llm=False)

def get_database():
    if st.session_state.get('logged_in', False) and st.session_state.user:
        return InvoiceDatabase(user_email=st.session_state.user['email'], db_type='postgres')
    return InvoiceDatabase(db_type='postgres')

parser = init_parser()
db = get_database()

st.set_page_config(
    page_title="Invoice Intelligence Platform",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ----------- GEAR ICON (top-right account access) -----------
def render_account_gear():
    """Render a gear icon in the top-right for account access"""
    col_spacer, col_gear = st.columns([12, 1])
    with col_gear:
        with st.popover("⚙️", use_container_width=True):
            if st.session_state.get('logged_in', False) and st.session_state.get('user'):
                user = st.session_state.user
                st.markdown(f"### 👤 {user['name']}")
                st.markdown(f"📧 {user['email']}")
                st.markdown("---")
                if st.button("🚪 Logout", use_container_width=True, key="gear_logout_home"):
                    st.session_state.logged_in = False
                    st.session_state.user = None
                    st.rerun()
                with st.expander("🔑 Change Password"):
                    auth = AuthSystem()
                    old_pwd = st.text_input("Current Password", type="password", key="gear_old_pwd")
                    new_pwd = st.text_input("New Password", type="password", key="gear_new_pwd")
                    new_pwd_confirm = st.text_input("Confirm", type="password", key="gear_confirm_pwd")
                    if st.button("Update Password", key="gear_update_pwd"):
                        if new_pwd != new_pwd_confirm:
                            st.error("Passwords don't match")
                        elif len(new_pwd) < 6:
                            st.error("Min 6 characters")
                        else:
                            result = auth.change_password(user['email'], old_pwd, new_pwd)
                            if result['success']:
                                st.success("✅ Password changed!")
                            else:
                                st.error(result['error'])
            else:
                st.markdown("### 🔐 Account")
                st.markdown("You are not logged in.")
                st.markdown("---")
                from utils.auth import show_login_page
                show_login_page()

render_account_gear()

# -------------- SAGE-INSPIRED DARK THEME CSS --------------
# This CSS is the *complete* version with all our changes
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap');
    
    * {
        margin: 0;
        padding: 0;
        font-family: 'Inter', sans-serif;
    }
    
    html, body {
        scroll-behavior: smooth;
        background-color: #1a1a1a; /* Dark base color */
        color: #e0e0e0;
    }
    
    /* This is the main gradient background */
    [data-testid="stApp"] {
        background: linear-gradient(180deg, #2d2d2d 0%, #1a1a1a 100%);
        color: #e0e0e0;
    }
    
    /* HIDE STREAMLIT'S DEFAULT MULTI-PAGE NAV AND SIDEBAR */
    [data-testid="stSidebarNav"] {
        display: none;
    }
    [data-testid="stSidebar"] {
        display: none !important;
    }
    [data-testid="collapsedControl"] {
        display: none !important;
    }

    /* Hide Streamlit defaults */
    MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    # header {visibility: hidden;}
    .stDeployButton {display: none;}
    
    /* 1. Make the header bar INVISIBLE, but functional */
header {
    visibility: visible !important; /* Make sure it's visible */
    background: none !important; /* Remove its background */
    box-shadow: none !important; /* Remove its shadow */
}

/* 2. Style the button itself to look like a floating icon */
[data-testid="stSidebarNavToggler"] {
    color: #00D639; /* Make the arrow Sage Green */
    background-color: rgba(26, 26, 26, 0.8); /* Give it a dark glass background */
    border-radius: 50px; /* Make it a circle */
    padding: 8px 10px; /* Adjust padding */
    margin-top: 10px;
    margin-left: 10px;
    transition: all 0.3s ease;
    border: 1px solid rgba(0, 214, 57, 0.5); /* Subtle green border */
}

/* 3. Add a hover effect to the button */
[data-testid="stSidebarNavToggler"]:hover {
    background-color: #00D639; /* Green on hover */
    color: #000000; /* Black arrow on hover */
    transform: scale(1.1);
}
            
    /* Main container */
    .main .block-container {
        padding: 0 !important;
        max-width: 100% !important;
    }
    
    /* Hero Section - Dark Theme */
    .hero-section {
        min-height: 50vh;
        width: 100%;
        display: flex;
        flex-direction: column;
        justify-content: center;
        align-items: center;
        color: white;
        position: relative;
        overflow: hidden;
        /* Using a subtle dark overlay */
        background: linear-gradient(135deg, 
            rgba(13, 13, 18, 0.7) 0%, 
            rgba(26, 26, 26, 0.7) 100%);
        animation: fadeIn 1.5s ease-out;
    }



# .hero-section {
#     /* ... (all your existing .hero-section styles) ... */

#     /* Add this transition for the new shadow effect */
#     transition: box-shadow 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275);
# }

/* Green animated top border, just like the feature-card */
.hero-section::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 6px; /* You can make this thicker if you want */
    background: linear-gradient(90deg, #00D639 0%, #00c800 100%);
    transform: scaleX(0);
    transform-origin: left;
    transition: transform 0.2s ease;
}

/* This adds the green glow shadow */
.hero-section:hover {
     box-shadow: 0 15px 40px rgba(0, 214, 57, 0.2);
}

/* This triggers the border animation on hover */
.hero-section:hover::before {
    transform: scaleX(1);
}
    
    /* Particles container */
    #particles-js {
        position: absolute;
        width: 100%;
        height: 100%;
        top: 0;
        left: 0;
        z-index: 1;
        pointer-events: none;
    }
    
    .hero-content {
        position: relative;
        z-index: 10;
        text-align: center;
        padding: 0 20px;
    }
    
    .hero-title {
        font-size: 5rem;
        font-weight: 900;
        margin-bottom: 30px;
        background: linear-gradient(135deg, #ffffff 0%, #00D639 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        text-shadow: 0 0 60px rgba(0, 214, 57, 0.3);
        letter-spacing: 3px;
        animation: slideDown 1.2s cubic-bezier(0.34, 1.56, 0.64, 1);
    }
    
    .hero-subtitle {
        font-size: 1.8rem;
        color: rgba(255, 255, 255, 0.95);
        font-weight: 400;
        margin-bottom: 40px;
        max-width: 800px;
        line-height: 1.6;
        animation: slideUp 1.2s cubic-bezier(0.34, 1.56, 0.64, 1);
        text-shadow: 0 2px 10px rgba(0, 0, 0, 0.5);
    }
    
    .hero-description {
        font-size: 1.2rem;
        color: rgba(255, 255, 255, 0.85);
        max-width: 700px;
        margin: 0 auto 50px;
        line-height: 1.8;
        animation: fadeIn 1.5s ease-out 0.5s both;
    }
    
    .scroll-indicator {
        position: absolute;
        bottom: 40px;
        left: 50%;
        transform: translateX(-50%);
        color: #00D639;
        font-size: 2.5rem;
        animation: bounce 2s infinite;
        cursor: pointer;
        z-index: 10;
        text-shadow: 0 2px 10px rgba(0, 0, 0, 0.5);
    }
    
    /* Wave Divider */
   .wave-divider {
        position: relative;
        width: 100%;
        height: 80px;
        margin-top: -1px;
    }
    
   .wave-svg {
        position: absolute;
        bottom: 0;
        left: 0;
        width: 100%;
        height: 100%;
    }
    
    /* Section Styling - Dark Theme */
    .section {
        padding: 100px 5%;
        position: relative;
        animation: fadeInSection 0.8s ease-out;
        background: rgba(13, 13, 18, 0.6); 
        backdrop-filter: blur(5px);
    }
    
    /* Darker, blended panels */
    .section-light, .section-cream {
        background: linear-gradient(180deg, 
            rgba(13, 13, 18, 0.9) 0%,
            rgba(20, 20, 25, 0.9) 100%);
        border-top: 1px solid rgba(255, 255, 255, 0.1);
        border-bottom: 1px solid rgba(255, 255, 255, 0.1);
    }
    
    .section-sage {
        background: linear-gradient(135deg, 
            #00D639 0%, 
            #00a02b 100%);
        color: white;
    }
    
    .section-dark {
        background: linear-gradient(135deg, 
            #1a1a1a 0%, 
            #2d2d2d 50%,
            #1a1a1a 100%);
        color: white;
    }
    
    .section-header {
        text-align: center;
        margin-bottom: 80px;
    }
    
    .section-title {
        font-size: 3.5rem;
        font-weight: 800;
        margin-bottom: 20px;
        position: relative;
        display: inline-block;
        letter-spacing: 2px;
        color: #ffffff;
    }
    
    .section-title::after {
        content: '';
        position: absolute;
        bottom: -15px;
        left: 50%;
        transform: translateX(-50%);
        width: 100px;
        height: 5px;
        background: linear-gradient(90deg, transparent, #00D639, transparent);
        border-radius: 3px;
        animation: expandWidth 1s ease-out;
    }
    
    .section-subtitle {
        font-size: 1.3rem;
        color: rgba(255, 255, 255, 0.8);
        max-width: 800px;
        margin: 30px auto 0;
        line-height: 1.8;
    }
    
    .section-sage .section-title,
    .section-dark .section-title {
        color: white;
    }
    
    .section-sage .section-subtitle,
    .section-dark .section-subtitle {
        color: rgba(255, 255, 255, 0.9);
    }
    
    /* Feature Cards - Dark Theme (Glassmorphism) */
    .features-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
        gap: 40px;
        margin-top: 60px;
    }
    
    .feature-card {
        background: linear-gradient(135deg, rgba(25, 25, 30, 0.85) 0%, rgba(15, 15, 20, 0.85) 100%);
        backdrop-filter: blur(10px);
        padding: 50px 40px;
        border-radius: 24px;
        box-shadow: 0 10px 40px rgba(0, 0, 0, 0.2);
        transition: all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275);
        border: 1px solid rgba(255, 255, 255, 0.1);
        position: relative;
        overflow: hidden;
    }
    
    .feature-card::before {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        width: 100%;
        height: 6px;
        background: linear-gradient(90deg, #00D639 0%, #00c800 100%);
        transform: scaleX(0);
        transform-origin: left;
        transition: transform 0.5s ease;
    }
    
    .feature-card:hover::before {
        transform: scaleX(1);
    }
    
    .feature-card:hover {
        transform: translateY(-15px) scale(1.03);
        box-shadow: 0 20px 60px rgba(0, 214, 57, 0.2);
        border-color: #00D639;
    }
    
    .feature-icon {
        font-size: 4rem;
        margin-bottom: 25px;
        display: inline-block;
        animation: float 3s ease-in-out infinite;
        filter: drop-shadow(0 4px 10px rgba(0, 214, 57, 0.3));
    }
    
    # @keyframes float {
    #     0%, 100% { transform: translateY(0); }
    #     50% { transform: translateY(-12px); }
    # }
    
    /* This rule fixes the unreadable card text */
    .feature-title {
        font-size: 1.8rem;
        font-weight: 700;
        color: #ffffff !important; 
        margin-bottom: 15px;
    }
    
    .feature-description {
        color: rgba(255, 255, 255, 0.85) !important;
        line-height: 1.8;
        font-size: 1.1rem;
    }
    
    /* Stats Boxes */
    .stats-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
        gap: 30px;
        margin-top: 60px;
    }
    
    .stat-box {
        text-align: center;
        padding: 40px 30px;
        background: linear-gradient(135deg, rgba(255,255,255,0.15) 0%, rgba(255,255,255,0.05) 100%);
        border-radius: 20px;
        backdrop-filter: blur(15px);
        border: 2px solid rgba(255, 255, 255, 0.3);
        transition: all 0.4s ease;
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
    }
    
    .stat-box:hover {
        background: linear-gradient(135deg, rgba(255,255,255,0.25) 0%, rgba(255,255,255,0.15) 100%);
        transform: translateY(-10px) scale(1.05);
        box-shadow: 0 15px 45px rgba(0, 0, 0, 0.2);
    }
    
    .stat-number {
        font-size: 3.5rem;
        font-weight: 800;
        background: linear-gradient(135deg, #ffffff 0%, #00D639 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        margin-bottom: 10px;
        display: block;
    }
    
    .stat-label {
        font-size: 1.1rem;
        color: rgba(255, 255, 255, 0.95);
        text-transform: uppercase;
        letter-spacing: 2px;
        font-weight: 600;
    }
    
    /* Dark Upload Zone */
    .upload-zone {
        border: 3px dashed #00D639;
        border-radius: 24px;
        padding: 80px 60px;
        text-align: center;
        background: rgba(13, 13, 18, 0.8);
        transition: all 0.4s ease;
        position: relative;
        overflow: hidden;
    }
    
    .upload-zone::before {
        content: '📤';
        position: absolute;
        font-size: 20rem;
        opacity: 0.03;
        top: 50%;
        left: 50%;
        transform: translate(-50%, -50%) rotate(-15deg);
        pointer-events: none;
    }
    
    .upload-zone:hover {
        border-color: #00c800;
        background: rgba(20, 20, 25, 0.9);
        transform: scale(1.02);
        box-shadow: 0 20px 60px rgba(0, 214, 57, 0.2);
    }
    
    /* Sidebar Styling - Dark */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #1a1a1a 0%, #2d2d2d 100%);
        border-right: 3px solid #00D639;
    }
    
    [data-testid="stSidebar"] * {
        color: #ffffff !important;
    }
    
    /* Metrics */
    [data-testid="stMetricValue"] {
        font-size: 2.5rem !important;
        font-weight: 800 !important;
        background: linear-gradient(135deg, #00D639 0%, #00c800 100%);
        -webkit-background-clip: text !important;
        -webkit-text-fill-color: transparent !important;
        background-clip: text !important;
    }
    
    [data-testid="stMetricLabel"] {
        font-size: 1rem !important;
        color: rgba(255, 255, 255, 0.7) !important;
        font-weight: 600 !important;
    }
    
    /* THIS IS THE NEW STYLE FOR THE PYTHON BUTTONS */
    .stButton > button {
        border: 1px solid rgba(255, 255, 255, 0.2);
        background: linear-gradient(135deg, rgba(255, 255, 255, 0.1) 0%, rgba(255, 255, 255, 0.05) 100%);
        backdrop-filter: blur(10px);
        color: #ffffff;
        font-size: 1rem;
        font-weight: 600;
        border-radius: 12px;
        padding: 12px 24px;
        cursor: pointer;
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        box-shadow: 0 4px 15px rgba(0, 0, 0, 0.2);
        width: 100%; /* Make button fill its column */
    }
    
    .stButton > button:hover {
        transform: translateY(-5px) scale(1.05);
        border-color: #00D639;
        background: linear-gradient(135deg, rgba(0, 214, 57, 0.2) 0%, rgba(0, 214, 57, 0.1) 100%);
        box-shadow: 0 8px 30px rgba(0, 214, 57, 0.4);
    }

    /* Fix for the horizontal rules */
    hr {
        border: none;
        height: 1px;
        background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.2), transparent);
        margin: 40px 0 !important;
    }
    
    /* Streamlit specific dark theme overrides */
    .stTextInput > div > div > input, .stTextArea > div > textarea {
        background-color: rgba(13, 13, 18, 0.9);
        color: #ffffff;
        border: 1px solid rgba(255, 255, 255, 0.2);
        border-radius: 8px;
    }
    
    .stDataFrame {
        border: 1px solid rgba(255, 255, 255, 0.2);
        border-radius: 12px;
        overflow: hidden;
    }
    
    .stPlotlyChart {
        border-radius: 12px;
        overflow: hidden;
    }
    
    .stExpander {
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 12px;
        background: rgba(13, 13, 18, 0.8);
    }
    
    /* Animations */
    @keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
    @keyframes slideDown { from { opacity: 0; transform: translateY(-80px); } to { opacity: 1; transform: translateY(0); } }
    @keyframes slideUp { from { opacity: 0; transform: translateY(80px); } to { opacity: 1; transform: translateY(0); } }
    @keyframes fadeInSection { from { opacity: 0; transform: translateY(50px); } to { opacity: 1; transform: translateY(0); } }
    @keyframes bounce { 0%, 20%, 50%, 80%, 100% { transform: translateX(-50%) translateY(0); } 40% { transform: translateX(-50%) translateY(-20px); } 60% { transform: translateX(-50%) translateY(-10px); } }
    @keyframes expandWidth { from { width: 0; } to { width: 100px; } }
    
    /* Smooth scrolling (for hero section only) */
    html { scroll-behavior: smooth; }
    
    /* Custom Scrollbar */
    ::-webkit-scrollbar { width: 12px; }
    ::-webkit-scrollbar-track { background: #1a1a1a; }
    ::-webkit-scrollbar-thumb { background: linear-gradient(180deg, #00D639 0%, #00c800 100%); border-radius: 6px; }
    ::-webkit-scrollbar-thumb:hover { background: #00D639; }
    
    /* Responsive */
    @media (max-width: 768px) {
        .hero-title { font-size: 3rem; }
        .hero-subtitle { font-size: 1.3rem; }
        .section-title { font-size: 2.5rem; }
        .features-grid { grid-template-columns: 1fr; }
    }

# The below info-hero section is for the block (Why this OCR? It is inherited from the main her-section class.)


.info-hero {
    min-height: 25vh !important; /* <-- This is the new height! */
}

/* This stops the green glow shadow on hover */
.info-hero:hover {
    box-shadow: none !important;
}

# /* This stops the green top border from animating in on hover */
# .info-hero:hover::before {
#     transform: scaleX(0) !important;
# }

     /* Login/Register Form Styling */
    .stTabs [data-baseweb="tab-list"] {
        gap: 20px;
    }
    
    .stTabs [data-baseweb="tab"] {
        padding: 12px 24px;
        background: rgba(0, 220, 131, 0.1);
        border-radius: 8px;
    }
    
    .stTabs [aria-selected="true"] {
        background: #00DC83;
        color: #000000 !important;
    }
    
    [data-testid="stForm"] {
        background: rgba(0, 0, 0, 0.3);
        padding: 30px;
        border-radius: 16px;
        border: 1px solid rgba(0, 220, 131, 0.3);
    }           
</style>
""", unsafe_allow_html=True)

# Wave divider function
def wave_divider():
    st.markdown("""
        <div class="wave-divider">
            <svg class="wave-svg" viewBox="0 0 1440 80" fill="none" xmlns="http://www.w.org/2000/svg">
                <path d="M0,40 C240,80 480,0 720,40 C960,80 1200,0 1440,40 L1440,80 L0,80 Z" 
                      fill="url(#wave-gradient)" fill-opacity="1"/>
                <defs>
                    <linearGradient id="wave-gradient" x1="0%" y1="0%" x2="100%" y2="0%">
                        <stop offset="0%" style="stop-color:#00D639;stop-opacity:0.3" />
                        <stop offset="50%" style="stop-color:#00c800;stop-opacity:0.5" />
                        <stop offset="100%" style="stop-color:#00D639;stop-opacity:0.3" />
                    </linearGradient>
                </defs>
            </svg>
        </div>
    """, unsafe_allow_html=True)

    st.markdown("---")
    
# Sidebar removed — account access is now in the gear icon

# ----------- NEW PYTHON NAVIGATION BUTTONS -----------
# This replaces your old HTML nav-tabs
st.markdown('<div style="margin-top: -30px; position: relative; z-index: 50; animation: slideUp 1.2s cubic-bezier(0.34, 1.56, 0.64, 1);">', unsafe_allow_html=True)
cols = st.columns(5)

# We use the file names from the 'pages' folder
page_files = {
    "Home": "main.py",
    "Upload": "pages/1_📤_Upload.py",
    "Fraud Detection": "pages/2_🔍_Fraud_Detection.py",
    "Analytics": "pages/3_📊_Analytics.py",
    "Database": "pages/4_💾_Database.py"
}

with cols[0]:
    if st.button("🏠 Home", use_container_width=True):
        st.switch_page(page_files["Home"])
with cols[1]:
    if st.button("📤 Upload", use_container_width=True):
        st.switch_page(page_files["Upload"])
with cols[2]:
    if st.button("🔍 Fraud Detection", use_container_width=True):
        st.switch_page(page_files["Fraud Detection"])
with cols[3]:
    if st.button("📊 Analytics", use_container_width=True):
        st.switch_page(page_files["Analytics"])
with cols[4]:
    if st.button("💾 Database", use_container_width=True):
        st.switch_page(page_files["Database"])
st.markdown('</div>', unsafe_allow_html=True)

# ----------- HERO SECTION (HOME PAGE) -------------
st.markdown('<a name="home"></a>', unsafe_allow_html=True)
st.markdown("""
<div class="hero-section">
    <div id="particles-js"></div>
    <div class="hero-content">
        <h1 class="hero-title">Invoice Intelligence Platform</h1>
        <p class="hero-subtitle">
            Transform invoices into actionable insights with AI-powered OCR technology
        </p>
        <p class="hero-description">
            Process, analyze, and detect fraud on all your invoices instantly. 
            Built with cutting-edge machine learning for maximum accuracy and security.
        </p>
</div>
""", unsafe_allow_html=True)

wave_divider()




# ----------- WHY CHOOSE THIS OCR (HOME PAGE) -------------


# 1. The Header (this text now goes *inside* the box)
# st.markdown("""
#     <div class="section-header">
#         <h2 class="section-title">Why This Invoice OCR?</h2>
#         <p class="section-subtitle">
#             Built as a comprehensive solution to automate invoice processing, eliminate manual data entry, 
#             and detect fraudulent documents before they impact your business.
#         </p>
#     </div>
# """, unsafe_allow_html=True)

st.markdown("""
<div class="hero-section info-hero">
    <div id="particles-js"></div>
    <div class="hero-content">
        <h1 class="hero-title">Why this tool...</h1>
        <p class="hero-subtitle">
            Built as a comprehensive solution to automate invoice processing, eliminate manual data entry,
            and detect fraudulent documents before they impact your business. 
            Trained on 500+ real-world invoices across multiple industries to deliver production-grade accuracy.
        </p>
    </div>
    <div class="scroll-indicator">↓</div>
</div>
""", unsafe_allow_html=True)

wave_divider()

# 2. The Feature Cards — row 1
col1, col2, col3 = st.columns(3)

with col1:
    st.markdown("""
        <div class="feature-card">
            <div class="feature-icon">⚡</div>
            <h3 class="feature-title">Lightning-Fast OCR</h3>
            <p class="feature-description">
                Process hundreds of invoices in seconds with 99.2% accuracy. Advanced text recognition 
                handles any invoice format, even from low-quality photos.
            </p>
        </div>
    """, unsafe_allow_html=True)

with col2:
    st.markdown("""
        <div class="feature-card">
            <div class="feature-icon">🛡️</div>
            <h3 class="feature-title">AI Fraud Detection</h3>
            <p class="feature-description">
                8+ intelligent fraud detection algorithms identify suspicious patterns, duplicates, 
                mathematical errors, and anomalies automatically.
            </p>
        </div>
    """, unsafe_allow_html=True)

with col3:
    st.markdown("""
        <div class="feature-card">
            <div class="feature-icon">📊</div>
            <h3 class="feature-title">Real-time Analytics</h3>
            <p class="feature-description">
                Gain instant insights into spending trends, vendor performance, and financial patterns 
                with interactive visualizations and reports.
            </p>
        </div>
    """, unsafe_allow_html=True)

# Feature Cards — row 2
col4, col5, col6 = st.columns(3)

with col4:
    st.markdown("""
        <div class="feature-card">
            <div class="feature-icon">🎓</div>
            <h3 class="feature-title">Trained on 500+ Invoices</h3>
            <p class="feature-description">
                Our OCR model has been trained and validated on over 500 real-world invoices spanning 
                retail, healthcare, logistics, and professional services.
            </p>
        </div>
    """, unsafe_allow_html=True)

with col5:
    st.markdown("""
        <div class="feature-card">
            <div class="feature-icon">🔍</div>
            <h3 class="feature-title">Easy Fraud Analysis</h3>
            <p class="feature-description">
                No expertise needed. Upload an invoice and instantly see flagged anomalies — duplicate 
                invoice numbers, math mismatches, future dates, and more — in a clear, visual report.
            </p>
        </div>
    """, unsafe_allow_html=True)

with col6:
    st.markdown("""
        <div class="feature-card">
            <div class="feature-icon">💾</div>
            <h3 class="feature-title">Secure Database Storage</h3>
            <p class="feature-description">
                Every processed invoice is stored securely in PostgreSQL with per-user isolation. 
                Export to CSV or JSON anytime for your accounting workflows.
            </p>
        </div>
    """, unsafe_allow_html=True)

# 3. Close the main box
st.markdown('</div>', unsafe_allow_html=True)


# -------------- Particles.js (HOME PAGE) ---------------
st.markdown("""
<script src="https://cdn.jsdelivr.net/npm/particles.js@2.0.0/particles.min.js"></script>
<script>
window.addEventListener("DOMContentLoaded", function(){
    const particlesEl = document.getElementById("particles-js");
    if(particlesEl && typeof particlesJS !== 'undefined'){
        particlesJS("particles-js", {
            particles: {
                number: { value: 60, density: { enable: true, value_area: 800 } },
                color: { value: "#00D639" },
                shape: { type: "circle" },
                opacity: { value: 0.5, random: true, anim: { enable: true, speed: 1, opacity_min: 0.1, sync: false } },
                size: { value: 3, random: true, anim: { enable: true, speed: 2, size_min: 0.1, sync: false } },
                line_linked: { enable: true, distance: 150, color: "#00D639", opacity: 0.2, width: 1 },
                move: { enable: true, speed: 2, direction: "none", random: true, straight: false, out_mode: "out", bounce: false, attract: { enable: false } }
            },
            interactivity: {
                detect_on: "canvas",
                events: { onhover: { enable: true, mode: "grab" }, onclick: { enable: true, mode: "push" }, resize: true },
                modes: { grab: { distance: 140, line_linked: { opacity: 0.5 } }, push: { particles_nb: 4 } }
            },
            retina_detect: true
        });
    }
});
</script>
""", unsafe_allow_html=True)
