"""
Enrichment Queue — Shows leads pending Scrapin.io enrichment.
Displays: pending count, credits estimate, "Run Enrichment" trigger button.
"""
import streamlit as st
import pandas as pd
import subprocess
import sys
from pathlib import Path


def render(df: pd.DataFrame) -> None:
    st.title("⚡ Enrichment Queue")

    if df.empty:
        st.info("No leads loaded.")
        return

    # Identify pending leads
    status_col = "enrichment_status" if "enrichment_status" in df.columns else None
    stage_col  = "pipeline_stage"   if "pipeline_stage"   in df.columns else None

    if status_col:
        pending = df[df[status_col].isin(["pending", "migrated", ""])]
    elif stage_col:
        pending = df[df[stage_col].isin(["Found", "ICP Candidate"])]
    else:
        pending = df.copy()

    enriched = df[df.get("enrichment_status", pd.Series(dtype=str)).isin(["enriched", "ready"])] if status_col else pd.DataFrame()

    # ── Stats row ────────────────────────────────────────────────────────────
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Leads",   len(df))
    c2.metric("Pending",       len(pending))
    c3.metric("Enriched",      len(enriched))
    c4.metric("Credits Est.",  f"~{len(pending) * 3}")

    st.markdown("---")

    # ── Pending table ─────────────────────────────────────────────────────────
    st.subheader(f"Pending Enrichment ({len(pending)} leads)")

    if pending.empty:
        st.success("All leads are enriched!")
    else:
        # Show top 50 pending
        show_cols = [c for c in ["name", "company", "location", "source", "icp_score", "quality_score", "icp_signal_type", "pipeline_stage"] if c in pending.columns]
        st.dataframe(
            pending[show_cols].head(50),
            use_container_width=True,
            height=300,
        )

    st.markdown("---")

    # ── Run Enrichment button ─────────────────────────────────────────────────
    st.subheader("Run Enrichment")

    limit = st.number_input("Max leads to enrich", min_value=1, max_value=50, value=10)
    credits_est = limit * 3

    st.info(
        f"This will enrich **{limit} leads** using Scrapin.io. "
        f"Estimated cost: **~{credits_est} credits** (3 per lead).\n\n"
        f"Make sure `SCRAPIN_API_KEY` is set in `.env` before running."
    )

    col1, col2 = st.columns([1, 3])
    with col1:
        run_test = st.button("Run Test (1 lead)", type="secondary", use_container_width=True)
    with col2:
        run_full = st.button(f"Run Enrichment ({limit} leads)", type="primary", use_container_width=True)

    if run_test or run_full:
        script = Path(__file__).parent.parent.parent / "scripts" / "scrapin_enrich.py"
        cmd    = [sys.executable, str(script)]
        if run_test:
            cmd.append("--test")
        else:
            cmd.extend(["--limit", str(limit)])

        with st.spinner("Running enrichment..."):
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
                if result.returncode == 0:
                    st.success("Enrichment complete!")
                    st.code(result.stdout[-2000:] if result.stdout else "(no output)")
                    st.cache_data.clear()
                    st.rerun()
                else:
                    st.error("Enrichment failed")
                    st.code(result.stderr[-2000:] if result.stderr else "(no stderr)")
            except subprocess.TimeoutExpired:
                st.error("Enrichment timed out (5 min limit)")
            except Exception as e:
                st.error(f"Error: {e}")
