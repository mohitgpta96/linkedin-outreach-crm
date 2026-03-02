"""
Source: Hacker News "Who is Hiring?" — Multi-Thread Scraper
Fetches the last 3 months of HN hiring threads and extracts
companies/founders posting PM roles.

Why HN is gold:
- Comments are posted by ACTUAL founders/hiring managers (not recruiters)
- Every commenter = direct decision-maker
- Free Algolia API, no auth, unlimited requests
- March + February + January 2026 = 130+ PM mentions

Data fields extracted:
- HN username = likely the founder/hiring manager
- Company name (parsed from comment)
- Location (parsed from comment)
- Company website (URL in comment)
- Role description
"""

import html
import logging
import re
import time
from datetime import date, datetime

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

HN_SEARCH_URL = "https://hn.algolia.com/api/v1/search"
HN_DATE_SEARCH_URL = "https://hn.algolia.com/api/v1/search_by_date"

PM_KEYWORDS = [
    "product manager", "project manager", "program manager",
    "junior pm", "associate pm", "pm role", "hiring pm",
    "head of product", "vp product",
]

# Known thread IDs for recent months (found via search)
KNOWN_THREAD_IDS = [
    "47219668",   # March 2026
    "46857488",   # February 2026
    "46466074",   # January 2026
]

SKIP_DOMAINS = [
    "linkedin", "twitter", "x.com", "github", "lever.co",
    "greenhouse", "grnh.se", "ashby", "workable", "jobs.",
    "boards.", "ycombinator", "hacker-news", "news.ycombinator",
    "bit.ly", "t.co", "lnkd.in", "apply.", "careers.", "job.",
    "smartrecruiters", "bamboohr", "rippling", "notion.so",
    "google.com", "facebook.com",
]

NEGATIVE_PATTERNS = [
    r"\bno longer\b", r"\bwe don.t need\b", r"\bwas hired\b",
    r"\bfilled\b",  r"\bclosed\b",
]


def _contains_pm_keyword(text: str) -> bool:
    t = text.lower()
    return any(kw in t for kw in PM_KEYWORDS)


def _find_thread_ids_dynamic() -> list[str]:
    """Find recent Who is Hiring threads via Algolia search_by_date."""
    found = []
    try:
        resp = requests.get(
            HN_DATE_SEARCH_URL,
            params={
                "query": "Ask HN: Who is hiring",
                "tags": "ask_hn",
                "hitsPerPage": 10,
            },
            timeout=20,
        )
        resp.raise_for_status()
        for hit in resp.json().get("hits", []):
            title = (hit.get("title") or "").lower()
            if "who is hiring" in title and "wants to be hired" not in title:
                found.append(str(hit["objectID"]))
                if len(found) >= 4:
                    break
    except Exception as exc:
        logger.warning(f"[HN] Dynamic thread search failed: {exc}")
    return found


def _fetch_pm_comments(thread_id: str) -> list[dict]:
    """Get all PM-related comments from a specific HN thread."""
    comments = []
    try:
        # Algolia search within thread for PM keywords
        for keyword in ["product manager", "project manager"]:
            resp = requests.get(
                HN_SEARCH_URL,
                params={
                    "query": keyword,
                    "tags": f"comment,story_{thread_id}",
                    "hitsPerPage": 200,
                },
                timeout=30,
            )
            resp.raise_for_status()
            hits = resp.json().get("hits", [])
            comments.extend(hits)
            time.sleep(0.5)

        # Deduplicate by objectID
        seen = set()
        unique = []
        for c in comments:
            oid = c.get("objectID")
            if oid and oid not in seen:
                seen.add(oid)
                unique.append(c)
        return unique

    except Exception as exc:
        logger.error(f"[HN] Failed to fetch comments for thread {thread_id}: {exc}")
        return []


def _parse_comment_to_lead(comment: dict, thread_label: str):
    """
    Parse a single HN comment into a lead dict.
    Returns None if the comment isn't useful.
    """
    raw_text = comment.get("comment_text") or comment.get("story_text") or ""
    if not raw_text:
        return None

    # Decode HTML and get clean text
    text_decoded = html.unescape(raw_text)
    soup = BeautifulSoup(text_decoded, "html.parser")
    text = soup.get_text(" ", strip=True)

    if not _contains_pm_keyword(text):
        return None

    # Skip negative mentions
    if any(re.search(p, text, re.I) for p in NEGATIVE_PATTERNS):
        return None

    author = comment.get("author", "")
    if not author:
        return None

    # Signal date
    signal_date = ""
    ts = comment.get("created_at")
    if ts:
        try:
            signal_date = datetime.strptime(ts[:19], "%Y-%m-%dT%H:%M:%S").strftime("%Y-%m-%d")
        except ValueError:
            signal_date = ts[:10]

    # ── Parse company name ──
    first_line = text.split("\n")[0][:150]
    company_raw = re.split(r"[|·\-–—(<\|]", first_line)[0].strip()

    if len(company_raw) > 45:
        # Try "CompanyName | roles | location" pattern — first segment too long, look harder
        is_match = re.search(r"\b([A-Z][a-zA-Z0-9]+(?:[\s.][A-Z][a-zA-Z0-9]+)?)\s+(?:is|are)\s+", first_line)
        if is_match:
            company_raw = is_match.group(1)
        else:
            # Find proper nouns
            SKIP = {"The", "Back", "Full", "Remote", "Senior", "Junior", "Series",
                    "We", "Our", "Looking", "Hiring", "Currently", "Seeking", "Join",
                    "Tech", "Software", "Startup", "Company", "Inc", "LLC", "Ltd"}
            nouns = re.findall(r"\b([A-Z][a-zA-Z0-9]{2,})\b", first_line)
            nouns = [n for n in nouns if n not in SKIP]
            company_raw = nouns[0] if nouns else company_raw[:40]

    company = re.sub(r"[\s,\.]+$", "", company_raw.strip())
    if not company or len(company) < 2:
        return None

    # ── Parse location ──
    location_match = re.search(
        r"\b(Remote|New York|San Francisco|London|Bangalore|Mumbai|Delhi|"
        r"Hyderabad|Pune|Chennai|Dubai|Singapore|Berlin|Toronto|Austin|"
        r"Seattle|Los Angeles|Boston|Chicago|NYC|SF|NYC)\b",
        text, re.I
    )
    location = location_match.group(1) if location_match else ""

    # Normalise location
    if location.lower() in ("remote",):
        location = "Remote"
    elif location.lower() in ("bangalore", "mumbai", "delhi", "hyderabad", "pune", "chennai"):
        location = "India"
    elif location.lower() in ("london",):
        location = "United Kingdom"
    elif location.lower() in ("dubai",):
        location = "UAE"
    elif location.lower() in ("new york", "san francisco", "nyc", "sf", "austin",
                               "seattle", "los angeles", "boston", "chicago"):
        location = "United States"

    # ── Extract company website ──
    hrefs = [a.get("href", "") for a in soup.find_all("a", href=True)]
    all_urls = hrefs + re.findall(r"https?://[^\s\"'<>]+", text)
    company_website = ""
    for url in all_urls:
        url_clean = url.rstrip("/.),;")
        if not url_clean.startswith("http"):
            continue
        if any(skip in url_clean.lower() for skip in SKIP_DOMAINS):
            continue
        parts = url_clean.split("/")
        company_website = "/".join(parts[:3])
        break

    # ── Extract LinkedIn URL if present ──
    li_matches = re.findall(r"linkedin\.com/in/[^\s\"'>]+", text_decoded)
    profile_url = li_matches[0] if li_matches else ""

    # ── Extract role title from comment ──
    role_match = re.search(
        r"\b((?:Senior|Junior|Associate|Staff|Head of|VP of?)\s+)?(?:Product|Project|Program)\s+Manager\b",
        text, re.I
    )
    role_title = role_match.group(0) if role_match else "Product Manager"

    return {
        "name":           author,
        "first_name":     author,
        "title":          "Founder/CEO",        # HN comments = decision-maker
        "company":        company,
        "location":       location,
        "profile_url":    profile_url,
        "company_website": company_website,
        "signal_type":    "hn_hiring_post",
        "signal_text":    text[:600],
        "signal_date":    signal_date,
        "source":         f"hacker_news_{thread_label}",
        "headline":       f"Hiring: {role_title} at {company}",
        "about_snippet":  text[:400],
        "what_they_do":   company + (" — " + text[:100] if text else ""),
        "industry":       "Technology",
        "scraped_at":     date.today().isoformat(),
    }


def scrape_hn_hiring() -> list[dict]:
    """
    Scrape last 3 months of HN 'Who is Hiring?' for PM roles.
    Returns lead dicts with standard schema.
    """
    leads: list[dict] = []
    seen_authors: set[str] = set()

    # Merge known + dynamically found thread IDs
    thread_ids = list(dict.fromkeys(KNOWN_THREAD_IDS + _find_thread_ids_dynamic()))
    logger.info(f"[HN] Processing {len(thread_ids)} hiring threads: {thread_ids}")

    for tid in thread_ids:
        comments = _fetch_pm_comments(tid)
        thread_label = tid
        logger.info(f"[HN] Thread {tid}: {len(comments)} PM comments found")

        for comment in comments:
            author = comment.get("author", "")
            if author in seen_authors:
                continue
            seen_authors.add(author)

            lead = _parse_comment_to_lead(comment, thread_label)
            if lead:
                leads.append(lead)
                logger.debug(f"[HN] Added: {lead['company']} (posted by @{author})")

        time.sleep(1)

    logger.info(f"[HN] Total unique leads from HN: {len(leads)}")
    return leads
