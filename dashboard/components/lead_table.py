"""
All Leads — Premium table with click-to-open lead detail dialog.
Design: Apollo.io / Attio inspired — clean rows, soft shadows, proper hierarchy.
"""
import streamlit as st
import pandas as pd
import math

TEMP_EMOJI  = {"Hot": "🔥", "Warm": "⚡", "Cold": "❄️", "Unknown": ""}
TEMP_BADGE  = {
    "Hot":     ("#FEF2F2", "#EF4444"),
    "Warm":    ("#FFFBEB", "#D97706"),
    "Cold":    ("#EFF6FF", "#3B82F6"),
    "Unknown": ("#F8FAFC", "#94A3B8"),
}
STAGE_BADGE = {
    "Found":         ("#EEF2FF", "#6366F1"),
    "ICP Candidate": ("#FFF7ED", "#F97316"),
    "Enriched":      ("#F5F3FF", "#8B5CF6"),
    "Ready":         ("#F0FDF4", "#22C55E"),
    "Verified":      ("#ECFDF5", "#10B981"),
    "Warming Up":    ("#FFF7ED", "#FB923C"),
    "Request Sent":  ("#F5F3FF", "#7C3AED"),
    "Connected":     ("#ECFEFF", "#06B6D4"),
    "Msg Sent":      ("#EFF6FF", "#3B82F6"),
    "Replied":       ("#F0FDF4", "#16A34A"),
    "Interested":    ("#DCFCE7", "#15803D"),
    "Closed":        ("#FFF1F2", "#F43F5E"),
}
PIPELINE_STAGES = [
    "Found", "ICP Candidate", "Enriched", "Ready",
    "Verified", "Warming Up", "Request Sent",
    "Connected", "Msg Sent", "Replied", "Interested", "Closed",
]


def _s(val) -> str:
    if val is None:
        return ""
    if isinstance(val, float) and math.isnan(val):
        return ""
    s = str(val).strip()
    return "" if s.lower() in ("nan", "none", "") else s


def _badge(text: str, bg: str, fg: str, bold: bool = False) -> str:
    fw = "700" if bold else "500"
    return (
        f'<span style="background:{bg}; color:{fg}; font-size:11px; font-weight:{fw}; '
        f'padding:3px 9px; border-radius:20px; white-space:nowrap;">{text}</span>'
    )


def _score_chip(score: int) -> str:
    if score >= 70:
        bg, fg = "#DCFCE7", "#16A34A"
    elif score >= 40:
        bg, fg = "#FEF9C3", "#CA8A04"
    else:
        bg, fg = "#FEE2E2", "#DC2626"
    return (
        f'<span style="background:{bg}; color:{fg}; font-size:12px; font-weight:700; '
        f'padding:3px 10px; border-radius:20px; font-variant-numeric:tabular-nums;">{score}</span>'
    )


def _update_stage(profile_url: str, stage: str) -> bool:
    try:
        from data_store import update_stage
        update_stage(profile_url, stage)
        st.cache_data.clear()
        return True
    except Exception as e:
        st.error(f"Save failed: {e}")
        return False


# ── Lead Detail Dialog ─────────────────────────────────────────────────────────
@st.dialog("Lead Detail", width="large")
def show_lead_modal(row: dict) -> None:
    """Premium lead detail modal — Apollo.io style."""
    name        = _s(row.get("name") or row.get("founder_name")) or "Unknown"
    title       = _s(row.get("title") or row.get("headline"))
    company     = _s(row.get("company") or row.get("company_name"))
    location    = _s(row.get("location"))
    profile_url = _s(row.get("profile_url") or row.get("linkedin_url"))
    website     = _s(row.get("company_website") or row.get("company_url"))
    score       = int(row.get("quality_score") or row.get("icp_score") or 0)
    icp_score   = int(row.get("icp_score") or 0)
    temp        = _s(row.get("lead_temperature")) or "Unknown"
    stage       = _s(row.get("pipeline_stage")) or "Found"
    source      = _s(row.get("source"))
    industry    = _s(row.get("industry"))
    size        = _s(row.get("company_size") or row.get("employee_count"))
    what        = _s(row.get("what_they_do") or row.get("about") or row.get("about_snippet"))
    pain        = _s(row.get("inferred_pain_points") or row.get("pain_points"))
    signal_text = _s(row.get("signal_text"))
    growth      = _s(row.get("growth_signals"))
    notes_val   = _s(row.get("notes"))
    enrichment  = _s(row.get("enrichment_status"))
    signal_date = _s(row.get("signal_date") or "")

    temp_bg, temp_fg   = TEMP_BADGE.get(temp, ("#F8FAFC", "#94A3B8"))
    stage_bg, stage_fg = STAGE_BADGE.get(stage, ("#F8FAFC", "#64748B"))
    display_score      = icp_score if icp_score > score else score

    # ── Header ──────────────────────────────────────────────────────
    st.markdown(f"""
    <div style="padding:4px 0 16px 0;">
        <div style="font-size:20px; font-weight:700; color:#0F172A; line-height:1.2; margin-bottom:6px;">
            {TEMP_EMOJI.get(temp,'')} {name}
        </div>
        <div style="font-size:13.5px; color:#475569; margin-bottom:12px;">
            {title + ' &nbsp;·&nbsp; ' if title else ''}
            <strong style="color:#1E293B;">{company}</strong>
            {' &nbsp;·&nbsp; 📍 ' + location if location else ''}
        </div>
        <div style="display:flex; gap:6px; flex-wrap:wrap; align-items:center;">
            {_badge(temp.upper(), temp_bg, temp_fg, bold=True)}
            {_score_chip(display_score)}
            {_badge(stage, stage_bg, stage_fg)}
            {_badge(enrichment.upper(), '#F0FDF4', '#16A34A') if enrichment else ''}
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Links
    links = []
    if profile_url and profile_url.startswith("http"):
        links.append(f'<a href="{profile_url}" target="_blank" style="color:#4F46E5; font-size:13px; text-decoration:none; font-weight:500;">🔗 LinkedIn Profile</a>')
    if website and website.startswith("http"):
        links.append(f'<a href="{website}" target="_blank" style="color:#4F46E5; font-size:13px; text-decoration:none; font-weight:500;">🌐 Company Website</a>')
    if links:
        st.markdown("&nbsp;&nbsp;|&nbsp;&nbsp;".join(links), unsafe_allow_html=True)
        st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)

    st.divider()

    # ── Two-column layout ───────────────────────────────────────────
    left, right = st.columns([3, 2], gap="large")

    with left:
        if what:
            st.markdown(
                f'<div style="font-size:13px; font-weight:600; color:#374151; margin-bottom:8px;">📋 Description</div>'
                f'<div style="background:#F8FAFC; border-radius:8px; padding:12px 16px; '
                f'font-size:13px; color:#374151; line-height:1.65; border:1px solid #E2E8F0;">{what}</div>',
                unsafe_allow_html=True,
            )
            st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)

        if pain:
            st.markdown('<div style="font-size:13px; font-weight:600; color:#374151; margin-bottom:8px;">🔴 Pain Points</div>', unsafe_allow_html=True)
            for p in pain.split("|"):
                p = p.strip()
                if p:
                    st.markdown(
                        f'<div style="display:flex; gap:8px; align-items:flex-start; '
                        f'padding:5px 0; font-size:13px; color:#475569; border-bottom:1px solid #F1F5F9;">'
                        f'<span style="color:#EF4444; margin-top:1px;">•</span><span>{p}</span></div>',
                        unsafe_allow_html=True,
                    )
            st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)

        if signal_text or growth:
            st.markdown('<div style="font-size:13px; font-weight:600; color:#374151; margin-bottom:8px;">⚡ Hiring Signal</div>', unsafe_allow_html=True)
            if signal_text:
                st.markdown(
                    f'<div style="background:#FFFBEB; border-left:3px solid #F59E0B; '
                    f'border-radius:0 8px 8px 0; padding:10px 14px; font-size:13px; '
                    f'color:#374151; line-height:1.6;">{signal_text[:350]}</div>',
                    unsafe_allow_html=True,
                )
            if growth:
                st.caption(f"Growth signals: {growth}")

    with right:
        # Right panel — details card
        def _field(label: str, val: str) -> None:
            if val:
                st.markdown(
                    f'<div style="margin-bottom:12px;">'
                    f'<div style="font-size:11px; font-weight:600; color:#94A3B8; '
                    f'letter-spacing:0.08em; text-transform:uppercase; margin-bottom:3px;">{label}</div>'
                    f'<div style="font-size:13px; color:#1E293B;">{val}</div></div>',
                    unsafe_allow_html=True,
                )

        st.markdown(
            '<div style="background:#F8FAFC; border-radius:10px; padding:16px; border:1px solid #E2E8F0;">',
            unsafe_allow_html=True,
        )

        # Stage selector
        st.markdown('<div style="font-size:11px; font-weight:600; color:#94A3B8; letter-spacing:0.08em; text-transform:uppercase; margin-bottom:4px;">PIPELINE STAGE</div>', unsafe_allow_html=True)
        stage_idx = PIPELINE_STAGES.index(stage) if stage in PIPELINE_STAGES else 0
        new_stage = st.selectbox(
            "Stage", PIPELINE_STAGES, index=stage_idx,
            key=f"ms_{profile_url or name}",
            label_visibility="collapsed",
        )
        if new_stage != stage and profile_url:
            if _update_stage(profile_url, new_stage):
                st.success(f"✅ Moved to **{new_stage}**")

        st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
        _field("SOURCE", source)
        _field("LOCATION", location)
        _field("INDUSTRY", industry)
        _field("TEAM SIZE", size)
        _field("SIGNAL DATE", signal_date[:10] if signal_date else "")

        st.markdown('</div>', unsafe_allow_html=True)

        # Notes
        st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
        st.markdown('<div style="font-size:11px; font-weight:600; color:#94A3B8; letter-spacing:0.08em; text-transform:uppercase; margin-bottom:4px;">NOTES</div>', unsafe_allow_html=True)
        notes = st.text_area(
            "Notes", value=notes_val, height=80,
            key=f"mn_{profile_url or name}",
            label_visibility="collapsed",
            placeholder="Add your notes...",
        )
        if st.button("💾  Save Notes", key=f"sn_{profile_url or name}", use_container_width=True):
            if profile_url:
                try:
                    from data_store import upsert_lead
                    upsert_lead({"profile_url": profile_url, "notes": notes})
                    st.success("Saved!")
                except Exception as e:
                    st.error(f"Save failed: {e}")

    st.divider()

    # ── Messages ────────────────────────────────────────────────────
    st.markdown('<div style="font-size:13px; font-weight:600; color:#374151; margin-bottom:4px;">✉️ Outreach Messages</div>', unsafe_allow_html=True)
    st.caption("Expert-optimized · < 75 words · starts with THEM · ends with a curiosity question")

    msg_tabs = st.tabs(["🔗 Connection", "💬 First DM", "📩 Day 7", "📩 Day 14", "📩 Day 21", "📩 Day 28"])
    messages = [
        (_s(row.get("msg_connection_note")), "Connection Note", 300),
        (_s(row.get("msg_first_dm")),        "First DM",        75),
        (_s(row.get("msg_followup_day7")),   "Follow-up Day 7", 75),
        (_s(row.get("msg_followup_day14")),  "Follow-up Day 14",75),
        (_s(row.get("msg_followup_day21")),  "Follow-up Day 21",75),
        (_s(row.get("msg_followup_day28")),  "Follow-up Day 28",75),
    ]
    for tab, (msg, label, lim) in zip(msg_tabs, messages):
        with tab:
            if msg:
                st.text_area(label, value=msg, height=105,
                             key=f"m_{label}_{profile_url or name}",
                             label_visibility="collapsed")
                wc  = len(msg.split())
                ok  = wc <= lim
                col = "#16A34A" if ok else "#DC2626"
                st.markdown(
                    f'<div style="font-size:11.5px; color:{col}; margin-top:2px;">'
                    f'{"✅" if ok else "⚠️"} {wc} words '
                    f'{"· within limit" if ok else f"· trim to <{lim}"}</div>',
                    unsafe_allow_html=True,
                )
            else:
                st.caption("Not generated yet — run enrichment.")


# ── Table render ───────────────────────────────────────────────────────────────
def render(df: pd.DataFrame) -> None:
    if df.empty:
        st.info("No leads yet.")
        return

    df = df[df["pipeline_stage"] != "Scrapped"].copy()

    # ── Page header ────────────────────────────────────────────────
    st.markdown(f"""
    <div style="margin-bottom:20px;">
        <div style="font-size:22px; font-weight:700; color:#0F172A; letter-spacing:-0.02em;">
            All Leads
        </div>
        <div style="font-size:13px; color:#94A3B8; margin-top:4px;">
            {len(df)} leads total &nbsp;·&nbsp; click any row to open detail view
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Filters ────────────────────────────────────────────────────
    fc1, fc2, fc3, fc4, fc5 = st.columns([3, 1.5, 1.5, 1.5, 1.2])
    with fc1:
        search = st.text_input("search", placeholder="🔍  Search name, company, title...",
                                label_visibility="collapsed")
    with fc2:
        all_stages  = ["All stages"]  + sorted(df["pipeline_stage"].dropna().unique().tolist())
        filter_stage = st.selectbox("Stage", all_stages, label_visibility="collapsed")
    with fc3:
        all_sources = ["All sources"] + sorted(df["source"].dropna().unique().tolist())
        filter_src  = st.selectbox("Source", all_sources, label_visibility="collapsed")
    with fc4:
        all_temps   = ["All temps"]   + sorted(df["lead_temperature"].dropna().unique().tolist())
        filter_temp = st.selectbox("Temp", all_temps, label_visibility="collapsed")
    with fc5:
        min_score = st.number_input("Min", 0, 100, 0, step=10, label_visibility="collapsed")

    # ── Apply filters ──────────────────────────────────────────────
    fdf = df.copy()
    if search:
        m = (
            fdf["name"].str.contains(search, case=False, na=False)
            | fdf["company"].str.contains(search, case=False, na=False)
            | fdf["title"].str.contains(search, case=False, na=False)
        )
        fdf = fdf[m]
    if filter_stage != "All stages":
        fdf = fdf[fdf["pipeline_stage"] == filter_stage]
    if filter_src != "All sources":
        fdf = fdf[fdf["source"] == filter_src]
    if filter_temp != "All temps":
        fdf = fdf[fdf["lead_temperature"] == filter_temp]

    score_col = "icp_score" if "icp_score" in fdf.columns and fdf["icp_score"].sum() > 0 else "quality_score"
    fdf = fdf[fdf[score_col] >= min_score]
    fdf = fdf.sort_values(score_col, ascending=False).reset_index(drop=True)

    # ── Pagination ─────────────────────────────────────────────────
    PAGE_SIZE   = 50
    total_pages = max(1, (len(fdf) - 1) // PAGE_SIZE + 1)
    if "lt_page" not in st.session_state:
        st.session_state["lt_page"] = 1
    st.session_state["lt_page"] = max(1, min(st.session_state["lt_page"], total_pages))
    page_num  = st.session_state["lt_page"]
    start_idx = (page_num - 1) * PAGE_SIZE
    page_df   = fdf.iloc[start_idx: start_idx + PAGE_SIZE]

    # ── Results summary ────────────────────────────────────────────
    st.markdown(
        f'<div style="font-size:12.5px; color:#64748B; margin-bottom:10px; font-weight:500;">'
        f'{len(fdf):,} leads &nbsp;·&nbsp; page {page_num} of {total_pages}</div>',
        unsafe_allow_html=True,
    )

    # ── Table header ───────────────────────────────────────────────
    st.markdown("""
    <div style="display:grid;
                grid-template-columns:36px 24px 200px 1fr 120px 100px 120px 80px;
                gap:0; padding:10px 12px;
                background:#F8FAFC; border:1px solid #E2E8F0;
                border-radius:10px 10px 0 0;
                font-size:11px; font-weight:700; color:#94A3B8;
                letter-spacing:0.07em; text-transform:uppercase;">
        <div>#</div><div></div><div>Name</div><div>Title · Company</div>
        <div>Location</div><div>Source</div><div>Stage</div><div style="text-align:right;">Score</div>
    </div>
    """, unsafe_allow_html=True)

    # ── Rows ───────────────────────────────────────────────────────
    for i, (_, row) in enumerate(page_df.iterrows(), start=start_idx + 1):
        temp     = _s(row.get("lead_temperature"))
        name     = _s(row.get("name")) or "—"
        title    = _s(row.get("title")) or ""
        company  = _s(row.get("company")) or "—"
        location = _s(row.get("location")) or "—"
        source   = _s(row.get("source")) or "—"
        stage    = _s(row.get("pipeline_stage")) or "Found"
        s_score  = int(row.get(score_col) or 0)
        purl     = _s(row.get("profile_url") or "")

        temp_emoji = TEMP_EMOJI.get(temp, "")
        sbg, sfg   = STAGE_BADGE.get(stage, ("#F8FAFC", "#64748B"))

        # Row border style
        row_bg = "background:#FFFFFF;"

        cs = st.columns([0.32, 0.22, 1.9, 3.8, 1.15, 0.9, 1.1, 0.75])
        with cs[0]:
            st.markdown(f'<div style="padding:13px 4px 13px 4px; font-size:12px; color:#CBD5E1; {row_bg}">{i}</div>', unsafe_allow_html=True)
        with cs[1]:
            st.markdown(f'<div style="padding:13px 0; font-size:14px; {row_bg}">{temp_emoji}</div>', unsafe_allow_html=True)
        with cs[2]:
            st.markdown(
                f'<div style="padding:11px 0; font-weight:600; font-size:13px; '
                f'color:#0F172A; {row_bg} white-space:nowrap; overflow:hidden; '
                f'text-overflow:ellipsis;">{name}</div>',
                unsafe_allow_html=True,
            )
        with cs[3]:
            st.markdown(
                f'<div style="padding:8px 0; font-size:12.5px; {row_bg}">'
                f'<div style="color:#374151; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">{title}</div>'
                f'<div style="color:#94A3B8; font-size:12px; margin-top:1px;">{company}</div></div>',
                unsafe_allow_html=True,
            )
        with cs[4]:
            st.markdown(f'<div style="padding:13px 0; font-size:12px; color:#64748B; {row_bg}">{location[:18]}</div>', unsafe_allow_html=True)
        with cs[5]:
            st.markdown(f'<div style="padding:13px 0; font-size:12px; color:#94A3B8; {row_bg}">{source[:14]}</div>', unsafe_allow_html=True)
        with cs[6]:
            st.markdown(
                f'<div style="padding:10px 0; {row_bg}">'
                f'{_badge(stage, sbg, sfg)}</div>',
                unsafe_allow_html=True,
            )
        with cs[7]:
            if st.button(
                f"{s_score}",
                key=f"open_{i}_{purl or name}",
                use_container_width=True,
                help=f"Open detail: {name}",
            ):
                show_lead_modal(row.to_dict())

        # Row divider
        st.markdown(
            '<div style="height:1px; background:#F1F5F9; margin:0;"></div>',
            unsafe_allow_html=True,
        )

    # ── Footer ─────────────────────────────────────────────────────
    st.markdown(
        f'<div style="padding:10px 12px; background:#F8FAFC; border:1px solid #E2E8F0; '
        f'border-top:none; border-radius:0 0 10px 10px; font-size:12px; color:#94A3B8;">'
        f'Showing {start_idx + 1}–{min(start_idx + PAGE_SIZE, len(fdf))} of {len(fdf):,} leads</div>',
        unsafe_allow_html=True,
    )

    # ── Pagination controls ────────────────────────────────────────
    if total_pages > 1:
        st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
        pc1, pc2, pc3 = st.columns([1, 2, 1])
        with pc1:
            if st.button("← Previous", disabled=(page_num <= 1), use_container_width=True):
                st.session_state["lt_page"] = page_num - 1
                st.rerun()
        with pc2:
            st.markdown(
                f'<div style="text-align:center; padding:8px; font-size:13px; color:#64748B; font-weight:500;">'
                f'Page {page_num} / {total_pages}</div>',
                unsafe_allow_html=True,
            )
        with pc3:
            if st.button("Next →", disabled=(page_num >= total_pages), use_container_width=True):
                st.session_state["lt_page"] = page_num + 1
                st.rerun()
