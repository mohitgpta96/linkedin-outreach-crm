"""
Source 2: LinkedIn Jobs Posted by Founders/CEOs/CTOs
Uses curious_coder/linkedin-jobs-scraper (4.9★, 18K users).
Actor takes LinkedIn jobs search page URLs directly.
"""

import logging
from datetime import datetime
from urllib.parse import quote_plus
from apify_client import ApifyClient

from config import (
    APIFY_TOKEN,
    APIFY_LINKEDIN_JOBS_SCRAPER,
    JOB_SEARCH_TERMS,
    TARGET_TITLES,
    EXCLUDE_TITLES,
    LOCATIONS,
    EXCLUDE_INDUSTRIES,
    MAX_DISCOVERY_RESULTS,
)

logger = logging.getLogger(__name__)

# LinkedIn location codes for URL-based filtering
LOCATION_CODES = {
    "India":                "102713980",
    "United States":        "103644278",
    "United Kingdom":       "101165590",
    "United Arab Emirates": "104305776",
}


def _build_jobs_url(keyword: str, location: str) -> str:
    """Build a LinkedIn jobs search URL."""
    loc_code = LOCATION_CODES.get(location, "")
    url = (
        f"https://www.linkedin.com/jobs/search/"
        f"?keywords={quote_plus(keyword)}"
        f"&location={quote_plus(location)}"
        f"&f_TPR=r2592000"   # last 30 days
        f"&sortBy=DD"         # date posted
    )
    if loc_code:
        url += f"&geoId={loc_code}"
    return url


def _title_is_valid(title: str) -> bool:
    if not title:
        return False
    t = title.lower()
    has_target  = any(x.lower() in t for x in TARGET_TITLES)
    has_exclude = any(x.lower() in t for x in EXCLUDE_TITLES)
    return has_target and not has_exclude


def _industry_ok(industry: str) -> bool:
    if not industry:
        return True
    ind = industry.lower()
    return not any(e.lower() in ind for e in EXCLUDE_INDUSTRIES)


def _parse_date(raw: str) -> str:
    if not raw:
        return ""
    for fmt in ("%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw[:10], "%Y-%m-%d").strftime("%Y-%m-%d")
        except ValueError:
            continue
    return raw[:10] if len(raw) >= 10 else raw


def scrape_linkedin_jobs() -> list[dict]:
    """
    Runs curious_coder/linkedin-jobs-scraper for each term × location combo.
    Filters to jobs posted by Founders/CEOs/CTOs only.
    """
    if not APIFY_TOKEN:
        logger.warning("APIFY_TOKEN not set — skipping LinkedIn jobs scrape.")
        return []

    client = ApifyClient(APIFY_TOKEN)
    seen_profiles: set[str] = set()
    leads: list[dict] = []

    for term in JOB_SEARCH_TERMS:
        if len(leads) >= MAX_DISCOVERY_RESULTS:
            break

        for location in LOCATIONS:
            if len(leads) >= MAX_DISCOVERY_RESULTS:
                break

            jobs_url = _build_jobs_url(term, location)
            logger.info(f"[LinkedIn Jobs] '{term}' in {location}")

            run_input = {
                "urls": [jobs_url],
                "scrapeCompany": False,   # skip company page scrape — saves 80% of requests
                "maxResults": 30,          # cap per run to ~30 jobs
                "proxy": {"useApifyProxy": True},
            }

            try:
                run = client.actor(APIFY_LINKEDIN_JOBS_SCRAPER).call(run_input=run_input)
                items = list(client.dataset(run["defaultDatasetId"]).iterate_items())
            except Exception as exc:
                logger.error(f"[LinkedIn Jobs] Failed for '{term}' / {location}: {exc}")
                continue

            for item in items:
                # Poster info (hiring manager / job poster)
                poster = (
                    item.get("hiringManager") or item.get("poster")
                    or item.get("recruiter") or {}
                )
                poster_url = (
                    poster.get("profileUrl") or poster.get("url")
                    or item.get("posterUrl") or item.get("hiringManagerUrl", "")
                )
                poster_title = (
                    poster.get("title") or poster.get("headline")
                    or poster.get("occupation")
                    or item.get("posterTitle") or item.get("hiringManagerTitle", "")
                )

                if not poster_url or poster_url in seen_profiles:
                    continue
                if not _title_is_valid(poster_title):
                    continue

                industry = item.get("industry") or item.get("companyIndustry", "")
                if not _industry_ok(industry):
                    continue

                poster_name = (
                    poster.get("name") or poster.get("fullName")
                    or item.get("posterName") or item.get("hiringManagerName", "")
                )

                seen_profiles.add(poster_url)
                leads.append({
                    "name":             poster_name,
                    "first_name":       (poster.get("firstName") or poster_name.split()[0] if poster_name else ""),
                    "title":            poster_title,
                    "company":          item.get("companyName") or item.get("company", ""),
                    "location":         item.get("location") or location,
                    "profile_url":      poster_url,
                    "signal_type":      "job_listing",
                    "signal_text":      (item.get("description") or item.get("jobDescription", ""))[:500],
                    "signal_date":      _parse_date(item.get("postedAt") or item.get("publishedAt", "")),
                    "source":           "linkedin_jobs",
                    "company_size_raw": str(item.get("companySize") or item.get("employeeCount") or ""),
                    "industry":         industry,
                    "company_website":  item.get("companyWebsite") or item.get("companyUrl", ""),
                })

    logger.info(f"[LinkedIn Jobs] Total leads: {len(leads)}")
    return leads
