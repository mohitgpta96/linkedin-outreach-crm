"""
Source: GitHub API — Founder/CEO/CTO Profiles
GitHub users who list 'founder', 'CEO', 'CTO', or 'co-founder' in their bio
and are located in India, US, UK, or UAE.

Why GitHub works:
- Many startup founders are technical and have GitHub accounts
- GitHub profiles often list company name, blog/website, bio with title
- FREE: 60 req/hr unauthenticated, 5000/hr with token
- No login required at all

Strategy:
- Search GitHub users by bio keyword + location
- Get detailed profile for each user
- Filter: must have company name, startup-sounding bio, real person (not org)
- Extract: name, company, website (blog field), location, title inferred from bio
"""

import logging
import re
import time
from datetime import date
from typing import Optional

import requests

logger = logging.getLogger(__name__)

GITHUB_SEARCH_URL = "https://api.github.com/search/users"
GITHUB_USER_URL   = "https://api.github.com/users/{login}"

HEADERS = {
    "Accept": "application/vnd.github.v3+json",
    "User-Agent": "LinkedInOutreachTool/1.0",
}

# Search queries: (location, bio_keyword, display_label)
SEARCH_QUERIES = [
    # India — highest density of startup founders on GitHub
    ("India", "founder",        "India/founder"),
    ("India", "co-founder",     "India/co-founder"),
    ("India", "CEO",            "India/CEO"),
    ("India", "CTO",            "India/CTO"),
    # United States
    ("United+States", "founder",    "US/founder"),
    ("United+States", "co-founder", "US/co-founder"),
    # United Kingdom
    ("United+Kingdom", "founder",   "UK/founder"),
    # UAE
    ("UAE",            "founder",   "UAE/founder"),
    ("Dubai",          "founder",   "Dubai/founder"),
]

# GitHub search returns max 1000 per query (10 pages x 100)
MAX_PAGES_PER_QUERY = 5      # 5 pages x 100 = 500 results per query
USERS_PER_PAGE      = 100
DELAY_BETWEEN_PAGES = 7      # seconds — stay within 10 search req/min
DELAY_BETWEEN_USERS = 1.2    # seconds — core API: 60 req/hr without token

# Title inference from bio keywords
FOUNDER_KEYWORDS = [
    "founder", "co-founder", "cofounder", "ceo", "chief executive",
    "cto", "chief technology", "managing director", "md ",
    "started", "building", "bootstrapped", "started ",
]

SKIP_ORGS    = {"facebook", "google", "microsoft", "amazon", "netflix", "apple"}
SKIP_BIO_PATTERNS = [
    r"\bstudent\b", r"\blearner\b", r"\bbootcamp\b", r"\bintern\b",
    r"\bfreelance\b",  # freelancers, not company founders
]

COMPANY_TECH_SIGNALS = [
    "saas", "software", "tech", "startup", "fintech", "edtech",
    "healthtech", "api", "platform", "app", "ai", "ml", "data",
    "cloud", "dev", "product", "solutions", "labs", "studio",
    "ventures", "digital", "mobile", "web", "automation",
    "intelligence", "analytics", "systems",
]


def _infer_title_from_bio(bio: str) -> str:
    """Extract the most senior title from a GitHub bio string."""
    bio_lower = bio.lower()
    if "founder" in bio_lower and "co" in bio_lower:
        return "Co-Founder"
    if "founder" in bio_lower:
        return "Founder"
    if "ceo" in bio_lower or "chief executive" in bio_lower:
        return "CEO"
    if "cto" in bio_lower or "chief technology" in bio_lower:
        return "CTO"
    if "managing director" in bio_lower or " md " in bio_lower:
        return "Managing Director"
    if "director" in bio_lower:
        return "Director"
    if "owner" in bio_lower:
        return "Owner"
    return "Founder"   # default — they're in the search result for a reason


def _is_tech_company(company: str, bio: str, blog: str) -> bool:
    """Return True if this person appears to be at a tech/startup company."""
    combined = (company + " " + bio + " " + blog).lower()
    return any(sig in combined for sig in COMPANY_TECH_SIGNALS)


def _clean_url(url: str) -> str:
    """Normalise a URL — add https if missing."""
    if not url:
        return ""
    url = url.strip()
    if url and not url.startswith("http"):
        url = "https://" + url
    return url


def _extract_company_website(user: dict) -> str:
    """Get the company website from the blog field (most reliable on GitHub)."""
    blog = user.get("blog") or ""
    if blog:
        return _clean_url(blog)
    # Fallback: if company looks like a domain
    company = user.get("company") or ""
    company = company.lstrip("@").strip()
    if "." in company and " " not in company:
        return _clean_url(company)
    return ""


def _get_user_detail(login: str) -> Optional[dict]:
    """Fetch full GitHub user profile."""
    try:
        resp = requests.get(
            GITHUB_USER_URL.format(login=login),
            headers=HEADERS,
            timeout=15,
        )
        if resp.status_code == 200:
            return resp.json()
        if resp.status_code == 429:
            logger.warning(f"[GitHub] Rate limited fetching {login}, sleeping 60s")
            time.sleep(60)
        return None
    except Exception as exc:
        logger.warning(f"[GitHub] Error fetching {login}: {exc}")
        return None


def _search_users(location: str, bio_keyword: str, page: int) -> list[dict]:
    """Run one page of GitHub user search."""
    query = f"type:user+location:{location}+in:bio+{bio_keyword}"
    params = {
        "q": query,
        "per_page": USERS_PER_PAGE,
        "page": page,
        "sort": "followers",   # more followers = more real/established
        "order": "desc",
    }
    try:
        resp = requests.get(GITHUB_SEARCH_URL, headers=HEADERS, params=params, timeout=20)
        if resp.status_code == 200:
            return resp.json().get("items", [])
        if resp.status_code == 422:
            return []   # bad query
        if resp.status_code == 429 or resp.status_code == 403:
            retry_after = int(resp.headers.get("X-RateLimit-Reset", time.time() + 70)) - int(time.time())
            wait = max(retry_after, 60)
            logger.warning(f"[GitHub] Search rate limit, sleeping {wait}s")
            time.sleep(wait)
            return []
        logger.warning(f"[GitHub] Search HTTP {resp.status_code} for query: {query}")
        return []
    except Exception as exc:
        logger.warning(f"[GitHub] Search error: {exc}")
        return []


def scrape_github_founders(max_leads: int = 600) -> list[dict]:
    """
    Search GitHub for startup founders/CEOs/CTOs.
    Returns list of lead dicts matching the standard schema.
    """
    leads: list[dict] = []
    seen_logins: set[str] = set()
    today = date.today().isoformat()

    logger.info(f"[GitHub] Starting founder search across {len(SEARCH_QUERIES)} queries...")

    for location, bio_keyword, label in SEARCH_QUERIES:
        if len(leads) >= max_leads:
            break

        logger.info(f"[GitHub] Query: {label}")

        for page in range(1, MAX_PAGES_PER_QUERY + 1):
            if len(leads) >= max_leads:
                break

            search_results = _search_users(location, bio_keyword, page)
            if not search_results:
                break   # no more results for this query

            for user_stub in search_results:
                if len(leads) >= max_leads:
                    break

                login = user_stub.get("login", "")
                if not login or login in seen_logins:
                    continue
                seen_logins.add(login)

                time.sleep(DELAY_BETWEEN_USERS)
                user = _get_user_detail(login)
                if not user:
                    continue

                bio     = (user.get("bio") or "").strip()
                name    = (user.get("name") or login).strip()
                company = (user.get("company") or "").lstrip("@").strip()
                blog    = (user.get("blog") or "").strip()
                loc     = (user.get("location") or "").strip()
                twitter = user.get("twitter_username") or ""
                email   = user.get("email") or ""
                followers = user.get("followers", 0) or 0

                # Must have a bio with founder/CEO keywords
                if not bio:
                    continue

                bio_lower = bio.lower()
                if not any(kw in bio_lower for kw in FOUNDER_KEYWORDS):
                    continue

                # Skip students/interns
                if any(re.search(pat, bio_lower) for pat in SKIP_BIO_PATTERNS):
                    continue

                # Must have some tech signal (company/bio/website)
                if not _is_tech_company(company, bio, blog):
                    continue

                # Skip mega-corp employees (FAANG)
                company_lower = company.lower()
                if any(sc in company_lower for sc in SKIP_ORGS):
                    continue

                # Infer title from bio
                title = _infer_title_from_bio(bio)

                # Company website
                website = _extract_company_website(user)

                # Build first_name from full name
                name_parts = name.split()
                first_name = name_parts[0] if name_parts else login

                # Signal text = bio (tells us what they do/who they are)
                signal_text = bio[:500]

                # Location cleanup
                if "india" in loc.lower():
                    clean_loc = "India"
                elif "united states" in loc.lower() or ", ca" in loc.lower() or ", ny" in loc.lower():
                    clean_loc = "United States"
                elif "united kingdom" in loc.lower() or ", uk" in loc.lower():
                    clean_loc = "United Kingdom"
                elif "uae" in loc.lower() or "dubai" in loc.lower():
                    clean_loc = "UAE"
                else:
                    clean_loc = loc or "Unknown"

                # Quality hint: higher-follower accounts are more likely real founders
                quality_hint = min(followers // 100, 5)  # +0-5 bonus

                lead = {
                    "name":           name,
                    "first_name":     first_name,
                    "title":          title,
                    "company":        company or f"@{login}",
                    "location":       clean_loc,
                    "profile_url":    f"https://github.com/{login}",
                    "company_website": website,
                    "signal_type":    "github_founder_bio",
                    "signal_text":    signal_text,
                    "signal_date":    today,
                    "source":         "github",
                    # Extra context for enrichment
                    "headline":       bio[:200],
                    "about_snippet":  bio[:400],
                    "background_summary": (
                        f"GitHub: {followers} followers | "
                        f"{'Twitter: @' + twitter if twitter else ''} | "
                        f"{'Email: ' + email if email else ''}"
                    ).strip(" | "),
                    "what_they_do":   (
                        company[:80] + " — " + bio[:100] if company else bio[:120]
                    ),
                    "industry":       "Technology",
                    "company_size":   "",
                    "scraped_at":     today,
                }

                leads.append(lead)
                logger.debug(f"[GitHub] Added: {name} @ {company or login} ({title})")

            # Respect GitHub search rate limit: 10 req/min
            if page < MAX_PAGES_PER_QUERY:
                logger.debug(f"[GitHub] Page {page} done. Sleeping {DELAY_BETWEEN_PAGES}s...")
                time.sleep(DELAY_BETWEEN_PAGES)

        logger.info(f"[GitHub] Query '{label}' done. Running total: {len(leads)} leads")

    logger.info(f"[GitHub] Final total: {len(leads)} founder leads")
    return leads
