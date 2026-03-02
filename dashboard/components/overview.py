"""
Dashboard Page 1: Overview
Stats cards, lead temperature breakdown, source/location charts, funnel.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go


def render(df: pd.DataFrame) -> None:
    st.title("📊 Overview")
    last_updated = df['scraped_at'].dropna().astype(str).max() if not df.empty else 'N/A'
    st.caption(f"Last updated: {last_updated}")

    if df.empty:
        st.info("No leads yet. Run `python main.py` to start scraping.")
        return

    # ── Stat Cards ────────────────────────────────────────────
    total  = len(df)
    hot    = len(df[df["lead_temperature"] == "Hot"])
    warm   = len(df[df["lead_temperature"] == "Warm"])
    cold   = len(df[df["lead_temperature"] == "Cold"])
    verified = len(df[df["verified"].astype(str).str.upper().isin(["YES", "Y", "TRUE"])])

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Total Leads",      total)
    c2.metric("🔥 Hot  (< 7d)",    hot)
    c3.metric("⚡ Warm (< 30d)",    warm)
    c4.metric("❄️ Cold (30d+)",    cold)
    c5.metric("✅ Verified",        verified)

    st.divider()

    # ── Row 1: Source distribution + Location ─────────────────
    col_l, col_r = st.columns(2)

    with col_l:
        st.subheader("Leads by Source")
        source_counts = df["source"].value_counts().reset_index()
        source_counts.columns = ["Source", "Count"]
        fig = px.bar(
            source_counts, x="Source", y="Count",
            color="Count", color_continuous_scale="Blues",
            text="Count",
        )
        fig.update_traces(textposition="outside")
        fig.update_layout(showlegend=False, height=300, margin=dict(t=20, b=20))
        st.plotly_chart(fig, use_container_width=True)

    with col_r:
        st.subheader("Leads by Location")
        # Location is already normalized — map to display name
        LOC_MAP = {
            "United States": "United States", "India": "India",
            "United Kingdom": "United Kingdom", "UAE": "UAE",
            "Remote/Global": "Remote/Global", "Europe": "Europe",
            "Canada": "Canada", "Southeast Asia": "Southeast Asia",
            "Africa": "Africa", "Latin America": "Latin America",
            "East Asia": "East Asia", "Australia": "Australia",
        }
        def extract_country(loc: str) -> str:
            loc = str(loc).strip()
            if loc in LOC_MAP:
                return LOC_MAP[loc]
            # Fallback for any old-format values
            lo = loc.lower()
            if "india" in lo or "south asia" in lo:
                return "India"
            if "united states" in lo or "america" in lo or "usa" in lo:
                return "United States"
            if "united kingdom" in lo or "uk" in lo or "london" in lo:
                return "United Kingdom"
            if "uae" in lo or "emirates" in lo or "dubai" in lo:
                return "UAE"
            if "remote" in lo or "global" in lo:
                return "Remote/Global"
            return "Other"

        df_loc = df.copy()
        df_loc["country"] = df_loc["location"].apply(extract_country)
        loc_counts = df_loc["country"].value_counts().reset_index()
        loc_counts.columns = ["Country", "Count"]
        fig2 = px.bar(
            loc_counts, x="Country", y="Count",
            color="Country",
            color_discrete_sequence=px.colors.qualitative.Set2,
            text="Count",
        )
        fig2.update_traces(textposition="outside")
        fig2.update_layout(showlegend=False, height=300, margin=dict(t=20, b=20))
        st.plotly_chart(fig2, use_container_width=True)

    st.divider()

    # ── Row 2: Quality Score Distribution + Outreach Funnel ───
    col_l2, col_r2 = st.columns(2)

    with col_l2:
        st.subheader("Quality Score Distribution")
        fig3 = px.histogram(
            df, x="quality_score", nbins=10,
            color_discrete_sequence=["#4C72B0"],
        )
        fig3.add_vline(x=70, line_dash="dash", line_color="orange",
                       annotation_text="High priority (70+)")
        fig3.update_layout(height=300, margin=dict(t=20, b=20))
        st.plotly_chart(fig3, use_container_width=True)

    with col_r2:
        st.subheader("Outreach Funnel")
        stage_order = [
            "Found", "Verified", "Warming Up", "Request Sent",
            "Connected", "Msg Sent", "Replied", "Interested", "Closed",
        ]
        stage_counts = df["pipeline_stage"].value_counts()
        funnel_data = [
            {"Stage": s, "Count": int(stage_counts.get(s, 0))}
            for s in stage_order
        ]
        funnel_df = pd.DataFrame(funnel_data)
        funnel_df = funnel_df[funnel_df["Count"] > 0]

        if not funnel_df.empty:
            fig4 = go.Figure(go.Funnel(
                y=funnel_df["Stage"],
                x=funnel_df["Count"],
                textinfo="value+percent initial",
                marker={"color": ["#4C72B0", "#5E8FC0", "#70A4C8",
                                  "#82B9D0", "#94CED8", "#A6E3E0",
                                  "#B8F8E8", "#CAF0D0", "#DCFFB8"]},
            ))
            fig4.update_layout(height=320, margin=dict(t=20, b=10))
            st.plotly_chart(fig4, use_container_width=True)
        else:
            st.info("No pipeline stage data yet.")

    st.divider()

    # ── Row 3: Top Leads Table ─────────────────────────────────
    st.subheader("Top 10 Leads by Quality Score")
    top10 = df.nlargest(10, "quality_score")[
        ["name", "title", "company", "location",
         "quality_score", "lead_temperature", "source", "pipeline_stage"]
    ].reset_index(drop=True)

    def style_temp(val: str) -> str:
        colors = {"Hot": "#FF6B6B", "Warm": "#FFA500", "Cold": "#6699CC"}
        return f"color: {colors.get(val, 'inherit')}; font-weight: bold"

    st.dataframe(
        top10.style.map(style_temp, subset=["lead_temperature"]),
        use_container_width=True,
        height=350,
    )
