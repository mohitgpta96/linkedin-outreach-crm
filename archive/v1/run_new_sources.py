"""
run_new_sources.py
==================
Orchestrator for the three new lead discovery sources:
  1. GitHub API     — startup founders with 'founder/CEO/CTO' in bio
  2. YC All Companies — all YC companies beyond already-scraped batches
  3. HN Who is Hiring — multi-thread PM hiring posts

Runs all three, enriches each lead with pain points + messages,
deduplicates against existing leads.csv, then appends new leads.

Usage:
    python3 run_new_sources.py
    python3 run_new_sources.py --source github
    python3 run_new_sources.py --source yc
    python3 run_new_sources.py --source hn
    python3 run_new_sources.py --max 500
    python3 run_new_sources.py --dry-run
"""

import argparse
import csv
import logging
import os
import sys
import time
from datetime import date
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from enrichment.pain_points import enrich_with_pain_points

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger("run_new_sources")

OUTPUT_DIR  = Path(__file__).parent / "output"
CSV_PATH    = OUTPUT_DIR / "leads.csv"
BACKUP_PATH = OUTPUT_DIR / f"leads_backup_{date.today().isoformat()}.csv"

# All CSV columns (must match existing leads.csv exactly)
CSV_COLUMNS = [
    "name", "first_name", "title", "company", "location",
    "profile_url", "company_website",
    "signal_type", "signal_text", "signal_date", "source",
    "lead_temperature", "quality_score", "pipeline_stage",
    "verified", "warm_up_status", "outreach_status",
    "headline", "about_snippet", "background_summary",
    "skills", "post_themes", "post_tone", "recent_notable_post",
    "what_they_do", "company_size", "industry",
    "target_customer", "growth_signals", "careers_page_roles",
    "funding_stage", "funding_date", "funding_amount",
    "trigger_event", "trigger_date",
    "inferred_pain_points", "pm_value_prop", "suggested_opener",
    "msg_connection_note", "msg_first_dm",
    "msg_followup_day4", "msg_followup_day10",
    "msg_followup_day17", "msg_followup_day25",
    "msg_word_count_note", "msg_word_count_dm",
    "notes", "scraped_at",
]


# ─── Deduplication ────────────────────────────────────────────────────────────

def _load_existing_keys(csv_path: Path) -> set[str]:
    """
    Load deduplication keys from existing leads.csv.
    Key = (company.lower(), name.lower()) OR (company.lower(), profile_url.lower())
    """
    keys: set[str] = set()
    if not csv_path.exists():
        return keys
    try:
        with open(csv_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                company = (row.get("company") or "").strip().lower()
                name    = (row.get("name") or "").strip().lower()
                url     = (row.get("profile_url") or "").strip().lower()
                website = (row.get("company_website") or "").strip().lower()
                if company:
                    keys.add(company)
                if url and url != "":
                    keys.add(url)
        logger.info(f"Loaded {len(keys)} dedup keys from existing CSV")
    except Exception as exc:
        logger.warning(f"Could not load existing CSV for dedup: {exc}")
    return keys


def _is_duplicate(lead: dict, existing_keys: set[str]) -> bool:
    """Return True if this lead is already in the CSV."""
    company = (lead.get("company") or "").strip().lower()
    url     = (lead.get("profile_url") or "").strip().lower()
    website = (lead.get("company_website") or "").strip().lower()

    if company and company in existing_keys:
        return True
    if url and url in existing_keys:
        return True
    return False


def _make_dedup_key(lead: dict) -> str:
    """Create a key to deduplicate within a new batch."""
    company = (lead.get("company") or "").strip().lower()
    url     = (lead.get("profile_url") or "").strip().lower()
    return url if url else company


# ─── CSV I/O ─────────────────────────────────────────────────────────────────

def _lead_to_row(lead: dict) -> dict:
    """Convert lead dict to CSV row dict with all required columns."""
    row = {}
    for col in CSV_COLUMNS:
        row[col] = lead.get(col, "")
    return row


def _append_to_csv(leads: list[dict], csv_path: Path, backup_path: Path):
    """Append new leads to existing CSV (create if not exists)."""
    # Backup existing file
    if csv_path.exists():
        import shutil
        shutil.copy2(csv_path, backup_path)
        logger.info(f"Backed up existing CSV to {backup_path}")

    file_exists = csv_path.exists()
    with open(csv_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        if not file_exists:
            writer.writeheader()
        for lead in leads:
            writer.writerow(_lead_to_row(lead))

    logger.info(f"Appended {len(leads)} leads to {csv_path}")


# ─── Source Runners ────────────────────────────────────────────────────────────

def run_github(max_leads: int = 600) -> list[dict]:
    logger.info("=" * 60)
    logger.info("SOURCE 1: GitHub API — Founder Profiles")
    logger.info("=" * 60)
    try:
        from discovery.github_founders import scrape_github_founders
        leads = scrape_github_founders(max_leads=max_leads)
        logger.info(f"[GitHub] Raw leads: {len(leads)}")
        return leads
    except Exception as exc:
        logger.error(f"[GitHub] FAILED: {exc}", exc_info=True)
        return []


def run_yc_all(max_leads: int = 2000) -> list[dict]:
    logger.info("=" * 60)
    logger.info("SOURCE 2: YC Company Directory — All Batches")
    logger.info("=" * 60)
    try:
        from discovery.yc_all_companies import scrape_yc_all_companies
        leads = scrape_yc_all_companies(max_leads=max_leads)
        logger.info(f"[YC All] Raw leads: {len(leads)}")
        return leads
    except Exception as exc:
        logger.error(f"[YC All] FAILED: {exc}", exc_info=True)
        return []


def run_hn(max_leads: int = 200) -> list[dict]:
    logger.info("=" * 60)
    logger.info("SOURCE 3: HN Who is Hiring — Multi-Thread")
    logger.info("=" * 60)
    try:
        from discovery.hn_hiring import scrape_hn_hiring
        leads = scrape_hn_hiring()
        logger.info(f"[HN] Raw leads: {len(leads)}")
        return leads[:max_leads]
    except Exception as exc:
        logger.error(f"[HN] FAILED: {exc}", exc_info=True)
        return []


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Run new lead discovery sources")
    parser.add_argument("--source", choices=["github", "yc", "hn", "all"], default="all",
                        help="Which source to run (default: all)")
    parser.add_argument("--max", type=int, default=2000,
                        help="Max total new leads to add (default: 2000)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Run but don't write to CSV")
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(exist_ok=True)

    # Load existing leads for deduplication
    existing_keys = _load_existing_keys(CSV_PATH)

    all_new_leads: list[dict] = []

    # ── Run selected sources ──
    if args.source in ("all", "yc"):
        yc_leads = run_yc_all(max_leads=args.max)
        all_new_leads.extend(yc_leads)
        logger.info(f"[YC All] Added {len(yc_leads)} raw leads")

    if args.source in ("all", "hn"):
        hn_leads = run_hn()
        all_new_leads.extend(hn_leads)
        logger.info(f"[HN] Added {len(hn_leads)} raw leads")

    if args.source in ("all", "github"):
        gh_leads = run_github(max_leads=min(600, args.max))
        all_new_leads.extend(gh_leads)
        logger.info(f"[GitHub] Added {len(gh_leads)} raw leads")

    if not all_new_leads:
        logger.warning("No leads collected from any source.")
        return

    logger.info(f"\nTotal raw leads from all sources: {len(all_new_leads)}")

    # ── Deduplicate against existing CSV ──
    deduped_leads: list[dict] = []
    batch_keys: set[str] = set()
    skipped_dup = 0
    skipped_batch = 0

    for lead in all_new_leads:
        # Skip if already in existing CSV
        if _is_duplicate(lead, existing_keys):
            skipped_dup += 1
            continue

        # Skip duplicates within this new batch
        key = _make_dedup_key(lead)
        if key and key in batch_keys:
            skipped_batch += 1
            continue
        if key:
            batch_keys.add(key)

        deduped_leads.append(lead)

    logger.info(f"After dedup: {len(deduped_leads)} unique new leads "
                f"(skipped {skipped_dup} already in CSV, {skipped_batch} within-batch dups)")

    # Limit total
    deduped_leads = deduped_leads[:args.max]

    # ── Enrich with pain points + messages ──
    logger.info(f"\nEnriching {len(deduped_leads)} leads with pain points + messages...")
    enriched = enrich_with_pain_points(deduped_leads)
    logger.info(f"Enrichment complete. {len(enriched)} leads ready.")

    # ── Print stats ──
    from collections import Counter
    source_counts = Counter(l.get("source", "unknown") for l in enriched)
    print("\n" + "=" * 60)
    print("RESULTS BY SOURCE:")
    print("=" * 60)
    for src, count in source_counts.most_common():
        print(f"  {src:30s}: {count:4d} leads")
    print(f"\n  {'TOTAL NEW LEADS':30s}: {len(enriched):4d}")

    # Current total
    existing_count = 0
    if CSV_PATH.exists():
        with open(CSV_PATH) as f:
            existing_count = sum(1 for _ in f) - 1  # minus header
    print(f"  {'EXISTING LEADS':30s}: {existing_count:4d}")
    print(f"  {'PROJECTED TOTAL':30s}: {existing_count + len(enriched):4d}")
    print("=" * 60)

    avg_score = sum(l.get("quality_score", 0) for l in enriched) / len(enriched) if enriched else 0
    hot_count  = sum(1 for l in enriched if l.get("lead_temperature") == "Hot")
    warm_count = sum(1 for l in enriched if l.get("lead_temperature") == "Warm")
    print(f"\n  Avg quality score : {avg_score:.1f}")
    print(f"  Hot leads         : {hot_count}")
    print(f"  Warm leads        : {warm_count}")

    # ── Write to CSV ──
    if args.dry_run:
        print(f"\n[DRY RUN] Would have written {len(enriched)} leads to {CSV_PATH}")
    else:
        _append_to_csv(enriched, CSV_PATH, BACKUP_PATH)
        print(f"\nWrote {len(enriched)} new leads to {CSV_PATH}")
        print(f"Total leads in file: {existing_count + len(enriched)}")


if __name__ == "__main__":
    main()
