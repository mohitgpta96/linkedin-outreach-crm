#!/usr/bin/env python3
"""
scrapin_enrich.py — Enrich leads using Scrapin.io API
Cost: 3 credits per lead (profile + posts + company)
Semaphore: max 3 concurrent requests

Usage:
    python3 scripts/scrapin_enrich.py --test          # enrich 1 lead (3 credits)
    python3 scripts/scrapin_enrich.py --limit 10      # enrich up to 10 leads
    python3 scripts/scrapin_enrich.py                 # enrich all pending leads
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

sys.path.insert(0, str(Path(__file__).parent.parent))
from data_store import get_leads, upsert_lead

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

SCRAPIN_KEY  = os.getenv("SCRAPIN_API_KEY", "")
SCRAPIN_BASE = "https://api.scrapin.io/enrichment"
MAX_CONCUR   = 3
SKIP_DAYS    = 7  # skip if enriched within this many days


# ── Scrapin.io API calls ─────────────────────────────────────────────────────

def scrapin_profile(linkedin_url: str) -> dict:
    """Fetch LinkedIn profile. 1 credit."""
    if not SCRAPIN_KEY:
        raise ValueError("SCRAPIN_API_KEY not set in .env")
    r = requests.get(
        f"{SCRAPIN_BASE}/profile",
        params={"linkedInUrl": linkedin_url, "apikey": SCRAPIN_KEY},
        timeout=15,
    )
    r.raise_for_status()
    return r.json()


def scrapin_posts(linkedin_url: str) -> dict:
    """Fetch recent LinkedIn posts. 1 credit."""
    if not SCRAPIN_KEY:
        raise ValueError("SCRAPIN_API_KEY not set in .env")
    r = requests.get(
        f"{SCRAPIN_BASE}/profile/posts",
        params={"linkedInUrl": linkedin_url, "apikey": SCRAPIN_KEY},
        timeout=15,
    )
    r.raise_for_status()
    return r.json()


def scrapin_company(company_url: str) -> dict:
    """Fetch company data from LinkedIn company URL. 1 credit."""
    if not SCRAPIN_KEY:
        raise ValueError("SCRAPIN_API_KEY not set in .env")
    r = requests.get(
        f"{SCRAPIN_BASE}/company",
        params={"linkedInUrl": company_url, "apikey": SCRAPIN_KEY},
        timeout=15,
    )
    r.raise_for_status()
    return r.json()


# ── Enrichment logic ─────────────────────────────────────────────────────────

sem = asyncio.Semaphore(MAX_CONCUR)


async def enrich_one(lead: dict, loop: asyncio.AbstractEventLoop) -> dict:
    """Enrich a single lead. Uses 3 credits. Thread-safe via semaphore."""
    async with sem:
        profile_url = lead.get("profile_url") or lead.get("linkedin_url", "")
        company_url = lead.get("company_url") or lead.get("company_website", "")
        name        = lead.get("founder_name") or lead.get("name", "")
        logger.info(f"Enriching: {name} ({profile_url[:60]})")

        updates: dict = {}

        try:
            profile_data = await loop.run_in_executor(None, scrapin_profile, profile_url)
            updates["scrapin_profile_json"] = profile_data
            p = profile_data.get("person") or {}
            updates["headline"]     = (p.get("headline") or "")[:500] or lead.get("headline")
            updates["about"]        = (p.get("summary") or "")[:2000] or lead.get("about")
            updates["location"]     = (p.get("location") or "")[:200] or lead.get("location")
        except Exception as e:
            logger.warning(f"  Profile fetch failed for {name}: {e}")

        try:
            posts_data = await loop.run_in_executor(None, scrapin_posts, profile_url)
            updates["posts_data"] = posts_data
        except Exception as e:
            logger.warning(f"  Posts fetch failed for {name}: {e}")

        if company_url:
            try:
                company_data = await loop.run_in_executor(None, scrapin_company, company_url)
                co = company_data.get("company") or {}
                emp = co.get("employeeCount")
                if emp:
                    updates["employee_count"] = int(emp)
                updates["industry"] = (co.get("industries") or [""])[0][:200] or lead.get("industry")
            except Exception as e:
                logger.warning(f"  Company fetch failed for {name}: {e}")

        from datetime import datetime, timezone
        updates["scrapin_fetched_at"] = datetime.now(timezone.utc).isoformat()
        updates["enrichment_status"]  = "enriched"

        merged = {**lead, **updates}
        upsert_lead(merged)
        logger.info(f"  ✅ {name} enriched and saved")
        return merged


async def run_enrichment(leads: list[dict], loop: asyncio.AbstractEventLoop) -> list[dict]:
    tasks = [enrich_one(lead, loop) for lead in leads]
    results = []
    for coro in asyncio.as_completed(tasks):
        result = await coro
        results.append(result)
    return results


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--test",  action="store_true", help="Enrich 1 lead only")
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    if not SCRAPIN_KEY:
        print("❌ SCRAPIN_API_KEY not set in .env")
        sys.exit(1)

    # Get leads pending enrichment
    all_leads = get_leads()
    pending = [
        l for l in all_leads
        if l.get("enrichment_status") in ("pending", "migrated", None, "")
        and (l.get("profile_url") or l.get("linkedin_url"))
    ]

    if not pending:
        print("✅ No leads pending enrichment.")
        return

    limit = 1 if args.test else (args.limit or len(pending))
    batch = pending[:limit]

    credits = len(batch) * 3
    print(f"\n{'='*55}")
    print(f"Scrapin.io Enrichment")
    print(f"{'='*55}")
    print(f"Pending    : {len(pending)} leads")
    print(f"Batch size : {len(batch)}")
    print(f"Credits    : ~{credits} (3 per lead)")
    print()

    t0   = time.time()
    loop = asyncio.get_event_loop()
    results = loop.run_until_complete(run_enrichment(batch, loop))

    elapsed = time.time() - t0
    print(f"\n✅ Enriched {len(results)} leads in {elapsed:.1f}s")
    print(f"   ~{credits} Scrapin.io credits used")


if __name__ == "__main__":
    main()
