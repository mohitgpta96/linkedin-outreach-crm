"""
Send Queue page — shows today's 15 leads ready for connection request.
Displays personalized note with one-click copy, LinkedIn profile link,
and a terminal command to run the automation script.
"""

import os
import subprocess
from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st

LEADS_CSV   = Path(__file__).parent.parent.parent / "output" / "leads.csv"
LOG_FILE    = Path(__file__).parent.parent.parent / "logs" / "outreach_log.csv"
SESSION_DIR = Path(__file__).parent.parent.parent / "output" / ".linkedin_session"
DAILY_LIMIT = 15


def count_sent_today():
    if not LOG_FILE.exists():
        return 0
    today = date.today().isoformat()
    try:
        log = pd.read_csv(LOG_FILE)
        return int(((log["date"].str.startswith(today)) & (log["status"] == "sent")).sum())
    except Exception:
        return 0


def get_queue(df):
    ready = df[
        (df["pipeline_stage"] == "Found") &
        (df["profile_url"].notna()) &
        (df["profile_url"].str.startswith("https://www.linkedin.com/in/", na=False)) &
        (df["msg_connection_note"].notna())
    ].copy()
    temp_map = {"Hot": 0, "Warm": 1, "Cold": 2}
    ready["_t"] = ready["lead_temperature"].map(temp_map).fillna(3)
    ready = ready.sort_values(["quality_score", "_t"], ascending=[False, True])
    ready.drop(columns=["_t"], inplace=True)
    return ready.head(DAILY_LIMIT)


def render(df: pd.DataFrame):
    sent_today = count_sent_today()
    remaining  = max(0, DAILY_LIMIT - sent_today)
    queue      = get_queue(df)
    session_ok = SESSION_DIR.exists()

    # ── Header stats strip ──────────────────────────────────────────────────
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Today's Queue",    len(queue))
    c2.metric("Sent Today",       sent_today)
    c3.metric("Remaining",        remaining)
    c4.metric("Total Queued",     int((df["pipeline_stage"] == "Found").sum()))

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    # ── Session status + run button ─────────────────────────────────────────
    col_a, col_b = st.columns([3, 1])
    with col_a:
        if session_ok:
            st.success("✅ LinkedIn session active — ready to send")
        else:
            st.warning("⚠️  No LinkedIn session. Run the login command below first.")

    with col_b:
        run_script = st.button("🚀 Run Outreach Script", use_container_width=True, type="primary")

    # ── Terminal commands ───────────────────────────────────────────────────
    with st.expander("📟 Terminal Commands", expanded=not session_ok):
        st.markdown("**Step 1 — Login once (opens browser):**")
        st.code("python3 linkedin_outreach.py --login", language="bash")
        st.markdown("**Step 2 — Send today's batch (reads each profile → generates note → sends):**")
        st.code("python3 linkedin_outreach.py", language="bash")
        st.markdown("**Preview queue without sending:**")
        st.code("python3 linkedin_outreach.py --dry-run", language="bash")
        st.markdown("**Send fewer (e.g. 5):**")
        st.code("python3 linkedin_outreach.py --limit 5", language="bash")

    # ── How it works ─────────────────────────────────────────────────────────
    with st.expander("⚙️ How personalization works", expanded=False):
        st.markdown("""
        For **each lead**, the script does this automatically:

        1. **Opens their LinkedIn profile** in browser (real session, not scraped)
        2. **Reads:**
           - Their recent posts (topic, keywords)
           - Their headline & about section
           - Company context from our CSV (industry, PM signal)
        3. **Generates note using priority order:**
           - 🥇 Reference their specific recent post topic
           - 🥈 Reference their about/mission statement
           - 🥉 Reference the specific PM job title they're hiring for
           - 4️⃣ Reference growth signal (funding, hiring trend)
           - 5️⃣ Industry + company fallback
        4. **Sends** with that note (< 300 chars, < 40 words)
        5. **Logs everything** → visible in 📜 Sent Log

        After requests are sent → **you do warm-up** (like/comment) tracked in Sent Log.
        """)

    if run_script:
        if not session_ok:
            st.error("Login first: `python3 linkedin_outreach.py --login`")
        else:
            script_path = Path(__file__).parent.parent.parent / "linkedin_outreach.py"
            st.info("🚀 Script started in background — check your terminal / logs for progress.")
            subprocess.Popen(
                ["python3", str(script_path)],
                cwd=str(script_path.parent),
                stdout=open(str(script_path.parent / "logs" / "last_run.log"), "w"),
                stderr=subprocess.STDOUT,
            )

    st.markdown("---")

    # ── Queue table ─────────────────────────────────────────────────────────
    st.markdown(
        f"### 📋 Today's Queue  "
        f"<span style='font-size:0.8em; color:#6B778C;'>({len(queue)} leads · Score 100 · Hot first)</span>",
        unsafe_allow_html=True,
    )

    if queue.empty:
        st.info("No leads in queue. All leads processed or pipeline empty.")
        return

    for i, (_, lead) in enumerate(queue.iterrows(), 1):
        with st.container():
            st.markdown(
                f"""
                <div style="background:#FFFFFF; border:1px solid #DFE1E6; border-radius:6px;
                            padding:14px 18px; margin-bottom:10px;">
                  <div style="display:flex; justify-content:space-between; align-items:center;">
                    <div>
                      <span style="font-weight:700; color:#172B4D; font-size:1em;">
                        {i}. {lead['name']}
                      </span>
                      <span style="color:#6B778C; font-size:0.88em; margin-left:8px;">
                        {lead.get('title','')} · {lead.get('company','')} · {lead.get('location','')}
                      </span>
                    </div>
                    <div>
                      <span style="background:#E3FCEF; color:#006644; border-radius:3px;
                                   padding:2px 8px; font-size:0.78em; font-weight:600;">
                        Score {int(lead['quality_score'])}
                      </span>
                      &nbsp;
                      <span style="background:#FFEBE6; color:#BF2600; border-radius:3px;
                                   padding:2px 8px; font-size:0.78em; font-weight:600;">
                        {lead.get('lead_temperature','')}
                      </span>
                    </div>
                  </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            col1, col2 = st.columns([3, 1])
            with col1:
                note = str(lead.get("msg_connection_note", ""))
                st.markdown("**Connection Note:**")
                st.info(note)
                word_count = len(note.split())
                char_count = len(note)
                color = "#006644" if char_count <= 300 else "#BF2600"
                st.markdown(
                    f'<span style="font-size:0.78em; color:{color};">'
                    f'{word_count} words · {char_count}/300 chars</span>',
                    unsafe_allow_html=True,
                )

            with col2:
                st.markdown("**Actions:**")
                linkedin_url = lead.get("profile_url", "")
                if linkedin_url:
                    st.link_button("🔗 Open LinkedIn", linkedin_url, use_container_width=True)

                company_url = lead.get("company_website", "")
                if pd.notna(company_url) and company_url:
                    st.link_button("🌐 Company Site", str(company_url), use_container_width=True)

                # Industry + size info
                industry = lead.get("industry", "")
                size     = lead.get("company_size", "")
                if industry or size:
                    st.caption(f"{industry}\n{size} employees")

        st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
