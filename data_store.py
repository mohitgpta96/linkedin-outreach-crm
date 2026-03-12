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
    if filters:
        if "pipeline_stage" in filters:
            df = df[df["pipeline_stage"] == filters["pipeline_stage"]]
        if "enrichment_status" in filters:
            df = df[df["enrichment_status"] == filters["enrichment_status"]]
        if "source" in filters:
            df = df[df["source"] == filters["source"]]
        if "icp_score_min" in filters:
            df = df[pd.to_numeric(df.get("icp_score", 0), errors="coerce").fillna(0) >= filters["icp_score_min"]]
    return df.to_dict("records")


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
