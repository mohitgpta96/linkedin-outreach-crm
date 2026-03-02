"""
Source 5: Y Combinator Jobs Board + Hacker News "Who is Hiring?" Thread
YC founders are vetted, high-quality. HN threads contain only real founders (no recruiters).
These are warm, high-quality leads with a direct line to the decision maker.
"""

import html
import logging
import re
from datetime import datetime, date

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

YC_JOBS_URL   = "https://www.ycombinator.com/jobs"
HN_SEARCH_URL = "https://hn.algolia.com/api/v1/search"

PM_KEYWORDS = [
    "project manager",
    "product manager",
    "junior pm",
    "associate pm",
    "pm role",
    "hiring pm",
]


def _contains_pm_keyword(text: str) -> bool:
    t = text.lower()
    return any(kw in t for kw in PM_KEYWORDS)


def _scrape_yc_jobs() -> list[dict]:
    """Scrape the public YC jobs board for PM roles."""
    leads = []
    try:
        resp = requests.get(YC_JOBS_URL, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # YC job cards vary in structure; try common selectors
        job_cards = (
            soup.select(".JobsPage_jobItem__Q5eWk")
            or soup.select("[class*='job']")
            or soup.select("article")
        )

        for card in job_cards:
            text = card.get_text(" ", strip=True)
            if not _contains_pm_keyword(text):
                continue

            company_el = card.select_one("[class*='company'], h3, h2")
            company = company_el.get_text(strip=True) if company_el else ""
            role_el  = card.select_one("[class*='role'], [class*='title'], h4")
            role     = role_el.get_text(strip=True) if role_el else ""
            link_el  = card.select_one("a[href]")
            url      = link_el["href"] if link_el else ""
            if url and url.startswith("/"):
                url = f"https://www.ycombinator.com{url}"

            if not company:
                continue

            leads.append({
                "name": "",
                "first_name": "",
                "title": "Founder/CEO",
                "company": company,
                "location": "USA",
                "profile_url": "",
                "signal_type": "job_listing",
                "signal_text": f"{role} at {company}".strip(),
                "signal_date": date.today().isoformat(),
                "source": "ycombinator",
                "company_website": url,
            })

    except Exception as exc:
        logger.error(f"[YC Jobs] Scrape failed: {exc}")

    logger.info(f"[YC Jobs] Found {len(leads)} PM listings.")
    return leads


def _scrape_hn_who_is_hiring() -> list[dict]:
    """
    Query HN Algolia API for the latest 'Ask HN: Who is hiring?' thread
    and extract comments mentioning PM roles.
    """
    leads = []

    # Find the current month's thread via HN Firebase API (most reliable)
    thread_id = None
    try:
        user_resp = requests.get(
            "https://hacker-news.firebaseio.com/v0/user/whoishiring.json",
            timeout=20,
        )
        user_resp.raise_for_status()
        submitted = user_resp.json().get("submitted", [])
        # Check the 10 most recent posts for current "Who is hiring?" thread
        for item_id in submitted[:10]:
            item_resp = requests.get(
                f"https://hacker-news.firebaseio.com/v0/item/{item_id}.json",
                timeout=10,
            )
            item_resp.raise_for_status()
            item = item_resp.json()
            title = (item.get("title") or "").lower()
            if "who is hiring" in title and "wants to be hired" not in title:
                thread_id = str(item_id)
                break
    except Exception as exc:
        logger.warning(f"[HN Hiring] Firebase API failed: {exc}")

    # Fallback: Algolia search
    if not thread_id:
        try:
            search_resp = requests.get(
                HN_SEARCH_URL,
                params={
                    "query": "Ask HN: Who is hiring?",
                    "tags": "story,ask_hn",
                    "hitsPerPage": 5,
                },
                timeout=20,
            )
            search_resp.raise_for_status()
            hits = search_resp.json().get("hits", [])
            if hits:
                thread_id = hits[0].get("objectID") or hits[0].get("story_id")
        except Exception as exc:
            logger.error(f"[HN Hiring] Thread search failed: {exc}")
            return []

    if not thread_id:
        logger.warning("[HN Hiring] No 'Who is hiring?' thread found.")
        return []
    logger.info(f"[HN Hiring] Using thread ID: {thread_id}")

    # Fetch comments
    try:
        comments_resp = requests.get(
            HN_SEARCH_URL,
            params={
                "tags": f"comment,story_{thread_id}",
                "hitsPerPage": 200,
            },
            timeout=30,
        )
        comments_resp.raise_for_status()
        comments = comments_resp.json().get("hits", [])
    except Exception as exc:
        logger.error(f"[HN Hiring] Comments fetch failed: {exc}")
        return []

    seen_authors: set[str] = set()
    for comment in comments:
        raw_text = comment.get("comment_text") or comment.get("story_text") or ""
        # Decode HTML entities and strip tags for clean text
        text_decoded = html.unescape(raw_text)
        soup_comment = BeautifulSoup(text_decoded, "html.parser")
        text = soup_comment.get_text(" ", strip=True)

        if not _contains_pm_keyword(text):
            continue

        # Skip negative context
        negative_patterns = [
            r"\bno longer\b", r"\bwe don.t need\b", r"\bpromoted\b",
            r"\bwe don.t use\b",
        ]
        if any(re.search(p, text, re.I) for p in negative_patterns):
            continue

        author = comment.get("author", "")
        if author in seen_authors:
            continue
        seen_authors.add(author)

        # Extract company name — first segment before pipe, dash, or parenthesis
        first_line = text.split("\n")[0][:120]
        company_raw = re.split(r"[|·\-–—(<]", first_line)[0].strip()
        # If first segment is too long (>40 chars), likely a sentence not a name
        # Try to find the actual company name using common HN patterns
        if len(company_raw) > 40:
            # Pattern 1: "Company is the/a ..." — most common HN company description format
            is_pattern = re.search(r"\b([A-Z][a-zA-Z0-9]+(?:\s[A-Z][a-zA-Z0-9]+)?)\s+is\s+(?:the|a[n]?)\s", first_line)
            if is_pattern:
                company_raw = is_pattern.group(1)
            else:
                # Pattern 2: Find proper nouns, skip known investor/generic words
                SKIP_WORDS = {
                    "Back", "Full", "Remote", "Hiring", "Senior", "Junior", "Series",
                    "The", "Sequoia", "Capital", "Andreessen", "Horowitz", "Softbank",
                    "YCombinator", "Partner", "Inc", "LLC", "Ltd", "Corp",
                }
                nouns = re.findall(r"\b([A-Z][a-zA-Z0-9]+)\b", first_line)
                nouns = [n for n in nouns if n not in SKIP_WORDS and len(n) >= 3]
                company_raw = nouns[0] if nouns else company_raw[:40]
        company = re.sub(r"[\s,]+$", "", company_raw.strip())

        signal_date = ""
        ts = comment.get("created_at")
        if ts:
            try:
                signal_date = datetime.strptime(ts[:19], "%Y-%m-%dT%H:%M:%S").strftime("%Y-%m-%d")
            except ValueError:
                signal_date = ts[:10]

        # Look for LinkedIn or email hints (use decoded HTML)
        profile_hints = re.findall(r"linkedin\.com/in/[^\s\"'>]+", text)
        profile_url = profile_hints[0] if profile_hints else ""
        # Also check raw HTML for LinkedIn href
        if not profile_url:
            raw_profile = re.findall(r"linkedin\.com/in/[^\s\"'>]+", text_decoded)
            profile_url = raw_profile[0] if raw_profile else ""

        # Extract company website — search decoded text for https:// URLs
        SKIP_DOMAINS = ["linkedin", "twitter", "x.com", "github", "lever.co",
                        "greenhouse", "grnh.se", "ashby", "workable", "jobs.",
                        "boards.", "ycombinator", "hacker-news", "news.ycombinator",
                        "bit.ly", "t.co", "lnkd.in", "apply.", "careers.", "job.",
                        "smartrecruiters", "bamboohr", "rippling", "notion.so"]
        # Collect href URLs from the original HTML first (most reliable)
        hrefs = [a["href"] for a in soup_comment.find_all("a", href=True)]
        all_urls = hrefs + re.findall(r"https?://[^\s\"'<>]+", text)
        company_website = ""
        for url in all_urls:
            url_clean = url.rstrip("/.),;")
            if not url_clean.startswith("http"):
                continue
            if any(skip in url_clean.lower() for skip in SKIP_DOMAINS):
                continue
            # Take just the base domain URL
            parts = url_clean.split("/")
            company_website = "/".join(parts[:3])  # https://domain.com
            break

        leads.append({
            "name": author,
            "first_name": author,
            "title": "Founder/CEO",
            "company": company,
            "location": "",
            "profile_url": profile_url,
            "signal_type": "hn_hiring_post",
            "signal_text": text[:500],          # clean decoded text
            "signal_date": signal_date,
            "source": "hacker_news",
            "company_website": company_website,
        })

    logger.info(f"[HN Hiring] Found {len(leads)} PM mentions.")
    return leads


def scrape_ycombinator() -> list[dict]:
    """Combine YC Jobs + HN 'Who is Hiring?' into one list."""
    yc_leads = _scrape_yc_jobs()
    hn_leads = _scrape_hn_who_is_hiring()
    all_leads = yc_leads + hn_leads
    logger.info(f"[YC/HN] Total leads: {len(all_leads)}")
    return all_leads
