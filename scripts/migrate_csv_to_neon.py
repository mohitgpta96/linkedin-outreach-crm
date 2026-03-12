#!/usr/bin/env python3
"""
migrate_csv_to_neon.py — Migrate leads.csv → Neon Postgres
- Renames: msg_followup_day4→day7, day10→day14, day17→day21, day25→day28
- Skips leads with NULL profile_url
- Casts icp_score (quality_score) float → int
- Idempotent: uses ON CONFLICT(profile_url) DO UPDATE

Usage:
    python3 scripts/migrate_csv_to_neon.py          # dry run (print stats)
    python3 scripts/migrate_csv_to_neon.py --apply  # actually insert
"""
import argparse
import os
import sys
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

DATABASE_URL = os.getenv("DATABASE_URL", "")
CSV_PATH     = Path(__file__).parent.parent / "output" / "leads.csv"

# Column rename map: CSV name → DB column name
RENAME = {
    "msg_followup_day4":  "msg_followup_day7",
    "msg_followup_day10": "msg_followup_day14",
    "msg_followup_day17": "msg_followup_day21",
    "msg_followup_day25": "msg_followup_day28",
    "quality_score":      "icp_score",
    "title":              "founder_name",
}

# DB columns we actually want (subset of what's in leads.csv)
DB_COLS = [
    "profile_url", "founder_name", "first_name", "company_name", "linkedin_url",
    "company_url", "headline", "about", "location", "industry",
    "employee_count", "icp_score", "icp_signal_type", "signal_text", "source",
    "pain_points", "msg_connection_note", "msg_first_dm",
    "msg_followup_day7", "msg_followup_day14", "msg_followup_day21", "msg_followup_day28",
    "pipeline_stage", "enrichment_status",
]


def build_rows(df: pd.DataFrame) -> list[dict]:
    """Transform CSV rows into DB-ready dicts."""
    rows = []
    skipped = 0
    for _, row in df.iterrows():
        purl = str(row.get("profile_url", "")).strip()
        if not purl or purl in ("nan", ""):
            skipped += 1
            continue

        # Map CSV columns to DB columns
        r: dict = {}
        r["profile_url"]      = purl
        r["founder_name"]     = str(row.get("name", "")).strip() or None
        r["first_name"]       = str(row.get("first_name", "")).strip() or None
        r["company_name"]     = str(row.get("company", "")).strip() or None
        r["linkedin_url"]     = purl  # profile_url IS the LinkedIn URL in CSV
        r["company_url"]      = str(row.get("company_website", "")).strip() or None
        r["headline"]         = str(row.get("headline", "")).strip() or None
        r["about"]            = str(row.get("about_snippet", "")).strip() or None
        r["location"]         = str(row.get("location", "")).strip() or None
        r["industry"]         = str(row.get("industry", "")).strip() or None
        raw_signal = str(row.get("signal_type", "")).strip()
        r["icp_signal_type"]  = raw_signal if raw_signal in ("A", "B", "AB") else None
        r["signal_text"]      = str(row.get("signal_text", "")).strip() or None
        r["source"]           = str(row.get("source", "")).strip() or None
        r["pain_points"]      = str(row.get("inferred_pain_points", "")).strip() or None
        r["msg_connection_note"]  = str(row.get("msg_connection_note", "")).strip() or None
        r["msg_first_dm"]         = str(row.get("msg_first_dm", "")).strip() or None
        r["msg_followup_day7"]    = str(row.get("msg_followup_day4", "")).strip() or None
        r["msg_followup_day14"]   = str(row.get("msg_followup_day10", "")).strip() or None
        r["msg_followup_day21"]   = str(row.get("msg_followup_day17", "")).strip() or None
        r["msg_followup_day28"]   = str(row.get("msg_followup_day25", "")).strip() or None
        r["pipeline_stage"]       = str(row.get("pipeline_stage", "Found")).strip() or "Found"
        r["enrichment_status"]    = "migrated"

        # Employee count
        size_str = str(row.get("company_size", "")).strip()
        try:
            # "10-50 employees" → take midpoint
            nums = [int(x) for x in size_str.replace("+", "").split("-") if x.strip().isdigit()]
            r["employee_count"] = int(sum(nums) / len(nums)) if nums else None
        except Exception:
            r["employee_count"] = None

        # icp_score (was quality_score float)
        try:
            r["icp_score"] = int(float(str(row.get("quality_score", 0))))
        except Exception:
            r["icp_score"] = None

        rows.append(r)

    print(f"  Rows ready: {len(rows)} | Skipped (no URL): {skipped}")
    return rows


def create_schema(conn) -> None:
    """Create leads table if it doesn't exist."""
    sql = """
    CREATE TABLE IF NOT EXISTS leads (
        id               uuid primary key default gen_random_uuid(),
        profile_url      text unique not null,
        founder_name     text,
        first_name       text,
        company_name     text,
        linkedin_url     text,
        company_url      text,
        headline         text,
        about            text,
        location         text,
        industry         text,
        employee_count   int,
        quality_score    int,
        icp_score        int CHECK (icp_score >= 0 AND icp_score <= 100),
        icp_signal_type  text CHECK (icp_signal_type IN ('A', 'B', 'AB') OR icp_signal_type IS NULL),
        signal_text      text,
        source           text,
        scrapin_profile_json jsonb,
        scrapin_fetched_at   timestamptz,
        posts_data       jsonb,
        pain_points      text,
        msg_connection_note text,
        msg_first_dm     text,
        msg_followup_day7  text,
        msg_followup_day14 text,
        msg_followup_day21 text,
        msg_followup_day28 text,
        pipeline_stage   text default 'Found' CHECK (pipeline_stage IN (
            'Found','ICP Candidate','Enriched','Ready',
            'Warm-up Queued','Warming Up','Request Sent',
            'Connected','Replied','Interested','Closed','Rejected'
        )),
        enrichment_status text default 'pending',
        created_at       timestamptz default now(),
        updated_at       timestamptz default now()
    );
    CREATE INDEX IF NOT EXISTS idx_leads_stage       ON leads(pipeline_stage);
    CREATE INDEX IF NOT EXISTS idx_leads_enrichment  ON leads(enrichment_status);
    """
    cur = conn.cursor()
    cur.execute(sql)
    conn.commit()
    cur.close()
    print("  Schema created/verified ✓")


def upsert_rows(conn, rows: list[dict]) -> int:
    """Insert all rows using ON CONFLICT DO UPDATE. Returns inserted count."""
    if not rows:
        return 0
    cur = conn.cursor()
    cols = list(rows[0].keys())
    placeholders = ", ".join(["%s"] * len(cols))
    col_names    = ", ".join(cols)
    updates      = ", ".join(
        f"{c} = EXCLUDED.{c}"
        for c in cols
        if c not in ("id", "profile_url", "created_at")
    )
    sql = f"""
        INSERT INTO leads ({col_names})
        VALUES ({placeholders})
        ON CONFLICT (profile_url) DO UPDATE SET {updates}
    """
    count = 0
    for row in rows:
        cur.execute(sql, [row[c] for c in cols])
        count += 1
        if count % 20 == 0:
            conn.commit()
            print(f"  {count}/{len(rows)} upserted...")
    conn.commit()
    cur.close()
    return count


def verify(conn) -> None:
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM leads")
    total = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM leads WHERE msg_connection_note IS NOT NULL")
    with_notes = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM leads WHERE pipeline_stage = 'Found'")
    found_stage = cur.fetchone()[0]
    cur.close()
    print(f"\n  DB verification:")
    print(f"    Total rows      : {total}")
    print(f"    With msg notes  : {with_notes}")
    print(f"    Stage=Found     : {found_stage}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Actually insert into Neon (default: dry run)")
    args = parser.parse_args()

    print(f"\n{'='*55}")
    print(f"CSV → Neon Postgres Migration")
    print(f"{'='*55}")
    print(f"CSV   : {CSV_PATH}")
    print(f"DB    : {'connected' if DATABASE_URL else 'NOT SET — dry run only'}")
    print(f"Mode  : {'APPLY (inserting)' if args.apply else 'DRY RUN (no DB writes)'}")
    print()

    if not CSV_PATH.exists():
        print(f"❌ CSV not found: {CSV_PATH}")
        sys.exit(1)

    df = pd.read_csv(CSV_PATH, dtype=str).fillna("")
    print(f"  Loaded {len(df)} rows from CSV")

    rows = build_rows(df)

    if not args.apply:
        print(f"\n  [DRY RUN] Would insert {len(rows)} leads.")
        print("  Run with --apply to insert into Neon Postgres.")
        return

    if not DATABASE_URL:
        print("❌ DATABASE_URL not set in .env")
        sys.exit(1)

    import psycopg2
    conn = psycopg2.connect(DATABASE_URL)
    create_schema(conn)
    inserted = upsert_rows(conn, rows)
    print(f"\n  ✅ Upserted {inserted} leads into Neon Postgres")
    verify(conn)
    conn.close()


if __name__ == "__main__":
    main()
