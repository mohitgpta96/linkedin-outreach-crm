"""
Source 1: LinkedIn Posts with PM Hiring Intent
Uses supreme_coder/linkedin-post (4.8★, 7.4K users).
Actor takes LinkedIn post search URLs (not raw keywords).
"""

import logging
from datetime import datetime
from urllib.parse import quote_plus
from apify_client import ApifyClient

from config import (
    APIFY_TOKEN,
    APIFY_LINKEDIN_POST_SCRAPER,
    POST_KEYWORDS,
    TARGET_TITLES,
    EXCLUDE_TITLES,
    LOCATIONS,
    MAX_DISCOVERY_RESULTS,
)

logger = logging.getLogger(__name__)


def _build_search_url(keyword: str) -> str:
    """Build a LinkedIn post search URL for a given keyword."""
    return (
        f"https://www.linkedin.com/search/results/content/"
        f"?keywords={quote_plus(keyword)}"
        f"&datePosted=past-month"
        f"&sortBy=date_posted"
    )


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
            return datetime.strptime(raw[:19], fmt[:len(fmt)]).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return raw[:10] if len(raw) >= 10 else raw


def scrape_linkedin_posts() -> list[dict]:
    """
    Runs supreme_coder/linkedin-post for each keyword search URL.
    Returns deduplicated leads filtered to Founders/CEOs/CTOs only.
    """
    if not APIFY_TOKEN:
        logger.warning("APIFY_TOKEN not set — skipping LinkedIn posts scrape.")
        return []

    client = ApifyClient(APIFY_TOKEN)
    seen_profiles: set[str] = set()
    leads: list[dict] = []

    for keyword in POST_KEYWORDS:
        if len(leads) >= MAX_DISCOVERY_RESULTS:
            break

        search_url = _build_search_url(keyword)
        logger.info(f"[LinkedIn Posts] Searching: '{keyword}'")

        run_input = {
            "urls": [search_url],
            "limitPerSource": 20,
            "proxy": {"useApifyProxy": True},
        }

        try:
            run = client.actor(APIFY_LINKEDIN_POST_SCRAPER).call(run_input=run_input)
            items = list(client.dataset(run["defaultDatasetId"]).iterate_items())
        except Exception as exc:
            logger.error(f"[LinkedIn Posts] Actor failed for '{keyword}': {exc}")
            continue

        for item in items:
            # The actor returns author info nested under 'author' or at top level
            author = item.get("author") or {}
            profile_url = (
                author.get("url") or author.get("profileUrl")
                or item.get("authorUrl") or item.get("authorProfileUrl", "")
            )
            if not profile_url:
                profile_url = item.get("url", "")

            if not profile_url or profile_url in seen_profiles:
                continue

            title = (
                author.get("headline") or author.get("title")
                or author.get("occupation")
                or item.get("authorHeadline", "")
            )
            if not _title_is_valid(title):
                continue

            location = author.get("location") or item.get("authorLocation", "")
            if LOCATIONS and location and not any(loc.lower() in location.lower() for loc in LOCATIONS):
                continue

            name = (
                author.get("name") or author.get("fullName")
                or item.get("authorName", "")
            )
            post_text = item.get("text") or item.get("content", "")
            signal_date = _parse_date(
                item.get("publishedAt") or item.get("date")
                or item.get("postedAt", "")
            )

            seen_profiles.add(profile_url)
            leads.append({
                "name":        name,
                "first_name":  (author.get("firstName") or name.split()[0] if name else ""),
                "title":       title,
                "company":     author.get("company") or author.get("companyName") or "",
                "location":    location,
                "profile_url": profile_url,
                "signal_type": "post",
                "signal_text": post_text[:500] if post_text else "",
                "signal_date": signal_date,
                "source":      "linkedin_posts",
            })

    logger.info(f"[LinkedIn Posts] Total leads: {len(leads)}")
    return leads
