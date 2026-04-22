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
# All pages need to init the parser and db
from utils.auth import init_auth_state, show_login_page, AuthSystem
init_auth_state()

# Redirect to login if not authenticated
if not st.session_state.get('logged_in', False):
    show_login_page()
    st.stop()

@st.cache_resource
def init_parser():
    return InvoiceParser(use_llm=False)

def get_database():
    import streamlit as st
    if st.session_state.get('logged_in', False) and st.session_state.user:
        return InvoiceDatabase(user_email=st.session_state.user['email'], db_type='postgres')
    return InvoiceDatabase(db_type='postgres')

parser = init_parser()
db = get_database()

st.set_page_config(
    page_title="Fraud Detection",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ----------- GEAR ICON -----------
def render_account_gear():
    col_spacer, col_gear = st.columns([12, 1])
    with col_gear:
        with st.popover("⚙️", use_container_width=True):
            if st.session_state.get('logged_in', False) and st.session_state.get('user'):
                user = st.session_state.user
                st.markdown(f"### 👤 {user['name']}")
                st.markdown(f"📧 {user['email']}")
                st.markdown("---")
                if st.button("🚪 Logout", use_container_width=True, key="gear_logout_fraud"):
                    st.session_state.logged_in = False
                    st.session_state.user = None
                    st.rerun()
            else:
                st.markdown("### 🔐 Not logged in")
                st.info("Please log in from the Home page.")

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
        min-height: 90vh;
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
    
    @keyframes float {
        0%, 100% { transform: translateY(0); }
        50% { transform: translateY(-12px); }
    }
    
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
</style>
""", unsafe_allow_html=True)
# This is critical for keeping the style consistent when you switch pages
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
        background-color: #1a1a1a;
        color: #e0e0e0;
    }
    
    [data-testid="stApp"] {
        background: linear-gradient(180deg, #2d2d2d 0%, #1a1a1a 100%);
        color: #e0e0e0;
    }
    
    [data-testid="stSidebarNav"] {
        display: none;
    }

    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    .stDeployButton {display: none;}
    
    .main .block-container {
        padding: 0 !important;
        max-width: 100% !important;
    }
    
    /* ... (etc.) ... */
    /* ... PASTE THE ENTIRE <style> BLOCK ... */
    /* ... (omitted here for brevity) ... */
    
    /* Responsive */
    @media (max-width: 768px) {
        .hero-title { font-size: 3rem; }
        .hero-subtitle { font-size: 1.3rem; }
        .section-title { font-size: 2.5rem; }
        .features-grid { grid-template-columns: 1fr; }
    }
</style>
""", unsafe_allow_html=True)


# Wave divider function (needed on all pages)
def wave_divider():
    st.markdown("""
        <div class="wave-divider">
            <svg class="wave-svg" viewBox="0 0 1440 80" fill="none" xmlns="http://www.w3.org/2000/svg">
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
    
    # --- Kept your original Quick Stats ---
    all_invoices = db.get_all_invoices()
    st.markdown("#### 📈 Quick Stats")
    
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Invoices", len(all_invoices))
    with col2:
        fraud_stats = analytics.get_fraud_statistics(all_invoices) if all_invoices else {"flagged_invoices": 0}
        st.metric("Flagged", fraud_stats['flagged_invoices'])
    
    if all_invoices:
        total = analytics.calculate_total_spending(all_invoices)
        currency = all_invoices[0].get('currency', 'USD')
        st.metric("Total Value", f"{currency} {total:,.0f}")

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


# ----------- Fraud Detection Section (PAGE CONTENT) -------------
# This is the code you CUT from your old main.py

st.markdown('<a name="fraud"></a>', unsafe_allow_html=True)
# st.markdown('<div class="section section-light">', unsafe_allow_html=True)
st.markdown("""
    <div class="section-header">
        <h2 class="section-title">Fraud Detection Center</h2>
        <p class="section-subtitle">
            AI-powered fraud detection scans every invoice for 8+ types of suspicious patterns and anomalies
        </p>
    </div>
""", unsafe_allow_html=True)

all_invoices = db.get_all_invoices()

if not all_invoices:
    st.info("🔍 Upload invoices to see fraud analysis")
else:
    fraud_stats = analytics.get_fraud_statistics(all_invoices)
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("🔍 Total Scanned", len(all_invoices))
    with col2:
        st.metric("⚠️ Flagged", fraud_stats['flagged_invoices'],
                 delta=f"{fraud_stats['fraud_rate']*100:.1f}%", delta_color="inverse")
    with col3:
        clean = len(all_invoices) - fraud_stats['flagged_invoices']
        st.metric("✅ Clean", clean, delta=f"{(clean/len(all_invoices)*100):.0f}%")
    with col4:
        risk = "🟢 Low" if fraud_stats['fraud_rate'] < 0.05 else "🟡 Medium" if fraud_stats['fraud_rate'] < 0.15 else "🔴 High"
        st.metric("📊 Risk Level", risk)
    
    st.markdown("---")
    
    if fraud_stats['fraud_types']:
        st.markdown("### ⚠️ Fraud Type Distribution")
        
        fraud_df = pd.DataFrame(
            list(fraud_stats['fraud_types'].items()),
            columns=['Type', 'Count']
        )
        fraud_df['Type'] = fraud_df['Type'].str.replace('_', ' ').str.title()
        
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=fraud_df['Count'],
            y=fraud_df['Type'],
            orientation='h',
            marker=dict(
                color=['#ef4444', '#f59e0b', '#10b981', '#3b82f6', '#8b5cf6'][:len(fraud_df)]
            ),
            text=fraud_df['Count'],
            textposition='auto'
        ))
        fig.update_layout(
            height=300,
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            xaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.1)', title="Count", color="#fff"),
            yaxis=dict(showgrid=False, color="#fff"),
            font=dict(color="#fff"),
            margin=dict(l=0, r=0, t=10, b=0)
        )
        st.plotly_chart(fig, use_container_width=True)
    
    st.markdown("---")
    st.markdown("### 🚨 Flagged Invoices")
    
    flagged = [inv for inv in all_invoices if inv.get('fraud_flags')]
    
    if flagged:
        for idx, inv in enumerate(flagged):
            with st.expander(f"⚠️ {inv.get('vendor_name', 'Unknown')} - #{inv.get('invoice_number', 'N/A')} - {inv.get('currency', '')} {(inv.get('total_amount') or 0):,.2f}"):
                col1, col2 = st.columns([2, 1])
                
                with col1:
                    st.markdown("**Invoice Details:**")
                    st.write(f"📅 Date: {inv.get('date', 'N/A')}")
                    st.write(f"💰 Amount: {inv.get('currency', '')} {(inv.get('total_amount') or 0):,.2f}")
                    st.write(f"🏢 Vendor: {inv.get('vendor_name', 'Unknown')}")
                    
                    st.markdown("**🚩 Detected Issues:**")
                    for flag in inv.get('fraud_flags', []):
                        severity = "🔴 High Risk" if flag in ['MATH_MISMATCH', 'FUTURE_DATE'] else "🟡 Medium Risk"
                        st.error(f"{severity}: {flag.replace('_', ' ').title()}")
                
                with col2:
                    st.markdown("**Actions:**")
                    if st.button("✅ Approve", key=f"approve_{idx}_{inv.get('invoice_number', 'na')}", use_container_width=True):
                        st.success("Marked as safe")
                    if st.button("🗑️ Delete", key=f"del_{idx}_{inv.get('invoice_number', 'na')}", use_container_width=True, type="secondary"):
                        if db.delete_invoice(inv.get('invoice_number')):
                            st.success("Deleted")
                            st.rerun()
    else:
        st.success("✅ Excellent! No fraudulent invoices detected. All invoices passed verification.")

st.markdown('</div>', unsafe_allow_html=True)

wave_divider()
