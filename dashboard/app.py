"""
Main Streamlit CRM Dashboard
4 pages: Overview · Pipeline · Lead Table · Lead Detail
Reads live from Supabase, falls back to local CSV.
"""

import os
import sys
import pandas as pd
import streamlit as st

# Make sure parent directory is on path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dashboard.components import overview, pipeline_view, lead_table, lead_detail

st.set_page_config(
    page_title="LinkedIn Outreach CRM",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    .stMetric { background: #f8f9fa; border-radius: 8px; padding: 12px; }
    div[data-testid="stHorizontalBlock"] { gap: 12px; }
    .stButton > button { border-radius: 6px; }
    section[data-testid="stSidebar"] { background: #1a1a2e; }
    section[data-testid="stSidebar"] * { color: white !important; }
    h1, h2, h3 { color: #1a1a2e; }
</style>
""", unsafe_allow_html=True)


@st.cache_data(ttl=300)  # refresh every 5 minutes
def load_data() -> pd.DataFrame:
    """Load leads from Supabase, falling back to CSV if not configured."""
    # Try Supabase first
    try:
        from database import fetch_all_leads
        from config import SUPABASE_URL, SUPABASE_KEY
        if SUPABASE_URL and SUPABASE_KEY:
            records = fetch_all_leads()
            if records:
                df = pd.DataFrame(records)
                df["quality_score"] = pd.to_numeric(df.get("quality_score", 0), errors="coerce").fillna(0).astype(int)
                return df
    except Exception:
        pass

    # Fallback: local CSV
    csv_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "output", "leads.csv",
    )
    if os.path.exists(csv_path):
        df = pd.read_csv(csv_path, low_memory=False)
        df["quality_score"] = pd.to_numeric(df.get("quality_score", 0), errors="coerce").fillna(0).astype(int)
        return df

    return pd.DataFrame()


# ── Sidebar Navigation ────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🚀 Outreach CRM")
    st.markdown("---")

    pages = ["Overview", "Pipeline", "Lead Table", "Lead Detail"]
    if "active_page" not in st.session_state:
        st.session_state["active_page"] = "Overview"

    for page in pages:
        icon = {"Overview": "📊", "Pipeline": "📋", "Lead Table": "📋", "Lead Detail": "👤"}[page]
        is_active = st.session_state["active_page"] == page
        if st.button(
            f"{icon} {page}",
            key=f"nav_{page}",
            use_container_width=True,
            type="primary" if is_active else "secondary",
        ):
            st.session_state["active_page"] = page
            # No st.rerun() needed — Streamlit reruns automatically on button click

    st.markdown("---")
    if st.button("🔄 Refresh Data", use_container_width=True):
        st.cache_data.clear()
        # No st.rerun() — Streamlit reruns automatically

    st.markdown("---")
    st.caption("Built with Streamlit + Supabase")
    st.caption("Data powered by Apify + RapidAPI")


# ── Load Data ─────────────────────────────────────────────────────────────────
df = load_data()

# Ensure required columns exist with defaults
required_cols = {
    "quality_score": 0, "lead_temperature": "Unknown",
    "pipeline_stage": "Found", "source": "", "warm_up_status": "Not started",
    "outreach_status": "Not contacted", "verified": "", "notes": "",
}
for col, default in required_cols.items():
    if col not in df.columns:
        df[col] = default

# ── Render Active Page ────────────────────────────────────────────────────────
active = st.session_state.get("active_page", "Overview")

if active == "Overview":
    overview.render(df)
elif active == "Pipeline":
    pipeline_view.render(df)
elif active == "Lead Table":
    lead_table.render(df)
elif active == "Lead Detail":
    lead_detail.render(df)
