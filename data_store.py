"""
DataStore — single data access layer.
Reads/writes Neon Postgres. Falls back to CSV if DATABASE_URL is not set.
"""
from __future__ import annotations

import csv
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")
logger = logging.getLogger(__name__)

# ── Lead lifecycle stage ─────────────────────────────────────────────────────

LEAD_STAGES = [
    "new", "qualified", "enriched", "personalized",
    "message_ready", "contacted", "replied",
    "meeting_booked", "closed", "skipped",
]

# Stage auto-detection priority (pipeline outputs set stage automatically)
def compute_lead_stage(lead: dict) -> str:
    """
    Auto-detect lifecycle stage from pipeline fields.
    Manual override wins if lead_stage is already set to a valid value.

    Auto-detection order (most → least advanced):
      meeting_booked  status==meeting_booked
      replied         status==replied | pipeline_stage=Replied/Interested
      contacted       status==connection_sent/accepted | pipeline_stage=Request Sent+
      message_ready   msg_connection_note present           (generate_messages complete)
      personalized    hook or pain_point present             (personalize.py complete)
      enriched        company_description or what_they_do    (enrich_leads.py complete)
      qualified       icp_score >= 70                        (icp_filter complete)
      skipped         status==skipped or pipeline_stage=Rejected
      new             fallback
    """
    stored = str(lead.get("lead_stage") or "").strip().lower()
    if stored in LEAD_STAGES:
        return stored

    status = str(lead.get("status") or "").lower().strip()
    ps     = str(lead.get("pipeline_stage") or "").lower().strip()

    if status == "meeting_booked" or ps in ("interested",):
        return "meeting_booked"
    if status == "replied" or ps in ("replied",):
        return "replied"
    if status in ("connection_sent", "accepted") or ps in ("request sent", "connected", "msg sent"):
        return "contacted"
    if status in ("closed", "skipped") or ps in ("rejected",):
        return "skipped"

    # Pipeline outputs
    cr = str(lead.get("msg_connection_note") or lead.get("connection_request") or "").strip()
    if cr and cr.lower() not in ("nan", "none", ""):
        return "message_ready"

    hook = str(lead.get("hook") or lead.get("pain_point") or lead.get("relevance") or "").strip()
    if hook and hook.lower() not in ("nan", "none", ""):
        return "personalized"

    for f in ("company_description", "what_they_do", "about_snippet"):
        val = str(lead.get(f) or "").strip()
        if val and val.lower() not in ("nan", "none", "{}", ""):
            return "enriched"

    icp = int(lead.get("icp_score") or lead.get("quality_score") or 0)
    if icp >= 70:
        return "qualified"

    return "new"


def update_lead_stage(profile_url: str, stage: str) -> None:
    """Persist a manual lead_stage override."""
    if stage not in LEAD_STAGES:
        raise ValueError(f"Invalid lead_stage: {stage}")
    if _db_available():
        _db_update_field(profile_url, "lead_stage", stage)
    else:
        _csv_update_field(profile_url, "lead_stage", stage)


# ── Priority scoring ─────────────────────────────────────────────────────────

def compute_priority_score(lead: dict) -> int:
    """
    Priority formula:
      icp_score * 0.5  (0–50 pts)
      hiring_signal    (0–15 pts)
      funding_signal   (0–10 pts)
      persona_weight   (0–10 pts)
      recent_activity  (0–5 pts)
    → capped at 100
    """
    score = 0.0

    icp = min(int(lead.get("icp_score") or lead.get("quality_score") or 0), 100)
    score += icp * 0.5

    pm_ev = str(lead.get("pm_hiring_evidence") or "").lower()
    sig   = str(lead.get("signal_text") or "").lower()
    pm_kw = ["project manager", "scrum master", " pm ", "product manager", "program manager"]
    if any(kw in pm_ev + sig for kw in pm_kw):
        score += 15

    funding = str(lead.get("funding_stage") or "").lower()
    if any(f in funding for f in ["seed", "series a", "series b", "series c", "pre-seed", "preseed"]):
        score += 10

    title = str(lead.get("title") or lead.get("headline") or "").lower()
    if any(t in title for t in ["founder", "ceo", "co-founder", "cofounder", "chief executive"]):
        score += 10
    elif any(t in title for t in ["cto", "vp engineering", "vp of engineering",
                                   "head of engineering", "head of product",
                                   "chief technology", "chief technical"]):
        score += 7
    elif any(t in title for t in ["director", "engineering manager", "managing director"]):
        score += 5

    if str(lead.get("post_themes") or "").strip() or str(lead.get("recent_notable_post") or "").strip():
        score += 5

    return min(int(round(score)), 100)

DATABASE_URL = os.getenv("DATABASE_URL", "")
CSV_PATH     = Path(__file__).parent / "output" / "leads.csv"

# ── Lazy Neon connection ─────────────────────────────────────────────────────

_conn = None


def _get_conn():
    global _conn
    if _conn is None or _conn.closed:
        import psycopg2
        _conn = psycopg2.connect(DATABASE_URL, connect_timeout=5)
        _conn.autocommit = False
    return _conn


def _db_available() -> bool:
    return bool(DATABASE_URL)


# ── Public API ───────────────────────────────────────────────────────────────

def get_leads(filters: dict | None = None) -> list[dict]:
    """
    Return all leads, optionally filtered.
    filters keys: pipeline_stage, enrichment_status, source, icp_score_min
    """
    if _db_available():
        return _db_get_leads(filters)
    return _csv_get_leads(filters)


def upsert_lead(lead: dict) -> dict:
    """Insert or update a lead by profile_url. Returns the saved lead dict."""
    if _db_available():
        return _db_upsert_lead(lead)
    return _csv_upsert_lead(lead)


def update_stage(profile_url: str, stage: str) -> None:
    """Move a lead to a new pipeline stage."""
    if _db_available():
        _db_update_stage(profile_url, stage)
    else:
        _csv_update_stage(profile_url, stage)


def update_lead_status(profile_url: str, status: str) -> None:
    """Set the outreach status of a lead (new/connection_sent/accepted/replied/meeting_booked/closed)."""
    if _db_available():
        _db_update_field(profile_url, "status", status)
    else:
        _csv_update_field(profile_url, "status", status)


def get_pipeline_runs() -> list[dict]:
    """Return summary rows for each distinct pipeline run_id."""
    leads = get_leads()
    if not leads:
        return []
    runs: dict[str, dict] = {}
    for lead in leads:
        rid = lead.get("run_id") or "legacy"
        if rid not in runs:
            runs[rid] = {
                "run_id":               rid,
                "pipeline_name":        lead.get("pipeline_name") or ("Legacy Import" if rid == "legacy" else rid),
                "generation_timestamp": lead.get("generation_timestamp") or lead.get("created_at") or "",
                "source_query":         lead.get("source_query") or "",
                "pipeline_version":     lead.get("pipeline_version") or "v1",
                "leads_generated":      0,
                "qualified":            0,
                "enriched":             0,
                "messages_generated":   0,
            }
        runs[rid]["leads_generated"] += 1
        if (lead.get("icp_score") or 0) >= 70:
            runs[rid]["qualified"] += 1
        if lead.get("enrichment_status") in ("ready", "enriched", "done"):
            runs[rid]["enriched"] += 1
        if lead.get("msg_connection_note"):
            runs[rid]["messages_generated"] += 1
    return sorted(runs.values(), key=lambda r: r.get("generation_timestamp") or "", reverse=True)


def get_leads_by_run(run_id: str) -> list[dict]:
    """Return all leads belonging to a specific pipeline run."""
    leads = get_leads()
    target = None if run_id == "legacy" else run_id
    return [
        l for l in leads
        if (l.get("run_id") or "legacy") == (run_id)
    ]


def get_lead_by_url(profile_url: str) -> dict | None:
    leads = get_leads()
    for lead in leads:
        if lead.get("profile_url") == profile_url:
            return lead
    return None


# ── Neon Postgres implementation ─────────────────────────────────────────────

def _db_get_leads(filters: dict | None) -> list[dict]:
    conn = _get_conn()
    cur  = conn.cursor()
    where_clauses = []
    params: list[Any] = []

    if filters:
        if "pipeline_stage" in filters:
            where_clauses.append("pipeline_stage = %s")
            params.append(filters["pipeline_stage"])
        if "enrichment_status" in filters:
            where_clauses.append("enrichment_status = %s")
            params.append(filters["enrichment_status"])
        if "source" in filters:
            where_clauses.append("source = %s")
            params.append(filters["source"])
        if "icp_score_min" in filters:
            where_clauses.append("icp_score >= %s")
            params.append(filters["icp_score_min"])

    where = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""
    cur.execute(f"SELECT * FROM leads {where} ORDER BY icp_score DESC NULLS LAST", params)
    cols = [desc[0] for desc in cur.description]
    rows = cur.fetchall()
    cur.close()
    return [dict(zip(cols, row)) for row in rows]


def _db_upsert_lead(lead: dict) -> dict:
    conn = _get_conn()
    cur  = conn.cursor()

    lead = dict(lead)
    lead["updated_at"] = datetime.now(timezone.utc).isoformat()

    # JSON-serialize dict/list fields
    for field in ("scrapin_profile_json", "posts_data"):
        if field in lead and not isinstance(lead[field], str):
            lead[field] = json.dumps(lead[field]) if lead[field] else None

    cols   = list(lead.keys())
    values = [lead[c] for c in cols]
    placeholders = ", ".join(["%s"] * len(cols))
    col_names    = ", ".join(cols)
    updates      = ", ".join(f"{c} = EXCLUDED.{c}" for c in cols if c not in ("id", "profile_url", "created_at"))

    sql = f"""
        INSERT INTO leads ({col_names})
        VALUES ({placeholders})
        ON CONFLICT (profile_url) DO UPDATE SET {updates}
        RETURNING *
    """
    cur.execute(sql, values)
    conn.commit()
    cols_out = [desc[0] for desc in cur.description]
    row = cur.fetchone()
    cur.close()
    return dict(zip(cols_out, row))


def _db_update_stage(profile_url: str, stage: str) -> None:
    conn = _get_conn()
    cur  = conn.cursor()
    cur.execute(
        "UPDATE leads SET pipeline_stage = %s, updated_at = %s WHERE profile_url = %s",
        (stage, datetime.now(timezone.utc), profile_url),
    )
    conn.commit()
    cur.close()


def _db_update_field(profile_url: str, field: str, value: str) -> None:
    conn = _get_conn()
    cur  = conn.cursor()
    cur.execute(
        f"UPDATE leads SET {field} = %s, updated_at = %s WHERE profile_url = %s",
        (value, datetime.now(timezone.utc), profile_url),
    )
    conn.commit()
    cur.close()


# ── CSV fallback implementation ──────────────────────────────────────────────

def _load_csv() -> pd.DataFrame:
    if CSV_PATH.exists():
        return pd.read_csv(CSV_PATH, dtype=str).fillna("")
    return pd.DataFrame()


def _save_csv(df: pd.DataFrame) -> None:
    try:
        df.to_csv(CSV_PATH, index=False)
    except Exception as e:
        raise RuntimeError(f"[DataStore] CSV save failed: {e}") from e


def _csv_get_leads(filters: dict | None) -> list[dict]:
    df = _load_csv()
    if df.empty:
        return []
    if "status" not in df.columns:
        df["status"] = "new"
    if filters:
        if "pipeline_stage" in filters:
            df = df[df["pipeline_stage"] == filters["pipeline_stage"]]
        if "enrichment_status" in filters:
            df = df[df["enrichment_status"] == filters["enrichment_status"]]
        if "source" in filters:
            df = df[df["source"] == filters["source"]]
        if "icp_score_min" in filters:
            df = df[pd.to_numeric(df.get("icp_score", 0), errors="coerce").fillna(0) >= filters["icp_score_min"]]
        if "status" in filters:
            df = df[df["status"] == filters["status"]]
        if "priority_score_min" in filters:
            pass  # applied below after computing
    if "lead_stage" not in df.columns:
        df["lead_stage"] = ""
    rows = df.to_dict("records")
    # Compute derived fields for leads that don't have them
    result = []
    for r in rows:
        if not r.get("priority_score"):
            r["priority_score"] = compute_priority_score(r)
        # Always recompute lead_stage so pipeline outputs are reflected
        stored = str(r.get("lead_stage") or "").strip().lower()
        if stored not in LEAD_STAGES:
            r["lead_stage"] = compute_lead_stage(r)
        result.append(r)
    if filters:
        if "priority_score_min" in filters:
            result = [r for r in result if r.get("priority_score", 0) >= filters["priority_score_min"]]
        if "lead_stage" in filters:
            result = [r for r in result if r.get("lead_stage") == filters["lead_stage"]]
    return result


def _csv_upsert_lead(lead: dict) -> dict:
    df   = _load_csv()
    purl = lead.get("profile_url", "")
    if purl and not df.empty and purl in df["profile_url"].values:
        idx = df.index[df["profile_url"] == purl][0]
        for k, v in lead.items():
            df.at[idx, k] = v
    else:
        df = pd.concat([df, pd.DataFrame([lead])], ignore_index=True)
    _save_csv(df)
    return lead


def _csv_update_stage(profile_url: str, stage: str) -> None:
    df = _load_csv()
    if df.empty:
        return
    mask = df["profile_url"] == profile_url
    df.loc[mask, "pipeline_stage"] = stage
    _save_csv(df)


def _csv_update_field(profile_url: str, field: str, value: str) -> None:
    df = _load_csv()
    if df.empty:
        return
    if field not in df.columns:
        df[field] = ""
    mask = df["profile_url"] == profile_url
    df.loc[mask, field] = value
    _save_csv(df)
