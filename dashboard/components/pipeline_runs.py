"""
📊 Pipeline Runs — track every pipeline run, click to drill into its leads.
Parts 4 + 5 of the dashboard upgrade.
"""
from __future__ import annotations

import math
import pandas as pd
import streamlit as st


def _s(val) -> str:
    if val is None:
        return ""
    if isinstance(val, float) and math.isnan(val):
        return ""
    s = str(val).strip()
    return "" if s.lower() in ("nan", "none", "") else s


def _badge(text: str, bg: str, fg: str) -> str:
    return (
        f'<span style="background:{bg}; color:{fg}; font-size:11px; font-weight:600; '
        f'padding:2px 8px; border-radius:12px; white-space:nowrap;">{text}</span>'
    )


def _pct(a: int, b: int) -> str:
    if b == 0:
        return "—"
    return f"{round(a / b * 100)}%"


# ── Run detail drill-down ─────────────────────────────────────────────────────

def _render_run_detail(run: dict, df: pd.DataFrame) -> None:
    rid = run["run_id"]
    run_leads = df[
        (df.get("run_id", pd.Series(["legacy"] * len(df))).fillna("legacy") == rid)
    ] if "run_id" in df.columns else df[df.index >= 0]

    st.markdown(f"""
    <div style="background:#FFFFFF; border:1px solid #E2E8F0; border-radius:12px;
                padding:20px 24px; margin-bottom:20px;">
        <div style="font-size:16px; font-weight:700; color:#0F172A; margin-bottom:4px;">
            📦 {run['pipeline_name']}
        </div>
        <div style="font-size:12px; color:#94A3B8;">
            Run ID: <code style="background:#F1F5F9; padding:2px 6px; border-radius:4px;">{rid}</code>
            &nbsp;·&nbsp; {_s(run.get('generation_timestamp', ''))[:19].replace('T', ' ')}
            &nbsp;·&nbsp; v{_s(run.get('pipeline_version','1'))}
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Stats
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Leads",    run.get("leads_generated", 0))
    c2.metric("ICP Qualified",  run.get("qualified", 0),       delta=_pct(run.get("qualified",0), run.get("leads_generated",1)))
    c3.metric("Enriched",       run.get("enriched", 0))
    c4.metric("Messages Ready", run.get("messages_generated",0))

    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)

    if run_leads.empty:
        st.info("No leads found for this run.")
        return

    # Show leads table
    st.markdown(f'<div style="font-size:13px; font-weight:600; color:#1E293B; margin-bottom:8px;">{len(run_leads)} leads in this run</div>', unsafe_allow_html=True)
    cols_show = [c for c in ["name","title","company","location","icp_score","priority_score","status","pipeline_stage","source"] if c in run_leads.columns]
    st.dataframe(run_leads[cols_show].reset_index(drop=True), use_container_width=True, height=320)


# ── Main render ───────────────────────────────────────────────────────────────

def render(df: pd.DataFrame) -> None:
    st.markdown("""
    <div style="margin-bottom:24px;">
        <div style="font-size:22px; font-weight:700; color:#0F172A; letter-spacing:-0.02em;">
            📊 Pipeline Runs
        </div>
        <div style="font-size:13px; color:#94A3B8; margin-top:4px;">
            Every pipeline run · click a run to inspect its leads
        </div>
    </div>
    """, unsafe_allow_html=True)

    try:
        from data_store import get_pipeline_runs
        runs = get_pipeline_runs()
    except Exception as e:
        st.error(f"Could not load pipeline runs: {e}")
        runs = []

    if not runs:
        st.info("No pipeline runs yet. Once you run the pipeline, each batch will appear here.")
        _render_how_runs_work()
        return

    # ── Summary metrics ───────────────────────────────────────
    total_runs     = len(runs)
    total_leads    = sum(r.get("leads_generated", 0) for r in runs)
    total_messages = sum(r.get("messages_generated", 0) for r in runs)

    c1, c2, c3 = st.columns(3)
    c1.metric("Total Runs",     total_runs)
    c2.metric("Leads Generated", total_leads)
    c3.metric("Messages Ready", total_messages)

    st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)

    # ── Runs table ────────────────────────────────────────────
    st.markdown("""
    <div style="display:grid; grid-template-columns:220px 1fr 80px 80px 80px 80px;
                gap:0; padding:10px 12px;
                background:#F8FAFC; border:1px solid #E2E8F0; border-radius:10px 10px 0 0;
                font-size:10.5px; font-weight:700; color:#94A3B8;
                letter-spacing:0.07em; text-transform:uppercase;">
        <div>Run ID</div><div>Pipeline Name</div>
        <div>Leads</div><div>Qualified</div><div>Enriched</div><div>Messages</div>
    </div>
    """, unsafe_allow_html=True)

    selected_run = st.session_state.get("selected_run_id")

    for run in runs:
        rid   = run["run_id"]
        name  = _s(run.get("pipeline_name")) or rid
        ts    = _s(run.get("generation_timestamp", ""))[:19].replace("T", " ")
        total = run.get("leads_generated", 0)
        qual  = run.get("qualified", 0)
        enr   = run.get("enriched", 0)
        msgs  = run.get("messages_generated", 0)
        is_legacy = (rid == "legacy")

        cs = st.columns([2.0, 3.5, 0.7, 0.7, 0.7, 0.7])
        with cs[0]:
            code_bg = "#EEF2FF" if rid == selected_run else "#F8FAFC"
            ts_span = f'<br><span style="font-size:10px; color:#94A3B8;">{ts}</span>' if ts else ""
            st.markdown(
                f'<div style="padding:10px 4px;">'
                f'<code style="background:{code_bg}; color:#6366F1; font-size:11px; '
                f'padding:2px 6px; border-radius:4px;">{rid}</code>'
                f'{ts_span}'
                f'</div>',
                unsafe_allow_html=True,
            )
        with cs[1]:
            legacy_badge = '<span style="margin-left:6px; background:#EEF2FF; color:#6366F1; font-size:10px; padding:1px 6px; border-radius:8px;">legacy</span>' if is_legacy else ""
            st.markdown(
                f'<div style="padding:12px 4px; font-size:13px; color:#1E293B; font-weight:500;">'
                f'{name}{legacy_badge}'
                f'</div>',
                unsafe_allow_html=True,
            )
        for col_i, val in zip(cs[2:], [total, qual, enr, msgs]):
            with col_i:
                st.markdown(f'<div style="padding:12px 4px; font-size:13px; color:#0F172A; font-weight:600;">{val}</div>', unsafe_allow_html=True)

        # Drill-down button (small)
        btn_col = st.columns([4.5, 1])[1]
        with btn_col:
            if st.button("View →", key=f"run_drill_{rid}", use_container_width=True):
                if st.session_state.get("selected_run_id") == rid:
                    st.session_state.pop("selected_run_id", None)
                else:
                    st.session_state["selected_run_id"] = rid
                st.rerun()

        st.markdown('<div style="height:1px; background:#F1F5F9;"></div>', unsafe_allow_html=True)

    st.markdown(
        f'<div style="padding:8px 12px; background:#F8FAFC; border:1px solid #E2E8F0; '
        f'border-top:none; border-radius:0 0 10px 10px; font-size:11.5px; color:#94A3B8;">'
        f'{total_runs} run{"s" if total_runs != 1 else ""}</div>',
        unsafe_allow_html=True,
    )

    # ── Drill-down ────────────────────────────────────────────
    if selected_run:
        st.markdown(f"<div style='height:24px'></div>", unsafe_allow_html=True)
        st.markdown(f"<hr style='border-color:#E2E8F0; margin:0;'>", unsafe_allow_html=True)
        st.markdown(f"<div style='height:20px'></div>", unsafe_allow_html=True)
        run_obj = next((r for r in runs if r["run_id"] == selected_run), None)
        if run_obj:
            _render_run_detail(run_obj, df)

    _render_how_runs_work()


def _render_how_runs_work() -> None:
    with st.expander("📖 How Pipeline Run Tracking Works", expanded=False):
        st.markdown("""
        Every time you run the pipeline, each generated lead gets tagged with:

        | Field | Example | Description |
        |-------|---------|-------------|
        | `run_id` | `20260312_1430_pipeline` | Unique run identifier |
        | `pipeline_name` | `YC W26 Batch` | Human-readable name |
        | `generation_timestamp` | `2026-03-12T14:30:00Z` | When the run happened |
        | `source_query` | `YC batch=W26, size<50` | What query was used |
        | `pipeline_version` | `v2` | Which pipeline version ran |

        **To tag leads with a run_id**, generate a run_id in your pipeline script:
        ```python
        from datetime import datetime
        run_id = datetime.now().strftime("%Y%m%d_%H%M") + "_pipeline"
        lead["run_id"]               = run_id
        lead["pipeline_name"]        = "YC W26 Batch"
        lead["generation_timestamp"] = datetime.now().isoformat()
        lead["source_query"]         = "YC batch=W26"
        lead["pipeline_version"]     = "v2"
        ```

        Existing leads without `run_id` appear under the **legacy** run.
        """)
