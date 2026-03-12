#!/usr/bin/env python3
"""
regenerate_messages.py — Regenerate outreach messages for all leads.

Fixes:
- Repositions Mohit as FRACTIONAL PM (not a job applicant)
- Renames day4→day7, day10→day14, day17→day21, day25→day28 in CSV
- Updates Neon Postgres with new messages

Usage:
    python3 scripts/regenerate_messages.py            # dry run (show sample)
    python3 scripts/regenerate_messages.py --apply    # apply to CSV + DB
    python3 scripts/regenerate_messages.py --apply --use-claude  # use Claude AI (costs ~$0.50)
"""
import argparse
import os
import sys
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

sys.path.insert(0, str(Path(__file__).parent.parent))

CSV_PATH     = Path(__file__).parent.parent / "output" / "leads.csv"
DATABASE_URL = os.getenv("DATABASE_URL", "")

# Old → new column name mapping
COL_RENAME = {
    "msg_followup_day4":  "msg_followup_day7",
    "msg_followup_day10": "msg_followup_day14",
    "msg_followup_day17": "msg_followup_day21",
    "msg_followup_day25": "msg_followup_day28",
}


def generate_rule_based(row: dict) -> dict:
    """Use rule-based generator from enrichment/pain_points.py."""
    from enrichment.pain_points import _generate_messages, _infer_pain_points, _build_value_prop
    row["inferred_pain_points"] = _infer_pain_points(row)
    row["pm_value_prop"]        = _build_value_prop(row)
    return _generate_messages(row)


def generate_with_claude(row: dict) -> dict:
    """Use Claude API for richer, personalized messages."""
    from enrichment.messages import generate_messages
    # Map CSV columns to what messages.py expects
    lead = {
        "founder_name":  row.get("name", ""),
        "first_name":    row.get("first_name", ""),
        "company_name":  row.get("company", ""),
        "headline":      row.get("headline", ""),
        "about":         row.get("about_snippet", ""),
        "what_they_do":  row.get("what_they_do", ""),
        "pain_points":   row.get("inferred_pain_points", ""),
        "growth_signals": row.get("growth_signals", ""),
        "signal_text":   row.get("signal_text", ""),
        "industry":      row.get("industry", ""),
        "location":      row.get("location", ""),
    }
    return generate_messages(lead)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply",      action="store_true", help="Apply changes to CSV + DB")
    parser.add_argument("--use-claude", action="store_true", help="Use Claude AI instead of rule-based (costs ~$0.50)")
    parser.add_argument("--limit",      type=int, default=0, help="Only process N leads (0 = all)")
    args = parser.parse_args()

    print(f"\n{'='*60}")
    print(f"Message Regeneration — Fractional PM Positioning Fix")
    print(f"{'='*60}")
    print(f"Mode      : {'APPLY' if args.apply else 'DRY RUN'}")
    print(f"Generator : {'Claude AI' if args.use_claude else 'Rule-based (free)'}")
    print()

    df = pd.read_csv(CSV_PATH, dtype=str).fillna("")
    print(f"  Loaded {len(df)} leads from CSV")

    # Rename old columns to new names if they exist
    df.rename(columns=COL_RENAME, inplace=True)

    limit = args.limit if args.limit > 0 else len(df)
    sample_shown = False

    updated = 0
    for idx, row in df.iterrows():
        if updated >= limit:
            break

        row_dict = row.to_dict()

        try:
            if args.use_claude:
                msgs = generate_with_claude(row_dict)
            else:
                msgs = generate_rule_based(row_dict)
        except Exception as e:
            print(f"  ⚠️  Row {idx}: {e}")
            continue

        # Show sample in dry run
        if not sample_shown:
            name = row_dict.get("name", "Unknown")
            company = row_dict.get("company", "Unknown")
            print(f"\n  === SAMPLE: {name} @ {company} ===")
            print(f"  Connection Note ({len(msgs.get('msg_connection_note',''))} chars):")
            print(f"  {msgs.get('msg_connection_note','')[:300]}")
            print(f"\n  First DM ({len(msgs.get('msg_first_dm','').split())} words):")
            print(f"  {msgs.get('msg_first_dm','')[:300]}")
            print(f"\n  Follow-up Day 7:")
            print(f"  {msgs.get('msg_followup_day7','')[:200]}")
            print()
            sample_shown = True

        if args.apply:
            for key, val in msgs.items():
                if not key.startswith("msg_"):
                    continue  # skip word_count fields
                val_str = str(val) if val is not None else ""
                if key in df.columns:
                    df.at[idx, key] = val_str
                else:
                    df[key] = ""
                    df.at[idx, key] = val_str

        updated += 1

    if not args.apply:
        print(f"  [DRY RUN] Would regenerate messages for {min(limit, len(df))} leads.")
        print(f"  Run with --apply to save changes.\n")
        return

    # Save CSV
    df.to_csv(CSV_PATH, index=False)
    print(f"  ✅ Saved {updated} leads to CSV with fractional PM messaging")

    # Update Neon Postgres if available
    if DATABASE_URL:
        try:
            import psycopg2
            conn = psycopg2.connect(DATABASE_URL)
            cur  = conn.cursor()

            msg_cols = [
                "msg_connection_note", "msg_first_dm",
                "msg_followup_day7", "msg_followup_day14",
                "msg_followup_day21", "msg_followup_day28"
            ]

            updated_db = 0
            for _, row in df.iterrows():
                purl = str(row.get("profile_url", "")).strip()
                if not purl or purl == "nan":
                    continue
                updates = {c: str(row.get(c, "")).strip() or None for c in msg_cols if c in df.columns}
                if not updates:
                    continue
                set_clause = ", ".join(f"{c} = %s" for c in updates)
                cur.execute(
                    f"UPDATE leads SET {set_clause} WHERE profile_url = %s",
                    list(updates.values()) + [purl]
                )
                updated_db += 1
                if updated_db % 20 == 0:
                    conn.commit()

            conn.commit()
            cur.close()
            conn.close()
            print(f"  ✅ Updated {updated_db} leads in Neon Postgres")
        except Exception as e:
            print(f"  ⚠️  Neon update failed: {e}")
    else:
        print("  ⚠️  DATABASE_URL not set — skipped Neon update")


if __name__ == "__main__":
    main()
