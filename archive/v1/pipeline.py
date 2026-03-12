"""
Pipeline Orchestrator
Runs all 5 discovery sources → deduplicates → runs enrichment → exports CSV + pushes to Supabase.
Designed to be re-run safely (skips already-enriched profiles).
"""

import logging
import os
import json
from datetime import datetime
from collections import defaultdict

import pandas as pd

from config import OUTPUT_DIR, CSV_FILENAME

# Discovery modules
from discovery.linkedin_posts  import scrape_linkedin_posts
from discovery.linkedin_jobs   import scrape_linkedin_jobs
from discovery.crunchbase      import scrape_crunchbase
from discovery.wellfound       import scrape_wellfound
from discovery.ycombinator     import scrape_ycombinator

# Enrichment modules
from enrichment.linkedin_profile          import enrich_profiles
from enrichment.linkedin_posts_enrichment import enrich_with_posts
from enrichment.company_website           import enrich_with_website, enrich_with_website_free
from enrichment.pain_points               import enrich_with_pain_points

# Database
from database import upsert_leads

logger = logging.getLogger(__name__)

CHECKPOINT_FILE = os.path.join(OUTPUT_DIR, ".pipeline_checkpoint.json")


def _save_checkpoint(leads: list[dict]) -> None:
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(CHECKPOINT_FILE, "w") as f:
        json.dump(leads, f, default=str)
    logger.info(f"[Pipeline] Checkpoint saved: {len(leads)} leads")


def _load_checkpoint() -> list[dict]:
    if os.path.exists(CHECKPOINT_FILE):
        with open(CHECKPOINT_FILE) as f:
            leads = json.load(f)
        logger.info(f"[Pipeline] Loaded checkpoint: {len(leads)} leads")
        return leads
    return []


def _deduplicate(all_leads: list[dict]) -> list[dict]:
    """
    Deduplicate by profile_url. If same URL appears from multiple sources,
    merge and increment source_count (boosts quality score +15).
    For leads without profile_url, deduplicate by (company, name).
    """
    by_url: dict[str, dict] = {}
    by_key: dict[tuple, dict] = {}
    no_url: list[dict] = []

    for lead in all_leads:
        url = (lead.get("profile_url") or "").strip().lower()
        if url:
            if url in by_url:
                existing = by_url[url]
                existing["source_count"] = existing.get("source_count", 1) + 1
                # Merge non-empty fields
                for k, v in lead.items():
                    if v and not existing.get(k):
                        existing[k] = v
            else:
                lead["source_count"] = 1
                by_url[url] = lead
        else:
            key = (
                (lead.get("company") or "").lower().strip(),
                (lead.get("name") or "").lower().strip(),
            )
            if key[0] and key in by_key:
                by_key[key]["source_count"] = by_key[key].get("source_count", 1) + 1
            elif key[0]:
                lead["source_count"] = 1
                by_key[key] = lead
            else:
                no_url.append(lead)

    deduped = list(by_url.values()) + list(by_key.values()) + no_url
    logger.info(f"[Pipeline] After dedup: {len(deduped)} unique leads (was {len(all_leads)})")
    return deduped


def _add_scraped_at(leads: list[dict]) -> list[dict]:
    now = datetime.utcnow().isoformat()
    for lead in leads:
        if not lead.get("scraped_at"):
            lead["scraped_at"] = now
    return leads


def _export_csv(leads: list[dict]) -> str:
    """Export leads to CSV and return filepath."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    filepath = os.path.join(OUTPUT_DIR, CSV_FILENAME)

    # Define column order for the CSV
    columns = [
        # Identity
        "quality_score", "lead_temperature", "name", "first_name", "title",
        "company", "location", "profile_url",
        # Signal
        "signal_type", "signal_text", "signal_date", "source", "source_count",
        # Profile enrichment
        "headline", "about_snippet", "background_summary", "skills",
        "post_themes", "post_tone", "recent_notable_post",
        # Company intelligence
        "company_website", "what_they_do", "company_size", "industry",
        "target_customer", "growth_signals", "careers_page_roles",
        # Funding
        "funding_stage", "funding_date", "funding_amount",
        # Outreach prep
        "inferred_pain_points", "pm_value_prop",
        "msg_connection_note", "msg_first_dm",
        "msg_followup_day4", "msg_followup_day10",
        "msg_followup_day17", "msg_followup_day25",
        "msg_word_count_note", "msg_word_count_dm",
        # CRM status
        "warm_up_status", "outreach_status", "pipeline_stage",
        "verified", "notes",
        # Meta
        "scraped_at",
    ]

    df = pd.DataFrame(leads)
    # Add missing columns with empty string
    for col in columns:
        if col not in df.columns:
            df[col] = ""

    df = df[columns]
    df.to_csv(filepath, index=False)
    logger.info(f"[Pipeline] CSV exported: {filepath} ({len(df)} rows)")
    return filepath


def run_pipeline(
    skip_discovery: bool = False,
    skip_enrichment: bool = False,
    skip_db: bool = False,
) -> list[dict]:
    """
    Main pipeline. Steps:
    1. Discovery (all 5 sources)
    2. Deduplication
    3. Enrichment (profile, posts, website, pain points)
    4. Export CSV
    5. Push to Supabase

    Args:
        skip_discovery:  If True, load from checkpoint instead of re-scraping.
        skip_enrichment: If True, skip enrichment and go straight to export.
        skip_db:         If True, don't push to Supabase.
    """
    logger.info("=" * 60)
    logger.info("LinkedIn Outreach Pipeline starting...")
    logger.info("=" * 60)

    # ── Step 1: Discovery ──────────────────────────────────────
    if skip_discovery:
        leads = _load_checkpoint()
        if not leads:
            logger.warning("[Pipeline] No checkpoint found — running discovery anyway.")
            skip_discovery = False

    if not skip_discovery:
        logger.info("\n[Pipeline] Phase 1: Discovery")
        raw_leads = []

        logger.info("  1/5 LinkedIn Posts...")
        raw_leads += scrape_linkedin_posts()

        logger.info("  2/5 LinkedIn Jobs...")
        raw_leads += scrape_linkedin_jobs()

        logger.info("  3/5 Crunchbase (funded startups)...")
        raw_leads += scrape_crunchbase()

        logger.info("  4/5 Wellfound...")
        raw_leads += scrape_wellfound()

        logger.info("  5/5 Y Combinator / Hacker News...")
        raw_leads += scrape_ycombinator()

        leads = _deduplicate(raw_leads)
        leads = _add_scraped_at(leads)
        if len(leads) < 3:
            raise ValueError(f"[Pipeline] Aborting — only {len(leads)} leads discovered (minimum 3 required). Check discovery sources.")
        _save_checkpoint(leads)
        logger.info(f"[Pipeline] Discovery complete: {len(leads)} unique leads")

    # ── Step 2: Enrichment ─────────────────────────────────────
    if not skip_enrichment:
        logger.info("\n[Pipeline] Phase 2: Enrichment")

        logger.info("  2A: LinkedIn profile enrichment...")
        leads = enrich_profiles(leads)
        _save_checkpoint(leads)

        logger.info("  2B: LinkedIn post analysis...")
        leads = enrich_with_posts(leads)
        _save_checkpoint(leads)

        logger.info("  2C: Company website intelligence...")
        leads = enrich_with_website(leads)
        # Free fallback for leads that Apify couldn't enrich
        leads = enrich_with_website_free(leads)
        _save_checkpoint(leads)

        logger.info("  2D: Pain point inference + message generation...")
        leads = enrich_with_pain_points(leads)
        _save_checkpoint(leads)

        logger.info(f"[Pipeline] Enrichment complete: {len(leads)} leads enriched")
    else:
        # Still run free website enrichment + pain points (no API calls needed)
        leads = enrich_with_website_free(leads)
        leads = enrich_with_pain_points(leads)

    # ── Step 3: Export CSV ─────────────────────────────────────
    logger.info("\n[Pipeline] Exporting CSV...")
    csv_path = _export_csv(leads)

    # ── Step 4: Push to Supabase ───────────────────────────────
    if not skip_db:
        logger.info("\n[Pipeline] Pushing to Supabase...")
        n = upsert_leads(leads)
        logger.info(f"[Pipeline] {n} records pushed to Supabase")
    else:
        logger.info("[Pipeline] Supabase push skipped (--skip-db flag).")

    # ── Summary ────────────────────────────────────────────────
    hot_count  = sum(1 for l in leads if l.get("lead_temperature") == "Hot")
    warm_count = sum(1 for l in leads if l.get("lead_temperature") == "Warm")
    cold_count = sum(1 for l in leads if l.get("lead_temperature") == "Cold")

    logger.info("\n" + "=" * 60)
    logger.info("Pipeline complete!")
    logger.info(f"  Total leads:  {len(leads)}")
    logger.info(f"  Hot  (< 7d):  {hot_count}")
    logger.info(f"  Warm (< 30d): {warm_count}")
    logger.info(f"  Cold (30d+):  {cold_count}")
    logger.info(f"  CSV:          {csv_path}")
    logger.info("=" * 60)

    return leads
