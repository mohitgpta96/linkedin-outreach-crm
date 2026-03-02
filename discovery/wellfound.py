"""
Source 4: Wellfound (AngelList) PM Job Listings
Wellfound is built for startups — founders often post directly.
Higher signal-to-noise ratio than LinkedIn for early-stage companies.
"""

import logging
from datetime import datetime
from apify_client import ApifyClient

from config import (
    APIFY_TOKEN,
    APIFY_WELLFOUND_SCRAPER,
    JOB_SEARCH_TERMS,
    TARGET_TITLES,
    EXCLUDE_TITLES,
    MAX_DISCOVERY_RESULTS,
)

logger = logging.getLogger(__name__)

WELLFOUND_URL = "https://wellfound.com/jobs?role=project-manager"


def _title_is_valid(title: str) -> bool:
    if not title:
        return False
    t = title.lower()
    has_target  = any(x.lower() in t for x in TARGET_TITLES)
    has_exclude = any(x.lower() in t for x in EXCLUDE_TITLES)
    return has_target and not has_exclude


def _parse_date(raw: str) -> str:
    if not raw:
        return ""
    for fmt in ("%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return raw[:10] if len(raw) >= 10 else raw


def scrape_wellfound() -> list[dict]:
    """
    Use Apify to scrape Wellfound PM job listings.
    Returns leads where the job poster is a Founder/CEO/CTO.
    """
    if not APIFY_TOKEN:
        logger.warning("APIFY_TOKEN not set — skipping Wellfound scrape.")
        return []

    client = ApifyClient(APIFY_TOKEN)
    seen_profiles: set[str] = set()
    leads: list[dict] = []

    run_input = {
        "startUrls": [{"url": WELLFOUND_URL}],
        "maxItems": 50,
        "proxy": {"useApifyProxy": True},
    }

    logger.info("[Wellfound] Scraping PM job listings...")
    try:
        run = client.actor(APIFY_WELLFOUND_SCRAPER).call(run_input=run_input)
        items = list(client.dataset(run["defaultDatasetId"]).iterate_items())
    except Exception as exc:
        logger.error(f"[Wellfound] Actor failed: {exc}")
        return []

    for item in items:
        if len(leads) >= MAX_DISCOVERY_RESULTS:
            break

        poster = item.get("poster") or item.get("hiringManager") or {}
        poster_profile = (
            poster.get("linkedinUrl")
            or poster.get("profileUrl")
            or poster.get("url", "")
        )
        poster_title = (
            poster.get("title")
            or poster.get("role")
            or poster.get("headline", "")
        )

        if not poster_profile or poster_profile in seen_profiles:
            # If no poster, include company-level lead (will be enriched later)
            company_name = item.get("company") or item.get("companyName", "")
            if not company_name:
                continue
            # Use company URL as key for dedup
            company_key = item.get("companyUrl") or company_name
            if company_key in seen_profiles:
                continue
            seen_profiles.add(company_key)
            leads.append({
                "name": "",
                "first_name": "",
                "title": "Founder/CEO",
                "company": company_name,
                "location": item.get("location", ""),
                "profile_url": "",
                "signal_type": "job_listing",
                "signal_text": (item.get("description") or item.get("jobDescription", ""))[:500],
                "signal_date": _parse_date(item.get("postedAt") or item.get("createdAt", "")),
                "source": "wellfound",
                "company_website": item.get("companyUrl") or item.get("companyWebsite", ""),
            })
            continue

        if not _title_is_valid(poster_title):
            continue

        seen_profiles.add(poster_profile)
        leads.append({
            "name": poster.get("name") or poster.get("fullName", ""),
            "first_name": (poster.get("firstName") or (poster.get("name") or "").split()[0]),
            "title": poster_title,
            "company": item.get("company") or item.get("companyName", ""),
            "location": item.get("location", ""),
            "profile_url": poster_profile,
            "signal_type": "job_listing",
            "signal_text": (item.get("description") or item.get("jobDescription", ""))[:500],
            "signal_date": _parse_date(item.get("postedAt") or item.get("createdAt", "")),
            "source": "wellfound",
            "company_website": item.get("companyUrl") or item.get("companyWebsite", ""),
        })

    logger.info(f"[Wellfound] Total leads collected: {len(leads)}")
    return leads
