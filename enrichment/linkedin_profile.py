"""
Enrichment Phase 2A: Deep LinkedIn Profile Scrape
Uses dev_fusion/linkedin-profile-scraper (4.7★, 40K users).
Input: profileUrls (array of LinkedIn profile URLs)
Output: headline, about, background, skills
"""

import logging
from apify_client import ApifyClient

from config import (
    APIFY_TOKEN,
    APIFY_LINKEDIN_PROFILE_SCRAPER,
    MAX_PROFILES_TO_ENRICH,
)

logger = logging.getLogger(__name__)


def enrich_profiles(leads: list[dict]) -> list[dict]:
    """
    For each lead with a profile_url, fetch their full LinkedIn profile.
    Returns the same list with enrichment fields populated.
    """
    if not APIFY_TOKEN:
        logger.warning("APIFY_TOKEN not set — skipping profile enrichment.")
        return leads

    to_enrich = [
        lead for lead in leads
        if lead.get("profile_url") and not lead.get("headline")
    ][:MAX_PROFILES_TO_ENRICH]

    if not to_enrich:
        logger.info("[Profile Enrichment] Nothing to enrich.")
        return leads

    profile_urls = [lead["profile_url"] for lead in to_enrich]
    logger.info(f"[Profile Enrichment] Enriching {len(profile_urls)} profiles...")

    client = ApifyClient(APIFY_TOKEN)

    # dev_fusion/linkedin-profile-scraper takes: { "profileUrls": [...] }
    run_input = {
        "profileUrls": profile_urls,
        "proxy": {"useApifyProxy": True},
    }

    try:
        run = client.actor(APIFY_LINKEDIN_PROFILE_SCRAPER).call(run_input=run_input)
        items = list(client.dataset(run["defaultDatasetId"]).iterate_items())
    except Exception as exc:
        logger.error(f"[Profile Enrichment] Actor failed: {exc}")
        return leads

    # Build lookup: normalized profile_url → item
    enrichment_map: dict[str, dict] = {}
    for item in items:
        url = (
            item.get("linkedInUrl") or item.get("profileUrl")
            or item.get("linkedin_url") or item.get("url", "")
        )
        if url:
            enrichment_map[url.rstrip("/").lower()] = item

    for lead in leads:
        url_key = (lead.get("profile_url") or "").rstrip("/").lower()
        data = enrichment_map.get(url_key)
        if not data:
            continue

        # Headline
        lead["headline"] = (
            data.get("headline") or data.get("title")
            or data.get("occupation", "")
        )

        # About snippet (first 250 chars)
        about = (
            data.get("summary") or data.get("about")
            or data.get("description") or data.get("bio", "")
        )
        lead["about_snippet"] = about[:250] if about else ""

        # Background from experience list
        experiences = (
            data.get("positions") or data.get("experience")
            or data.get("workExperience") or []
        )
        parts = []
        for exp in experiences[:3]:
            company = exp.get("companyName") or exp.get("company", "")
            role    = exp.get("title") or exp.get("role", "")
            if company and role:
                parts.append(f"{role} at {company}")
        lead["background_summary"] = " → ".join(parts)

        # Skills
        skills_raw = data.get("skills") or []
        if isinstance(skills_raw, list):
            skill_names = [
                (s.get("name") if isinstance(s, dict) else str(s))
                for s in skills_raw[:8]
            ]
            lead["skills"] = ", ".join(filter(None, skill_names))

        # Company website
        if not lead.get("company_website"):
            company_info = data.get("company") or {}
            if isinstance(company_info, dict):
                lead["company_website"] = (
                    company_info.get("websiteUrl") or company_info.get("url", "")
                )

        # Fill missing name fields
        if not lead.get("name"):
            lead["name"] = data.get("fullName") or data.get("name", "")
        if not lead.get("first_name"):
            name = lead.get("name") or ""
            lead["first_name"] = data.get("firstName") or (name.split()[0] if name else "")
        if not lead.get("company"):
            if experiences:
                lead["company"] = (
                    experiences[0].get("companyName") or experiences[0].get("company", "")
                )

    logger.info(f"[Profile Enrichment] Enriched {len(enrichment_map)} profiles.")
    return leads
