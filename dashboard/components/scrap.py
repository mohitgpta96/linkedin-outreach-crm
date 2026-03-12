"""
Scrap Page — Shows all scrapped leads with option to restore.
"""
import os
import streamlit as st
import pandas as pd

CSV_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "output", "leads.csv"
)

TEMP_EMOJI = {"Hot": "🔥", "Warm": "⚡", "Cold": "❄️"}


def _save_csv(df: pd.DataFrame) -> None:
    df.to_csv(CSV_PATH, index=False)
    st.cache_data.clear()


def render(df: pd.DataFrame) -> None:
    scrapped = df[df["pipeline_stage"] == "Scrapped"].reset_index(drop=True)

    # ── Header ────────────────────────────────────────────────────
    col1, col2 = st.columns([4, 1])
    with col1:
        st.markdown(f"### 🗑️ Scrap &nbsp; <span style='font-size:0.7em; color:#6B778C; font-weight:400;'>{len(scrapped)} leads</span>", unsafe_allow_html=True)
        st.caption("These leads have been scrapped. You can restore any lead back to 'Found'.")
    with col2:
        if len(scrapped) > 0:
            if st.button("♻️ Restore All", use_container_width=True, type="secondary"):
                full_df = pd.read_csv(CSV_PATH, low_memory=False)
                full_df.loc[full_df["pipeline_stage"] == "Scrapped", "pipeline_stage"] = "Found"
                _save_csv(full_df)
                st.success(f"✅ {len(scrapped)} leads restored!")
                st.rerun()

    if scrapped.empty:
        st.markdown(
            """
            <div style="text-align:center; padding:60px 20px; color:#6B778C;">
              <div style="font-size:3em;">🗑️</div>
              <div style="font-size:1.1em; font-weight:600; margin-top:12px;">Scrap is empty</div>
              <div style="font-size:0.88em; margin-top:6px;">No leads have been scrapped yet.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    st.divider()

    # ── Table header ──────────────────────────────────────────────
    st.markdown(
        """
        <div style="display:grid; grid-template-columns:36px 36px 2fr 2fr 1.5fr 1.2fr 100px;
                    gap:0; padding:6px 10px; background:#F4F5F7;
                    border:1px solid #DFE1E6; border-radius:6px 6px 0 0;
                    font-size:0.76em; font-weight:700; color:#6B778C;
                    letter-spacing:0.05em; text-transform:uppercase;">
          <div>#</div><div>🌡</div><div>Name</div><div>Title · Company</div>
          <div>Location</div><div>Source</div><div>Action</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── Rows ──────────────────────────────────────────────────────
    for i, (_, row) in enumerate(scrapped.iterrows()):
        temp    = row.get("lead_temperature", "")
        name    = row.get("name", "—")
        title   = row.get("title", "—")
        company = row.get("company", "—")
        location= row.get("location", "—")
        source  = row.get("source", "—")

        cols = st.columns([0.3, 0.3, 2, 2, 1.5, 1.2, 1])
        with cols[0]:
            st.markdown(f'<div style="padding:8px 4px; font-size:0.78em; color:#6B778C;">{i+1}</div>', unsafe_allow_html=True)
        with cols[1]:
            st.markdown(f'<div style="padding:8px 0; font-size:1.1em; opacity:0.5;">{TEMP_EMOJI.get(temp,"")}</div>', unsafe_allow_html=True)
        with cols[2]:
            st.markdown(f'<div style="padding:6px 0; font-weight:600; font-size:0.88em; color:#6B778C;">{name}</div>', unsafe_allow_html=True)
        with cols[3]:
            st.markdown(f'<div style="padding:6px 0; font-size:0.82em; color:#97A0AF;">{title}<br><span style="color:#B3BAC5;">{company}</span></div>', unsafe_allow_html=True)
        with cols[4]:
            st.markdown(f'<div style="padding:8px 0; font-size:0.80em; color:#97A0AF;">{location}</div>', unsafe_allow_html=True)
        with cols[5]:
            st.markdown(f'<div style="padding:8px 0; font-size:0.78em; color:#97A0AF;">{source}</div>', unsafe_allow_html=True)
        with cols[6]:
            if st.button("↩ Restore", key=f"restore_{i}_{row.get('profile_url', i)}", use_container_width=True):
                full_df = pd.read_csv(CSV_PATH, low_memory=False)
                mask = full_df["name"] == name
                full_df.loc[mask, "pipeline_stage"] = "Found"
                _save_csv(full_df)
                st.success(f"✅ {name} restored!")
                st.rerun()

    st.markdown(
        f'<div style="padding:6px 10px; background:#F4F5F7; border:1px solid #DFE1E6; '
        f'border-top:none; border-radius:0 0 6px 6px; font-size:0.78em; color:#6B778C;">'
        f'{len(scrapped)} scrapped leads</div>',
        unsafe_allow_html=True,
    )
