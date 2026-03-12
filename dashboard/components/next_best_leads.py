"""
🔥 Today — Next Best Leads + Priority Engine + Leads to Contact.
Parts 1, 2, 7 of the dashboard upgrade.
"""
from __future__ import annotations

import math

import pandas as pd
import streamlit as st

STATUS_OPTIONS = ["new", "connection_sent", "accepted", "replied", "meeting_booked", "closed"]
STATUS_BADGE = {
    "new":              ("#EEF2FF", "#6366F1"),
    "connection_sent":  ("#FFF7ED", "#F97316"),
    "accepted":         ("#F0FDF4", "#16A34A"),
    "replied":          ("#ECFDF5", "#059669"),
    "meeting_booked":   ("#DCFCE7", "#15803D"),
    "closed":           ("#F0FDF4", "#22C55E"),
}
PRIORITY_COLOR = {
    (80, 101): ("#DCFCE7", "#15803D", "🔥 Must Contact"),
    (60,  80): ("#FFF7ED", "#D97706", "⚡ High Priority"),
    (40,  60): ("#F8FAFC", "#64748B", "📋 Warm"),
    (0,   40): ("#F9FAFB", "#9CA3AF", "❄️ Low"),
}


def _s(val) -> str:
    if val is None:
        return ""
    if isinstance(val, float) and math.isnan(val):
        return ""
    s = str(val).strip()
    return "" if s.lower() in ("nan", "none", "") else s


def _priority_label(score: int) -> tuple[str, str, str]:
    for (lo, hi), (bg, fg, label) in PRIORITY_COLOR.items():
        if lo <= score < hi:
            return bg, fg, label
    return "#F9FAFB", "#9CA3AF", "❄️ Low"


def _badge(text: str, bg: str, fg: str) -> str:
    return (
        f'<span style="background:{bg}; color:{fg}; font-size:11px; font-weight:600; '
        f'padding:2px 8px; border-radius:12px;">{text}</span>'
    )


def _priority_chip(score: int) -> str:
    bg, fg, _ = _priority_label(score)
    return (
        f'<span style="background:{bg}; color:{fg}; font-size:13px; font-weight:700; '
        f'padding:4px 12px; border-radius:20px; font-variant-numeric:tabular-nums;">{score}</span>'
    )


def _mark_status(profile_url: str, status: str, key: str) -> None:
    if st.button(f"Mark: {status.replace('_', ' ').title()}", key=key, use_container_width=True):
        try:
            from data_store import update_lead_status
            update_lead_status(profile_url, status)
            st.cache_data.clear()
            st.success(f"✅ Marked as {status}")
            st.rerun()
        except Exception as e:
            st.error(f"Save failed: {e}")


def _ensure_priority(df: pd.DataFrame) -> pd.DataFrame:
    if "priority_score" not in df.columns or df["priority_score"].sum() == 0:
        from data_store import compute_priority_score
        df = df.copy()
        df["priority_score"] = df.apply(lambda r: compute_priority_score(r.to_dict()), axis=1)
    else:
        df["priority_score"] = pd.to_numeric(df["priority_score"], errors="coerce").fillna(0).astype(int)
    return df


def _ensure_status(df: pd.DataFrame) -> pd.DataFrame:
    if "status" not in df.columns:
        df = df.copy()
        df["status"] = "new"
    else:
        df["status"] = df["status"].fillna("new")
    return df


# ── Priority Score Explainer ──────────────────────────────────────────────────

def _render_priority_explainer() -> None:
    st.markdown("""
    <div style="background:#FFFFFF; border:1px solid #E2E8F0; border-radius:12px;
                padding:20px 24px; margin-bottom:20px;">
        <div style="font-size:14px; font-weight:700; color:#0F172A; margin-bottom:12px;">
            ⚙️ Priority Score Formula
        </div>
        <div style="display:grid; grid-template-columns:1fr 1fr 1fr 1fr 1fr; gap:12px;">
            <div style="text-align:center;">
                <div style="font-size:22px; font-weight:700; color:#6366F1;">50 pts</div>
                <div style="font-size:11px; color:#64748B; margin-top:4px;">ICP Score × 0.5</div>
            </div>
            <div style="text-align:center;">
                <div style="font-size:22px; font-weight:700; color:#F59E0B;">15 pts</div>
                <div style="font-size:11px; color:#64748B; margin-top:4px;">PM Hiring Signal</div>
            </div>
            <div style="text-align:center;">
                <div style="font-size:22px; font-weight:700; color:#10B981;">10 pts</div>
                <div style="font-size:11px; color:#64748B; margin-top:4px;">Funding Round</div>
            </div>
            <div style="text-align:center;">
                <div style="font-size:22px; font-weight:700; color:#8B5CF6;">10 pts</div>
                <div style="font-size:11px; color:#64748B; margin-top:4px;">Persona (Founder/CTO)</div>
            </div>
            <div style="text-align:center;">
                <div style="font-size:22px; font-weight:700; color:#3B82F6;">5 pts</div>
                <div style="font-size:11px; color:#64748B; margin-top:4px;">Recent Activity</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)


# ── Top 5 Lead Cards ──────────────────────────────────────────────────────────

def _render_lead_card(rank: int, row: dict) -> None:
    name        = _s(row.get("name") or row.get("founder_name")) or "Unknown"
    title       = _s(row.get("title") or row.get("headline"))
    company     = _s(row.get("company") or row.get("company_name"))
    icp         = int(row.get("icp_score") or row.get("quality_score") or 0)
    priority    = int(row.get("priority_score") or 0)
    funding     = _s(row.get("funding_stage"))
    hook        = _s(row.get("hook") or row.get("signal_text") or "")
    profile_url = _s(row.get("profile_url") or row.get("linkedin_url"))
    status      = _s(row.get("status")) or "new"
    bg_p, fg_p, plabel = _priority_label(priority)
    sbg, sfg = STATUS_BADGE.get(status, ("#F8FAFC", "#64748B"))

    pm_gap = row.get("pm_gap_signal") in (True, "True", "true", 1, "1")

    with st.container():
        hook_div = f'<div style="font-size:12px; color:#64748B; line-height:1.5; margin-bottom:8px;">📌 {hook[:120]}{"..." if len(hook) > 120 else ""}</div>' if hook else ""
        funding_badge = _badge(funding, "#F0FDF4", "#16A34A") if funding else ""
        pm_gap_badge  = _badge("⚡ PM GAP", "#FFF7ED", "#EA580C") if pm_gap else ""
        border_color  = "#EA580C" if pm_gap else fg_p
        card_html = (
            f'<div style="background:#FFFFFF; border:1px solid #E2E8F0; border-radius:12px;'
            f' padding:16px 20px; margin-bottom:12px; border-left:4px solid {border_color};">'
            f'<div style="display:flex; align-items:flex-start; justify-content:space-between; gap:12px;">'
            f'<div style="flex:1; min-width:0;">'
            f'<div style="display:flex; align-items:center; gap:8px; margin-bottom:4px;">'
            f'<div style="width:24px; height:24px; background:{fg_p}18; border-radius:6px;'
            f' display:flex; align-items:center; justify-content:center;'
            f' font-size:12px; font-weight:700; color:{fg_p}; flex-shrink:0;">{rank}</div>'
            f'<div style="font-size:15px; font-weight:700; color:#0F172A;">{name}</div>'
            f'</div>'
            f'<div style="font-size:12.5px; color:#475569; margin-bottom:8px;">'
            f'{"" + title + " · " if title else ""}<strong>{company}</strong></div>'
            f'{hook_div}'
            f'<div style="display:flex; gap:6px; flex-wrap:wrap;">'
            f'{_badge(plabel, bg_p, fg_p)}'
            f'{_badge(f"ICP {icp}", "#EEF2FF", "#6366F1")}'
            f'{funding_badge}'
            f'{pm_gap_badge}'
            f'{_badge(status.replace("_", " ").title(), sbg, sfg)}'
            f'</div></div>'
            f'<div style="text-align:center; flex-shrink:0;">'
            f'<div style="font-size:28px; font-weight:700; color:{fg_p}; line-height:1;">{priority}</div>'
            f'<div style="font-size:10px; color:#94A3B8; margin-top:2px;">PRIORITY</div>'
            f'</div></div></div>'
        )
        st.html(card_html)

        # Action buttons
        btn_cols = st.columns([1, 1, 1])
        with btn_cols[0]:
            if profile_url and profile_url.startswith("http"):
                st.link_button("🔗 LinkedIn", profile_url, use_container_width=True)
        with btn_cols[1]:
            msg = _s(row.get("msg_connection_note") or row.get("connection_request") or "")
            if msg:
                if st.button("✉️ View Message", key=f"vm_{rank}_{profile_url or name}", use_container_width=True):
                    st.session_state[f"show_msg_{rank}"] = not st.session_state.get(f"show_msg_{rank}", False)
        with btn_cols[2]:
            next_status = {
                "new": "connection_sent",
                "connection_sent": "accepted",
                "accepted": "replied",
                "replied": "meeting_booked",
                "meeting_booked": "closed",
            }.get(status, "connection_sent")
            _mark_status(profile_url or name, next_status, f"ms_{rank}_{profile_url or name}")

        if st.session_state.get(f"show_msg_{rank}", False):
            msg = _s(row.get("msg_connection_note") or row.get("connection_request") or "")
            if msg:
                st.code(msg, language=None)
                wc = len(msg.split())
                cc = len(msg)
                col = "#16A34A" if cc <= 300 else "#DC2626"
                st.markdown(
                    f'<div style="font-size:11.5px; color:{col}; margin-top:-6px; margin-bottom:6px;">'
                    f'{"✅" if cc <= 300 else "⚠️"} {wc} words · {cc}/300 chars</div>',
                    unsafe_allow_html=True,
                )


# ── Leads to Contact Today ────────────────────────────────────────────────────

def _render_contact_today(df: pd.DataFrame) -> None:
    today_df = df[
        (df["status"] == "new") &
        (df["priority_score"] >= 70)
    ].sort_values("priority_score", ascending=False).head(20)

    st.markdown(f"""
    <div style="font-size:16px; font-weight:700; color:#0F172A; margin:28px 0 12px 0;">
        🚀 Leads to Contact Today
        <span style="font-size:12px; font-weight:500; color:#64748B; margin-left:8px;">
            status = new · priority ≥ 70 · top 20
        </span>
    </div>
    """, unsafe_allow_html=True)

    if today_df.empty:
        st.info("No high-priority new leads right now. Lower the threshold or run a new pipeline batch.")
        return

    # Table header
    st.markdown("""
    <div style="display:grid; grid-template-columns:28px 180px 1fr 100px 90px 80px;
                gap:0; padding:8px 12px;
                background:#F8FAFC; border:1px solid #E2E8F0; border-radius:8px 8px 0 0;
                font-size:10.5px; font-weight:700; color:#94A3B8;
                letter-spacing:0.07em; text-transform:uppercase;">
        <div>#</div><div>Name</div><div>Title · Company</div>
        <div>Funding</div><div>ICP</div><div style="text-align:right;">Priority</div>
    </div>
    """, unsafe_allow_html=True)

    for i, (_, row) in enumerate(today_df.iterrows(), 1):
        name     = _s(row.get("name") or row.get("founder_name")) or "—"
        title    = _s(row.get("title") or row.get("headline"))
        company  = _s(row.get("company") or row.get("company_name"))
        funding  = _s(row.get("funding_stage"))
        icp      = int(row.get("icp_score") or row.get("quality_score") or 0)
        priority = int(row.get("priority_score") or 0)
        purl     = _s(row.get("profile_url") or "")
        bg_p, fg_p, _ = _priority_label(priority)

        cs = st.columns([0.25, 1.6, 3.5, 0.9, 0.75, 0.7])
        with cs[0]:
            st.markdown(f'<div style="padding:10px 2px; font-size:11px; color:#CBD5E1;">{i}</div>', unsafe_allow_html=True)
        with cs[1]:
            st.markdown(f'<div style="padding:10px 0; font-weight:600; font-size:12.5px; color:#0F172A;">{name}</div>', unsafe_allow_html=True)
        with cs[2]:
            st.markdown(
                f'<div style="padding:6px 0;">'
                f'<div style="font-size:12px; color:#374151;">{title}</div>'
                f'<div style="font-size:11.5px; color:#94A3B8;">{company}</div></div>',
                unsafe_allow_html=True,
            )
        with cs[3]:
            st.markdown(f'<div style="padding:10px 0; font-size:11.5px; color:#16A34A;">{funding}</div>', unsafe_allow_html=True)
        with cs[4]:
            st.markdown(
                f'<div style="padding:10px 0;">'
                f'<span style="background:#EEF2FF; color:#6366F1; font-size:11px; font-weight:700; padding:2px 8px; border-radius:10px;">{icp}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )
        with cs[5]:
            if st.button(
                str(priority),
                key=f"tod_{i}_{purl or name}",
                use_container_width=True,
                help=f"Priority score: {priority}",
            ):
                st.session_state["page"] = "Lead Detail"
                st.session_state["detail_url"] = purl
                st.rerun()

        st.markdown('<div style="height:1px; background:#F1F5F9;"></div>', unsafe_allow_html=True)

    st.markdown(
        f'<div style="padding:8px 12px; background:#F8FAFC; border:1px solid #E2E8F0; '
        f'border-top:none; border-radius:0 0 8px 8px; font-size:11.5px; color:#94A3B8;">'
        f'{len(today_df)} leads ready to contact</div>',
        unsafe_allow_html=True,
    )


# ── Main render ───────────────────────────────────────────────────────────────

def render(df: pd.DataFrame) -> None:
    st.markdown("""
    <div style="margin-bottom:24px;">
        <div style="font-size:22px; font-weight:700; color:#0F172A; letter-spacing:-0.02em;">
            🔥 Today's Command Center
        </div>
        <div style="font-size:13px; color:#94A3B8; margin-top:4px;">
            AI-ranked leads · Next best actions · Outreach queue
        </div>
    </div>
    """, unsafe_allow_html=True)

    if df.empty:
        st.info("No leads yet. Run the pipeline to start.")
        return

    df = _ensure_priority(df)
    df = _ensure_status(df)

    # ── Summary strip ─────────────────────────────────────────
    total_new    = int((df["status"] == "new").sum())
    high_pri     = int((df["priority_score"] >= 80).sum())
    med_pri      = int(((df["priority_score"] >= 60) & (df["priority_score"] < 80)).sum())
    contacted    = int((df["status"] != "new").sum())

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("🆕 New Leads", total_new, help="Status = new, not yet contacted")
    with c2:
        st.metric("🔥 Must Contact", high_pri, help="Priority score ≥ 80")
    with c3:
        st.metric("⚡ High Priority", med_pri, help="Priority score 60–79")
    with c4:
        st.metric("✅ Contacted", contacted, help="Any status other than new")

    st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)

    # ── Priority explainer ────────────────────────────────────
    with st.expander("⚙️ How Priority Score is Calculated", expanded=False):
        _render_priority_explainer()

    # ── Next 5 best leads ─────────────────────────────────────
    st.markdown("""
    <div style="font-size:16px; font-weight:700; color:#0F172A; margin-bottom:12px;">
        🎯 Next Best Leads to Contact
        <span style="font-size:12px; font-weight:500; color:#64748B; margin-left:8px;">
            top 5 by priority score
        </span>
    </div>
    """, unsafe_allow_html=True)

    top5 = df[df["status"] == "new"].sort_values("priority_score", ascending=False).head(5)
    if top5.empty:
        st.success("🎉 All high-priority leads have been contacted! Great work.")
    else:
        for rank, (_, row) in enumerate(top5.iterrows(), 1):
            _render_lead_card(rank, row.to_dict())

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    # ── Leads to Contact Today ────────────────────────────────
    _render_contact_today(df)
