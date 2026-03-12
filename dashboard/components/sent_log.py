"""
Sent Log — Monitor all connection requests sent.
Shows: who, note sent, scraped post/headline, status, warm-up checklist.
Mohit can tick warm-up steps from here.
"""

from datetime import date, datetime
from pathlib import Path

import pandas as pd
import streamlit as st

LOG_FILE  = Path(__file__).parent.parent.parent / "logs" / "outreach_log.csv"
LEADS_CSV = Path(__file__).parent.parent.parent / "output" / "leads.csv"

STATUS_STYLE = {
    "sent":              ("🟢 Sent",           "#E3FCEF", "#006644"),
    "already_connected": ("🔵 Connected",       "#DEEBFF", "#0052CC"),
    "pending":           ("🟡 Pending",         "#FFFAE6", "#974F0C"),
    "failed":            ("🔴 Failed",          "#FFEBE6", "#BF2600"),
    "no_button":         ("⚪ No Button",       "#F4F5F7", "#6B778C"),
}

WARMUP_STEPS = [
    ("view_profile",   "Day 1: View profile + Follow company"),
    ("like_post",      "Day 2: Like 1–2 recent posts"),
    ("comment_post",   "Day 3: Comment on a post"),
]


def load_log() -> pd.DataFrame:
    if not LOG_FILE.exists():
        return pd.DataFrame()
    try:
        df = pd.read_csv(LOG_FILE)
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        return df.sort_values("date", ascending=False)
    except Exception:
        return pd.DataFrame()


def load_leads() -> pd.DataFrame:
    try:
        return pd.read_csv(LEADS_CSV)
    except Exception:
        return pd.DataFrame()


def save_warmup(profile_url: str, step_key: str, done: bool):
    """Update warm_up_status in leads.csv."""
    df = load_leads()
    if df.empty:
        return
    mask = df["profile_url"] == profile_url
    if not mask.any():
        return
    current = str(df.loc[mask, "warm_up_status"].values[0])
    tags = set(t.strip() for t in current.split("|") if t.strip() and t.strip() != "Not started")
    if done:
        tags.add(step_key)
    else:
        tags.discard(step_key)
    new_status = " | ".join(sorted(tags)) if tags else "Not started"
    df.loc[mask, "warm_up_status"] = new_status
    df.to_csv(LEADS_CSV, index=False)


def render():
    log = load_log()

    st.markdown("### 📜 Connection Requests Sent")

    if log.empty:
        st.info("No connection requests sent yet. Go to **Send Queue** to start outreach.")
        return

    # ── Summary metrics ──────────────────────────────────────────────────────
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Total Sent",       int((log["status"] == "sent").sum()))
    c2.metric("Pending Accept",   int((log["status"] == "pending").sum()))
    c3.metric("Already Connected",int((log["status"] == "already_connected").sum()))
    c4.metric("Failed",           int((log["status"] == "failed").sum()))
    today_str = date.today().isoformat()
    c5.metric("Sent Today",       int(log["date"].dt.date.astype(str).str.startswith(today_str).sum()))

    st.markdown("---")

    # ── Filters ──────────────────────────────────────────────────────────────
    col_f1, col_f2, col_f3 = st.columns([2, 2, 2])
    with col_f1:
        statuses   = ["All"] + sorted(log["status"].dropna().unique().tolist())
        sel_status = st.selectbox("Status", statuses)
    with col_f2:
        search = st.text_input("Search name / company", placeholder="e.g. Akshay")
    with col_f3:
        sort_by = st.selectbox("Sort", ["Newest first", "Oldest first"])

    filtered = log.copy()
    if sel_status != "All":
        filtered = filtered[filtered["status"] == sel_status]
    if search:
        mask = (
            filtered["name"].fillna("").str.contains(search, case=False) |
            filtered["company"].fillna("").str.contains(search, case=False)
        )
        filtered = filtered[mask]
    if sort_by == "Oldest first":
        filtered = filtered.sort_values("date", ascending=True)

    st.markdown(f"**{len(filtered)} records**")
    st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)

    # ── Load warm-up status from leads.csv ───────────────────────────────────
    leads_df    = load_leads()
    warmup_map  = {}
    if not leads_df.empty and "profile_url" in leads_df.columns:
        warmup_map = dict(zip(leads_df["profile_url"], leads_df["warm_up_status"].fillna("")))

    # ── Cards ─────────────────────────────────────────────────────────────────
    for _, row in filtered.iterrows():
        status_label, bg, fg = STATUS_STYLE.get(
            str(row.get("status", "")), ("⚪ Unknown", "#F4F5F7", "#6B778C")
        )
        date_str  = str(row["date"])[:16] if pd.notna(row["date"]) else ""
        name      = str(row.get("name", ""))
        company   = str(row.get("company", ""))
        title     = str(row.get("title", ""))
        location  = str(row.get("location", ""))
        note_sent = str(row.get("note_sent", ""))
        post_ref  = str(row.get("scraped_post", ""))
        headline  = str(row.get("scraped_headline", ""))
        url       = str(row.get("profile_url", ""))
        score     = row.get("quality_score", "")
        temp      = str(row.get("lead_temperature", ""))

        with st.expander(
            f"{'🔥' if temp=='Hot' else '⚡'} **{name}** — {company}  |  "
            f"{status_label}  |  {date_str}",
            expanded=False,
        ):
            col1, col2 = st.columns([3, 2])

            with col1:
                # Name + meta
                st.markdown(
                    f"**{name}** · {title} · {company}  \n"
                    f"📍 {location} · Score {int(score) if score else '?'} · {temp}"
                )

                # Note sent
                st.markdown("**✉️ Note sent:**")
                st.info(note_sent if note_sent and note_sent != "nan" else "—")

                # What was scraped
                if headline and headline != "nan":
                    st.caption(f"📖 Scraped headline: {headline[:120]}")
                if post_ref and post_ref != "nan":
                    st.caption(f"📝 Recent post used: {post_ref[:120]}...")

            with col2:
                # LinkedIn link
                if url and url.startswith("http"):
                    st.link_button("🔗 Open LinkedIn Profile", url, use_container_width=True)

                # Status badge
                st.markdown(
                    f'<div style="background:{bg}; color:{fg}; border-radius:4px; '
                    f'padding:6px 12px; text-align:center; font-weight:600; '
                    f'font-size:0.88em; margin:6px 0;">{status_label}</div>',
                    unsafe_allow_html=True,
                )

                # Warm-up checklist (Mohit ticks manually)
                if str(row.get("status")) == "sent":
                    st.markdown("**🌡️ Warm-up steps (you do):**")
                    warm_status = warmup_map.get(url, "")
                    for step_key, step_label in WARMUP_STEPS:
                        checked = step_key in warm_status
                        new_val = st.checkbox(
                            step_label,
                            value=checked,
                            key=f"warmup_{url}_{step_key}",
                        )
                        if new_val != checked:
                            save_warmup(url, step_key, new_val)
                            st.rerun()

        st.markdown("<div style='height:2px'></div>", unsafe_allow_html=True)
