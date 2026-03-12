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

# Part 2 — Lead lifecycle stage colors
LEAD_STAGE_STYLE: dict[str, tuple[str, str]] = {
    "new":            ("#F1F5F9", "#64748B"),
    "qualified":      ("#EFF6FF", "#3B82F6"),
    "enriched":       ("#F5F3FF", "#8B5CF6"),
    "personalized":   ("#FFF7ED", "#F97316"),
    "message_ready":  ("#F0FDF4", "#22C55E"),
    "contacted":      ("#FEFCE8", "#CA8A04"),
    "replied":        ("#ECFEFF", "#0891B2"),
    "meeting_booked": ("#DCFCE7", "#16A34A"),
    "closed":         ("#FEF2F2", "#EF4444"),
    "skipped":        ("#F9FAFB", "#9CA3AF"),
}
LEAD_STAGE_ICONS = {
    "new": "○", "qualified": "◔", "enriched": "◑", "personalized": "◕",
    "message_ready": "●", "contacted": "📤", "replied": "💬",
    "meeting_booked": "📅", "closed": "✓", "skipped": "×",
}
LEAD_STAGE_PROGRESS = [
    "new", "qualified", "enriched", "personalized",
    "message_ready", "contacted", "replied", "meeting_booked",
]


def _lead_stage_badge(stage: str) -> str:
    bg, fg = LEAD_STAGE_STYLE.get(stage, ("#F1F5F9", "#64748B"))
    icon   = LEAD_STAGE_ICONS.get(stage, "•")
    label  = stage.replace("_", " ").title()
    return (
        f'<span style="background:{bg}; color:{fg}; font-size:10.5px; font-weight:600; '
        f'padding:2px 8px; border-radius:20px; white-space:nowrap;">'
        f'{icon} {label}</span>'
    )


def _mini_progress(stage: str) -> str:
    """Compact 8-step dot progress bar."""
    try:
        idx = LEAD_STAGE_PROGRESS.index(stage)
    except ValueError:
        idx = -1
    dots = ""
    for i, s in enumerate(LEAD_STAGE_PROGRESS):
        bg, fg = LEAD_STAGE_STYLE.get(s, ("#E2E8F0", "#94A3B8"))
        if i <= idx:
            color = fg
        else:
            color = "#E2E8F0"
        dots += f'<span style="display:inline-block; width:7px; height:7px; border-radius:50%; background:{color}; margin:0 1px;"></span>'
    return f'<div style="line-height:1; padding:3px 0;">{dots}</div>'
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
    pm_gap      = row.get("pm_gap_signal") in (True, "True", "true", 1, "1")

    temp_bg, temp_fg   = TEMP_BADGE.get(temp, ("#F8FAFC", "#94A3B8"))
    stage_bg, stage_fg = STAGE_BADGE.get(stage, ("#F8FAFC", "#64748B"))
    display_score      = icp_score if icp_score > score else score

    pm_gap_badge = _badge("⚡ PM GAP", "#FFF7ED", "#EA580C", bold=True) if pm_gap else ""

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
            {pm_gap_badge}
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

    # ── Active filter breadcrumb ────────────────────────────────────
    from dashboard.utils.filter_engine import get_active_filter, apply_filter, clear_filter
    active_filter, active_label = get_active_filter()

    if active_filter and active_filter != "all":
        df_filtered = apply_filter(df)
        # Breadcrumb + clear
        bc1, bc2 = st.columns([5, 1])
        with bc1:
            st.markdown(
                f'<div style="display:flex; align-items:center; gap:8px; margin-bottom:8px;">'
                f'<span style="font-size:13px; color:#94A3B8;">Dashboard</span>'
                f'<span style="color:#CBD5E1;">›</span>'
                f'<span style="font-size:13px; font-weight:600; color:#4338CA;">{active_label}</span>'
                f'<span style="background:#EEF2FF; color:#6366F1; font-size:11px; font-weight:600; '
                f'padding:2px 8px; border-radius:10px; margin-left:4px;">{len(df_filtered):,} leads</span>'
                f'</div>',
                unsafe_allow_html=True,
            )
        with bc2:
            if st.button("✕ Clear filter", key="lt_clear_filter", use_container_width=True):
                clear_filter()
                st.rerun()
    else:
        df_filtered = df

    # ── Page header ────────────────────────────────────────────────
    st.markdown(f"""
    <div style="margin-bottom:20px;">
        <div style="font-size:22px; font-weight:700; color:#0F172A; letter-spacing:-0.02em;">
            All Leads
        </div>
        <div style="font-size:13px; color:#94A3B8; margin-top:4px;">
            {len(df_filtered):,} leads &nbsp;·&nbsp; click any row to open detail view
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Ensure computed columns
    df = df.copy()
    # Ensure computed columns exist on the base df (used for filter dropdowns)
    if "priority_score" not in df.columns or pd.to_numeric(df["priority_score"], errors="coerce").fillna(0).sum() == 0:
        try:
            from data_store import compute_priority_score
            df["priority_score"] = df.apply(lambda r: compute_priority_score(r.to_dict()), axis=1)
        except Exception:
            df["priority_score"] = 0
    else:
        df["priority_score"] = pd.to_numeric(df["priority_score"], errors="coerce").fillna(0).astype(int)

    if "status" not in df.columns:
        df["status"] = "new"

    # Part 1: compute lead_stage on base df
    try:
        from data_store import compute_lead_stage, LEAD_STAGES
        if "lead_stage" not in df.columns or not df["lead_stage"].isin(LEAD_STAGES).any():
            df["lead_stage"] = df.apply(lambda r: compute_lead_stage(r.to_dict()), axis=1)
        else:
            mask = ~df["lead_stage"].isin(LEAD_STAGES)
            if mask.any():
                df.loc[mask, "lead_stage"] = df[mask].apply(lambda r: compute_lead_stage(r.to_dict()), axis=1)
    except Exception:
        if "lead_stage" not in df.columns:
            df["lead_stage"] = "new"

    # Propagate computed columns into df_filtered
    for _col in ("priority_score", "status", "lead_stage"):
        if _col in df.columns and _col not in df_filtered.columns:
            df_filtered = df_filtered.copy()
            df_filtered[_col] = df[_col].reindex(df_filtered.index)
        elif _col in df.columns:
            df_filtered = df_filtered.copy()
            df_filtered[_col] = df[_col].reindex(df_filtered.index).combine_first(df_filtered[_col])

    # ── Filters Row 1 ──────────────────────────────────────────────
    fc1, fc2, fc3, fc4, fc5 = st.columns([3, 1.5, 1.5, 1.5, 1.2])
    with fc1:
        search = st.text_input("search", placeholder="🔍  Search name, company, title...",
                                label_visibility="collapsed")
    with fc2:
        # Part 6: lead_stage filter (primary)
        ls_opts = ["All stages"] + list(LEAD_STAGE_STYLE.keys())
        filter_lead_stage = st.selectbox("Lead Stage", ls_opts, label_visibility="collapsed", key="lt_lead_stage")
    with fc3:
        all_sources = ["All sources"] + sorted(df["source"].dropna().unique().tolist())
        filter_src  = st.selectbox("Source", all_sources, label_visibility="collapsed")
    with fc4:
        # Part 6: persona filter
        persona_col = next((c for c in ["persona", "persona_match", "icp_signal_type"] if c in df.columns), None)
        if persona_col:
            persona_opts = ["All personas"] + sorted(df[persona_col].dropna().unique().tolist())
            filter_persona = st.selectbox("Persona", persona_opts, label_visibility="collapsed", key="lt_persona")
        else:
            filter_persona = "All personas"
            st.caption("")
    with fc5:
        min_score = st.number_input("Min ICP", 0, 100, 0, step=10, label_visibility="collapsed")

    # ── Filters Row 2 ──────────────────────────────────────────────
    fr1, fr2, fr3, fr4 = st.columns([1.5, 1.5, 1.5, 1.5])
    with fr1:
        # Part 6: industry filter
        ind_col = next((c for c in ["industry", "company_industry"] if c in df.columns), None)
        if ind_col:
            ind_opts = ["All industries"] + sorted(df[ind_col].dropna().unique().tolist())
            filter_industry = st.selectbox("Industry", ind_opts, label_visibility="collapsed", key="lt_industry")
        else:
            filter_industry = "All industries"
            st.caption("")
    with fr2:
        if "run_id" in df.columns and df["run_id"].notna().any():
            run_opts = ["All runs"] + sorted(df["run_id"].dropna().unique().tolist())
            filter_run = st.selectbox("Pipeline Run", run_opts, label_visibility="collapsed", key="lt_run_filter")
        else:
            filter_run = "All runs"
            st.caption("")
    with fr3:
        min_priority = st.number_input("Min Priority", 0, 100, 0, step=10, label_visibility="collapsed", key="lt_min_priority")
    with fr4:
        all_temps   = ["All temps"] + sorted(df["lead_temperature"].dropna().unique().tolist())
        filter_temp = st.selectbox("Temp", all_temps, label_visibility="collapsed")

    # ── Apply manual filters on top of any active dashboard filter ──
    fdf = df_filtered.copy()
    if search:
        m = (
            fdf["name"].str.contains(search, case=False, na=False)
            | fdf["company"].str.contains(search, case=False, na=False)
            | fdf["title"].str.contains(search, case=False, na=False)
        )
        fdf = fdf[m]
    if filter_lead_stage != "All stages":
        fdf = fdf[fdf["lead_stage"] == filter_lead_stage]
    if filter_src != "All sources":
        fdf = fdf[fdf["source"] == filter_src]
    if filter_temp != "All temps":
        fdf = fdf[fdf["lead_temperature"] == filter_temp]
    if filter_persona != "All personas" and persona_col:
        fdf = fdf[fdf[persona_col] == filter_persona]
    if filter_industry != "All industries" and ind_col:
        fdf = fdf[fdf[ind_col] == filter_industry]
    if filter_run != "All runs" and "run_id" in fdf.columns:
        fdf = fdf[fdf["run_id"] == filter_run]

    score_col = "icp_score" if "icp_score" in fdf.columns and fdf["icp_score"].sum() > 0 else "quality_score"
    fdf = fdf[fdf[score_col] >= min_score]
    if min_priority > 0:
        fdf = fdf[fdf["priority_score"] >= min_priority]
    fdf = fdf.sort_values("priority_score", ascending=False).reset_index(drop=True)

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
                grid-template-columns:28px 18px 165px 1fr 150px 90px 68px 68px;
                gap:0; padding:10px 12px;
                background:#F8FAFC; border:1px solid #E2E8F0;
                border-radius:10px 10px 0 0;
                font-size:10.5px; font-weight:700; color:#94A3B8;
                letter-spacing:0.07em; text-transform:uppercase;">
        <div>#</div><div></div><div>Name</div><div>Title · Company</div>
        <div>Lead Stage + Progress</div><div>Location</div>
        <div style="text-align:right;">ICP</div><div style="text-align:right;">Priority</div>
    </div>
    """, unsafe_allow_html=True)

    # ── Rows ───────────────────────────────────────────────────────
    for i, (_, row) in enumerate(page_df.iterrows(), start=start_idx + 1):
        temp       = _s(row.get("lead_temperature"))
        name       = _s(row.get("name")) or "—"
        title      = _s(row.get("title")) or ""
        company    = _s(row.get("company")) or "—"
        location   = _s(row.get("location")) or "—"
        lead_stage = _s(row.get("lead_stage")) or "new"
        s_score    = int(row.get(score_col) or 0)
        priority   = int(row.get("priority_score") or 0)
        purl       = _s(row.get("profile_url") or "")

        temp_emoji = TEMP_EMOJI.get(temp, "")
        row_bg     = "background:#FFFFFF;"
        pm_gap     = row.get("pm_gap_signal") in (True, "True", "true", 1, "1")
        pm_gap_dot = '<span title="PM Gap — hiring engineers, no PM yet" style="display:inline-block; width:7px; height:7px; background:#EA580C; border-radius:50%; margin-left:5px; vertical-align:middle;"></span>' if pm_gap else ""

        cs = st.columns([0.24, 0.16, 1.5, 3.2, 1.4, 0.8, 0.58, 0.58])
        with cs[0]:
            st.markdown(f'<div style="padding:13px 4px; font-size:12px; color:#CBD5E1; {row_bg}">{i}</div>', unsafe_allow_html=True)
        with cs[1]:
            st.markdown(f'<div style="padding:13px 0; font-size:14px; {row_bg}">{temp_emoji}</div>', unsafe_allow_html=True)
        with cs[2]:
            st.markdown(
                f'<div style="padding:11px 0; font-weight:600; font-size:13px; '
                f'color:#0F172A; {row_bg} white-space:nowrap; overflow:hidden; '
                f'text-overflow:ellipsis;">{name}{pm_gap_dot}</div>',
                unsafe_allow_html=True,
            )
        with cs[3]:
            pm_gap_badge = '&nbsp;<span style="font-size:10px;background:#FFF7ED;color:#EA580C;padding:1px 5px;border-radius:6px;font-weight:600;">⚡PM</span>' if pm_gap else ""
            st.markdown(
                f'<div style="padding:8px 0; font-size:12.5px; {row_bg}">'
                f'<div style="color:#374151; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">{title}</div>'
                f'<div style="color:#94A3B8; font-size:12px; margin-top:1px;">{company}{pm_gap_badge}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
        with cs[4]:
            # Part 2: lead_stage badge + Part 8: progress bar
            st.markdown(
                f'<div style="padding:8px 0; {row_bg}">'
                f'{_lead_stage_badge(lead_stage)}'
                f'<div style="margin-top:5px;">{_mini_progress(lead_stage)}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
        with cs[5]:
            st.markdown(f'<div style="padding:13px 0; font-size:11.5px; color:#64748B; {row_bg}">{location[:16]}</div>', unsafe_allow_html=True)
        with cs[6]:
            st.markdown(
                f'<div style="padding:12px 2px; text-align:right; font-size:12px; font-weight:600; color:#6366F1;">{s_score}</div>',
                unsafe_allow_html=True,
            )
        with cs[7]:
            if st.button(
                f"{priority}",
                key=f"open_{i}_{purl or name}",
                use_container_width=True,
                help=f"Priority: {priority} · Click to open detail",
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
