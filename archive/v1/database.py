"""
Supabase database interface.
Handles upserts (insert new leads, update existing ones by profile_url).
Schema matches the CSV columns exactly so the dashboard reads live data.
"""

import logging
from typing import Optional
from supabase import create_client, Client

from config import SUPABASE_URL, SUPABASE_KEY

logger = logging.getLogger(__name__)

TABLE_NAME = "leads"


def get_client() -> Optional[Client]:
    if not SUPABASE_URL or not SUPABASE_KEY:
        logger.warning("Supabase credentials not set — DB writes disabled.")
        return None
    try:
        return create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception as exc:
        logger.error(f"[DB] Failed to create Supabase client: {exc}")
        return None


def _prepare_record(lead: dict) -> dict:
    """Sanitize and cast types for Supabase insert."""
    record = {}
    str_fields = [
        "name", "first_name", "title", "company", "location", "profile_url",
        "signal_type", "signal_text", "signal_date", "source",
        "headline", "about_snippet", "background_summary", "skills",
        "post_themes", "post_tone", "recent_notable_post",
        "company_website", "what_they_do", "company_size", "industry",
        "target_customer", "growth_signals", "careers_page_roles",
        "funding_stage", "funding_date", "funding_amount",
        "trigger_event", "trigger_date", "lead_temperature",
        "inferred_pain_points", "pm_value_prop", "suggested_opener",
        "msg_connection_note", "msg_first_dm",
        "msg_followup_day4", "msg_followup_day10",
        "msg_followup_day17", "msg_followup_day25",
        "warm_up_status", "outreach_status", "pipeline_stage",
        "verified", "notes", "scraped_at",
    ]
    int_fields = [
        "quality_score", "msg_word_count_note", "msg_word_count_dm",
        "source_count",
    ]
    for f in str_fields:
        val = lead.get(f, "")
        record[f] = str(val) if val is not None else ""
    for f in int_fields:
        val = lead.get(f, 0)
        try:
            record[f] = int(val)
        except (TypeError, ValueError):
            record[f] = 0
    return record


def upsert_leads(leads: list[dict]) -> int:
    """
    Upsert leads into Supabase.
    Uses profile_url as the conflict key (unique constraint must exist in Supabase).
    Returns number of records upserted.
    """
    client = get_client()
    if not client:
        return 0

    records = [_prepare_record(lead) for lead in leads]
    if not records:
        return 0

    # Batch upserts (Supabase free tier: 500 rows/request is safe)
    BATCH_SIZE = 100
    total_upserted = 0
    for i in range(0, len(records), BATCH_SIZE):
        batch = records[i : i + BATCH_SIZE]
        try:
            response = (
                client.table(TABLE_NAME)
                .upsert(batch, on_conflict="profile_url")
                .execute()
            )
            upserted = len(response.data) if response.data else len(batch)
            total_upserted += upserted
            logger.info(f"[DB] Upserted batch {i // BATCH_SIZE + 1}: {upserted} records")
        except Exception as exc:
            logger.error(f"[DB] Upsert failed for batch {i // BATCH_SIZE + 1}: {exc}")

    logger.info(f"[DB] Total upserted: {total_upserted}")
    return total_upserted


def update_lead_status(profile_url: str, updates: dict) -> bool:
    """Update a single lead's status fields (pipeline_stage, outreach_status, etc.)."""
    client = get_client()
    if not client:
        return False
    try:
        client.table(TABLE_NAME).update(updates).eq("profile_url", profile_url).execute()
        return True
    except Exception as exc:
        logger.error(f"[DB] Update failed for {profile_url}: {exc}")
        return False


def fetch_all_leads() -> list[dict]:
    """Fetch all leads from Supabase (used by dashboard)."""
    client = get_client()
    if not client:
        return []
    try:
        response = client.table(TABLE_NAME).select("*").order("quality_score", desc=True).execute()
        return response.data or []
    except Exception as exc:
        logger.error(f"[DB] Fetch failed: {exc}")
        return []


def create_table_if_not_exists() -> None:
    """
    Print the SQL to create the leads table in Supabase.
    Run this once in the Supabase SQL editor.
    """
    sql = """
-- Run this once in Supabase SQL Editor → New Query

CREATE TABLE IF NOT EXISTS leads (
    id                    BIGSERIAL PRIMARY KEY,
    name                  TEXT,
    first_name            TEXT,
    title                 TEXT,
    company               TEXT,
    location              TEXT,
    profile_url           TEXT UNIQUE,
    signal_type           TEXT,
    signal_text           TEXT,
    signal_date           TEXT,
    source                TEXT,
    headline              TEXT,
    about_snippet         TEXT,
    background_summary    TEXT,
    skills                TEXT,
    post_themes           TEXT,
    post_tone             TEXT,
    recent_notable_post   TEXT,
    company_website       TEXT,
    what_they_do          TEXT,
    company_size          TEXT,
    industry              TEXT,
    target_customer       TEXT,
    growth_signals        TEXT,
    careers_page_roles    TEXT,
    funding_stage         TEXT,
    funding_date          TEXT,
    funding_amount        TEXT,
    trigger_event         TEXT,
    trigger_date          TEXT,
    lead_temperature      TEXT,
    inferred_pain_points  TEXT,
    pm_value_prop         TEXT,
    suggested_opener      TEXT,
    msg_connection_note   TEXT,
    msg_first_dm          TEXT,
    msg_followup_day4     TEXT,
    msg_followup_day10    TEXT,
    msg_followup_day17    TEXT,
    msg_followup_day25    TEXT,
    warm_up_status        TEXT DEFAULT 'Not started',
    outreach_status       TEXT DEFAULT 'Not contacted',
    pipeline_stage        TEXT DEFAULT 'Found',
    verified              TEXT DEFAULT '',
    notes                 TEXT DEFAULT '',
    quality_score         INTEGER DEFAULT 0,
    source_count          INTEGER DEFAULT 1,
    msg_word_count_note   INTEGER DEFAULT 0,
    msg_word_count_dm     INTEGER DEFAULT 0,
    scraped_at            TEXT,
    created_at            TIMESTAMPTZ DEFAULT NOW(),
    updated_at            TIMESTAMPTZ DEFAULT NOW()
);

-- Enable Row Level Security (keep data private)
ALTER TABLE leads ENABLE ROW LEVEL SECURITY;

-- Allow all operations for authenticated users (your Streamlit app)
CREATE POLICY "Allow all for authenticated" ON leads
    FOR ALL USING (true);
"""
    print("\n" + "=" * 60)
    print("SUPABASE SETUP — Run this SQL in your Supabase SQL editor:")
    print("=" * 60)
    print(sql)
    print("=" * 60 + "\n")
