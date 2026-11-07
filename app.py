# ============================================================================
# app.py — BrandGuard Streamlit Frontend (Upgraded Light Theme + RBAC)
# ============================================================================

try:
    __import__('pysqlite3')
    import sys
    sys.modules['sqlite3'] = sys.modules.pop('pysqlite3')
except ImportError:
    pass

import streamlit as st
import os
import json
import base64
from datetime import datetime

import db
import ingest
import evaluate
import scoring

# ─── PAGE CONFIG ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="BrandGuard — AI Brand Compliance",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── LOGO HELPER ─────────────────────────────────────────────────────────────
def get_logo_base64():
    logo_path = os.path.join(os.path.dirname(__file__), "data", "logo.jpg")
    if os.path.exists(logo_path):
        with open(logo_path, "rb") as f:
            return base64.b64encode(f.read()).decode()
    return None

LOGO_B64 = get_logo_base64()

# ─── CUSTOM CSS — Premium Light Theme ────────────────────────────────────────
st.markdown("""
<style>
    /* ── Google Fonts ── */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

    /* ── Global Reset ── */
    html, body, [class*="css"] {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }

    /* ── App Background ── */
    .stApp {
        background: linear-gradient(135deg, #f0f4ff 0%, #fafbff 50%, #f5f0ff 100%);
        min-height: 100vh;
    }

    /* ── Main content area ── */
    .main .block-container {
        padding: 2rem 2.5rem 3rem 2.5rem;
        max-width: 1400px;
    }

    /* ── Sidebar ── */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0d1b4b 0%, #1a2f6e 60%, #0d2240 100%);
        border-right: none;
        box-shadow: 4px 0 20px rgba(13,27,75,0.15);
    }
    [data-testid="stSidebar"] * {
        color: #e8eeff !important;
    }
    [data-testid="stSidebar"] .stRadio > div {
        gap: 0.3rem;
    }
    [data-testid="stSidebar"] .stRadio label {
        background: rgba(255,255,255,0.07);
        border: 1px solid rgba(255,255,255,0.12);
        border-radius: 10px;
        padding: 0.6rem 1rem !important;
        margin: 2px 0;
        cursor: pointer;
        transition: all 0.2s ease;
        color: #c8d4f8 !important;
        font-size: 0.9rem;
        font-weight: 500;
    }
    [data-testid="stSidebar"] .stRadio label:hover {
        background: rgba(255,255,255,0.15) !important;
        border-color: rgba(255,255,255,0.3) !important;
        color: #fff !important;
    }
    [data-testid="stSidebar"] [data-baseweb="radio"] input:checked + div {
        background: rgba(99,179,237,0.2) !important;
        border-color: #63b3ed !important;
    }
    [data-testid="stSidebar"] .stMetric {
        background: rgba(255,255,255,0.08) !important;
        border: 1px solid rgba(255,255,255,0.12) !important;
        border-radius: 12px;
        padding: 0.8rem !important;
        margin: 4px 0 !important;
    }
    [data-testid="stSidebar"] .stMetric label,
    [data-testid="stSidebar"] .stMetric [data-testid="stMetricValue"] {
        color: #e8eeff !important;
    }

    /* ── Page Header Card ── */
    .page-header {
        background: linear-gradient(135deg, #1a2f6e 0%, #2563eb 50%, #0ea5e9 100%);
        border-radius: 20px;
        padding: 2rem 2.5rem;
        margin-bottom: 2rem;
        box-shadow: 0 8px 32px rgba(37,99,235,0.25);
        display: flex;
        align-items: center;
        gap: 1.5rem;
    }
    .page-header-text h1 {
        color: #ffffff !important;
        font-size: 1.9rem !important;
        font-weight: 800 !important;
        margin: 0 0 0.3rem 0 !important;
        letter-spacing: -0.5px;
    }
    .page-header-text p {
        color: rgba(255,255,255,0.8) !important;
        font-size: 1rem !important;
        margin: 0 !important;
    }

    /* ── Role Badge ── */
    .role-badge {
        display: inline-flex;
        align-items: center;
        gap: 0.4rem;
        padding: 0.35rem 0.9rem;
        border-radius: 20px;
        font-size: 0.78rem;
        font-weight: 600;
        letter-spacing: 0.5px;
        text-transform: uppercase;
    }
    .role-creator { background: #dbeafe; color: #1d4ed8; border: 1px solid #bfdbfe; }
    .role-reviewer { background: #d1fae5; color: #065f46; border: 1px solid #a7f3d0; }
    .role-admin { background: #fce7f3; color: #9d174d; border: 1px solid #fbcfe8; }

    /* ── Cards ── */
    .bg-card {
        background: #ffffff;
        border: 1px solid #e5eaf5;
        border-radius: 16px;
        padding: 1.5rem;
        margin-bottom: 1rem;
        box-shadow: 0 2px 12px rgba(37,99,235,0.06);
        transition: box-shadow 0.2s;
    }
    .bg-card:hover { box-shadow: 0 6px 24px rgba(37,99,235,0.1); }

    /* ── Score Gauge ── */
    .score-gauge {
        text-align: center;
        padding: 1.5rem;
        border-radius: 16px;
        background: #ffffff;
        border: 2px solid #e5eaf5;
        box-shadow: 0 4px 16px rgba(37,99,235,0.08);
    }
    .score-number {
        font-size: 3.5rem;
        font-weight: 800;
        line-height: 1;
        letter-spacing: -2px;
    }
    .score-pass    { color: #059669; }
    .score-warn    { color: #d97706; }
    .score-fail    { color: #dc2626; }

    /* ── Status Pills ── */
    .pill {
        display: inline-flex; align-items: center; gap: 0.3rem;
        padding: 0.25rem 0.75rem; border-radius: 20px;
        font-size: 0.78rem; font-weight: 600;
    }
    .pill-pass     { background:#d1fae5; color:#065f46; }
    .pill-warn     { background:#fef3c7; color:#92400e; }
    .pill-fail     { background:#fee2e2; color:#991b1b; }
    .pill-pending  { background:#e0e7ff; color:#3730a3; }
    .pill-review   { background:#fce7f3; color:#9d174d; }

    /* ── Metric Cards ── */
    .stMetric {
        background: #ffffff !important;
        border: 1px solid #e5eaf5 !important;
        border-radius: 14px !important;
        padding: 1rem 1.2rem !important;
        box-shadow: 0 2px 10px rgba(37,99,235,0.06) !important;
    }
    [data-testid="stMetricLabel"] {
        color: #64748b !important;
        font-weight: 600 !important;
        font-size: 0.8rem !important;
        letter-spacing: 0.3px;
    }
    [data-testid="stMetricValue"] {
        color: #1e293b !important;
        font-weight: 800 !important;
        font-size: 1.6rem !important;
    }

    /* ── Buttons ── */
    .stButton > button {
        border-radius: 10px !important;
        font-weight: 600 !important;
        font-size: 0.9rem !important;
        padding: 0.55rem 1.4rem !important;
        transition: all 0.2s ease !important;
        border: none !important;
    }
    .stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #2563eb, #0ea5e9) !important;
        color: #fff !important;
        box-shadow: 0 4px 14px rgba(37,99,235,0.35) !important;
    }
    .stButton > button[kind="primary"]:hover {
        background: linear-gradient(135deg, #1d4ed8, #0284c7) !important;
        box-shadow: 0 6px 20px rgba(37,99,235,0.45) !important;
        transform: translateY(-1px) !important;
    }
    .stButton > button:not([kind="primary"]) {
        background: #f1f5f9 !important;
        color: #334155 !important;
        border: 1px solid #cbd5e1 !important;
    }
    .stButton > button:not([kind="primary"]):hover {
        background: #e2e8f0 !important;
        transform: translateY(-1px) !important;
    }

    /* Fix Sidebar Button & Main Labels visibility */
    [data-testid="stSidebar"] .stButton > button * {
        color: #1e293b !important;
    }
    label, .stTabs [data-baseweb="tab"] * {
        color: #1e293b !important;
    }
    /* ── Form elements ── */
    .stTextInput > div > input,
    .stTextArea > div > textarea,
    .stSelectbox > div > div {
        border-radius: 10px !important;
        border-color: #cbd5e1 !important;
        background: #ffffff !important;
        font-size: 0.9rem !important;
        color: #1e293b !important;
    }
    .stTextInput > div > input:focus,
    .stTextArea > div > textarea:focus {
        border-color: #2563eb !important;
        box-shadow: 0 0 0 3px rgba(37,99,235,0.1) !important;
    }

    /* ── Tabs ── */
    .stTabs [data-baseweb="tab-list"] {
        background: #f1f5f9;
        border-radius: 12px;
        padding: 4px;
        gap: 4px;
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 9px;
        font-weight: 600;
        font-size: 0.88rem;
        color: #64748b !important;
        padding: 0.5rem 1.2rem;
        border: none;
        background: transparent;
    }
    .stTabs [aria-selected="true"] {
        background: #ffffff !important;
        color: #2563eb !important;
        box-shadow: 0 2px 8px rgba(37,99,235,0.12);
    }

    /* ── Expander ── */
    .stExpander {
        border: 1px solid #e5eaf5 !important;
        border-radius: 12px !important;
        background: #ffffff !important;
        margin-bottom: 0.5rem !important;
        overflow: hidden;
    }
    .stExpander > div:first-child {
        font-weight: 600 !important;
        color: #1e293b !important;
        background: #f8faff !important;
        border-bottom: 1px solid #e5eaf5;
        padding: 0.8rem 1rem !important;
    }

    /* ── Alerts ── */
    .stAlert {
        border-radius: 12px !important;
        border-left-width: 4px !important;
    }

    /* ── History Entry Card ── */
    .history-card {
        background: #ffffff;
        border: 1px solid #e5eaf5;
        border-radius: 14px;
        padding: 1.2rem 1.4rem;
        margin-bottom: 0.8rem;
        box-shadow: 0 2px 8px rgba(37,99,235,0.05);
        transition: all 0.2s;
    }
    .history-card:hover {
        border-color: #93c5fd;
        box-shadow: 0 4px 16px rgba(37,99,235,0.1);
    }

    /* ── Divider ── */
    hr { border-color: #e5eaf5 !important; margin: 1.5rem 0 !important; }

    /* ── Progress bar color ── */
    .stProgress > div > div > div { background: linear-gradient(90deg, #2563eb, #0ea5e9) !important; }

    /* ── Spinner ── */
    .stSpinner > div { border-top-color: #2563eb !important; }

    /* Hide Streamlit footer, menu & deploy button — but NOT the sidebar toggle ── */
    #MainMenu, footer { visibility: hidden; }
    /* Hide only the decorative parts of the header, not the sidebar toggle */
    [data-testid="stToolbar"] { visibility: hidden; }
    [data-testid="stStatusWidget"] { visibility: hidden; }
    [data-testid="stDeployButton"] { display: none; }
    /* Ensure sidebar collapse/expand control is always clickable */
    [data-testid="collapsedControl"] { visibility: visible !important; display: flex !important; }

    /* ── FORCE LIGHT MODE TEXT & INPUT VISIBILITY ── */
    .main label, 
    .main label p, 
    .main [data-testid="stWidgetLabel"] p,
    .main [data-testid="stMarkdownContainer"] p,
    .stTabs [data-baseweb="tab"] p {
        color: #1e293b !important;
        font-weight: 600 !important;
    }

    /* Input boxes aur Dropdown ko hamesha White rakho */
    .stTextInput input, 
    .stTextArea textarea, 
    [data-baseweb="input"], 
    [data-baseweb="base-input"],
    [data-baseweb="select"] > div {
        background-color: #ffffff !important;
        color: #1e293b !important;
        -webkit-text-fill-color: #1e293b !important;
    }

    /* Sidebar ke 'Switch Role' button ka text Dark rakho */
    [data-testid="stSidebar"] .stButton > button,
    [data-testid="stSidebar"] .stButton > button p,
    [data-testid="stSidebar"] .stButton > button span {
        color: #0d1b4b !important;
        font-weight: 700 !important;
    }
    /* ── SPLASH PAGE ── */
    .splash-bg {
        min-height: 100vh;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        background: linear-gradient(135deg, #0d1b4b 0%, #1a2f6e 40%, #0ea5e9 100%);
        padding: 2rem;
    }
    .splash-logo {
        width: 140px;
        border-radius: 20px;
        box-shadow: 0 12px 48px rgba(0,0,0,0.5);
        margin-bottom: 1.5rem;
        animation: float 3s ease-in-out infinite;
    }
    @keyframes float {
        0%,100% { transform: translateY(0px); }
        50%      { transform: translateY(-8px); }
    }
    .splash-title {
        font-size: 3rem;
        font-weight: 900;
        color: #ffffff;
        letter-spacing: -1.5px;
        margin: 0;
        text-align: center;
    }
    .splash-sub {
        font-size: 1.1rem;
        color: rgba(255,255,255,0.65);
        margin: 0.6rem 0 2.5rem;
        text-align: center;
        letter-spacing: 0.3px;
    }
    .role-grid {
        display: grid;
        grid-template-columns: repeat(2, 1fr);
        gap: 1.2rem;
        width: 100%;
        max-width: 680px;
    }
    .role-card {
        background: rgba(255,255,255,0.08);
        border: 1.5px solid rgba(255,255,255,0.15);
        border-radius: 20px;
        padding: 1.8rem 1.5rem;
        cursor: pointer;
        transition: all 0.25s ease;
        text-align: center;
        backdrop-filter: blur(12px);
        -webkit-backdrop-filter: blur(12px);
    }
    .role-card:hover {
        background: rgba(255,255,255,0.18);
        border-color: rgba(255,255,255,0.4);
        transform: translateY(-4px);
        box-shadow: 0 16px 40px rgba(0,0,0,0.3);
    }
    .role-card-icon { font-size: 2.8rem; margin-bottom: 0.6rem; display:block; }
    .role-card-title {
        font-size: 1.1rem;
        font-weight: 700;
        color: #ffffff;
        margin: 0 0 0.3rem;
    }
    .role-card-desc {
        font-size: 0.82rem;
        color: rgba(255,255,255,0.55);
        line-height: 1.4;
    }
    .splash-footer {
        margin-top: 3rem;
        font-size: 0.75rem;
        color: rgba(255,255,255,0.3);
        text-align: center;
    }
</style>
""", unsafe_allow_html=True)


# ─── RBAC ROLE DEFINITIONS ───────────────────────────────────────────────────
ROLES = {
    "creator": {
        "label": "Content Creator",
        "emoji": "🎨",
        "desc": "Submit drafts, get AI feedback\nand track your content history.",
        "pages": ["🎨 Creator — Submit Content"],
        "color": "#3b82f6",
    },
    "reviewer": {
        "label": "Reviewer",
        "emoji": "✅",
        "desc": "Review AI-approved posts and\ngive final approval or rejection.",
        "pages": ["✅ Reviewer — Approve Posts"],
        "color": "#10b981",
    },
    "admin": {
        "label": "Admin",
        "emoji": "⚙️",
        "desc": "Manage the knowledge base,\nupload guidelines and rules.",
        "pages": ["⚙️ Admin — Knowledge Base"],
        "color": "#ec4899",
    },
    "superadmin": {
        "label": "Super Admin",
        "emoji": "👑",
        "desc": "Full access to all modules\nand the analytics dashboard.",
        "pages": [
            "🎨 Creator — Submit Content",
            "✅ Reviewer — Approve Posts",
            "⚙️ Admin — Knowledge Base",
            "📊 Dashboard",
        ],
        "color": "#f59e0b",
    },
}

# ─── SESSION STATE INIT ───────────────────────────────────────────────────────
if "current_role" not in st.session_state:
    st.session_state.current_role = None   # None → show splash

# ─── SPLASH PAGE ─────────────────────────────────────────────────────────────
def splash_page():
    """Full-screen role-selection landing page shown on first load."""

    # On splash, visually hide sidebar content but DON'T use display:none
    # (display:none creates a persistent conflict; visibility:hidden is safer)
    st.markdown(
        "<style>"
        "[data-testid='stSidebar']{visibility:hidden!important;width:0!important;min-width:0!important;}"
        ".main .block-container{padding:0!important;max-width:100%!important;}"
        "</style>",
        unsafe_allow_html=True,
    )

    logo_html = ""
    if LOGO_B64:
        logo_html = (
            f'<img src="data:image/jpeg;base64,{LOGO_B64}" '
            f'class="splash-logo" alt="BrandGuard Logo" />'
        )
    else:
        logo_html = '<div style="font-size:5rem;margin-bottom:1.5rem;">🛡️</div>'

    st.markdown(
        f'<div class="splash-bg">'
        f'{logo_html}'
        f'<h1 class="splash-title">BrandGuard</h1>'
        f'<p class="splash-sub">AI-Powered Brand Compliance · Select your role to continue</p>'
        f'</div>',
        unsafe_allow_html=True,
    )

    # Role cards — 2×2 grid using Streamlit columns
    # We render them as buttons styled to look like cards
    st.markdown(
        '<div style="display:flex;justify-content:center;margin-top:-18rem;">',
        unsafe_allow_html=True,
    )

    # Render cards in two rows of two
    role_keys = list(ROLES.keys())
    for row in range(2):
        cols = st.columns(2, gap="medium")
        for col_idx in range(2):
            rk = role_keys[row * 2 + col_idx]
            info = ROLES[rk]
            with cols[col_idx]:
                # Card-style button using HTML + a real Streamlit button underneath
                st.markdown(
                    f'<div class="role-card" style="border-color:{info["color"]}33;">'
                    f'<span class="role-card-icon">{info["emoji"]}</span>'
                    f'<div class="role-card-title" style="color:{info["color"]};">'
                    f'{info["label"]}</div>'
                    f'<div class="role-card-desc">'
                    f'{info["desc"].replace(chr(10), "<br/>")}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
                if st.button(
                    f"Enter as {info['label']}",
                    key=f"splash_role_{rk}",
                    use_container_width=True,
                    type="primary",
                ):
                    st.session_state.current_role = rk
                    st.rerun()

    st.markdown(
        '<p class="splash-footer">BrandGuard © 2026 · AI Brand Compliance Platform</p>',
        unsafe_allow_html=True,
    )

# ── Show splash if no role chosen yet ────────────────────────────────────────
if st.session_state.current_role is None:
    splash_page()
    st.stop()   # Nothing below runs until a role is picked

# ── FORCE SIDEBAR OPEN ────────────────────────────────────────────────────
# Override ALL mechanisms Streamlit uses to hide the sidebar:
#   • display / visibility  (CSS hiding)
#   • transform: translateX (JS-driven slide-out animation)
#   • width / min-width / margin-left (collapsed-state sizing)
st.markdown("""
<style>
    /* Force the sidebar to always be visible and open */
    [data-testid="stSidebar"] {
        display: flex !important;
        visibility: visible !important;
        transform: translateX(0px) !important;
        width: 21rem !important;
        min-width: 21rem !important;
        margin-left: 0 !important;
        position: relative !important;
        flex-shrink: 0 !important;
    }
    /* Hide the collapse arrow button so users can't close it */
    [data-testid="stSidebarCollapseButton"],
    [data-testid="collapsedControl"],
    button[aria-label="Close sidebar"],
    button[kind="header"] { display: none !important; }
</style>
""", unsafe_allow_html=True)

# ─── SIDEBAR ─────────────────────────────────────────────────────────────────
with st.sidebar:
    # Logo + Brand
    if LOGO_B64:
        st.markdown(
            f'<div style="text-align:center; padding: 1rem 0 0.5rem;">'
            f'<img src="data:image/jpeg;base64,{LOGO_B64}" '
            f'style="width:160px; border-radius:12px; '
            f'box-shadow: 0 4px 16px rgba(0,0,0,0.3);" />'
            f'</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<div style="text-align:center;padding:1rem 0 0.5rem;">'
            '<span style="font-size:3rem;">🛡️</span></div>',
            unsafe_allow_html=True,
        )

    st.markdown(
        '<div style="text-align:center; margin-bottom:0.5rem;">'
        '<span style="color:#ffffff; font-size:1.3rem; font-weight:800; '
        'letter-spacing:-0.5px;">BrandGuard</span><br/>'
        '<span style="color:rgba(255,255,255,0.6); font-size:0.78rem;">'
        'AI Brand Compliance</span></div>',
        unsafe_allow_html=True,
    )

    st.markdown('<hr style="border-color:rgba(255,255,255,0.15);margin:0.8rem 0;"/>', unsafe_allow_html=True)

    # ── Active role badge ──
    role_info = ROLES[st.session_state.current_role]
    st.markdown(
        f'<div style="background:rgba(255,255,255,0.1);border-radius:12px;'
        f'padding:0.7rem 1rem;border:1px solid rgba(255,255,255,0.18);margin-bottom:0.6rem;">'
        f'<span style="color:rgba(255,255,255,0.5);font-size:0.68rem;text-transform:uppercase;'
        f'letter-spacing:1px;font-weight:600;">Active Role</span><br/>'
        f'<span style="color:#fff;font-size:1rem;font-weight:700;">'
        f'{role_info["emoji"]} {role_info["label"]}</span>'
        f'</div>',
        unsafe_allow_html=True,
    )

    # Switch Role button → back to splash
    if st.button("🔄 Switch Role", use_container_width=True):
        st.session_state.current_role = None
        st.rerun()

    st.markdown('<hr style="border-color:rgba(255,255,255,0.15);margin:0.8rem 0;"/>', unsafe_allow_html=True)

    # ── Page Navigation (based on role) ──
    allowed_pages = role_info["pages"]
    if len(allowed_pages) > 1:
        st.markdown(
            '<p style="color:rgba(255,255,255,0.5);font-size:0.72rem;'
            'letter-spacing:1px;text-transform:uppercase;font-weight:600;'
            'margin-bottom:0.5rem;">Navigate</p>',
            unsafe_allow_html=True,
        )
        page = st.radio("Page", allowed_pages, label_visibility="collapsed")
    else:
        page = allowed_pages[0]

    st.markdown('<hr style="border-color:rgba(255,255,255,0.15);margin:0.8rem 0;"/>', unsafe_allow_html=True)

    # ── Live Stats ──
    st.markdown(
        '<p style="color:rgba(255,255,255,0.5);font-size:0.72rem;'
        'letter-spacing:1px;text-transform:uppercase;font-weight:600;'
        'margin-bottom:0.5rem;">Live Stats</p>',
        unsafe_allow_html=True,
    )
    try:
        kb_stats = ingest.get_collection_stats()
        st.metric("📚 KB Chunks", kb_stats["total_chunks"])
    except Exception:
        st.metric("📚 KB Chunks", 0)

    stats = db.get_dashboard_stats()
    st.metric("📝 Submissions", stats["total_submissions"])
    st.metric("📊 Avg Score", f"{stats['average_score']}")

    # ── Score Threshold Info ──
    st.markdown('<hr style="border-color:rgba(255,255,255,0.15);margin:0.8rem 0;"/>', unsafe_allow_html=True)
    st.markdown(
        f'<div style="background:rgba(255,255,255,0.08);border-radius:10px;'
        f'padding:0.8rem;border:1px solid rgba(255,255,255,0.12);">'
        f'<p style="color:rgba(255,255,255,0.5);font-size:0.68rem;'
        f'text-transform:uppercase;letter-spacing:1px;margin:0 0 0.5rem;">Thresholds</p>'
        f'<p style="color:#6ee7b7;font-size:0.82rem;margin:0.2rem 0;">'
        f'✅ Pass: ≥ {scoring.PASS_THRESHOLD}</p>'
        f'<p style="color:#fcd34d;font-size:0.82rem;margin:0.2rem 0;">'
        f'⚠️ Improve: ≥ {scoring.WARNING_THRESHOLD}</p>'
        f'<p style="color:#fca5a5;font-size:0.82rem;margin:0.2rem 0;">'
        f'❌ Fail: &lt; {scoring.WARNING_THRESHOLD}</p>'
        f'</div>',
        unsafe_allow_html=True,
    )


# ─── PAGE HEADER HELPER ───────────────────────────────────────────────────────
def render_header(title, subtitle, emoji):
    logo_html = ""
    if LOGO_B64:
        logo_html = (
            f'<img src="data:image/jpeg;base64,{LOGO_B64}" '
            f'style="height:60px;border-radius:10px;'
            f'box-shadow:0 4px 12px rgba(0,0,0,0.25);" />'
        )
    else:
        logo_html = f'<span style="font-size:3rem;">{emoji}</span>'

    st.markdown(
        f'<div class="page-header">'
        f'{logo_html}'
        f'<div class="page-header-text">'
        f'<h1>{title}</h1>'
        f'<p>{subtitle}</p>'
        f'</div>'
        f'</div>',
        unsafe_allow_html=True,
    )


def score_class(score):
    if score >= scoring.PASS_THRESHOLD:
        return "score-pass"
    elif score >= scoring.WARNING_THRESHOLD:
        return "score-warn"
    return "score-fail"


def pill_for_status(status):
    MAP = {
        "pending":        ("pill-pending",  "⏳ Pending"),
        "evaluated":      ("pill-warn",     "📊 Evaluated"),
        "sent_for_review":("pill-review",   "📤 In Review"),
        "approved":       ("pill-pass",     "✅ Approved"),
        "rejected":       ("pill-fail",     "❌ Rejected"),
    }
    cls, label = MAP.get(status, ("pill-pending", f"❓ {status}"))
    return f'<span class="pill {cls}">{label}</span>'


# ============================================================================
# 🎨 CREATOR PAGE
# ============================================================================

def creator_page():
    render_header(
        "Content Creator",
        "Submit your social media content for AI-powered brand compliance review.",
        "🎨",
    )

    # ── Tabs: Submit | History ──
    tab_submit, tab_history = st.tabs(["📝 Submit Content", "📜 Feedback History"])

    # ── TAB 1: SUBMIT ──────────────────────────────────────────────────────
    with tab_submit:
        with st.form("submission_form", clear_on_submit=False):
            col1, col2 = st.columns([2, 1])

            with col1:
                creator_name = st.text_input(
                    "Your Name",
                    value="Creator",
                    placeholder="Enter your name",
                )
                post_text = st.text_area(
                    "Post Text Content",
                    height=200,
                    placeholder=(
                        "Paste your social media post text here...\n\n"
                        "Example: '🚀 Excited to announce our NEW SuperWidget Pro! "
                        "It's 10x faster and guaranteed to boost productivity by 500%! "
                        "#Innovation #BestInClass'"
                    ),
                )

            with col2:
                campaign_objective = st.selectbox(
                    "Campaign Objective",
                    options=[
                        "brand_awareness", "lead_generation", "engagement",
                        "product_launch", "promotional_offer", "educational", "event_promotion",
                    ],
                    format_func=lambda x: x.replace("_", " ").title(),
                )
                uploaded_image = st.file_uploader(
                    "Post Image (Optional)",
                    type=["png", "jpg", "jpeg", "gif", "webp"],
                )
                if uploaded_image:
                    st.image(uploaded_image, caption="Preview", use_container_width=True)

            submitted = st.form_submit_button(
                "🔍 Evaluate My Content",
                use_container_width=True,
                type="primary",
            )

        if submitted:
            if not post_text.strip() and not uploaded_image:
                st.error("❌ Please provide at least text content or an image!")
                return

            image_path = None
            if uploaded_image:
                temp_dir = os.path.join(os.path.dirname(__file__), "temp_uploads")
                os.makedirs(temp_dir, exist_ok=True)
                image_path = os.path.join(temp_dir, uploaded_image.name)
                with open(image_path, "wb") as f:
                    f.write(uploaded_image.getbuffer())

            submission_id = db.create_submission(
                creator_name=creator_name,
                text_content=post_text,
                image_path=image_path,
                campaign_objective=campaign_objective,
            )

            with st.spinner("🤖 AI is evaluating your content… This may take 15–30 seconds."):
                result = evaluate.evaluate_post(
                    text_content=post_text,
                    campaign_objective=campaign_objective,
                    image_path=image_path,
                    submission_id=submission_id,
                )

            if result.get("status") == "error":
                st.error(f"❌ Evaluation failed: {result.get('message', 'Unknown error')}")
                return

            # ── Results ────────────────────────────────────────────────────
            st.markdown("---")

            decision = result["decision"]
            overall = result["overall_score"]
            sc = score_class(overall)

            # Decision banner
            if decision == "pass":
                st.success(f"✅ {result['decision_reason']}")
            elif decision == "needs_improvement":
                st.warning(f"⚠️ {result['decision_reason']}")
            else:
                st.error(f"❌ {result['decision_reason']}")

            # Score gauge + key metrics
            g1, g2, g3 = st.columns(3)
            with g1:
                st.markdown(
                    f'<div class="score-gauge">'
                    f'<div style="color:#64748b;font-size:0.82rem;font-weight:600;'
                    f'letter-spacing:0.5px;text-transform:uppercase;margin-bottom:0.5rem;">'
                    f'Overall Score</div>'
                    f'<div class="score-number {sc}">{overall}</div>'
                    f'<div style="color:#94a3b8;font-size:0.85rem;">/100</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
            with g2:
                st.metric("🚨 Critical Issues", len(result["critical_flags"]))
            with g3:
                st.metric(
                    "📤 Ready for Review",
                    "Yes ✅" if result["can_send_for_review"] else "No ❌",
                )

            # Category scores
            st.markdown("---")
            st.markdown("### 📈 Category Scores")
            cat_labels = {
                "factual_accuracy":      "📋 Factual Accuracy",
                "regulatory_compliance": "⚖️ Regulatory",
                "brand_identity":        "🏷️ Brand Identity",
                "visual_consistency":    "🎨 Visual",
                "campaign_effectiveness":"🎯 Campaign",
                "accessibility":         "♿ Accessibility",
                "overall_design":        "✨ Design",
            }
            scores = result.get("category_scores", {})
            keys = list(cat_labels.keys())
            cols1 = st.columns(4)
            for i, k in enumerate(keys[:4]):
                with cols1[i]:
                    s = scores.get(k, 0)
                    icon = scoring.get_score_color(s)
                    st.metric(cat_labels[k], f"{icon} {s}/100")
            cols2 = st.columns(4)
            for i, k in enumerate(keys[4:]):
                with cols2[i]:
                    s = scores.get(k, 0)
                    icon = scoring.get_score_color(s)
                    st.metric(cat_labels[k], f"{icon} {s}/100")

            # Detailed feedback (saved to history)
            st.markdown("---")
            st.markdown("### 💬 Detailed Feedback")
            cat_feedback = result.get("category_feedback", {})
            for cat, label in cat_labels.items():
                fb = cat_feedback.get(cat, "No feedback available.")
                with st.expander(label):
                    st.write(fb)

            # Critical issues
            if result["critical_flags"]:
                st.markdown("---")
                st.markdown("### 🚨 Critical Issues")
                for flag in result["critical_flags"]:
                    st.error(f"🔴 {flag}")

            # Suggestions
            suggestions = result.get("suggestions", [])
            if suggestions:
                st.markdown("---")
                st.markdown("### 💡 Actionable Suggestions")
                for i, sug in enumerate(suggestions, 1):
                    if isinstance(sug, dict):
                        with st.expander(f"Suggestion {i}: {sug.get('issue', 'Issue')}"):
                            st.markdown(f"**🔍 Issue:** {sug.get('issue', 'N/A')}")
                            st.markdown(f"**⚠️ Risk:** {sug.get('risk', 'N/A')}")
                            st.markdown(f"**📋 Guideline:** {sug.get('guideline_reference', 'N/A')}")
                            st.markdown(f"**✅ Fix:** {sug.get('fix', 'N/A')}")
                    else:
                        st.info(f"💡 {sug}")

            # Summary
            summary = result.get("overall_summary", "")
            if summary:
                st.markdown("---")
                st.info(f"📝 **Summary:** {summary}")

            # Send for review
            if result["can_send_for_review"]:
                st.markdown("---")
                if st.button("📤 Send for Human Review", type="primary", use_container_width=True):
                    db.update_submission_status(submission_id, "sent_for_review")
                    st.success("✅ Post sent for human review! A reviewer will check it soon.")
                    st.balloons()

    # ── TAB 2: FEEDBACK HISTORY ────────────────────────────────────────────
    with tab_history:
        st.markdown("### 📜 Your Complete Feedback History")
        st.markdown(
            "All your past submissions with AI scores, feedback, suggestions, "
            "and reviewer decisions — saved and accessible anytime."
        )

        all_subs = db.get_all_submissions()
        if not all_subs:
            st.info("No submissions yet. Submit your first content! ☝️")
        else:
            for sub in all_subs[:20]:
                _render_history_card(sub, role="creator")


# ============================================================================
# ✅ REVIEWER PAGE
# ============================================================================

def reviewer_page():
    render_header(
        "Content Reviewer",
        "Review and approve content that has passed AI evaluation.",
        "✅",
    )

    reviewer_name = st.text_input("Your Name (Reviewer)", value="Manager", key="reviewer_name_input")
    st.markdown("---")

    reviewable = db.get_reviewable_submissions()

    if not reviewable:
        st.info(
            f"📭 No content is waiting for review right now.\n\n"
            f"Posts appear here when creators submit content that passes AI evaluation "
            f"(score ≥ {scoring.PASS_THRESHOLD}, no critical issues)."
        )
        return

    st.markdown(f"### 📋 {len(reviewable)} Post(s) Awaiting Review")

    for sub in reviewable:
        with st.expander(
            f"📄 #{sub['id']} — Score: {sub['overall_score']}/100 — {sub['created_at'][:16]}",
            expanded=True,
        ):
            col1, col2 = st.columns([2, 1])
            with col1:
                st.markdown(f"**Creator:** {sub.get('creator_name', 'Unknown')}")
                st.markdown(f"**Objective:** {sub.get('campaign_objective', 'N/A')}")
                if sub.get("text_content"):
                    st.markdown("**Post Text:**")
                    st.text(sub["text_content"])
                if sub.get("image_path") and os.path.exists(sub["image_path"]):
                    st.image(sub["image_path"], caption="Post Image", width=300)

            with col2:
                sc = score_class(sub["overall_score"])
                st.markdown(
                    f'<div class="score-gauge">'
                    f'<div style="color:#64748b;font-size:0.78rem;font-weight:600;'
                    f'margin-bottom:0.4rem;">AI Score</div>'
                    f'<div class="score-number {sc}">{sub["overall_score"]}</div>'
                    f'<div style="color:#94a3b8;font-size:0.82rem;">/100</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
                st.metric(
                    "Critical Issues",
                    "None ✅" if not sub.get("has_critical_issues") else "Yes ❌",
                )

            # Category breakdown
            latest_eval = db.get_latest_evaluation(sub["id"])
            if latest_eval:
                st.markdown("**Category Scores:**")
                cats = ["factual_accuracy","regulatory_compliance","brand_identity",
                        "visual_consistency","campaign_effectiveness","accessibility","overall_design"]
                cols = st.columns(4)
                for i, cat in enumerate(cats):
                    s = latest_eval.get(cat, 0)
                    with cols[i % 4]:
                        st.metric(cat.replace("_"," ").title(), f"{scoring.get_score_color(s)} {s}")

                # Show full feedback in expander
                if latest_eval.get("feedback"):
                    fb_data = latest_eval["feedback"]
                    cat_fb = fb_data.get("category_feedback", {}) if isinstance(fb_data, dict) else {}
                    if cat_fb:
                        with st.expander("💬 View Full AI Feedback"):
                            for cat, text in cat_fb.items():
                                st.markdown(f"**{cat.replace('_',' ').title()}:** {text}")

            st.markdown("---")
            rc1, rc2, rc3 = st.columns(3)
            with rc1:
                if st.button("✅ Approve", key=f"approve_{sub['id']}", type="primary"):
                    eval_id = sub.get("eval_id", latest_eval["id"] if latest_eval else 0)
                    db.save_review(sub["id"], eval_id, reviewer_name, "approved", "Approved by reviewer.")
                    st.success("✅ Post approved!")
                    st.rerun()
            with rc2:
                if st.button("❌ Reject", key=f"reject_{sub['id']}"):
                    reject_reason = st.text_input("Reason for rejection", key=f"rr_{sub['id']}")
                    eval_id = sub.get("eval_id", latest_eval["id"] if latest_eval else 0)
                    db.save_review(sub["id"], eval_id, reviewer_name, "rejected",
                                   reject_reason or "Rejected by reviewer.")
                    st.error("❌ Post rejected.")
                    st.rerun()
            with rc3:
                if st.button("🔄 Request Revision", key=f"revise_{sub['id']}"):
                    eval_id = sub.get("eval_id", latest_eval["id"] if latest_eval else 0)
                    db.save_review(sub["id"], eval_id, reviewer_name,
                                   "revision_needed", "Please revise and resubmit.")
                    st.warning("🔄 Revision requested.")
                    st.rerun()


# ============================================================================
# ⚙️ ADMIN PAGE
# ============================================================================

def admin_page():
    render_header(
        "Knowledge Base Admin",
        "Upload and manage brand guidelines, product facts, and compliance rules.",
        "⚙️",
    )

    tab1, tab2, tab3 = st.tabs([
        "📤 Upload Documents",
        "✍️ Add Text Guidelines",
        "📚 View Knowledge Base",
    ])

    with tab1:
        st.markdown("### Upload Brand Documents")
        doc_type = st.selectbox(
            "Document Type",
            ["guideline", "factsheet", "legal", "template"],
            format_func=lambda x: {
                "guideline": "📋 Brand Guidelines",
                "factsheet":  "📊 Product Fact Sheet",
                "legal":      "⚖️ Legal / Regulatory Rules",
                "template":   "📄 Content Template",
            }.get(x, x),
            key="upload_doc_type",
        )
        uploaded_files = st.file_uploader(
            "Upload files (.txt or .pdf)",
            type=["txt", "pdf"],
            accept_multiple_files=True,
            key="kb_upload",
        )
        if uploaded_files and st.button("📥 Ingest Documents", type="primary"):
            for uf in uploaded_files:
                temp_dir = os.path.join(os.path.dirname(__file__), "temp_uploads")
                os.makedirs(temp_dir, exist_ok=True)
                temp_path = os.path.join(temp_dir, uf.name)
                with open(temp_path, "wb") as f:
                    f.write(uf.getbuffer())

                fname_lower = uf.name.lower()
                if "guideline" in fname_lower:
                    detected_type = "guideline"
                elif "fact" in fname_lower or "product" in fname_lower:
                    detected_type = "factsheet"
                elif "legal" in fname_lower or "regulatory" in fname_lower:
                    detected_type = "legal"
                elif "template" in fname_lower:
                    detected_type = "template"
                else:
                    detected_type = doc_type

                with st.spinner(f"Processing {uf.name}…"):
                    res = ingest.ingest_document(temp_path, detected_type)
                if res["status"] == "success":
                    st.success(f"✅ {uf.name} ({detected_type}): {res['chunk_count']} chunks ingested ({res['char_count']} chars)")
                else:
                    st.error(f"❌ {uf.name}: {res.get('message', 'Error')}")

    with tab2:
        st.markdown("### Add Guidelines as Text")
        with st.form("text_ingest_form"):
            title = st.text_input("Document Title", placeholder="e.g., Brand Voice Guidelines 2026")
            text_doc_type = st.selectbox(
                "Document Type",
                ["guideline", "factsheet", "legal", "template"],
                format_func=lambda x: x.replace("_", " ").title(),
                key="text_doc_type",
            )
            guidelines_text = st.text_area(
                "Guidelines Text", height=300,
                placeholder="Paste your brand guidelines here…",
            )
            if st.form_submit_button("📥 Ingest Text", type="primary"):
                if title.strip() and guidelines_text.strip():
                    with st.spinner("Processing text…"):
                        res = ingest.ingest_text_directly(guidelines_text, title, text_doc_type)
                    if res["status"] == "success":
                        st.success(f"✅ '{title}': {res['chunk_count']} chunks ingested!")
                    else:
                        st.error(f"❌ {res.get('message', 'Error')}")
                else:
                    st.error("Please provide both a title and guidelines text.")

    with tab3:
        st.markdown("### Knowledge Base Contents")
        col1, col2 = st.columns(2)
        kb_stats = ingest.get_collection_stats()
        docs = db.get_all_documents()
        with col1:
            st.metric("Total Chunks in Vector DB", kb_stats["total_chunks"])
        with col2:
            st.metric("Total Documents", len(docs))

        if docs:
            st.markdown("---")
            st.markdown("#### 📄 Uploaded Documents")
            for doc in docs:
                c1, c2 = st.columns([4, 1])
                with c1:
                    st.markdown(
                        f"**{doc['filename']}** ({doc['doc_type']}) — "
                        f"{doc['chunk_count']} chunks — v{doc['version']} — "
                        f"{doc['uploaded_at'][:16]}"
                    )
                    if doc.get("content_preview"):
                        st.caption(doc["content_preview"][:200] + "…")
                with c2:
                    if st.button("🗑️", key=f"del_doc_{doc['id']}"):
                        db.delete_document(doc["id"])
                        st.warning(f"Document '{doc['filename']}' deactivated.")
                        st.rerun()
        else:
            st.info("📭 No documents uploaded yet. Use the tabs above to add guidelines!")

        st.markdown("---")
        st.markdown("#### 🔍 Search Knowledge Base")
        search_query = st.text_input("Search query", placeholder="e.g., What is our brand color?")
        if search_query:
            with st.spinner("Searching…"):
                from retrive import search_knowledge_base
                results = search_knowledge_base(search_query, n_results=5)
            if results:
                for i, r in enumerate(results, 1):
                    with st.expander(f"Result {i} — {r['source']} (relevance: {r['relevance_score']:.4f})"):
                        st.write(r["text"])
            else:
                st.info("No matching results found.")


# ============================================================================
# 📊 DASHBOARD
# ============================================================================

def dashboard_page():
    render_header(
        "BrandGuard Dashboard",
        "Overview of content evaluation activity and brand compliance metrics.",
        "📊",
    )

    stats = db.get_dashboard_stats()

    # Top metrics
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1: st.metric("📝 Total", stats["total_submissions"])
    with c2: st.metric("✅ Approved", stats.get("approved_count", 0))
    with c3: st.metric("❌ Rejected", stats.get("rejected_count", 0))
    with c4: st.metric("⏳ Pending", stats.get("pending_count", 0))
    with c5: st.metric("📊 Avg Score", stats.get("average_score", 0))

    # Compliance bar
    total = stats["total_submissions"]
    if total > 0:
        st.markdown("---")
        approved = stats.get("approved_count", 0)
        rate = int((approved / total) * 100)
        st.markdown(f"### 🏆 Approval Rate — **{rate}%**")
        st.progress(rate / 100)

    # KB stats
    st.markdown("---")
    st.markdown("### 📚 Knowledge Base")
    kc1, kc2 = st.columns(2)
    with kc1: st.metric("Documents", stats.get("total_documents", 0))
    with kc2:
        kb_stats = ingest.get_collection_stats()
        st.metric("Guideline Chunks", kb_stats["total_chunks"])

    # Recent activity
    st.markdown("---")
    st.markdown("### 📜 Recent Submissions")
    all_subs = db.get_all_submissions()
    if all_subs:
        for sub in all_subs[:20]:
            _render_history_card(sub, role="admin")
    else:
        st.info("No submissions yet.")


# ============================================================================
# 🗂️ SHARED: History Card Renderer (saves & shows full feedback history)
# ============================================================================

def _render_history_card(sub, role="creator"):
    """
    Renders a rich history card for a submission.
    Shows complete feedback, scores, suggestions, and reviewer decisions.
    All data is saved in the DB — this just reads and displays it.
    """
    status = sub.get("status", "pending")
    status_pill = pill_for_status(status)
    latest_eval = db.get_latest_evaluation(sub["id"])
    score_txt = f"{latest_eval['overall_score']}/100" if latest_eval else "N/A"

    with st.expander(
        f"#{sub['id']} — {sub.get('creator_name','?')} — "
        f"{sub.get('campaign_objective','').replace('_',' ').title()} — "
        f"Score: {score_txt} — {sub['created_at'][:16]}",
        expanded=False,
    ):
        # Header row
        h1, h2, h3 = st.columns([2, 1, 1])
        with h1:
            st.markdown(status_pill, unsafe_allow_html=True)
        with h2:
            if latest_eval:
                sc = latest_eval["overall_score"]
                cls = score_class(sc)
                st.markdown(
                    f'<div style="text-align:center;">'
                    f'<span class="score-number {cls}" style="font-size:2rem;">{sc}</span>'
                    f'<span style="color:#94a3b8;">/100</span></div>',
                    unsafe_allow_html=True,
                )
        with h3:
            if latest_eval:
                issues = latest_eval.get("critical_flags", [])
                st.metric("Critical Issues", len(issues) if issues else "None ✅")

        st.markdown("---")

        # Text content preview
        if sub.get("text_content"):
            st.markdown("**📝 Post Text:**")
            st.text(sub["text_content"][:300] + ("…" if len(sub["text_content"]) > 300 else ""))

        if not latest_eval:
            st.info("No evaluation data yet.")
            return

        # Category scores grid
        st.markdown("**📈 Category Scores:**")
        cats = {
            "factual_accuracy":      "📋 Factual",
            "regulatory_compliance": "⚖️ Regulatory",
            "brand_identity":        "🏷️ Brand",
            "visual_consistency":    "🎨 Visual",
            "campaign_effectiveness":"🎯 Campaign",
            "accessibility":         "♿ Access",
            "overall_design":        "✨ Design",
        }
        col_groups = st.columns(4)
        for idx, (cat, label) in enumerate(cats.items()):
            s = latest_eval.get(cat, 0)
            with col_groups[idx % 4]:
                st.metric(label, f"{scoring.get_score_color(s)} {s}")

        # Critical flags
        flags = latest_eval.get("critical_flags", [])
        if flags:
            st.markdown("**🚨 Critical Issues:**")
            for flag in flags:
                st.error(f"🔴 {flag}")

        # Full feedback per category
        fb_data = latest_eval.get("feedback", {})
        cat_fb = {}
        if isinstance(fb_data, dict):
            cat_fb = fb_data.get("category_feedback", {})
        elif isinstance(fb_data, str):
            try:
                parsed = json.loads(fb_data)
                cat_fb = parsed.get("category_feedback", {})
            except Exception:
                cat_fb = {}

        if cat_fb:
            with st.expander("💬 Detailed Category Feedback (Full)"):
                for cat, text in cat_fb.items():
                    st.markdown(
                        f'<div class="bg-card" style="margin-bottom:0.5rem;">'
                        f'<strong>{cat.replace("_"," ").title()}</strong><br/>'
                        f'<span style="color:#475569;">{text}</span></div>',
                        unsafe_allow_html=True,
                    )

        # Suggestions
        suggestions = latest_eval.get("suggestions", [])
        if suggestions:
            with st.expander("💡 Actionable Suggestions"):
                for i, sug in enumerate(suggestions, 1):
                    if isinstance(sug, dict):
                        st.markdown(
                            f'<div class="bg-card" style="margin-bottom:0.5rem;">'
                            f'<strong>#{i} — {sug.get("issue","Issue")}</strong><br/>'
                            f'⚠️ <em>{sug.get("risk","")}</em><br/>'
                            f'📋 {sug.get("guideline_reference","")}<br/>'
                            f'✅ <strong>Fix:</strong> {sug.get("fix","")}'
                            f'</div>',
                            unsafe_allow_html=True,
                        )
                    else:
                        st.info(f"💡 {sug}")

        # Overall summary
        summary_data = latest_eval.get("feedback", {})
        if isinstance(summary_data, dict):
            summary = summary_data.get("overall_summary", "")
        else:
            summary = ""
        if summary:
            st.info(f"📝 **Summary:** {summary}")

        # Reviewer decisions history
        reviews = db.get_reviews_for_submission(sub["id"])
        if reviews:
            with st.expander("👤 Reviewer Decision History"):
                for rev in reviews:
                    decision_map = {
                        "approved": "✅ Approved",
                        "rejected": "❌ Rejected",
                        "revision_needed": "🔄 Revision Needed",
                    }
                    dec_label = decision_map.get(rev["decision"], rev["decision"])
                    st.markdown(
                        f'<div class="history-card">'
                        f'<strong>{dec_label}</strong> — by {rev.get("reviewer_name","?")} '
                        f'— {rev["reviewed_at"][:16]}<br/>'
                        f'<em style="color:#64748b;">{rev.get("comments","")}</em>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )


# ============================================================================
# 🚀 ROUTER
# ============================================================================

if "Creator" in page:
    creator_page()
elif "Reviewer" in page:
    reviewer_page()
elif "Admin" in page:
    admin_page()
elif "Dashboard" in page:
    dashboard_page()
