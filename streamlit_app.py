"""
LinkedIn Outreach CRM — Jira-style Single Page Application
Left sidebar navigation, session-state routing, no top tabs.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import streamlit as st
import pandas as pd

# ── Page config (must be first Streamlit call) ──────────────────────────────
st.set_page_config(
    page_title="Outreach CRM",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Global CSS — Jira palette + hide default nav ─────────────────────────────
st.markdown(
    """
    <style>
    /* ── Hide Streamlit's auto-generated pages/ navigation ── */
    [data-testid="stSidebarNav"] { display: none !important; }
    section[data-testid="stSidebar"] > div:first-child { padding-top: 1rem; }

    /* ── App background ── */
    .stApp { background-color: #F4F5F7; }

    /* ── Remove default Streamlit padding from sidebar ── */
    section[data-testid="stSidebar"] {
        background-color: #FFFFFF;
        border-right: 1px solid #DFE1E6;
    }

    /* ── Breadcrumb strip ── */
    .crm-breadcrumb {
        background: #FFFFFF;
        border-bottom: 1px solid #DFE1E6;
        padding: 8px 20px;
        font-size: 0.82em;
        color: #6B778C;
        margin-bottom: 16px;
        border-radius: 0 0 4px 4px;
    }
    .crm-breadcrumb span.page-name {
        color: #172B4D;
        font-weight: 600;
    }

    /* ── Sidebar nav item base ── */
    div[data-testid="stButton"] > button.nav-btn {
        width: 100%;
        text-align: left;
        border: none;
        background: transparent;
        color: #172B4D;
        font-size: 0.9em;
        padding: 6px 12px 6px 28px;
        border-radius: 3px;
        cursor: pointer;
        transition: background 0.15s;
    }
    div[data-testid="stButton"] > button.nav-btn:hover {
        background: #DEEBFF;
        color: #0052CC;
    }

    /* ── Metric card overrides ── */
    div[data-testid="stMetric"] {
        background: #FFFFFF;
        border: 1px solid #DFE1E6;
        border-radius: 4px;
        padding: 12px 16px;
    }

    /* ── Kanban column headers ── */
    .kanban-header {
        font-size: 0.78em;
        font-weight: 700;
        letter-spacing: 0.06em;
        text-transform: uppercase;
        padding: 6px 10px;
        border-radius: 4px 4px 0 0;
        margin-bottom: 6px;
    }

    /* ── Board-view "Create Lead" strip ── */
    .crm-action-bar {
        display: flex;
        justify-content: flex-end;
        margin-bottom: 12px;
    }

    /* ── General card ── */
    .crm-card {
        background: #FFFFFF;
        border: 1px solid #DFE1E6;
        border-radius: 6px;
        padding: 14px 18px;
        margin-bottom: 12px;
    }

    /* ── Back link ── */
    .back-link {
        color: #0052CC;
        font-size: 0.88em;
        cursor: pointer;
        margin-bottom: 12px;
        display: inline-block;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ── Data loader ──────────────────────────────────────────────────────────────
@st.cache_data(ttl=60)
def load_data() -> pd.DataFrame:
    csv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output", "leads.csv")
    if os.path.exists(csv_path):
        df = pd.read_csv(csv_path, low_memory=False)
        df["quality_score"] = (
            pd.to_numeric(df.get("quality_score", 0), errors="coerce")
            .fillna(0)
            .astype(int)
        )
        return df
    return pd.DataFrame()


def _ensure_columns(df: pd.DataFrame) -> pd.DataFrame:
    defaults = {
        "quality_score": 0,
        "lead_temperature": "Unknown",
        "pipeline_stage": "Found",
        "source": "",
        "warm_up_status": "Not started",
        "outreach_status": "Not contacted",
        "verified": "",
        "notes": "",
    }
    for col, default in defaults.items():
        if col not in df.columns:
            df[col] = default
    return df


# ── Session state defaults ───────────────────────────────────────────────────
if "page" not in st.session_state:
    st.session_state["page"] = "Overview"
if "selected_lead" not in st.session_state:
    st.session_state["selected_lead"] = None


# ── Load data ────────────────────────────────────────────────────────────────
df = _ensure_columns(load_data())

# Quick stats for sidebar
total_leads = len(df)
hot_count   = int((df["lead_temperature"] == "Hot").sum())  if not df.empty else 0
warm_count  = int((df["lead_temperature"] == "Warm").sum()) if not df.empty else 0
cold_count  = int((df["lead_temperature"] == "Cold").sum()) if not df.empty else 0


# ── Sidebar ──────────────────────────────────────────────────────────────────
def _nav_button(label: str, page_key: str) -> None:
    """Render a sidebar nav button. Active page gets blue highlight."""
    is_active = st.session_state["page"] == page_key
    bg_style  = "background:#DEEBFF; color:#0052CC; font-weight:600;" if is_active else ""
    # We render a styled button using markdown + st.button overlay trick
    if st.button(
        label,
        key=f"nav_{page_key}",
        use_container_width=True,
    ):
        st.session_state["page"] = page_key
        st.rerun()

    # Inject active-state highlight via targeted CSS after render
    if is_active:
        st.markdown(
            f"""
            <style>
            div[data-testid="stButton"] > button[kind="secondary"]:has(+ *),
            </style>
            """,
            unsafe_allow_html=True,
        )


with st.sidebar:
    # ── Logo / Title ─────────────────────────────────────────────
    st.markdown(
        """
        <div style="padding: 4px 8px 12px 8px;">
          <span style="font-size:1.35em; font-weight:700; color:#0052CC;">
            🚀 Outreach CRM
          </span>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        '<hr style="margin:0 0 10px 0; border-color:#DFE1E6;">',
        unsafe_allow_html=True,
    )

    # ── Section: PLAN ────────────────────────────────────────────
    st.markdown(
        '<p style="font-size:0.72em; font-weight:700; color:#6B778C; '
        'letter-spacing:0.08em; margin:4px 0 6px 6px;">PLAN</p>',
        unsafe_allow_html=True,
    )

    for label, key in [("📊  Overview", "Overview"), ("📋  Board", "Board")]:
        is_active = st.session_state["page"] == key
        if is_active:
            st.markdown(
                f'<div style="background:#DEEBFF; color:#0052CC; font-weight:600; '
                f'border-radius:4px; padding:7px 12px 7px 18px; '
                f'font-size:0.9em; margin-bottom:2px;">{label}</div>',
                unsafe_allow_html=True,
            )
        else:
            if st.button(label, key=f"nav_{key}", use_container_width=True):
                st.session_state["page"] = key
                st.rerun()

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    # ── Section: VIEWS ───────────────────────────────────────────
    st.markdown(
        '<p style="font-size:0.72em; font-weight:700; color:#6B778C; '
        'letter-spacing:0.08em; margin:4px 0 6px 6px;">VIEWS</p>',
        unsafe_allow_html=True,
    )

    for label, key in [("🗂️  All Leads", "All Leads"), ("👤  Lead Detail", "Lead Detail")]:
        is_active = st.session_state["page"] == key
        if is_active:
            st.markdown(
                f'<div style="background:#DEEBFF; color:#0052CC; font-weight:600; '
                f'border-radius:4px; padding:7px 12px 7px 18px; '
                f'font-size:0.9em; margin-bottom:2px;">{label}</div>',
                unsafe_allow_html=True,
            )
        else:
            if st.button(label, key=f"nav_{key}", use_container_width=True):
                st.session_state["page"] = key
                st.rerun()

    # ── Stats ─────────────────────────────────────────────────────
    st.markdown(
        '<hr style="margin:14px 0 10px 0; border-color:#DFE1E6;">',
        unsafe_allow_html=True,
    )
    st.markdown(
        f"""
        <div style="padding: 0 8px; font-size:0.88em; color:#172B4D; line-height:2.0;">
          <div>📦 <strong>Total:</strong> {total_leads}</div>
          <div>🔥 <strong>Hot:</strong> {hot_count}</div>
          <div>⚡ <strong>Warm:</strong> {warm_count}</div>
          <div>❄️ <strong>Cold:</strong> {cold_count}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)

    # ── Refresh ───────────────────────────────────────────────────
    if st.button("🔄  Refresh Data", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    st.markdown(
        '<hr style="margin:10px 0 6px 0; border-color:#DFE1E6;">',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<p style="font-size:0.72em; color:#6B778C; padding:0 8px;">Streamlit · Supabase · Apify</p>',
        unsafe_allow_html=True,
    )


# ── Breadcrumb helper ─────────────────────────────────────────────────────────
def _breadcrumb(page_name: str, extra: str = "") -> None:
    extra_html = f" / <span class='page-name'>{extra}</span>" if extra else ""
    st.markdown(
        f"""
        <div class="crm-breadcrumb">
          Outreach CRM / <span class='page-name'>{page_name}</span>{extra_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


# ── Active-state button styling (global, keyed on current page) ──────────────
# We inject CSS that targets the button matching the active page label so it
# renders with Jira-blue background even though st.button doesn't support this
# natively.  The hidden-button trick above already handles the visual block;
# this CSS just makes the visible inline buttons look right on hover.
_active_page = st.session_state["page"]
st.markdown(
    f"""
    <style>
    /* Make all sidebar nav buttons look clean */
    section[data-testid="stSidebar"] button[kind="secondary"] {{
        background: transparent !important;
        border: none !important;
        box-shadow: none !important;
        text-align: left !important;
        padding: 7px 12px 7px 18px !important;
        font-size: 0.9em !important;
        color: #172B4D !important;
        border-radius: 4px !important;
        width: 100% !important;
    }}
    section[data-testid="stSidebar"] button[kind="secondary"]:hover {{
        background: #DEEBFF !important;
        color: #0052CC !important;
    }}
    /* Refresh button — keep it styled differently */
    section[data-testid="stSidebar"] button[kind="secondary"]:last-of-type {{
        background: #F4F5F7 !important;
        border: 1px solid #DFE1E6 !important;
        color: #172B4D !important;
    }}
    section[data-testid="stSidebar"] button[kind="secondary"]:last-of-type:hover {{
        background: #DEEBFF !important;
        color: #0052CC !important;
    }}
    </style>
    """,
    unsafe_allow_html=True,
)


# ── Page routing ─────────────────────────────────────────────────────────────
current_page = st.session_state["page"]

# ─────────────────────────────────────────────────────────────────────────────
# PAGE: Overview
# ─────────────────────────────────────────────────────────────────────────────
if current_page == "Overview":
    _breadcrumb("Overview")
    from dashboard.components.overview import render
    render(df)

# ─────────────────────────────────────────────────────────────────────────────
# PAGE: Board (Pipeline Kanban)
# ─────────────────────────────────────────────────────────────────────────────
elif current_page == "Board":
    _breadcrumb("Board")

    # Action bar (Jira-style "Create" button placeholder)
    st.markdown(
        """
        <div style="display:flex; justify-content:flex-end; margin-bottom:10px;">
          <div style="background:#0052CC; color:#FFFFFF; padding:7px 18px;
                      border-radius:3px; font-size:0.88em; font-weight:600;
                      cursor:pointer; opacity:0.85;">
            + Create Lead
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Inject Jira-style column header overrides for the kanban
    st.markdown(
        """
        <style>
        /* Kanban stage header pill — override pipeline_view.py inline styles */
        .stMarkdown div[style*="border-radius:8px"] {
            border-radius: 3px !important;
            font-size: 0.78em !important;
            font-weight: 700 !important;
            letter-spacing: 0.06em !important;
            text-transform: uppercase !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    from dashboard.components.pipeline_view import render
    render(df)

# ─────────────────────────────────────────────────────────────────────────────
# PAGE: All Leads
# ─────────────────────────────────────────────────────────────────────────────
elif current_page == "All Leads":
    _breadcrumb("All Leads")

    # Action bar
    st.markdown(
        """
        <div style="display:flex; justify-content:flex-end; margin-bottom:10px;">
          <div style="background:#0052CC; color:#FFFFFF; padding:7px 18px;
                      border-radius:3px; font-size:0.88em; font-weight:600;
                      cursor:pointer; opacity:0.85;">
            + Create Lead
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    from dashboard.components.lead_table import render
    render(df)

# ─────────────────────────────────────────────────────────────────────────────
# PAGE: Lead Detail
# ─────────────────────────────────────────────────────────────────────────────
elif current_page == "Lead Detail":
    _breadcrumb("All Leads", "Lead Detail")

    # Back button
    if st.button("← All Leads", key="back_to_all_leads"):
        st.session_state["page"] = "All Leads"
        st.rerun()

    from dashboard.components.lead_detail import render
    render(df)
