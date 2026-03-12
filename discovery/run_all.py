#!/usr/bin/env python3
"""
run_all.py — Parallel discovery orchestrator
Runs YC + HN + GitHub in parallel, deduplicates, ICP-filters, stores to DB.

Usage:
    python3 discovery/run_all.py          # full run
    python3 discovery/run_all.py --dry-run  # print results, don't save
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from data_store import get_leads, upsert_lead
from discovery.dedup import deduplicate_and_score

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def run_yc(max_leads: int = 500) -> list[dict]:
    try:
        from discovery.yc_all_companies import scrape_yc_all_companies
        leads = scrape_yc_all_companies(max_leads=max_leads)
        logger.info(f"[YC] {len(leads)} leads")
        return leads
    except Exception as e:
        logger.error(f"[YC] Failed: {e}")
        return []


def run_hn() -> list[dict]:
    try:
        from discovery.hn_hiring import scrape_hn_hiring
        leads = scrape_hn_hiring()
        logger.info(f"[HN] {len(leads)} leads")
        return leads
    except Exception as e:
        logger.error(f"[HN] Failed: {e}")
        return []


def run_github(max_leads: int = 200) -> list[dict]:
    try:
        from discovery.github_founders import scrape_github_founders
        leads = scrape_github_founders(max_leads=max_leads)
        logger.info(f"[GitHub] {len(leads)} leads")
        return leads
    except Exception as e:
        logger.error(f"[GitHub] Failed: {e}")
        return []


async def run_discovery_async() -> list[dict]:
    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor(max_workers=3) as pool:
        yc_task     = loop.run_in_executor(pool, run_yc, 500)
        hn_task     = loop.run_in_executor(pool, run_hn)
        github_task = loop.run_in_executor(pool, run_github, 200)
        results     = await asyncio.gather(yc_task, hn_task, github_task, return_exceptions=True)

    all_leads = []
    for r in results:
        if isinstance(r, list):
            all_leads.extend(r)
        elif isinstance(r, Exception):
            logger.error(f"Discovery source failed: {r}")

    return all_leads


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    t0 = time.time()
    print("\n" + "="*55)
    print("Discovery — All Sources")
    print("="*55)

    # Get existing URLs to avoid re-adding
    existing = get_leads()
    existing_urls = {
        str(l.get("profile_url") or "").strip().lower()
        for l in existing
        if l.get("profile_url")
    }
    print(f"Existing leads in DB: {len(existing_urls)}")

    # Run all sources in parallel
    print("\nRunning discovery (parallel)...")
    loop = asyncio.get_event_loop()
    raw_leads = loop.run_until_complete(run_discovery_async())

    print(f"\nRaw leads from all sources: {len(raw_leads)}")

    # Deduplicate and score
    new_leads = deduplicate_and_score(raw_leads, existing_urls)
    print(f"After dedup: {len(new_leads)} new unique leads")

    if not new_leads:
        print("⚠️  No new leads found. Exiting.")
        return

    # Gate check
    if len(new_leads) < 5:
        print(f"⚠️  Only {len(new_leads)} new leads — below minimum threshold of 5.")
        print("   Check discovery sources or broaden filters.")
        if len(new_leads) < 3:
            raise ValueError(f"Aborting — only {len(new_leads)} leads (minimum 3 required)")

    # Signal distribution
    sig_a = sum(1 for l in new_leads if l.get("icp_signal_type") == "A")
    sig_b = len(new_leads) - sig_a
    print(f"Signal A (direct PM): {sig_a} | Signal B (inferred): {sig_b}")

    if args.dry_run:
        print(f"\n[DRY RUN] Would save {len(new_leads)} leads. Sample:")
        for lead in new_leads[:5]:
            print(f"  - {lead.get('name','-')} @ {lead.get('company','-')} [{lead.get('source','-')}]")
        return

    # Save to data_store
    saved = 0
    for lead in new_leads:
        lead.setdefault("pipeline_stage", "ICP Candidate")
        lead.setdefault("enrichment_status", "pending")
        try:
            upsert_lead(lead)
            saved += 1
        except Exception as e:
            logger.warning(f"  Save failed for {lead.get('name')}: {e}")

    elapsed = time.time() - t0
    print(f"\n✅ Saved {saved}/{len(new_leads)} new leads ({elapsed:.1f}s)")
    print(f"   Total in DB now: {len(existing_urls) + saved}")


if __name__ == "__main__":
    main()
