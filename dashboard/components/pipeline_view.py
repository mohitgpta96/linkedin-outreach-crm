"""
Dashboard Page 2: Pipeline Kanban
9 stages. Each lead is a card. Click to update stage.
"""

import streamlit as st
import pandas as pd

PIPELINE_STAGES = [
    "Found",
    "Verified",
    "Warming Up",
    "Request Sent",
    "Connected",
    "Msg Sent",
    "Replied",
    "Interested",
    "Closed",
]

STAGE_COLORS = {
    "Found":        "#E8F4FD",
    "Verified":     "#D4EDDA",
    "Warming Up":   "#FFF3CD",
    "Request Sent": "#FCE8C3",
    "Connected":    "#F5C6CB",
    "Msg Sent":     "#E2D9F3",
    "Replied":      "#C3E6CB",
    "Interested":   "#B8DAFF",
    "Closed":       "#D4EDDA",
}

TEMP_EMOJI = {"Hot": "🔥", "Warm": "⚡", "Cold": "❄️"}


def _stage_selector(key: str, current: str) -> str:
    idx = PIPELINE_STAGES.index(current) if current in PIPELINE_STAGES else 0
    return st.selectbox(
        "Stage", PIPELINE_STAGES, index=idx, key=key, label_visibility="collapsed"
    )


def render(df: pd.DataFrame) -> None:
    st.title("📋 Pipeline")

    if df.empty:
        st.info("No leads yet. Run the pipeline first.")
        return

    # Filter controls
    with st.expander("Filters", expanded=False):
        filter_temp = st.multiselect(
            "Lead Temperature",
            ["Hot", "Warm", "Cold"],
            default=["Hot", "Warm"],
        )
        filter_score = st.slider("Min Quality Score", 0, 100, 40)
        if filter_temp:
            df = df[df["lead_temperature"].isin(filter_temp)]
        df = df[df["quality_score"] >= filter_score]

    st.markdown("---")
    st.markdown(
        "**Tip:** Click a lead card to view full details. "
        "Use the stage dropdown to move them through the pipeline."
    )

    # Render kanban columns (3 rows × 3 columns per row to fit 9 stages)
    for row_start in range(0, len(PIPELINE_STAGES), 3):
        row_stages = PIPELINE_STAGES[row_start : row_start + 3]
        cols = st.columns(3)

        for col, stage in zip(cols, row_stages):
            stage_leads = df[df["pipeline_stage"] == stage].head(8)
            count = len(df[df["pipeline_stage"] == stage])
            bg = STAGE_COLORS.get(stage, "#F0F0F0")

            with col:
                st.markdown(
                    f"""<div style="background:{bg}; border-radius:8px;
                    padding:8px 12px; margin-bottom:4px;">
                    <strong>{stage}</strong> <span style="color:#666">({count})</span>
                    </div>""",
                    unsafe_allow_html=True,
                )

                if stage_leads.empty:
                    st.markdown(
                        '<div style="color:#aaa; font-size:0.85em; '
                        'padding: 8px 0;">— empty —</div>',
                        unsafe_allow_html=True,
                    )
                    continue

                for _, lead in stage_leads.iterrows():
                    temp = lead.get("lead_temperature", "")
                    emoji = TEMP_EMOJI.get(temp, "")
                    score = lead.get("quality_score", 0)
                    name  = lead.get("name") or "Unknown"
                    title = lead.get("title") or ""
                    company = lead.get("company") or ""

                    with st.container():
                        st.markdown(
                            f"""<div style="border:1px solid #ddd; border-radius:6px;
                            padding:8px 10px; margin-bottom:6px; background:white;
                            font-size:0.88em;">
                            <div><strong>{name}</strong> {emoji}</div>
                            <div style="color:#555">{title}</div>
                            <div style="color:#777">{company}</div>
                            <div style="color:#999; font-size:0.8em;">Score: {score}</div>
                            </div>""",
                            unsafe_allow_html=True,
                        )
                        # Store selected lead in session state for detail view
                        if st.button("View", key=f"view_{lead.name}_{stage}"):
                            st.session_state["selected_lead"] = lead.to_dict()
                            st.session_state["active_page"] = "Lead Detail"
                            pass  # Streamlit reruns automatically on button click

        st.markdown("")  # spacing between rows

    # Show overflow count
    for stage in PIPELINE_STAGES:
        stage_count = len(df[df["pipeline_stage"] == stage])
        if stage_count > 8:
            st.caption(f"  {stage}: showing 8 of {stage_count} leads — use Lead Table for full list")
