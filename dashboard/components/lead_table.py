"""
Dashboard Page 3: Lead Table
Searchable, filterable, sortable table with all leads.
Click any row to open Lead Detail panel.
"""

import streamlit as st
import pandas as pd


DISPLAY_COLUMNS = [
    "quality_score", "lead_temperature", "name", "title", "company",
    "location", "source", "signal_date", "pipeline_stage",
    "warm_up_status", "verified",
]

TEMP_EMOJI = {"Hot": "🔥 Hot", "Warm": "⚡ Warm", "Cold": "❄️ Cold"}


def render(df: pd.DataFrame) -> None:
    st.title("📋 Lead Table")

    if df.empty:
        st.info("No leads yet. Run `python main.py` to start scraping.")
        return

    # ── Filters ───────────────────────────────────────────────
    with st.expander("🔍 Search & Filters", expanded=True):
        col1, col2 = st.columns([2, 1])
        with col1:
            search = st.text_input("Search name, company, title...", placeholder="e.g. Rahul, Buildfast, CTO")
        with col2:
            sort_by = st.selectbox("Sort by", ["quality_score", "signal_date", "name", "company"], index=0)

        col3, col4, col5, col6 = st.columns(4)
        with col3:
            filter_temp = st.multiselect(
                "Temperature", ["Hot", "Warm", "Cold", "Unknown"],
                default=["Hot", "Warm"],
            )
        with col4:
            all_sources = ["All"] + sorted(df["source"].dropna().unique().tolist())
            filter_source = st.selectbox("Source", all_sources)
        with col5:
            all_stages = ["All"] + sorted(df["pipeline_stage"].dropna().unique().tolist())
            filter_stage = st.selectbox("Pipeline Stage", all_stages)
        with col6:
            min_score = st.slider("Min Score", 0, 100, 0)

    # ── Apply Filters ─────────────────────────────────────────
    filtered = df.copy()

    if search:
        mask = (
            filtered["name"].str.contains(search, case=False, na=False)
            | filtered["company"].str.contains(search, case=False, na=False)
            | filtered["title"].str.contains(search, case=False, na=False)
        )
        filtered = filtered[mask]

    if filter_temp:
        filtered = filtered[filtered["lead_temperature"].isin(filter_temp)]

    if filter_source != "All":
        filtered = filtered[filtered["source"] == filter_source]

    if filter_stage != "All":
        filtered = filtered[filtered["pipeline_stage"] == filter_stage]

    filtered = filtered[filtered["quality_score"] >= min_score]
    filtered = filtered.sort_values(sort_by, ascending=(sort_by == "name"))

    st.caption(f"Showing **{len(filtered)}** of **{len(df)}** leads")

    if filtered.empty:
        st.warning("No leads match the current filters.")
        return

    # ── Render Table ──────────────────────────────────────────
    # Map temperature to emoji labels for display
    display_df = filtered[
        [c for c in DISPLAY_COLUMNS if c in filtered.columns]
    ].copy()

    if "lead_temperature" in display_df.columns:
        display_df["lead_temperature"] = display_df["lead_temperature"].map(
            lambda t: TEMP_EMOJI.get(t, t)
        )

    # Rename columns for readability
    display_df = display_df.rename(columns={
        "quality_score":   "Score",
        "lead_temperature": "Temp",
        "pipeline_stage":  "Stage",
        "warm_up_status":  "Warm-up",
        "signal_date":     "Signal Date",
    })

    # Color-code the Score column
    def color_score(val):
        if isinstance(val, (int, float)):
            if val >= 70:   return "color: #28a745; font-weight: bold"
            if val >= 45:   return "color: #fd7e14"
            return "color: #dc3545"
        return ""

    st.dataframe(
        display_df.style.map(color_score, subset=["Score"]),
        use_container_width=True,
        height=500,
    )

    # ── Row Selection: Open Detail View ───────────────────────
    st.markdown("---")
    st.caption("Click a name below to view full lead details:")

    for i, (_, row) in enumerate(filtered.head(30).iterrows()):
        col_a, col_b = st.columns([6, 1])
        with col_a:
            label = (
                f"{TEMP_EMOJI.get(row.get('lead_temperature_raw', ''), '')} "
                f"**{row.get('name','?')}** — {row.get('title','?')} at {row.get('company','?')} "
                f"(Score: {row.get('quality_score', 0)})"
            )
            st.markdown(label)
        with col_b:
            if st.button("Open", key=f"open_{i}_{row.get('profile_url', i)}"):
                st.session_state["selected_lead"] = row.to_dict()
                st.session_state["active_page"] = "Lead Detail"
                pass  # Streamlit reruns automatically on button click

    if len(filtered) > 30:
        st.caption(f"... and {len(filtered) - 30} more. Use the filters to narrow down.")
