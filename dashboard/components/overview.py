"""
Overview — clickable metric cards + charts.
Every number is a button: click to navigate to a filtered lead table.
Design: Apollo.io / Attio inspired — white cards, soft shadows, Inter typography.
"""
from __future__ import annotations

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from dashboard.utils.filter_engine import set_filter, get_active_filter


# ── CSS: make metric-card buttons look like real stat cards ───────────────────
_METRIC_CARD_CSS = """
<style>
/* ── Pipeline metric buttons ── */
div.ov-metric-btn > div[data-testid="stButton"] > button {
    background: #FFFFFF !important;
    border: 1px solid #E2E8F0 !important;
    border-radius: 10px !important;
    padding: 14px 16px !important;
    text-align: left !important;
    min-height: 76px !important;
    width: 100% !important;
    box-shadow: 0 1px 2px rgba(0,0,0,0.05) !important;
    transition: box-shadow 150ms ease, border-color 150ms ease, transform 120ms ease !important;
    white-space: pre-line !important;
    line-height: 1.3 !important;
    color: #0F172A !important;
    font-family: Inter, sans-serif !important;
    cursor: pointer !important;
}
div.ov-metric-btn > div[data-testid="stButton"] > button:hover {
    box-shadow: 0 4px 14px rgba(99,102,241,0.18) !important;
    border-color: #6366F1 !important;
    transform: translateY(-2px) !important;
}
div.ov-metric-btn.active > div[data-testid="stButton"] > button {
    background: #EEF2FF !important;
    border-color: #6366F1 !important;
    box-shadow: 0 0 0 3px rgba(99,102,241,0.15) !important;
}

/* ── Stat-card buttons (larger 6-up row) ── */
div.ov-stat-btn > div[data-testid="stButton"] > button {
    background: #FFFFFF !important;
    border: 1px solid #E2E8F0 !important;
    border-radius: 12px !important;
    padding: 20px 18px !important;
    text-align: left !important;
    min-height: 96px !important;
    width: 100% !important;
    box-shadow: 0 1px 3px rgba(0,0,0,0.07),0 1px 2px rgba(0,0,0,0.04) !important;
    transition: box-shadow 150ms ease, border-color 150ms ease, transform 120ms ease !important;
    white-space: pre-line !important;
    line-height: 1.3 !important;
    color: #0F172A !important;
    font-family: Inter, sans-serif !important;
    cursor: pointer !important;
}
div.ov-stat-btn > div[data-testid="stButton"] > button:hover {
    box-shadow: 0 6px 20px rgba(99,102,241,0.16) !important;
    border-color: #818CF8 !important;
    transform: translateY(-2px) !important;
}
div.ov-stat-btn.active > div[data-testid="stButton"] > button {
    background: #EEF2FF !important;
    border-color: #6366F1 !important;
    box-shadow: 0 0 0 3px rgba(99,102,241,0.15) !important;
}
</style>
"""

# ── Shared plotly layout ───────────────────────────────────────────────────────
_CHART_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="Inter, sans-serif", color="#64748B", size=12),
    margin=dict(t=10, b=10, l=10, r=10),
    showlegend=False,
    height=260,
    xaxis=dict(
        gridcolor="#F1F5F9", linecolor="#E2E8F0",
        tickfont=dict(size=11, color="#94A3B8"),
    ),
    yaxis=dict(
        gridcolor="#F1F5F9", linecolor="rgba(0,0,0,0)",
        tickfont=dict(size=11, color="#94A3B8"),
    ),
)


def _section_label(text: str) -> None:
    st.markdown(
        f'<div style="font-size:12px; font-weight:700; color:#94A3B8; letter-spacing:0.08em; '
        f'text-transform:uppercase; margin-bottom:10px;">{text}</div>',
        unsafe_allow_html=True,
    )


def _metric_btn(col, icon: str, label: str, value, filter_type: str, color: str, active_filter: str | None) -> None:
    """Render a single clickable metric card inside `col`."""
    is_active = active_filter == filter_type
    css_class = "ov-metric-btn active" if is_active else "ov-metric-btn"
    with col:
        st.markdown(f'<div class="{css_class}">', unsafe_allow_html=True)
        btn_label = f"{icon}  {value:,}\n{label}" if isinstance(value, int) else f"{icon}  {value}\n{label}"
        if st.button(btn_label, key=f"ov_m_{filter_type}", use_container_width=True, help=f"Click to filter: {label}"):
            set_filter(filter_type, label)
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)


def _stat_btn(col, icon: str, label: str, value, sub: str, filter_type: str, color: str, active_filter: str | None) -> None:
    """Render a larger clickable stat card inside `col`."""
    is_active = active_filter == filter_type
    css_class = "ov-stat-btn active" if is_active else "ov-stat-btn"
    with col:
        st.markdown(f'<div class="{css_class}">', unsafe_allow_html=True)
        btn_label = f"{icon}  {value:,}\n{label}" if isinstance(value, int) else f"{icon}  {value}\n{label}"
        if st.button(btn_label, key=f"ov_s_{filter_type}", use_container_width=True, help=f"Click to filter: {label}"):
            set_filter(filter_type, label)
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)


def render(df: pd.DataFrame) -> None:
    st.markdown(_METRIC_CARD_CSS, unsafe_allow_html=True)

    active_filter, active_label = get_active_filter()

    # ── Page header ────────────────────────────────────────────────────────────
    _ts_col  = next((c for c in ["updated_at", "created_at", "scraped_at"] if c in df.columns), None)
    last_upd = df[_ts_col].dropna().astype(str).max()[:10] if (_ts_col and not df.empty) else "N/A"

    st.markdown(f"""
    <div style="margin-bottom:28px;">
        <div style="font-size:22px; font-weight:700; color:#0F172A; letter-spacing:-0.02em;">
            Overview
        </div>
        <div style="font-size:13px; color:#94A3B8; margin-top:4px;">
            Last updated: {last_upd} &nbsp;·&nbsp; Neon Postgres
            &nbsp;·&nbsp; <span style="color:#6366F1; font-weight:500;">Click any card to filter leads</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    if df.empty:
        st.info("No leads yet. Run the pipeline to start scraping.")
        return

    # ── Active filter banner ──────────────────────────────────────────────────
    if active_filter and active_filter != "all":
        bc1, bc2 = st.columns([5, 1])
        with bc1:
            st.markdown(
                f'<div style="background:#EEF2FF; border:1px solid #C7D2FE; border-radius:8px; '
                f'padding:10px 16px; font-size:13px; color:#4338CA; font-weight:500;">'
                f'🔍 Active filter: <strong>{active_label}</strong> &nbsp;·&nbsp; '
                f'Viewing All Leads with this filter applied</div>',
                unsafe_allow_html=True,
            )
        with bc2:
            if st.button("✕ Clear", key="ov_clear_filter", use_container_width=True):
                from dashboard.utils.filter_engine import clear_filter
                clear_filter()
                st.rerun()
        st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

    # ── Compute pipeline metrics ──────────────────────────────────────────────
    try:
        from data_store import get_pipeline_runs
        runs = get_pipeline_runs()
    except Exception:
        runs = []

    score_col = (
        "icp_score"
        if "icp_score" in df.columns and pd.to_numeric(df["icp_score"], errors="coerce").fillna(0).sum() > 0
        else "quality_score"
    )
    scores   = pd.to_numeric(df.get(score_col, pd.Series(dtype=float)), errors="coerce").fillna(0)
    priority = pd.to_numeric(df.get("priority_score", pd.Series(dtype=float)), errors="coerce").fillna(0)

    total_raw      = len(df)
    total_qual     = int((scores >= 70).sum())
    total_enriched = int(df.get("enrichment_status", pd.Series()).isin(["ready", "enriched", "done"]).sum()) \
                     if "enrichment_status" in df.columns else 0
    total_messages = int(
        df.get("msg_connection_note", pd.Series()).apply(
            lambda x: bool(str(x).strip() and str(x).strip().lower() not in ("nan", "none", ""))
        ).sum()
    ) if "msg_connection_note" in df.columns else 0
    outreach_sent  = int(
        df.get("status", pd.Series()).isin(["connection_sent", "accepted", "replied", "meeting_booked", "closed"]).sum()
    ) if "status" in df.columns else 0
    total_replies  = int(
        df.get("status", pd.Series()).isin(["replied", "meeting_booked", "closed"]).sum()
    ) if "status" in df.columns else 0
    total_meetings = int(
        df.get("status", pd.Series()).isin(["meeting_booked"]).sum()
    ) if "status" in df.columns else 0

    # ── Pipeline Metrics Row (all clickable) ──────────────────────────────────
    _section_label("Pipeline Metrics")

    pm_cols = st.columns(7)
    pipeline_metrics = [
        ("📥", "Raw Leads",      total_raw,      "all",           "#6366F1"),
        ("✅", "Qualified",      total_qual,     "qualified",     "#10B981"),
        ("🔍", "Enriched",       total_enriched, "enriched",      "#8B5CF6"),
        ("✉️", "Messages Ready", total_messages, "message_ready", "#3B82F6"),
        ("📤", "Outreach Sent",  outreach_sent,  "contacted",     "#F59E0B"),
        ("💬", "Replies",        total_replies,  "replied",       "#EC4899"),
        ("📅", "Meetings",       total_meetings, "meeting_booked","#14B8A6"),
    ]
    for col, (icon, label, val, ftype, color) in zip(pm_cols, pipeline_metrics):
        _metric_btn(col, icon, label, val, ftype, color, active_filter)

    st.markdown("<div style='height:24px'></div>", unsafe_allow_html=True)

    # ── Stat Cards Row (all clickable) ────────────────────────────────────────
    _section_label("Lead Health")

    total    = len(df)
    hot      = int((df["lead_temperature"] == "Hot").sum())  if "lead_temperature" in df.columns else 0
    warm     = int((df["lead_temperature"] == "Warm").sum()) if "lead_temperature" in df.columns else 0
    cold     = int((df["lead_temperature"] == "Cold").sum()) if "lead_temperature" in df.columns else 0
    high_pri = int((priority >= 80).sum())
    pm_gap   = int(df.get("pm_gap_signal", pd.Series()).isin([True, "True", "true", 1, "1"]).sum()) \
               if "pm_gap_signal" in df.columns else 0

    stat_cols = st.columns(6)
    stat_cards = [
        ("🎯", "Total Leads",    total,    f"{total_qual} qualified", "all",          "#6366F1"),
        ("🔥", "Hot Leads",      hot,      "active signal < 7d",     "hot",          "#EF4444"),
        ("⚡", "Warm Leads",     warm,     "active signal < 30d",    "warm",         "#F59E0B"),
        ("❄️", "Cold Leads",     cold,     "signal 30d+",            "cold",         "#3B82F6"),
        ("⭐", "High Priority",  high_pri, "priority score ≥ 80",    "high_priority","#8B5CF6"),
        ("⚡", "PM Gap",         pm_gap,   "hiring eng, no PM yet",  "pm_gap",       "#EA580C"),
    ]
    for col, (icon, label, val, sub, ftype, color) in zip(stat_cols, stat_cards):
        _stat_btn(col, icon, label, val, sub, ftype, color, active_filter)

    st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)

    # ── Charts Row 1: Source + Location (clickable bars) ─────────────────────
    col_l, col_r = st.columns(2, gap="large")

    with col_l:
        st.markdown(
            '<div style="font-size:14px; font-weight:600; color:#1E293B; margin-bottom:4px;">Leads by Source</div>'
            '<div style="font-size:12px; color:#94A3B8; margin-bottom:10px;">Click a bar to filter by source</div>',
            unsafe_allow_html=True,
        )
        source_counts = df["source"].value_counts().reset_index()
        source_counts.columns = ["Source", "Count"]
        fig = px.bar(
            source_counts, x="Source", y="Count",
            color="Count",
            color_continuous_scale=[[0, "#C7D2FE"], [1, "#4F46E5"]],
            text="Count",
        )
        fig.update_traces(textposition="outside", marker_line_width=0, textfont_size=11)
        fig.update_layout(**_CHART_LAYOUT, coloraxis_showscale=False)
        event = st.plotly_chart(
            fig, use_container_width=True,
            config={"displayModeBar": False},
            on_select="rerun",
            key="chart_source",
        )
        if event and event.get("select") and event["select"].get("points"):
            src_clicked = event["select"]["points"][0].get("x") or event["select"]["points"][0].get("label")
            if src_clicked:
                set_filter(f"source:{src_clicked}", f"Source: {src_clicked}")
                st.rerun()

    with col_r:
        st.markdown(
            '<div style="font-size:14px; font-weight:600; color:#1E293B; margin-bottom:4px;">Leads by Location</div>'
            '<div style="font-size:12px; color:#94A3B8; margin-bottom:10px;">Click a bar to filter by location</div>',
            unsafe_allow_html=True,
        )
        def _loc(loc: str) -> str:
            loc = str(loc).strip()
            lo  = loc.lower()
            if "india"         in lo: return "India"
            if "united states" in lo or "usa" in lo or "america" in lo: return "United States"
            if "united kingdom" in lo or " uk" in lo or "london" in lo: return "United Kingdom"
            if "uae" in lo or "dubai" in lo: return "UAE"
            if loc in ("United States", "India", "United Kingdom", "UAE", "Remote/Global",
                       "Europe", "Canada", "Australia"): return loc
            return "Other"

        df_loc = df.copy()
        df_loc["country"] = df_loc["location"].apply(_loc)
        loc_counts = df_loc["country"].value_counts().reset_index()
        loc_counts.columns = ["Country", "Count"]
        PALETTE = ["#4F46E5","#7C3AED","#2563EB","#0891B2","#059669","#D97706","#DC2626","#475569"]
        fig2 = px.bar(
            loc_counts, x="Country", y="Count",
            color="Country",
            color_discrete_sequence=PALETTE,
            text="Count",
        )
        fig2.update_traces(textposition="outside", marker_line_width=0, textfont_size=11)
        fig2.update_layout(**_CHART_LAYOUT)
        event2 = st.plotly_chart(
            fig2, use_container_width=True,
            config={"displayModeBar": False},
            on_select="rerun",
            key="chart_location",
        )
        if event2 and event2.get("select") and event2["select"].get("points"):
            loc_clicked = event2["select"]["points"][0].get("x") or event2["select"]["points"][0].get("label")
            if loc_clicked and loc_clicked != "Other":
                set_filter(f"location:{loc_clicked}", f"Location: {loc_clicked}")
                st.rerun()

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    # ── Charts Row 2: Score histogram + Funnel ────────────────────────────────
    col_l2, col_r2 = st.columns(2, gap="large")

    with col_l2:
        st.markdown(
            '<div style="font-size:14px; font-weight:600; color:#1E293B; margin-bottom:4px;">ICP Score Distribution</div>'
            '<div style="font-size:12px; color:#94A3B8; margin-bottom:10px;">Click a bar to filter ≥ that score range</div>',
            unsafe_allow_html=True,
        )
        fig3 = px.histogram(df, x=score_col, nbins=10, color_discrete_sequence=["#6366F1"])
        fig3.add_vline(
            x=70, line_dash="dot", line_color="#F59E0B", line_width=1.5,
            annotation_text="Qualified", annotation_font_size=11,
            annotation_font_color="#F59E0B",
        )
        fig3.update_layout(**_CHART_LAYOUT)
        event3 = st.plotly_chart(
            fig3, use_container_width=True,
            config={"displayModeBar": False},
            on_select="rerun",
            key="chart_score",
        )
        if event3 and event3.get("select") and event3["select"].get("points"):
            pt = event3["select"]["points"][0]
            bin_start = pt.get("x") or pt.get("binStart")
            if bin_start is not None:
                threshold = int(bin_start)
                set_filter(f"icp_gte:{threshold}", f"ICP Score ≥ {threshold}")
                st.rerun()

    with col_r2:
        st.markdown(
            '<div style="font-size:14px; font-weight:600; color:#1E293B; margin-bottom:12px;">Outreach Funnel</div>',
            unsafe_allow_html=True,
        )
        stage_order = [
            "Found", "Verified", "Warming Up", "Request Sent",
            "Connected", "Msg Sent", "Replied", "Interested", "Closed",
        ]
        stage_counts = df["pipeline_stage"].value_counts() if "pipeline_stage" in df.columns else pd.Series()
        funnel_df = pd.DataFrame([
            {"Stage": s, "Count": int(stage_counts.get(s, 0))}
            for s in stage_order
        ])
        funnel_df = funnel_df[funnel_df["Count"] > 0]

        if not funnel_df.empty:
            FUNNEL_COLORS = ["#4F46E5","#6366F1","#818CF8","#7C3AED",
                             "#8B5CF6","#A78BFA","#C4B5FD","#DDD6FE","#EDE9FE"]
            fig4 = go.Figure(go.Funnel(
                y=funnel_df["Stage"], x=funnel_df["Count"],
                textinfo="value+percent initial",
                marker={"color": FUNNEL_COLORS[:len(funnel_df)]},
                textfont=dict(family="Inter, sans-serif", size=12),
            ))
            fig4.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font=dict(family="Inter, sans-serif", color="#64748B", size=12),
                margin=dict(t=10, b=10, l=0, r=10),
                height=260,
            )
            st.plotly_chart(fig4, use_container_width=True, config={"displayModeBar": False})
        else:
            st.caption("No pipeline data yet — move leads through stages to see funnel.")

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    # ── Top 10 leads table ────────────────────────────────────────────────────
    st.markdown(
        '<div style="font-size:14px; font-weight:600; color:#1E293B; margin-bottom:12px;">Top 10 Leads by ICP Score</div>',
        unsafe_allow_html=True,
    )
    cols_show = [c for c in ["name", "title", "company", "location", score_col, "lead_temperature", "source", "pipeline_stage"] if c in df.columns]
    top10 = df.nlargest(10, score_col)[cols_show].reset_index(drop=True)

    def _style_temp(val: str) -> str:
        return {
            "Hot":  "color:#EF4444; font-weight:600",
            "Warm": "color:#F59E0B; font-weight:600",
            "Cold": "color:#3B82F6; font-weight:600",
        }.get(str(val), "color:#94A3B8")

    styled = top10.style.map(_style_temp, subset=["lead_temperature"] if "lead_temperature" in top10.columns else [])
    st.dataframe(styled, use_container_width=True, height=360)

    # ── View All Leads CTA ────────────────────────────────────────────────────
    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
    cta1, cta2, cta3 = st.columns([1, 2, 1])
    with cta2:
        if st.button("📋 View All Leads →", key="ov_view_all", use_container_width=True):
            from dashboard.utils.filter_engine import clear_filter
            clear_filter()
            st.session_state["page"] = "All Leads"
            st.rerun()
