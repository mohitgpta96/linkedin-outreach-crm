"""
Universal filter engine — clickable metric cards → filtered lead table.

Usage:
    from dashboard.utils.filter_engine import set_filter, apply_filter, get_active_filter, clear_filter
"""
from __future__ import annotations

import pandas as pd
import streamlit as st


# ── Filter label registry ─────────────────────────────────────────────────────

FILTER_LABELS: dict[str, str] = {
    "all":           "All Leads",
    "qualified":     "Qualified Leads (ICP ≥ 70)",
    "enriched":      "Enriched Leads",
    "message_ready": "Messages Ready",
    "contacted":     "Outreach Sent",
    "replied":       "Replied",
    "meeting_booked":"Meetings Booked",
    "hot":           "Hot Leads",
    "warm":          "Warm Leads",
    "cold":          "Cold Leads",
    "high_priority": "High Priority (Score ≥ 80)",
    "pm_gap":        "PM Gap Leads",
}


# ── State helpers ─────────────────────────────────────────────────────────────

def set_filter(filter_type: str, label: str | None = None) -> None:
    """Set active filter and navigate to All Leads page."""
    st.session_state["dashboard_filter"]       = filter_type
    st.session_state["dashboard_filter_label"] = label or FILTER_LABELS.get(filter_type, filter_type)
    st.session_state["page"]    = "All Leads"
    st.session_state["lt_page"] = 1  # reset pagination


def clear_filter() -> None:
    """Clear active filter, stay on current page."""
    st.session_state.pop("dashboard_filter",       None)
    st.session_state.pop("dashboard_filter_label", None)
    st.session_state["lt_page"] = 1


def get_active_filter() -> tuple[str | None, str | None]:
    """Return (filter_type, label) of the currently active filter."""
    return (
        st.session_state.get("dashboard_filter"),
        st.session_state.get("dashboard_filter_label"),
    )


# ── Filter application ────────────────────────────────────────────────────────

def apply_filter(df: pd.DataFrame) -> pd.DataFrame:
    """Apply st.session_state['dashboard_filter'] to df and return a copy."""
    filter_type = st.session_state.get("dashboard_filter")
    if not filter_type or filter_type == "all":
        return df

    score_col = (
        "icp_score"
        if "icp_score" in df.columns and pd.to_numeric(df["icp_score"], errors="coerce").fillna(0).sum() > 0
        else "quality_score"
    )
    scores   = pd.to_numeric(df.get(score_col,      pd.Series(dtype=float)), errors="coerce").fillna(0)
    priority = pd.to_numeric(df.get("priority_score", pd.Series(dtype=float)), errors="coerce").fillna(0)

    if filter_type == "qualified":
        return df[scores >= 70].copy()

    if filter_type == "enriched":
        if "enrichment_status" in df.columns:
            return df[df["enrichment_status"].isin(["ready", "enriched", "done"])].copy()
        return df.copy()

    if filter_type == "message_ready":
        if "msg_connection_note" in df.columns:
            mask = df["msg_connection_note"].apply(
                lambda x: bool(str(x).strip() and str(x).strip().lower() not in ("nan", "none", ""))
            )
            return df[mask].copy()
        return df.copy()

    if filter_type == "contacted":
        if "status" in df.columns:
            return df[df["status"].isin(
                ["connection_sent", "accepted", "replied", "meeting_booked", "closed"]
            )].copy()
        return df.copy()

    if filter_type == "replied":
        if "status" in df.columns:
            return df[df["status"].isin(["replied", "meeting_booked", "closed"])].copy()
        return df.copy()

    if filter_type == "meeting_booked":
        if "status" in df.columns:
            return df[df["status"] == "meeting_booked"].copy()
        return df.copy()

    if filter_type == "hot":
        if "lead_temperature" in df.columns:
            return df[df["lead_temperature"] == "Hot"].copy()
        return df.copy()

    if filter_type == "warm":
        if "lead_temperature" in df.columns:
            return df[df["lead_temperature"] == "Warm"].copy()
        return df.copy()

    if filter_type == "cold":
        if "lead_temperature" in df.columns:
            return df[df["lead_temperature"] == "Cold"].copy()
        return df.copy()

    if filter_type == "high_priority":
        return df[priority >= 80].copy()

    if filter_type == "pm_gap":
        if "pm_gap_signal" in df.columns:
            return df[df["pm_gap_signal"].isin([True, "True", "true", 1, "1"])].copy()
        return df.copy()

    # Dynamic: "source:YC"
    if filter_type.startswith("source:"):
        src = filter_type[7:]
        if "source" in df.columns:
            return df[df["source"] == src].copy()
        return df.copy()

    # Dynamic: "location:United States"
    if filter_type.startswith("location:"):
        loc = filter_type[9:]
        if "location" in df.columns:
            return df[df["location"].str.contains(loc, case=False, na=False)].copy()
        return df.copy()

    # Dynamic: "icp_gte:80"
    if filter_type.startswith("icp_gte:"):
        threshold = int(filter_type[8:])
        return df[scores >= threshold].copy()

    return df.copy()
