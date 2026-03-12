"""
Action Center — Lead Lifecycle Command Dashboard.
Parts 3, 4, 5, 7, 8 of the Lead Lifecycle Status System.

Single page that instantly answers:
  • Which leads are ready to contact now?
  • Which are waiting for reply?
  • What's the pipeline health?
  • What to work on today?
"""
from __future__ import annotations

import math
import pandas as pd
import streamlit as st

# ── Stage config ─────────────────────────────────────────────────────────────

STAGE_STYLE: dict[str, tuple[str, str, str]] = {
    # key: (bg, fg, label)
    "new":            ("#F1F5F9", "#64748B", "New"),
    "qualified":      ("#EFF6FF", "#3B82F6", "Qualified"),
    "enriched":       ("#F5F3FF", "#8B5CF6", "Enriched"),
    "personalized":   ("#FFF7ED", "#F97316", "Personalized"),
    "message_ready":  ("#F0FDF4", "#22C55E", "Message Ready"),
    "contacted":      ("#FEFCE8", "#CA8A04", "Contacted"),
    "replied":        ("#ECFEFF", "#0891B2", "Replied"),
    "meeting_booked": ("#DCFCE7", "#16A34A", "Meeting Booked"),
    "closed":         ("#FEF2F2", "#EF4444", "Closed"),
    "skipped":        ("#F9FAFB", "#9CA3AF", "Skipped"),
}

STAGE_PROGRESS = [
    "new", "qualified", "enriched", "personalized",
    "message_ready", "contacted", "replied", "meeting_booked",
]

STAGE_ICONS = {
    "new": "○", "qualified": "◔", "enriched": "◑",
    "personalized": "◕", "message_ready": "●",
    "contacted": "📤", "replied": "💬", "meeting_booked": "📅",
    "closed": "✓", "skipped": "×",
}


def _s(val) -> str:
    if val is None:
        return ""
    if isinstance(val, float) and math.isnan(val):
        return ""
    s = str(val).strip()
    return "" if s.lower() in ("nan", "none", "") else s


def _stage_badge(stage: str, size: int = 11) -> str:
    bg, fg, label = STAGE_STYLE.get(stage, ("#F1F5F9", "#64748B", stage.replace("_", " ").title()))
    return (
        f'<span style="background:{bg}; color:{fg}; font-size:{size}px; font-weight:600; '
        f'padding:2px 9px; border-radius:20px; white-space:nowrap;">'
        f'{STAGE_ICONS.get(stage, "•")} {label}</span>'
    )


def _priority_chip(score: int) -> str:
    if score >= 80:
        bg, fg = "#DCFCE7", "#15803D"
    elif score >= 60:
        bg, fg = "#FFF7ED", "#D97706"
    elif score >= 40:
        bg, fg = "#EFF6FF", "#3B82F6"
    else:
        bg, fg = "#F1F5F9", "#64748B"
    return (
        f'<span style="background:{bg}; color:{fg}; font-size:13px; font-weight:700; '
        f'padding:3px 10px; border-radius:20px;">{score}</span>'
    )


def _progress_bar(stage: str) -> str:
    """Part 8 — 8-step progress bar for the pipeline."""
    try:
        current_idx = STAGE_PROGRESS.index(stage)
    except ValueError:
        current_idx = -1

    steps_html = ""
    for i, s in enumerate(STAGE_PROGRESS):
        bg, fg, label = STAGE_STYLE.get(s, ("#E2E8F0", "#94A3B8", s))
        if i < current_idx:
            # completed
            fill = fg
            dot_color = "white"
        elif i == current_idx:
            # active
            fill = fg
            dot_color = "white"
        else:
            # future
            fill = "#E2E8F0"
            dot_color = "#CBD5E1"

        connector = ""
        if i < len(STAGE_PROGRESS) - 1:
            conn_bg = fg if i < current_idx else "#E2E8F0"
            connector = f'<div style="flex:1; height:2px; background:{conn_bg}; margin:0 2px; align-self:center;"></div>'

        tooltip = label
        dot = (
            f'<div style="display:flex; flex-direction:column; align-items:center; gap:3px;">'
            f'<div title="{tooltip}" style="width:16px; height:16px; border-radius:50%; '
            f'background:{fill}; border:2px solid {fill}; '
            f'display:flex; align-items:center; justify-content:center; flex-shrink:0;">'
            f'<div style="width:5px; height:5px; border-radius:50%; background:{dot_color};"></div>'
            f'</div>'
            f'</div>'
        )
        steps_html += dot
        if connector:
            steps_html += connector

    return (
        f'<div style="display:flex; align-items:center; width:100%; padding:2px 0;">'
        f'{steps_html}</div>'
    )


def _update_lead_stage(profile_url: str, new_stage: str, key_suffix: str) -> None:
    if st.button(f"→ {new_stage.replace('_', ' ').title()}", key=f"als_{key_suffix}", use_container_width=True):
        try:
            from data_store import update_lead_stage
            update_lead_stage(profile_url, new_stage)
            st.cache_data.clear()
            st.rerun()
        except Exception as e:
            st.error(f"Save failed: {e}")


def _ensure_lead_stage(df: pd.DataFrame) -> pd.DataFrame:
    from data_store import compute_lead_stage, LEAD_STAGES
    df = df.copy()
    if "lead_stage" not in df.columns:
        df["lead_stage"] = df.apply(lambda r: compute_lead_stage(r.to_dict()), axis=1)
    else:
        df["lead_stage"] = df["lead_stage"].apply(
            lambda v: v if str(v).strip().lower() in LEAD_STAGES
            else None
        )
        mask = df["lead_stage"].isna()
        if mask.any():
            df.loc[mask, "lead_stage"] = df[mask].apply(lambda r: compute_lead_stage(r.to_dict()), axis=1)
    return df


def _ensure_priority(df: pd.DataFrame) -> pd.DataFrame:
    if "priority_score" not in df.columns or pd.to_numeric(df["priority_score"], errors="coerce").fillna(0).sum() == 0:
        from data_store import compute_priority_score
        df = df.copy()
        df["priority_score"] = df.apply(lambda r: compute_priority_score(r.to_dict()), axis=1)
    else:
        df = df.copy()
        df["priority_score"] = pd.to_numeric(df["priority_score"], errors="coerce").fillna(0).astype(int)
    return df


# ── Part 5: Pipeline Health Panel ────────────────────────────────────────────

def _render_pipeline_health(df: pd.DataFrame) -> None:
    stage_counts = df["lead_stage"].value_counts().to_dict()

    health_stages = [
        ("new",            "📥", "New Leads",          "#64748B"),
        ("qualified",      "✅", "Qualified",           "#3B82F6"),
        ("enriched",       "🔍", "Enriched",            "#8B5CF6"),
        ("personalized",   "🎯", "Personalized",        "#F97316"),
        ("message_ready",  "✉️", "Messages Ready",      "#22C55E"),
        ("contacted",      "📤", "Contacted",           "#CA8A04"),
        ("replied",        "💬", "Replied",             "#0891B2"),
        ("meeting_booked", "📅", "Meetings",            "#16A34A"),
    ]

    cols = st.columns(8)
    for col, (stage, icon, label, color) in zip(cols, health_stages):
        count = stage_counts.get(stage, 0)
        with col:
            st.markdown(f"""
            <div style="background:#FFFFFF; border-radius:10px; border:1px solid #E2E8F0;
                        border-top:3px solid {color};
                        padding:14px 12px 12px 12px; text-align:center;
                        box-shadow:0 1px 2px rgba(0,0,0,0.04);">
                <div style="font-size:20px; margin-bottom:4px;">{icon}</div>
                <div style="font-size:24px; font-weight:700; color:{color}; line-height:1;">{count}</div>
                <div style="font-size:10.5px; color:#94A3B8; margin-top:5px; font-weight:600;
                            text-transform:uppercase; letter-spacing:0.05em;">{label}</div>
            </div>
            """, unsafe_allow_html=True)


# ── Part 3: Action Required Panel ────────────────────────────────────────────

def _render_action_required(df: pd.DataFrame) -> None:
    action_df = df[df["lead_stage"] == "message_ready"].sort_values(
        "priority_score", ascending=False
    ).head(20)

    count = len(action_df)
    st.markdown(f"""
    <div style="display:flex; align-items:center; gap:10px; margin:28px 0 14px 0;">
        <div style="width:8px; height:32px; background:#22C55E; border-radius:4px;"></div>
        <div>
            <div style="font-size:16px; font-weight:700; color:#0F172A;">
                🔥 Leads Requiring Action
                <span style="font-size:12px; font-weight:500; color:#94A3B8; margin-left:8px;">
                    {count} leads with messages ready
                </span>
            </div>
            <div style="font-size:12px; color:#64748B; margin-top:2px;">
                lead_stage = message_ready · sorted by priority score
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    if action_df.empty:
        st.info("No leads with messages ready. Run `personalize.py` then `generate_messages.py` to prepare messages.")
        return

    # Column headers
    st.markdown("""
    <div style="display:grid;
                grid-template-columns:180px 1fr 130px 64px 64px 120px 100px;
                gap:0; padding:9px 12px;
                background:#F8FAFC; border:1px solid #E2E8F0; border-radius:8px 8px 0 0;
                font-size:10.5px; font-weight:700; color:#94A3B8;
                letter-spacing:0.07em; text-transform:uppercase;">
        <div>Name</div><div>Title · Company</div><div>Hook</div>
        <div style="text-align:center;">ICP</div>
        <div style="text-align:center;">Priority</div>
        <div>Funding</div><div>Actions</div>
    </div>
    """, unsafe_allow_html=True)

    for i, (_, row) in enumerate(action_df.iterrows()):
        name     = _s(row.get("name") or row.get("founder_name")) or "—"
        title    = _s(row.get("title") or row.get("headline"))
        company  = _s(row.get("company") or row.get("company_name"))
        icp      = int(row.get("icp_score") or row.get("quality_score") or 0)
        priority = int(row.get("priority_score") or 0)
        funding  = _s(row.get("funding_stage"))
        hook     = _s(row.get("hook") or row.get("signal_text") or "")[:80]
        purl     = _s(row.get("profile_url") or row.get("linkedin_url") or "")
        msg      = _s(row.get("msg_connection_note") or row.get("connection_request") or "")

        cs = st.columns([1.6, 3.0, 1.2, 0.6, 0.6, 1.1, 0.9])
        with cs[0]:
            st.markdown(
                f'<div style="padding:11px 4px; font-weight:600; font-size:13px; color:#0F172A;">{name}</div>',
                unsafe_allow_html=True,
            )
        with cs[1]:
            hook_html = f'<div style="font-size:11px; color:#64748B; margin-top:2px;">📌 {hook}</div>' if hook else ""
            st.markdown(
                f'<div style="padding:7px 4px;">'
                f'<div style="font-size:12px; color:#374151;">{title}</div>'
                f'<div style="font-size:11.5px; color:#94A3B8;">{company}</div>'
                f'{hook_html}'
                f'</div>',
                unsafe_allow_html=True,
            )
        with cs[2]:
            st.markdown(
                f'<div style="padding:12px 4px; font-size:11px; color:#64748B;">'
                f'{_progress_bar(row.get("lead_stage","new"))}</div>',
                unsafe_allow_html=True,
            )
        with cs[3]:
            st.markdown(
                f'<div style="padding:12px 2px; text-align:center;">'
                f'<span style="background:#EEF2FF; color:#6366F1; font-size:12px; font-weight:700; '
                f'padding:2px 8px; border-radius:10px;">{icp}</span></div>',
                unsafe_allow_html=True,
            )
        with cs[4]:
            st.markdown(
                f'<div style="padding:12px 2px; text-align:center;">{_priority_chip(priority)}</div>',
                unsafe_allow_html=True,
            )
        with cs[5]:
            st.markdown(
                f'<div style="padding:12px 4px; font-size:11.5px; color:#16A34A; font-weight:500;">'
                f'{funding}</div>',
                unsafe_allow_html=True,
            )
        with cs[6]:
            if st.button("✉️ Msg", key=f"ar_msg_{i}_{purl or name}", use_container_width=True,
                         help="View connection request"):
                st.session_state[f"ar_show_{i}"] = not st.session_state.get(f"ar_show_{i}", False)
            if st.button("📤 Sent", key=f"ar_sent_{i}_{purl or name}", use_container_width=True,
                         help="Mark connection sent"):
                if purl:
                    try:
                        from data_store import update_lead_stage
                        update_lead_stage(purl, "contacted")
                        st.cache_data.clear()
                        st.rerun()
                    except Exception as e:
                        st.error(str(e))
            if st.button("⏭️ Skip", key=f"ar_skip_{i}_{purl or name}", use_container_width=True,
                         help="Skip this lead"):
                if purl:
                    try:
                        from data_store import update_lead_stage
                        update_lead_stage(purl, "skipped")
                        st.cache_data.clear()
                        st.rerun()
                    except Exception as e:
                        st.error(str(e))

        if st.session_state.get(f"ar_show_{i}", False) and msg:
            with st.container():
                st.code(msg, language=None)
                cc = len(msg)
                color = "#16A34A" if cc <= 300 else "#DC2626"
                st.markdown(
                    f'<div style="font-size:11px; color:{color}; margin-top:-6px; margin-bottom:4px;">'
                    f'{"✅" if cc <= 300 else "⚠️"} {len(msg.split())} words · {cc}/300 chars</div>',
                    unsafe_allow_html=True,
                )

        st.markdown('<div style="height:1px; background:#F1F5F9;"></div>', unsafe_allow_html=True)

    st.markdown(
        f'<div style="padding:8px 12px; background:#F8FAFC; border:1px solid #E2E8F0; '
        f'border-top:none; border-radius:0 0 8px 8px; font-size:11.5px; color:#94A3B8;">'
        f'{count} leads with messages ready</div>',
        unsafe_allow_html=True,
    )


# ── Part 4: Waiting for Reply Panel ──────────────────────────────────────────

def _render_waiting_reply(df: pd.DataFrame) -> None:
    waiting_df = df[df["lead_stage"] == "contacted"].copy()

    # Try to compute days since contact
    contacted_col = next(
        (c for c in ["date_contacted", "contacted_at", "updated_at", "created_at"] if c in waiting_df.columns),
        None,
    )
    if contacted_col:
        waiting_df["_ts"] = pd.to_datetime(waiting_df[contacted_col], errors="coerce", utc=True)
        now = pd.Timestamp.now(tz="UTC")
        waiting_df["days_waiting"] = (now - waiting_df["_ts"]).dt.days.fillna(0).astype(int)
    else:
        waiting_df["days_waiting"] = 0

    waiting_df = waiting_df.sort_values("days_waiting", ascending=False)
    count = len(waiting_df)

    st.markdown(f"""
    <div style="display:flex; align-items:center; gap:10px; margin:28px 0 14px 0;">
        <div style="width:8px; height:32px; background:#CA8A04; border-radius:4px;"></div>
        <div>
            <div style="font-size:16px; font-weight:700; color:#0F172A;">
                ⏳ Waiting for Reply
                <span style="font-size:12px; font-weight:500; color:#94A3B8; margin-left:8px;">
                    {count} leads contacted
                </span>
            </div>
            <div style="font-size:12px; color:#64748B; margin-top:2px;">
                lead_stage = contacted · oldest first
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    if waiting_df.empty:
        st.info("No leads in 'contacted' stage yet. Send connection requests to move leads here.")
        return

    # Table header
    st.markdown("""
    <div style="display:grid;
                grid-template-columns:180px 140px 1fr 120px 80px;
                gap:0; padding:9px 12px;
                background:#F8FAFC; border:1px solid #E2E8F0; border-radius:8px 8px 0 0;
                font-size:10.5px; font-weight:700; color:#94A3B8;
                letter-spacing:0.07em; text-transform:uppercase;">
        <div>Name</div><div>Company</div><div>Title</div>
        <div>Date Contacted</div><div style="text-align:center;">Days Waiting</div>
    </div>
    """, unsafe_allow_html=True)

    for i, (_, row) in enumerate(waiting_df.head(20).iterrows()):
        name    = _s(row.get("name") or row.get("founder_name")) or "—"
        company = _s(row.get("company") or row.get("company_name"))
        title   = _s(row.get("title") or row.get("headline"))
        purl    = _s(row.get("profile_url") or "")
        days    = int(row.get("days_waiting") or 0)
        ts_raw  = _s(row.get(contacted_col, "")) if contacted_col else ""
        date_str = ts_raw[:10] if ts_raw else "—"

        # Color days waiting: green < 3, yellow 3-7, orange 7-14, red 14+
        if days <= 3:
            day_color = "#16A34A"
        elif days <= 7:
            day_color = "#CA8A04"
        elif days <= 14:
            day_color = "#F97316"
        else:
            day_color = "#EF4444"

        cs = st.columns([1.5, 1.2, 2.5, 1.0, 0.7])
        with cs[0]:
            st.markdown(f'<div style="padding:11px 4px; font-weight:600; font-size:12.5px; color:#0F172A;">{name}</div>', unsafe_allow_html=True)
        with cs[1]:
            st.markdown(f'<div style="padding:11px 4px; font-size:12px; color:#374151;">{company}</div>', unsafe_allow_html=True)
        with cs[2]:
            st.markdown(f'<div style="padding:11px 4px; font-size:12px; color:#64748B;">{title}</div>', unsafe_allow_html=True)
        with cs[3]:
            st.markdown(f'<div style="padding:11px 4px; font-size:12px; color:#94A3B8;">{date_str}</div>', unsafe_allow_html=True)
        with cs[4]:
            st.markdown(
                f'<div style="padding:10px 2px; text-align:center;">'
                f'<span style="font-size:14px; font-weight:700; color:{day_color};">{days}d</span>'
                f'</div>',
                unsafe_allow_html=True,
            )

        # Quick action — mark replied
        act1, act2, _ = st.columns([1, 1, 3])
        with act1:
            if st.button("💬 Replied", key=f"wr_rep_{i}_{purl or name}", use_container_width=True):
                if purl:
                    try:
                        from data_store import update_lead_stage
                        update_lead_stage(purl, "replied")
                        st.cache_data.clear()
                        st.rerun()
                    except Exception as e:
                        st.error(str(e))
        with act2:
            if purl and purl.startswith("http"):
                st.link_button("🔗 LinkedIn", purl, use_container_width=True)

        st.markdown('<div style="height:1px; background:#F1F5F9;"></div>', unsafe_allow_html=True)

    st.markdown(
        f'<div style="padding:8px 12px; background:#FEFCE8; border:1px solid #FDE68A; '
        f'border-top:none; border-radius:0 0 8px 8px; font-size:11.5px; color:#92400E;">'
        f'⏳ {count} waiting — follow up after 5–7 days of no reply</div>',
        unsafe_allow_html=True,
    )


# ── Part 7: Leads to Work On Today ───────────────────────────────────────────

def _render_work_today(df: pd.DataFrame) -> None:
    today_df = df[
        (df["lead_stage"] == "message_ready") &
        (df["priority_score"] >= 70)
    ].sort_values("priority_score", ascending=False).head(20)

    count = len(today_df)
    st.markdown(f"""
    <div style="display:flex; align-items:center; gap:10px; margin:28px 0 14px 0;">
        <div style="width:8px; height:32px; background:#6366F1; border-radius:4px;"></div>
        <div>
            <div style="font-size:16px; font-weight:700; color:#0F172A;">
                🚀 Leads to Work On Today
                <span style="font-size:12px; font-weight:500; color:#94A3B8; margin-left:8px;">
                    {count} leads · message_ready + priority ≥ 70
                </span>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    if today_df.empty:
        st.info("No high-priority message-ready leads right now. Run the pipeline to generate more.")
        return

    # Compact card grid
    for i, (_, row) in enumerate(today_df.iterrows()):
        name     = _s(row.get("name") or row.get("founder_name")) or "Unknown"
        title    = _s(row.get("title") or row.get("headline"))
        company  = _s(row.get("company") or row.get("company_name"))
        priority = int(row.get("priority_score") or 0)
        icp      = int(row.get("icp_score") or row.get("quality_score") or 0)
        funding  = _s(row.get("funding_stage"))
        hook     = _s(row.get("hook") or row.get("signal_text") or "")[:100]
        purl     = _s(row.get("profile_url") or "")
        msg      = _s(row.get("msg_connection_note") or row.get("connection_request") or "")
        stage    = _s(row.get("lead_stage")) or "message_ready"

        # Priority color
        p_color = "#15803D" if priority >= 80 else "#D97706"
        p_bg    = "#DCFCE7" if priority >= 80 else "#FFF7ED"

        st.markdown(f"""
        <div style="background:#FFFFFF; border:1px solid #E2E8F0; border-radius:10px;
                    padding:14px 18px; margin-bottom:8px; border-left:4px solid {p_color};">
            <div style="display:flex; justify-content:space-between; align-items:flex-start; gap:8px;">
                <div style="flex:1; min-width:0;">
                    <div style="display:flex; align-items:center; gap:8px; margin-bottom:3px;">
                        <span style="font-size:14px; font-weight:700; color:#0F172A;">{name}</span>
                        <span style="background:{p_bg}; color:{p_color}; font-size:11px; font-weight:700;
                                     padding:1px 7px; border-radius:10px;">{priority}</span>
                        <span style="background:#EEF2FF; color:#6366F1; font-size:11px; font-weight:600;
                                     padding:1px 7px; border-radius:10px;">ICP {icp}</span>
                        {f'<span style="background:#F0FDF4; color:#16A34A; font-size:11px; font-weight:600; padding:1px 7px; border-radius:10px;">{funding}</span>' if funding else ""}
                    </div>
                    <div style="font-size:12.5px; color:#64748B;">
                        {title + " · " if title else ""}{company}
                    </div>
                    {f'<div style="font-size:12px; color:#94A3B8; margin-top:4px;">📌 {hook}</div>' if hook else ""}
                </div>
                <div style="flex-shrink:0; text-align:right;">
                    {_progress_bar(stage)}
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        btn_cols = st.columns([1, 1, 1, 3])
        with btn_cols[0]:
            if msg and st.button("✉️ Message", key=f"wt_msg_{i}_{purl or name}", use_container_width=True):
                st.session_state[f"wt_show_{i}"] = not st.session_state.get(f"wt_show_{i}", False)
        with btn_cols[1]:
            if st.button("✅ Sent", key=f"wt_sent_{i}_{purl or name}", use_container_width=True,
                         help="Mark connection sent → moves to Contacted"):
                if purl:
                    try:
                        from data_store import update_lead_stage
                        update_lead_stage(purl, "contacted")
                        st.cache_data.clear()
                        st.rerun()
                    except Exception as e:
                        st.error(str(e))
        with btn_cols[2]:
            if st.button("⏭️ Skip", key=f"wt_skip_{i}_{purl or name}", use_container_width=True):
                if purl:
                    try:
                        from data_store import update_lead_stage
                        update_lead_stage(purl, "skipped")
                        st.cache_data.clear()
                        st.rerun()
                    except Exception as e:
                        st.error(str(e))

        if st.session_state.get(f"wt_show_{i}", False) and msg:
            st.code(msg, language=None)
            cc = len(msg)
            c = "#16A34A" if cc <= 300 else "#DC2626"
            st.markdown(
                f'<div style="font-size:11px; color:{c}; margin-top:-6px; margin-bottom:4px;">'
                f'{"✅" if cc <= 300 else "⚠️"} {len(msg.split())} words · {cc}/300 chars</div>',
                unsafe_allow_html=True,
            )


# ── Part 8: Stage Progress Bar (standalone, for use in other components) ─────

def stage_progress_html(stage: str) -> str:
    """Return HTML for a compact stage progress bar. Importable by other components."""
    return _progress_bar(stage)


# ── Main render ───────────────────────────────────────────────────────────────

def render(df: pd.DataFrame) -> None:
    st.markdown("""
    <div style="margin-bottom:24px;">
        <div style="font-size:22px; font-weight:700; color:#0F172A; letter-spacing:-0.02em;">
            🎯 Action Center
        </div>
        <div style="font-size:13px; color:#94A3B8; margin-top:4px;">
            Lead lifecycle · what to do now · what's waiting
        </div>
    </div>
    """, unsafe_allow_html=True)

    if df.empty:
        st.info("No leads yet. Run the pipeline to start.")
        return

    df = _ensure_lead_stage(df)
    df = _ensure_priority(df)

    # ── Part 5: Pipeline Health ──────────────────────────────────
    st.markdown("""
    <div style="font-size:13px; font-weight:700; color:#1E293B;
                letter-spacing:-0.01em; margin-bottom:12px;">
        📊 Pipeline Health
    </div>
    """, unsafe_allow_html=True)
    _render_pipeline_health(df)

    st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)

    # Quick stats: what needs attention vs processed
    total        = len(df)
    needs_action = len(df[df["lead_stage"] == "message_ready"])
    waiting      = len(df[df["lead_stage"] == "contacted"])
    processing   = len(df[df["lead_stage"].isin(["new", "qualified", "enriched", "personalized"])])
    done_or_skip = len(df[df["lead_stage"].isin(["meeting_booked", "closed", "skipped", "replied"])])

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(f"""<div style="background:#F0FDF4; border-radius:10px; border:1px solid #BBF7D0;
            padding:14px 16px; text-align:center; margin-top:16px;">
            <div style="font-size:22px; font-weight:700; color:#16A34A;">{needs_action}</div>
            <div style="font-size:11px; color:#15803D; font-weight:600; margin-top:4px;">READY TO CONTACT</div>
        </div>""", unsafe_allow_html=True)
    with c2:
        st.markdown(f"""<div style="background:#FEFCE8; border-radius:10px; border:1px solid #FDE68A;
            padding:14px 16px; text-align:center; margin-top:16px;">
            <div style="font-size:22px; font-weight:700; color:#CA8A04;">{waiting}</div>
            <div style="font-size:11px; color:#92400E; font-weight:600; margin-top:4px;">WAITING FOR REPLY</div>
        </div>""", unsafe_allow_html=True)
    with c3:
        st.markdown(f"""<div style="background:#EFF6FF; border-radius:10px; border:1px solid #BFDBFE;
            padding:14px 16px; text-align:center; margin-top:16px;">
            <div style="font-size:22px; font-weight:700; color:#3B82F6;">{processing}</div>
            <div style="font-size:11px; color:#1D4ED8; font-weight:600; margin-top:4px;">STILL PROCESSING</div>
        </div>""", unsafe_allow_html=True)
    with c4:
        st.markdown(f"""<div style="background:#F8FAFC; border-radius:10px; border:1px solid #E2E8F0;
            padding:14px 16px; text-align:center; margin-top:16px;">
            <div style="font-size:22px; font-weight:700; color:#64748B;">{done_or_skip}</div>
            <div style="font-size:11px; color:#475569; font-weight:600; margin-top:4px;">DONE / SKIPPED</div>
        </div>""", unsafe_allow_html=True)

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
    st.divider()

    # ── Tabs for the three action panels ────────────────────────
    tab_action, tab_today, tab_waiting = st.tabs([
        f"🔥 Action Required ({needs_action})",
        f"🚀 Work On Today ({len(df[(df['lead_stage']=='message_ready') & (df['priority_score']>=70)])})",
        f"⏳ Waiting for Reply ({waiting})",
    ])

    with tab_action:
        _render_action_required(df)

    with tab_today:
        _render_work_today(df)

    with tab_waiting:
        _render_waiting_reply(df)
