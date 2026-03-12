"""
Pipeline — Premium Kanban Board.
Design: Clean white cards with colored left borders, soft shadows, hover elevation.
"""
import streamlit as st
import pandas as pd
from dashboard.components.lead_table import show_lead_modal

PIPELINE_STAGES = [
    "Found", "ICP Candidate", "Enriched", "Ready",
    "Verified", "Warming Up", "Request Sent",
    "Connected", "Msg Sent", "Replied", "Interested", "Closed",
]

# Each stage: (header_bg, accent_color, dot_color)
STAGE_STYLE = {
    "Found":         ("#EEF2FF", "#6366F1", "#6366F1"),
    "ICP Candidate": ("#FFF7ED", "#F97316", "#F97316"),
    "Enriched":      ("#F5F3FF", "#8B5CF6", "#8B5CF6"),
    "Ready":         ("#F0FDF4", "#22C55E", "#22C55E"),
    "Verified":      ("#ECFDF5", "#10B981", "#10B981"),
    "Warming Up":    ("#FFF7ED", "#FB923C", "#FB923C"),
    "Request Sent":  ("#F5F3FF", "#7C3AED", "#7C3AED"),
    "Connected":     ("#ECFEFF", "#06B6D4", "#06B6D4"),
    "Msg Sent":      ("#EFF6FF", "#3B82F6", "#3B82F6"),
    "Replied":       ("#F0FDF4", "#16A34A", "#16A34A"),
    "Interested":    ("#DCFCE7", "#15803D", "#15803D"),
    "Closed":        ("#FFF1F2", "#F43F5E", "#F43F5E"),
}

TEMP_EMOJI = {"Hot": "🔥", "Warm": "⚡", "Cold": "❄️"}
SCORE_COLOR = {
    "high":   ("#DCFCE7", "#16A34A"),  # green
    "medium": ("#FEF9C3", "#CA8A04"),  # yellow
    "low":    ("#FEE2E2", "#DC2626"),  # red
}


def _score_badge(score: int) -> str:
    if score >= 70:
        bg, fg = SCORE_COLOR["high"]
    elif score >= 40:
        bg, fg = SCORE_COLOR["medium"]
    else:
        bg, fg = SCORE_COLOR["low"]
    return (
        f'<span style="background:{bg}; color:{fg}; font-size:11px; font-weight:700; '
        f'padding:2px 8px; border-radius:20px; letter-spacing:0.02em;">{score}</span>'
    )


def render(df: pd.DataFrame) -> None:
    if df.empty:
        st.info("No leads yet.")
        return

    # ── Page header ────────────────────────────────────────────────────────────
    stage_counts = df["pipeline_stage"].value_counts()
    in_progress  = int(df["pipeline_stage"].isin(
        ["Warming Up", "Request Sent", "Connected", "Msg Sent"]
    ).sum())

    st.markdown(f"""
    <div style="margin-bottom:24px;">
        <div style="font-size:22px; font-weight:700; color:#0F172A; letter-spacing:-0.02em;">
            Pipeline Board
        </div>
        <div style="font-size:13px; color:#94A3B8; margin-top:4px;">
            {len(df)} leads across {len(PIPELINE_STAGES)} stages
            &nbsp;·&nbsp; {in_progress} active outreach
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Filters ────────────────────────────────────────────────────────────────
    fc1, fc2, _ = st.columns([2, 1.5, 5])
    with fc1:
        filter_stage = st.multiselect(
            "Filter stages", PIPELINE_STAGES,
            default=[], placeholder="All stages",
            label_visibility="collapsed",
        )
    with fc2:
        min_score = st.number_input(
            "Min score", 0, 100, 0, step=10, label_visibility="collapsed",
        )

    filtered = df.copy()
    if filter_stage:
        filtered = filtered[filtered["pipeline_stage"].isin(filter_stage)]
    if min_score > 0:
        filtered = filtered[filtered["quality_score"] >= min_score]

    display_stages = filter_stage if filter_stage else PIPELINE_STAGES

    # ── Kanban grid — 4 columns per row ────────────────────────────────────────
    COLS_PER_ROW = 4
    for row_start in range(0, len(display_stages), COLS_PER_ROW):
        row_stages = display_stages[row_start: row_start + COLS_PER_ROW]
        cols = st.columns(COLS_PER_ROW, gap="small")

        for col, stage in zip(cols, row_stages):
            bg, accent, dot = STAGE_STYLE.get(stage, ("#F8FAFC", "#64748B", "#94A3B8"))
            stage_leads = filtered[filtered["pipeline_stage"] == stage].head(8)
            count = int((filtered["pipeline_stage"] == stage).sum())

            with col:
                # Column header
                st.markdown(f"""
                <div style="background:{bg}; border-radius:10px 10px 0 0;
                            border:1px solid {accent}30; border-bottom:none;
                            padding:10px 12px; margin-bottom:0;">
                    <div style="display:flex; align-items:center; justify-content:space-between;">
                        <span style="font-size:11.5px; font-weight:700; color:{accent};
                                     letter-spacing:0.06em; text-transform:uppercase;">
                            {stage}
                        </span>
                        <span style="background:{accent}20; color:{accent}; font-size:11px;
                                     font-weight:700; padding:2px 8px; border-radius:20px;">
                            {count}
                        </span>
                    </div>
                </div>
                <div style="background:#F8FAFC; border:1px solid {accent}20;
                            border-top:2px solid {accent}; border-radius:0 0 10px 10px;
                            min-height:60px; padding:8px 8px 6px 8px;">
                """, unsafe_allow_html=True)

                if stage_leads.empty:
                    st.markdown(
                        '<div style="text-align:center; padding:20px 8px; '
                        'color:#CBD5E1; font-size:12px;">No leads</div>',
                        unsafe_allow_html=True,
                    )
                else:
                    for _, lead in stage_leads.iterrows():
                        score   = int(lead.get("quality_score") or lead.get("icp_score") or 0)
                        name    = str(lead.get("name") or "Unknown")
                        title   = str(lead.get("title") or "")
                        company = str(lead.get("company") or "")
                        source  = str(lead.get("source") or "")
                        temp    = str(lead.get("lead_temperature") or "")
                        emoji   = TEMP_EMOJI.get(temp, "")
                        purl    = str(lead.get("profile_url") or lead.name)

                        # Card
                        st.markdown(f"""
                        <div style="background:#FFFFFF; border-radius:8px;
                                    border:1px solid #E2E8F0; padding:10px 12px;
                                    margin-bottom:6px;
                                    box-shadow:0 1px 3px rgba(0,0,0,0.06);
                                    border-left:3px solid {accent};">
                            <div style="font-weight:600; font-size:13px; color:#0F172A;
                                        margin-bottom:3px; white-space:nowrap;
                                        overflow:hidden; text-overflow:ellipsis;">
                                {emoji} {name}
                            </div>
                            <div style="font-size:11.5px; color:#475569; margin-bottom:1px;
                                        white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">
                                {title[:32] if title else "—"}
                            </div>
                            <div style="font-size:11px; color:#94A3B8; margin-bottom:7px;">
                                {company}
                            </div>
                            <div style="display:flex; align-items:center; justify-content:space-between;">
                                {_score_badge(score)}
                                <span style="font-size:10.5px; color:#CBD5E1;">{source[:12]}</span>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)

                        if st.button(
                            f"View →  {name[:18]}",
                            key=f"k_{purl}_{stage}",
                            use_container_width=True,
                            help=f"Open: {name}",
                        ):
                            show_lead_modal(lead.to_dict())

                st.markdown("</div>", unsafe_allow_html=True)

        if row_start + COLS_PER_ROW < len(display_stages):
            st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
