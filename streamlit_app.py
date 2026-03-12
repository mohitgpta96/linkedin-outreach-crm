"""
Outreach CRM — Premium Dark Sidebar Design
Inspired by Apollo.io / Attio / Linear design language.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import streamlit as st
import pandas as pd

st.set_page_config(
    page_title="Outreach CRM",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Premium CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

/* Global font */
html, body, [class*="css"], .stApp * {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif !important;
}

/* Hide Streamlit chrome */
[data-testid="stSidebarNav"]          { display: none !important; }
header[data-testid="stHeader"]        { display: none !important; }
[data-testid="stDecoration"]          { display: none !important; }
footer                                { display: none !important; }
[data-testid="collapsedControl"]      { color: #94A3B8 !important; }
.viewerBadge_container__r5tak        { display: none !important; }

/* App background */
.stApp { background: #F8FAFC !important; }

/* ── SIDEBAR — Dark premium ── */
section[data-testid="stSidebar"] {
    background: #0F172A !important;
    min-width: 248px !important;
    max-width: 248px !important;
    border-right: none !important;
}
section[data-testid="stSidebar"] > div:first-child {
    background: #0F172A !important;
    padding: 0 !important;
}
section[data-testid="stSidebar"] .block-container {
    padding: 0 !important;
}

/* Sidebar nav buttons — all inactive items */
section[data-testid="stSidebar"] .stButton > button {
    background: transparent !important;
    color: #94A3B8 !important;
    border: none !important;
    border-radius: 8px !important;
    text-align: left !important;
    width: 100% !important;
    padding: 9px 14px !important;
    font-size: 13.5px !important;
    font-weight: 500 !important;
    transition: all 150ms ease !important;
    box-shadow: none !important;
    margin: 1px 0 !important;
    justify-content: flex-start !important;
}
section[data-testid="stSidebar"] .stButton > button:hover {
    background: rgba(255,255,255,0.07) !important;
    color: #E2E8F0 !important;
    box-shadow: none !important;
}
section[data-testid="stSidebar"] .stButton > button:focus {
    box-shadow: none !important;
    outline: none !important;
}

/* Sidebar divider */
section[data-testid="stSidebar"] hr {
    border-color: rgba(255,255,255,0.08) !important;
    margin: 8px 16px !important;
}

/* ── MAIN CONTENT AREA ── */
.main .block-container {
    padding: 28px 32px 32px 32px !important;
    max-width: 1440px !important;
}

/* ── METRIC CARDS — Premium ── */
div[data-testid="stMetric"] {
    background: #FFFFFF !important;
    border-radius: 12px !important;
    border: 1px solid #E2E8F0 !important;
    box-shadow: 0 1px 3px rgba(0,0,0,0.07), 0 1px 2px rgba(0,0,0,0.04) !important;
    padding: 20px 24px !important;
    transition: box-shadow 150ms ease, transform 150ms ease !important;
}
div[data-testid="stMetric"]:hover {
    box-shadow: 0 4px 12px rgba(0,0,0,0.09), 0 2px 4px rgba(0,0,0,0.05) !important;
    transform: translateY(-1px) !important;
}
div[data-testid="stMetric"] label {
    font-size: 12px !important;
    font-weight: 600 !important;
    color: #64748B !important;
    letter-spacing: 0.04em !important;
    text-transform: uppercase !important;
}
div[data-testid="stMetricValue"] {
    font-size: 28px !important;
    font-weight: 700 !important;
    color: #0F172A !important;
}

/* ── BUTTONS — Premium ── */
.main .stButton > button {
    font-size: 13px !important;
    font-weight: 500 !important;
    border-radius: 7px !important;
    border: 1px solid #E2E8F0 !important;
    color: #374151 !important;
    background: #FFFFFF !important;
    padding: 7px 15px !important;
    transition: all 150ms ease !important;
    box-shadow: 0 1px 2px rgba(0,0,0,0.05) !important;
}
.main .stButton > button:hover {
    background: #F8FAFC !important;
    border-color: #CBD5E1 !important;
    box-shadow: 0 3px 8px rgba(0,0,0,0.08) !important;
    transform: translateY(-1px) !important;
}

/* ── TABS inside content ── */
.main .stTabs [data-baseweb="tab-list"] {
    gap: 0 !important;
    background: transparent !important;
    border-bottom: 2px solid #E2E8F0 !important;
    padding: 0 !important;
    margin-bottom: 20px !important;
}
.main .stTabs [data-baseweb="tab"] {
    background: transparent !important;
    color: #64748B !important;
    border: none !important;
    font-size: 13px !important;
    font-weight: 500 !important;
    padding: 10px 18px !important;
    border-radius: 0 !important;
    transition: color 150ms ease !important;
}
.main .stTabs [data-baseweb="tab"]:hover { color: #0F172A !important; }
.main .stTabs [aria-selected="true"] {
    color: #4F46E5 !important;
    font-weight: 600 !important;
    border-bottom: 2px solid #4F46E5 !important;
    background: transparent !important;
}
.main .stTabs [data-baseweb="tab-highlight"],
.main .stTabs [data-baseweb="tab-border"] { display: none !important; }

/* ── INPUTS ── */
.stTextInput > div > div > input,
.stSelectbox > div > div,
.stMultiSelect > div > div {
    border-radius: 8px !important;
    border: 1px solid #E2E8F0 !important;
    font-size: 13px !important;
    color: #0F172A !important;
    background: #FFFFFF !important;
}
.stTextInput > div > div > input:focus,
.stSelectbox > div > div:focus-within {
    border-color: #6366F1 !important;
    box-shadow: 0 0 0 3px rgba(99,102,241,0.1) !important;
}
.stNumberInput > div > div > input {
    border-radius: 8px !important;
    font-size: 13px !important;
}

/* ── TEXT AREAS ── */
.stTextArea > div > div > textarea {
    border-radius: 8px !important;
    border: 1px solid #E2E8F0 !important;
    font-size: 13px !important;
    color: #0F172A !important;
}

/* ── DATAFRAME ── */
[data-testid="stDataFrame"] > div {
    border-radius: 12px !important;
    border: 1px solid #E2E8F0 !important;
    overflow: hidden !important;
    box-shadow: 0 1px 3px rgba(0,0,0,0.06) !important;
}

/* ── DIALOG / MODAL ── */
div[role="dialog"] {
    border-radius: 16px !important;
    box-shadow: 0 25px 50px rgba(0,0,0,0.18), 0 10px 20px rgba(0,0,0,0.08) !important;
    border: 1px solid #E2E8F0 !important;
}

/* ── DIVIDERS ── */
hr { border-color: #E2E8F0 !important; margin: 20px 0 !important; }

/* ── INFO / SUCCESS / ERROR boxes ── */
.stAlert {
    border-radius: 10px !important;
    border: none !important;
    font-size: 13px !important;
}

/* ── CHECKBOXES ── */
.stCheckbox label {
    font-size: 13px !important;
    color: #374151 !important;
}

/* ── CAPTION ── */
.stCaption, .stCaption p {
    color: #94A3B8 !important;
    font-size: 12px !important;
}

/* ── SUBHEADER / HEADERS ── */
h1 { font-size: 24px !important; font-weight: 700 !important; color: #0F172A !important; }
h2 { font-size: 18px !important; font-weight: 600 !important; color: #0F172A !important; }
h3 { font-size: 15px !important; font-weight: 600 !important; color: #1E293B !important; }

/* ── PLOTLY CHART ── */
[data-testid="stPlotlyChart"] > div {
    border-radius: 12px !important;
}

/* ── PAGE HEADER (custom HTML) ── */
.page-header {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 24px;
    padding-bottom: 20px;
    border-bottom: 1px solid #E2E8F0;
}
.page-header-title {
    font-size: 22px;
    font-weight: 700;
    color: #0F172A;
    line-height: 1.2;
}
.page-header-sub {
    font-size: 13px;
    color: #64748B;
    margin-top: 2px;
}
</style>
""", unsafe_allow_html=True)


# ── Data loader ────────────────────────────────────────────────────────────────
@st.cache_data(ttl=60)
def load_data() -> pd.DataFrame:
    try:
        from data_store import get_leads
        rows = get_leads()
        if not rows:
            raise ValueError("empty")
        df = pd.DataFrame(rows)
    except Exception:
        csv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output", "leads.csv")
        if os.path.exists(csv_path):
            df = pd.read_csv(csv_path, low_memory=False)
        else:
            return pd.DataFrame()

    for col in ("quality_score", "icp_score"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)

    # Normalize Neon column names
    if "founder_name" in df.columns and "name" not in df.columns:
        df["name"] = df["founder_name"]
    if "company_name" in df.columns and "company" not in df.columns:
        df["company"] = df["company_name"]
    if "headline" in df.columns and "title" not in df.columns:
        df["title"] = df["headline"]
    if "about" in df.columns and "about_snippet" not in df.columns:
        df["about_snippet"] = df["about"]
    if "pain_points" in df.columns and "inferred_pain_points" not in df.columns:
        df["inferred_pain_points"] = df["pain_points"]

    # ── Merge deep enrichment (pm_gap_signal etc.) from JSON if available ──
    enriched_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "leads", "high_priority", "top_50_enriched.json")
    if os.path.exists(enriched_path):
        import json
        with open(enriched_path) as f:
            enriched = json.load(f)
        enrich_map = {str(l.get("profile_url", "") or ""): l for l in enriched if l.get("profile_url")}
        enrich_fields = ["pm_gap_signal", "hiring_engineers", "hiring_pm", "company_description", "product_category", "final_score"]
        for field in enrich_fields:
            if field not in df.columns:
                df[field] = None
        url_col = "profile_url" if "profile_url" in df.columns else "linkedin_url"
        if url_col in df.columns:
            for idx, row in df.iterrows():
                url = str(row.get(url_col) or "")
                if url in enrich_map:
                    for field in enrich_fields:
                        df.at[idx, field] = enrich_map[url].get(field)

    return df


def _ensure_columns(df: pd.DataFrame) -> pd.DataFrame:
    defaults = {
        "quality_score": 0, "icp_score": 0,
        "lead_temperature": "Unknown", "pipeline_stage": "Found",
        "source": "", "title": "", "company": "", "name": "",
        "location": "", "verified": "", "notes": "",
        "status": "new", "priority_score": 0,
        "lead_stage": "", "date_contacted": "",
        "run_id": "", "pipeline_name": "", "pipeline_version": "",
    }
    for col, default in defaults.items():
        if col not in df.columns:
            df[col] = default
    return df


# ── Load data ──────────────────────────────────────────────────────────────────
df = _ensure_columns(load_data())
total_leads = len(df)
hot_count   = int((df["lead_temperature"] == "Hot").sum())  if not df.empty else 0
warm_count  = int((df["lead_temperature"] == "Warm").sum()) if not df.empty else 0
cold_count  = int((df["lead_temperature"] == "Cold").sum()) if not df.empty else 0

# ── Sidebar ────────────────────────────────────────────────────────────────────
if "page" not in st.session_state:
    st.session_state["page"] = "Overview"

NAV_ITEMS = [
    ("📊", "Overview"),
    ("🎯", "Action Center"),
    ("🔥", "Today"),
    ("📋", "Pipeline"),
    ("🗂️", "All Leads"),
    ("👤", "Lead Detail"),
    ("📦", "Pipeline Runs"),
    ("⚡", "Enrichment"),
    ("🔭", "Observability"),
    ("📜", "Sent Log"),
]

with st.sidebar:
    # ── Logo ──
    st.markdown(f"""
    <div style="padding:20px 16px 8px 16px;">
        <div style="display:flex; align-items:center; gap:10px; margin-bottom:3px;">
            <div style="width:34px; height:34px;
                        background:linear-gradient(135deg,#6366F1 0%,#8B5CF6 100%);
                        border-radius:9px; display:flex; align-items:center;
                        justify-content:center; font-size:17px; flex-shrink:0;">🚀</div>
            <div>
                <div style="color:#F1F5F9; font-weight:700; font-size:14.5px;
                            letter-spacing:-0.01em;">Outreach CRM</div>
                <div style="color:#475569; font-size:11px; margin-top:1px;">PM Job Search Tool</div>
            </div>
        </div>
    </div>

    <div style="height:1px; background:rgba(255,255,255,0.07); margin:8px 16px 10px 16px;"></div>

    <div style="padding:0 8px 4px 8px;">
        <div style="color:#475569; font-size:10.5px; font-weight:700; letter-spacing:0.1em;
                    text-transform:uppercase; padding:4px 8px 8px 8px;">Menu</div>
    """, unsafe_allow_html=True)

    current = st.session_state["page"]
    for icon, label in NAV_ITEMS:
        if current == label:
            # Active item — non-clickable HTML
            st.markdown(f"""
            <div style="background:rgba(99,102,241,0.18); border-radius:8px;
                        padding:9px 12px; margin:1px 0; display:flex; align-items:center;
                        gap:10px; border-left:3px solid #6366F1; cursor:default;">
                <span style="font-size:15px; opacity:0.9;">{icon}</span>
                <span style="color:#E0E7FF; font-size:13.5px; font-weight:600;">{label}</span>
            </div>
            """, unsafe_allow_html=True)
        else:
            if st.button(f"{icon}  {label}", key=f"nav_{label}", use_container_width=True):
                st.session_state["page"] = label
                st.rerun()

    st.markdown("""
    <div style="height:1px; background:rgba(255,255,255,0.07); margin:16px 8px 12px 8px;"></div>
    """, unsafe_allow_html=True)

    if st.button("🔄  Refresh Data", key="sidebar_refresh", use_container_width=True):
        st.cache_data.clear()
        st.rerun()


# ── Page routing ───────────────────────────────────────────────────────────────
page = st.session_state["page"]

if page == "Overview":
    from dashboard.components.overview import render as _r
    _r(df)

elif page == "Action Center":
    from dashboard.components.action_center import render as _r
    _r(df)

elif page == "Today":
    from dashboard.components.next_best_leads import render as _r
    _r(df)

elif page == "Pipeline":
    from dashboard.components.pipeline_view import render as _r
    _r(df)

elif page == "All Leads":
    from dashboard.components.lead_table import render as _r
    _r(df)

elif page == "Lead Detail":
    from dashboard.components.lead_detail import render as _r
    _r(df)

elif page == "Pipeline Runs":
    from dashboard.components.pipeline_runs import render as _r
    _r(df)

elif page == "Enrichment":
    from dashboard.components.enrichment_queue import render as _r
    _r(df)

elif page == "Observability":
    from dashboard.components.observability import render as _r
    _r()

elif page == "Sent Log":
    from dashboard.components.sent_log import render as _r
    _r()
