"""
Overview — Premium stat cards + clean charts.
Design: Apollo.io / Attio inspired — white cards, soft shadows, Inter typography.
"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go


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

def _card(content: str) -> str:
    return (
        f'<div style="background:#FFFFFF; border-radius:12px; '
        f'border:1px solid #E2E8F0; padding:20px 24px; '
        f'box-shadow:0 1px 3px rgba(0,0,0,0.07),0 1px 2px rgba(0,0,0,0.04);">'
        f'{content}</div>'
    )


def _stat_card(label: str, value, icon: str, accent: str, sub: str = "") -> str:
    sub_html = (
        f'<div style="font-size:11.5px; color:#94A3B8; margin-top:5px;">{sub}</div>'
        if sub else ""
    )
    return f"""
    <div style="background:#FFFFFF; border-radius:12px; border:1px solid #E2E8F0;
                padding:20px 24px; box-shadow:0 1px 3px rgba(0,0,0,0.07),0 1px 2px rgba(0,0,0,0.04);
                transition:box-shadow 150ms ease, transform 150ms ease; height:100%;">
        <div style="display:flex; align-items:flex-start; justify-content:space-between; gap:12px;">
            <div>
                <div style="font-size:11.5px; font-weight:600; color:#64748B;
                            letter-spacing:0.05em; text-transform:uppercase; margin-bottom:10px;">
                    {label}
                </div>
                <div style="font-size:30px; font-weight:700; color:#0F172A; line-height:1;">
                    {value}
                </div>
                {sub_html}
            </div>
            <div style="width:44px; height:44px; background:{accent}18; border-radius:10px;
                        display:flex; align-items:center; justify-content:center;
                        font-size:20px; flex-shrink:0;">
                {icon}
            </div>
        </div>
    </div>
    """


def render(df: pd.DataFrame) -> None:
    # ── Page header ────────────────────────────────────────────────────────────
    _ts_col = next((c for c in ["updated_at", "created_at", "scraped_at"] if c in df.columns), None)
    last_upd = df[_ts_col].dropna().astype(str).max()[:10] if (_ts_col and not df.empty) else "N/A"

    st.markdown(f"""
    <div style="margin-bottom:28px;">
        <div style="font-size:22px; font-weight:700; color:#0F172A; letter-spacing:-0.02em;">
            Overview
        </div>
        <div style="font-size:13px; color:#94A3B8; margin-top:4px;">
            Last updated: {last_upd} &nbsp;·&nbsp; Neon Postgres
        </div>
    </div>
    """, unsafe_allow_html=True)

    if df.empty:
        st.info("No leads yet. Run the pipeline to start scraping.")
        return

    # ── Stat cards ─────────────────────────────────────────────────────────────
    total    = len(df)
    hot      = len(df[df["lead_temperature"] == "Hot"])
    warm     = len(df[df["lead_temperature"] == "Warm"])
    cold     = len(df[df["lead_temperature"] == "Cold"])
    verified = len(df[df.get("verified", pd.Series(dtype=str)).astype(str).str.upper().isin(["YES", "Y", "TRUE"])])
    ready    = len(df[df["pipeline_stage"].isin(["Ready", "Verified", "Warming Up", "Request Sent"])])

    c1, c2, c3, c4, c5, c6 = st.columns(6)
    cols = [c1, c2, c3, c4, c5, c6]
    cards = [
        ("Total Leads",    total,    "🎯", "#6366F1", f"{ready} ready"),
        ("🔥 Hot",         hot,      "🔥", "#EF4444", "< 7 days old"),
        ("⚡ Warm",         warm,     "⚡", "#F59E0B", "< 30 days old"),
        ("❄️ Cold",         cold,     "❄️", "#3B82F6", "30 days+"),
        ("✅ Verified",     verified, "✅", "#10B981", "confirmed ICP"),
        ("📋 In Pipeline",  ready,    "📋", "#8B5CF6", "warming up+"),
    ]
    for col, (label, val, icon, accent, sub) in zip(cols, cards):
        with col:
            st.markdown(_stat_card(label, val, icon, accent, sub), unsafe_allow_html=True)

    st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)

    # ── Row 1: Source + Location ────────────────────────────────────────────────
    col_l, col_r = st.columns(2, gap="large")

    with col_l:
        st.markdown(
            '<div style="font-size:14px; font-weight:600; color:#1E293B; margin-bottom:12px;">Leads by Source</div>',
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
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    with col_r:
        st.markdown(
            '<div style="font-size:14px; font-weight:600; color:#1E293B; margin-bottom:12px;">Leads by Location</div>',
            unsafe_allow_html=True,
        )
        LOC_MAP = {
            "United States": "United States", "India": "India",
            "United Kingdom": "United Kingdom", "UAE": "UAE",
            "Remote/Global": "Remote/Global", "Europe": "Europe",
            "Canada": "Canada", "Australia": "Australia",
        }
        def _loc(loc: str) -> str:
            loc = str(loc).strip()
            if loc in LOC_MAP:
                return LOC_MAP[loc]
            lo = loc.lower()
            if "india" in lo: return "India"
            if "united states" in lo or "usa" in lo or "america" in lo: return "United States"
            if "united kingdom" in lo or "uk" in lo or "london" in lo: return "United Kingdom"
            if "uae" in lo or "dubai" in lo: return "UAE"
            return "Other"

        df_loc = df.copy()
        df_loc["country"] = df_loc["location"].apply(_loc)
        loc_counts = df_loc["country"].value_counts().reset_index()
        loc_counts.columns = ["Country", "Count"]
        PALETTE = ["#4F46E5", "#7C3AED", "#2563EB", "#0891B2", "#059669", "#D97706", "#DC2626", "#475569"]
        fig2 = px.bar(
            loc_counts, x="Country", y="Count",
            color="Country",
            color_discrete_sequence=PALETTE,
            text="Count",
        )
        fig2.update_traces(textposition="outside", marker_line_width=0, textfont_size=11)
        fig2.update_layout(**_CHART_LAYOUT)
        st.plotly_chart(fig2, use_container_width=True, config={"displayModeBar": False})

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    # ── Row 2: Score histogram + Funnel ────────────────────────────────────────
    col_l2, col_r2 = st.columns(2, gap="large")

    with col_l2:
        st.markdown(
            '<div style="font-size:14px; font-weight:600; color:#1E293B; margin-bottom:12px;">Quality Score Distribution</div>',
            unsafe_allow_html=True,
        )
        fig3 = px.histogram(df, x="quality_score", nbins=10, color_discrete_sequence=["#6366F1"])
        fig3.add_vline(
            x=70, line_dash="dot", line_color="#F59E0B", line_width=1.5,
            annotation_text="High priority", annotation_font_size=11,
            annotation_font_color="#F59E0B",
        )
        fig3.update_layout(**_CHART_LAYOUT)
        st.plotly_chart(fig3, use_container_width=True, config={"displayModeBar": False})

    with col_r2:
        st.markdown(
            '<div style="font-size:14px; font-weight:600; color:#1E293B; margin-bottom:12px;">Outreach Funnel</div>',
            unsafe_allow_html=True,
        )
        stage_order = [
            "Found", "Verified", "Warming Up", "Request Sent",
            "Connected", "Msg Sent", "Replied", "Interested", "Closed",
        ]
        stage_counts = df["pipeline_stage"].value_counts()
        funnel_df = pd.DataFrame([
            {"Stage": s, "Count": int(stage_counts.get(s, 0))}
            for s in stage_order
        ])
        funnel_df = funnel_df[funnel_df["Count"] > 0]

        if not funnel_df.empty:
            FUNNEL_COLORS = ["#4F46E5", "#6366F1", "#818CF8", "#7C3AED",
                             "#8B5CF6", "#A78BFA", "#C4B5FD", "#DDD6FE", "#EDE9FE"]
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

    # ── Top leads table ─────────────────────────────────────────────────────────
    st.markdown(
        '<div style="font-size:14px; font-weight:600; color:#1E293B; margin-bottom:12px;">Top 10 Leads by ICP Score</div>',
        unsafe_allow_html=True,
    )
    score_col = "icp_score" if "icp_score" in df.columns and df["icp_score"].sum() > 0 else "quality_score"
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
