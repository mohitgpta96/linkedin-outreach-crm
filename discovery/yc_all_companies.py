"""
Source: YC Company Directory — Full Paginated Scraper
Fetches ALL Y Combinator companies (not just recent batches) and converts
each company into a lead targeting the Founder/CEO.

Why this is different from the existing ycombinator.py:
- The existing scraper hits ycombinator.com/jobs (PM job listings only)
- THIS scraper hits api.ycombinator.com/v0.1/companies (ALL 5750 companies)
- We generate a lead for the Founder/CEO of every small YC company
- Founders at YC companies are extremely open to hiring (they have money + pressure to scale)
- We already have 298 YC leads — this fills in ALL the rest

Filtering:
- teamSize < 200 (avoid big companies where founder is no longer PM bottleneck)
- status = Active (company still operating)
- Tags containing tech/SaaS/B2B signals
- Skip batches we already have leads for (configurable)

Output: standard lead dict with source = "yc_{batch}"
"""

import logging
import re
import time
from datetime import date
from typing import Optional

import requests

logger = logging.getLogger(__name__)

YC_API_URL = "https://api.ycombinator.com/v0.1/companies"
DELAY_BETWEEN_PAGES = 0.3   # YC API is generous — no rate limit documented

# Max team size to include (small startups need PMs the most)
MAX_TEAM_SIZE = 200

# Tags that indicate a tech/SaaS company
TECH_TAGS = {
    "saas", "b2b", "developer tools", "enterprise", "fintech", "edtech",
    "healthtech", "ai", "ml", "artificial intelligence", "machine learning",
    "data", "analytics", "api", "platform", "mobile", "cloud", "devops",
    "cybersecurity", "marketplace", "e-commerce", "ecommerce", "proptech",
    "legaltech", "insurtech", "logistics", "supply chain", "automation",
    "productivity", "collaboration", "hr tech", "hrtech", "recruiting",
    "sales", "marketing", "crm", "erp", "no-code", "low-code",
}

# Exclude industries that are not tech (e.g. pure biotech, hardware-only)
EXCLUDE_TAGS = {
    "biotech", "medical devices", "hardware", "consumer",
    "food and beverage", "fashion", "beauty",
}

# Batches already scraped in existing leads.csv (skip to avoid duplicates)
# Based on existing data: YC, YC S25, YC W25, YC S24, YC W24, YC F25
# Note: "YC" without batch label covers the bulk of previously scraped companies
ALREADY_SCRAPED_SOURCES = {"YC S25", "YC W25", "YC S24", "YC W24", "YC F25", "YC X25"}

REGIONS_OF_INTEREST = {
    "us": "United States",
    "uk": "United Kingdom",
    "india": "India",
    "uae": "UAE",
    "gb": "United Kingdom",
    "in": "India",
    "ae": "UAE",
    "ca": "Canada",
    "sg": "Singapore",
}


def _normalize_location(company: dict) -> str:
    """Extract location from YC company data."""
    locations = company.get("locations") or []
    regions   = company.get("regions") or []

    if locations:
        loc = locations[0] if isinstance(locations[0], str) else str(locations[0])
        return loc

    if regions:
        for r in regions:
            r_lower = r.lower()
            for key, name in REGIONS_OF_INTEREST.items():
                if key in r_lower:
                    return name

    return "United States"   # default: most YC companies are US-based


def _is_tech_company(company: dict) -> bool:
    """Check if company has tech/SaaS tags."""
    tags = [t.lower() for t in (company.get("tags") or [])]
    industries = [i.lower() for i in (company.get("industries") or [])]
    all_labels = set(tags + industries)

    # Must have at least one tech signal
    has_tech = bool(all_labels & TECH_TAGS)

    # Hard exclude non-tech
    has_exclude = bool(all_labels & EXCLUDE_TAGS) and not has_tech

    return has_tech or (not has_exclude)   # if no tags at all, include (startup = default tech)


def _infer_batch_source(batch: str) -> str:
    """Convert batch label to source string: 'W26' → 'YC W26'"""
    if not batch:
        return "YC"
    return f"YC {batch}"


def _company_to_lead(company: dict) -> Optional[dict]:
    """Convert a YC company dict to a lead dict."""
    name     = company.get("name") or ""
    slug     = company.get("slug") or ""
    website  = company.get("website") or ""
    one_liner = company.get("oneLiner") or ""
    long_desc = company.get("longDescription") or ""
    team_size = company.get("teamSize")
    batch    = company.get("batch") or ""
    tags     = company.get("tags") or []
    status   = company.get("status") or "Active"
    url      = company.get("url") or f"https://www.ycombinator.com/companies/{slug}"

    if not name:
        return None

    # Skip inactive companies
    if status.lower() not in ("active", ""):
        return None

    # Skip companies that are too large
    try:
        if team_size and int(team_size) > MAX_TEAM_SIZE:
            return None
    except (ValueError, TypeError):
        pass

    # Skip non-tech
    if not _is_tech_company(company):
        return None

    source = _infer_batch_source(batch)

    # Skip already-scraped batches
    if source in ALREADY_SCRAPED_SOURCES:
        return None

    location = _normalize_location(company)

    # What they do = one_liner + first sentence of long_desc
    what_they_do = one_liner or ""
    if long_desc and len(what_they_do) < 80:
        first_sentence = long_desc.split(".")[0][:120]
        what_they_do = (what_they_do + ". " + first_sentence).strip(". ")

    # Company size label
    size_label = str(team_size) if team_size else "Unknown"

    # Tags to industry string
    tech_tags = [t for t in tags if t.lower() in TECH_TAGS]
    industry = ", ".join(tech_tags[:3]) if tech_tags else "Technology"

    today = date.today().isoformat()

    return {
        "name":            "",               # Founder name not in API — blank
        "first_name":      "Founder",        # Generic — will be personalised later
        "title":           "Founder/CEO",
        "company":         name,
        "location":        location,
        "profile_url":     "",               # No LinkedIn from YC API
        "company_website": website or url,
        "signal_type":     "yc_company_listing",
        "signal_text":     what_they_do[:500],
        "signal_date":     today,
        "source":          source,
        "headline":        f"Founder/CEO at {name} (YC {batch})",
        "about_snippet":   one_liner[:300],
        "what_they_do":    what_they_do[:300],
        "industry":        industry,
        "company_size":    size_label,
        "funding_stage":   f"YC {batch}" if batch else "YC-backed",
        "funding_date":    "",
        "background_summary": (
            f"YC {batch} company | Team: {size_label} | "
            f"Tags: {', '.join(tags[:5])}"
        ),
        "scraped_at":      today,
    }


def scrape_yc_all_companies(max_leads: int = 2000) -> list[dict]:
    """
    Paginate through ALL YC companies and convert to leads.
    Skips companies in already-scraped batches (S24, W25, S25, F25).
    Returns list of lead dicts.
    """
    leads: list[dict] = []
    page = 1
    total_pages = None

    logger.info("[YC All] Starting full YC company directory scrape...")

    while True:
        if len(leads) >= max_leads:
            break

        try:
            resp = requests.get(
                YC_API_URL,
                params={"page": page, "per_page": 25},
                timeout=20,
                headers={"User-Agent": "LinkedInOutreachTool/1.0"},
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            logger.error(f"[YC All] Page {page} failed: {exc}")
            break

        companies = data.get("companies", [])
        if not companies:
            break

        if total_pages is None:
            total_pages = data.get("totalPages", 999)
            logger.info(f"[YC All] Total pages: {total_pages} (~{total_pages * 25} companies)")

        for company in companies:
            lead = _company_to_lead(company)
            if lead:
                leads.append(lead)

        logger.debug(f"[YC All] Page {page}/{total_pages} — running total: {len(leads)}")

        if page >= total_pages:
            break

        page += 1
        time.sleep(DELAY_BETWEEN_PAGES)

    logger.info(f"[YC All] Done. {len(leads)} new YC company leads (new batches only)")
    return leads
