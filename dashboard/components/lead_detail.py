"""
Dashboard Page 4: Lead Detail Panel
Everything about a single lead in one screen:
- Signal, profile, company intel, pain points, value prop
- 5 generated messages with copy buttons
- Warm-up activity log with checkboxes
- Free-text notes
"""

import math
import streamlit as st
import pandas as pd


def _s(val) -> str:
    """Return empty string for None, float NaN, or the string 'nan'."""
    if val is None:
        return ""
    if isinstance(val, float) and math.isnan(val):
        return ""
    s = str(val).strip()
    return "" if s.lower() == "nan" else s


PIPELINE_STAGES = [
    "Found", "Verified", "Warming Up", "Request Sent",
    "Connected", "Msg Sent", "Replied", "Interested", "Closed",
]
TEMP_EMOJI = {"Hot": "🔥", "Warm": "⚡", "Cold": "❄️", "Unknown": ""}


def _copy_block(label: str, text: str, key: str) -> None:
    """Display a message with a copy button."""
    st.text_area(label, value=text, height=100, key=key, disabled=False)


def render(df: pd.DataFrame) -> None:
    # Sidebar lead selector
    if df.empty:
        st.info("No leads found. Run the pipeline first.")
        return

    with st.sidebar:
        st.markdown("### Select Lead")
        lead_options = [
            f"{r.get('name','?')} — {r.get('company','?')} ({r.get('quality_score',0)})"
            for _, r in df.head(50).iterrows()
        ]
        lead_idx = st.selectbox("Lead", range(len(lead_options)),
                                format_func=lambda i: lead_options[i],
                                key="lead_detail_idx")

    # Auto-render based on selectbox — no button needed
    lead_idx = st.session_state.get("lead_detail_idx", 0)
    selected = df.iloc[lead_idx].to_dict()

    lead = selected
    name         = _s(lead.get("name")) or "Unknown"
    title        = _s(lead.get("title"))
    company      = _s(lead.get("company"))
    location     = _s(lead.get("location"))
    profile_url  = _s(lead.get("profile_url"))
    website      = _s(lead.get("company_website"))
    score        = lead.get("quality_score", 0)
    temperature  = _s(lead.get("lead_temperature"))
    temp_emoji   = TEMP_EMOJI.get(temperature, "")

    # ── Header ────────────────────────────────────────────────
    st.markdown(f"## {name}")
    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown(f"**{title}** · {company}")
        if location:   st.caption(f"📍 {location}")
        if profile_url: st.markdown(f"[LinkedIn Profile]({profile_url})")
        if website:     st.markdown(f"[Company Website]({website})")
    with col2:
        st.metric("Quality Score", f"{score}/100 {temp_emoji}")

    # ── Pipeline Stage ────────────────────────────────────────
    st.divider()
    col_a, col_b = st.columns(2)
    with col_a:
        current_stage = _s(lead.get("pipeline_stage")) or "Found"
        idx = PIPELINE_STAGES.index(current_stage) if current_stage in PIPELINE_STAGES else 0
        new_stage = st.selectbox("Pipeline Stage", PIPELINE_STAGES, index=idx)
        if new_stage != current_stage:
            st.session_state["selected_lead"]["pipeline_stage"] = new_stage
            # Update in DB if possible
            try:
                from database import update_lead_status
                if profile_url:
                    update_lead_status(profile_url, {"pipeline_stage": new_stage})
                    st.success(f"Stage updated to: {new_stage}")
            except Exception:
                st.caption("(DB update skipped — credentials not configured)")
    with col_b:
        verified = _s(lead.get("verified"))
        new_verified = st.selectbox(
            "Verified?", ["", "Yes", "No", "Maybe"],
            index=["", "Yes", "No", "Maybe"].index(verified) if verified in ["", "Yes", "No", "Maybe"] else 0,
        )
        if new_verified != verified:
            st.session_state["selected_lead"]["verified"] = new_verified

    # ── Why This Lead Was Found ───────────────────────────────
    st.divider()
    st.subheader("🎯 Why This Person Was Found")
    signal_type = _s(lead.get("signal_type"))
    signal_date = _s(lead.get("signal_date"))
    signal_text = _s(lead.get("signal_text"))
    source      = _s(lead.get("source"))

    info_cols = st.columns(3)
    info_cols[0].markdown(f"**Source:** {source}")
    info_cols[1].markdown(f"**Signal:** {signal_type}")
    info_cols[2].markdown(f"**Date:** {signal_date} {temp_emoji}")

    if signal_text:
        st.markdown(f"> *{signal_text[:400]}*")

    # ── LinkedIn Profile ──────────────────────────────────────
    st.divider()
    st.subheader("👤 Their LinkedIn Profile")

    headline = _s(lead.get("headline"))
    about    = _s(lead.get("about_snippet"))
    bg       = _s(lead.get("background_summary"))
    skills   = _s(lead.get("skills"))
    themes   = _s(lead.get("post_themes"))
    tone     = _s(lead.get("post_tone"))
    notable  = _s(lead.get("recent_notable_post"))

    if headline: st.markdown(f"**Headline:** {headline}")
    if about:    st.markdown(f"**About:** {about}")
    if bg:       st.markdown(f"**Background:** {bg}")
    if skills:   st.markdown(f"**Skills:** {skills}")
    if themes:   st.markdown(f"**Post Themes:** {themes}")
    if tone:     st.markdown(f"**Post Tone:** {tone}")
    if notable:
        st.markdown("**Most Relevant Post:**")
        st.info(notable[:300])

    # ── Company Intelligence ──────────────────────────────────
    st.divider()
    st.subheader("🏢 Company Intelligence")

    what     = _s(lead.get("what_they_do"))
    size     = _s(lead.get("company_size"))
    industry = _s(lead.get("industry"))
    growth   = _s(lead.get("growth_signals"))
    roles    = _s(lead.get("careers_page_roles"))
    funding  = _s(lead.get("funding_stage"))
    fund_d   = _s(lead.get("funding_date"))
    fund_a   = _s(lead.get("funding_amount"))

    c1, c2 = st.columns(2)
    with c1:
        if what:     st.markdown(f"**What they do:** {what}")
        if size:     st.markdown(f"**Team size:** {size}")
        if industry: st.markdown(f"**Industry:** {industry}")
    with c2:
        if funding:  st.markdown(f"**Funding:** {funding} {fund_a} ({fund_d})")
        if growth:   st.markdown(f"**Growth signals:** {growth}")
        if roles:    st.markdown(f"**Other open roles:** {roles}")

    # ── Pain Points ───────────────────────────────────────────
    st.divider()
    st.subheader("🔴 Inferred Pain Points")
    pain = _s(lead.get("inferred_pain_points"))
    if pain:
        for point in pain.split(" | "):
            if point.strip():
                st.markdown(f"• {point.strip()}")
    else:
        st.caption("Not yet inferred — run enrichment.")

    # ── Value Prop ────────────────────────────────────────────
    st.subheader("💡 Your Value Proposition (as their PM)")
    value = _s(lead.get("pm_value_prop"))
    if value:
        for prop in value.split(" | "):
            if prop.strip():
                st.markdown(f"✅ {prop.strip()}")
    else:
        st.caption("Not yet generated — run enrichment.")

    # ── Generated Messages ────────────────────────────────────
    st.divider()
    st.subheader("✉️ Generated Outreach Messages")
    st.caption("Expert-optimized: < 75 words · starts with THEM · ends with curiosity question")

    tabs = st.tabs([
        "Connection Note", "First DM (Day 0)",
        "Follow-up 1 (Day 4)", "Follow-up 2 (Day 10)",
        "Follow-up 3 (Day 17)", "Follow-up 4 (Day 25)",
    ])

    messages = [
        _s(lead.get("msg_connection_note")) or "Not yet generated",
        _s(lead.get("msg_first_dm")) or "Not yet generated",
        _s(lead.get("msg_followup_day4")) or "Not yet generated",
        _s(lead.get("msg_followup_day10")) or "Not yet generated",
        _s(lead.get("msg_followup_day17")) or "Not yet generated",
        _s(lead.get("msg_followup_day25")) or "Not yet generated",
    ]
    day_labels = ["Connection request note", "First DM", "Follow-up Day 4",
                  "Follow-up Day 10", "Follow-up Day 17", "Follow-up Day 25"]
    wc_note = lead.get("msg_word_count_note", 0)
    wc_dm   = lead.get("msg_word_count_dm", 0)

    for tab, msg, label, wc in zip(tabs, messages, day_labels, [wc_note, wc_dm, 0, 0, 0, 0]):
        with tab:
            st.text_area(label, value=msg, height=110, key=f"msg_{label}_{name}")
            if wc:
                color = "green" if wc <= 75 else "orange"
                st.caption(f"Word count: :{color}[{wc}] {'✅' if wc <= 75 else '⚠️ trim to < 75'}")
            st.caption("💡 Copy the text above manually.")

    # ── Warm-up Activity Log ──────────────────────────────────
    st.divider()
    st.subheader("📅 Warm-up Activity Log")
    st.caption("Check off steps as you complete them (Vaibhav Sisinty's Ninja Outbound method)")

    warm_steps = [
        "Day 1: Viewed profile + followed company page",
        "Day 2: Liked 1–2 recent posts",
        "Day 3: Left a thoughtful comment on a post",
        "Day 4: Sent connection request with the note above",
        "Day 6–7: They accepted → sent first voice note / DM",
        "Day 10: Sent Follow-up 1",
        "Day 17: Sent Follow-up 2",
        "Day 25: Sent Follow-up 3 (final)",
    ]
    for step in warm_steps:
        st.checkbox(step, key=f"warmup_{step}_{name}")

    # ── Notes ─────────────────────────────────────────────────
    st.divider()
    st.subheader("📝 Your Notes")
    notes = st.text_area(
        "Add anything you noticed or want to remember",
        value=_s(lead.get("notes")),
        height=100,
        key=f"notes_{name}",
    )
    if st.button("Save Notes", key=f"save_notes_{name}"):
        st.session_state["selected_lead"]["notes"] = notes
        try:
            from database import update_lead_status
            if profile_url:
                update_lead_status(profile_url, {"notes": notes})
                st.success("Notes saved!")
            else:
                st.warning("No profile URL — notes saved in session only.")
        except Exception:
            st.caption("(DB not configured — notes in session only)")
